import os
from dotenv import load_dotenv
import chainlit as cl
import openai
import asyncio
import json
from datetime import datetime
from prompts import ASSESSMENT_PROMPT, SYSTEM_PROMPT
from products_record import read_product_record, write_product_record, format_product_record, parse_product_record

# Load environment variables
load_dotenv()

configurations = {
    "openai_gpt-4": {
        "endpoint_url": os.getenv("OPENAI_ENDPOINT"),
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": "gpt-4"
    }
}

# Choose configuration
config_key = "openai_gpt-4"

# Get selected configuration
config = configurations[config_key]

from langsmith.wrappers import wrap_openai
from langsmith import traceable

# Initialize the OpenAI async client
client = wrap_openai(openai.AsyncClient(api_key=config["api_key"], base_url=config["endpoint_url"]))

gen_kwargs = {
    "model": config["model"],
    "temperature": 0.3,
    "max_tokens": 500
}

# Configuration setting to enable or disable the system prompt
ENABLE_SYSTEM_PROMPT = True

@traceable
def get_latest_user_message(message_history):
    # Iterate through the message history in reverse to find the last user message
    for message in reversed(message_history):
        if message['role'] == 'user':
            return message['content']
    return None

@traceable
async def assess_message(message_history):
    file_path = "product_record.md"
    markdown_content = read_product_record(file_path)
    parsed_record = parse_product_record(markdown_content)

    latest_message = get_latest_user_message(message_history)

    # Remove the original prompt from the message history for assessment
    filtered_history = [msg for msg in message_history if msg['role'] != 'system']

    # Convert message history and alerts to strings
    history_str = json.dumps(filtered_history, indent=4)
    alerts_str = json.dumps(parsed_record.get("Alerts", []), indent=4)
    
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Generate the assessment prompt
    filled_prompt = ASSESSMENT_PROMPT.format(
        latest_message=latest_message,
        history=history_str,
        existing_alerts=alerts_str,
        current_date=current_date
    )
    print("Filled prompt: \n\n", filled_prompt)

    response = await client.chat.completions.create(messages=[{"role": "system", "content": filled_prompt}], **gen_kwargs)

    assessment_output = response.choices[0].message.content.strip()
    print("Assessment Output: \n\n", assessment_output)

    # Parse the assessment output
    new_alerts = parse_assessment_output(assessment_output)

    # Update the product record with the new alerts
    parsed_record["Alerts"].extend(new_alerts)

    # Format the updated record and write it back to the file
    updated_content = format_product_record(
        parsed_record["Product Information"],
        parsed_record["Alerts"],
    )
    write_product_record(file_path, updated_content)

@traceable
def parse_assessment_output(output):
    try:
        parsed_output = json.loads(output)
        new_alerts = parsed_output.get("new_alerts", [])
        return new_alerts
    except json.JSONDecodeError as e:
        print("Failed to parse assessment output:", e)
        return [], []

@cl.on_message
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])

    if ENABLE_SYSTEM_PROMPT and (not message_history or message_history[0].get("role") != "system"):
        system_prompt_content = SYSTEM_PROMPT
        message_history.insert(0, {"role": "system", "content": system_prompt_content})

    message_history.append({"role": "user", "content": message.content})

    asyncio.create_task(assess_message(message_history))
    
    response_message = cl.Message(content="")
    await response_message.send()

    if config_key == "mistral_7B":
        stream = await client.completions.create(prompt=message.content, stream=True, **gen_kwargs)
        async for part in stream:
            if token := part.choices[0].text or "":
                await response_message.stream_token(token)
    else:
        stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
        async for part in stream:
            if token := part.choices[0].delta.content or "":
                await response_message.stream_token(token)

    message_history.append({"role": "assistant", "content": response_message.content})
    cl.user_session.set("message_history", message_history)
    await response_message.update()


if __name__ == "__main__":
    cl.main()
