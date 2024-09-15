from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith.evaluation import evaluate, LangChainStringEvaluator
from langsmith.schemas import Run, Example
from openai import OpenAI
import json

from dotenv import load_dotenv
load_dotenv()

from langsmith.wrappers import wrap_openai
from langsmith import traceable

import requests
from bs4 import BeautifulSoup

url = "https://www.pcmag.com/lists/best-projectors"
response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser")
text = [p.text for p in soup.find_all("p")]
full_text = "\n".join(text)

client = wrap_openai(OpenAI())

@traceable
def prompt_compliance_evaluator(run: Run, example: Example) -> dict:
    inputs = example.inputs['input']
    outputs = example.outputs['output']

    # Extract system prompt
    system_prompt = [{
        "role": "system",
        "content": "Extract product names, pros, cons with the context below"
    }]

    # Extract message history
    message_history = []
    message_history.append({
        "role": "user",
        "content": "Find me the best projector. {full_text}"
    })

    message_history.append({
        "role": "assistant",
        "content": "BenQ TK860i, Epson Home Cinema 2150, Optoma UHD50X, BenQ LH730, BenQ HT2050A"

    })

    # Extract latest user message and model output
    latest_message = message_history[-1]['content'] if message_history else ""
    model_output = outputs['data']['content']

    evaluation_prompt = f"""
    System Prompt: {system_prompt}

    Message History:
    {json.dumps(message_history, indent=2)}

    Latest User Message: {latest_message}

    Model Output: {model_output}

    Based on the above information, evaluate the model's output for compliance with the system prompt and context of the conversation.
    Provide a score from 1 to 4, where 1 is completely non-compliant and 4 is perfectly compliant.
    Based on the context, did the output have names, pros, and cons. Also provide a brief explanation for your score.

    Here is the scale you should use to build your answer:
    1: The system_answer is terrible: completely irrelevant to the question asked, or very partial
    2: The system_answer is mostly not helpful: misses some key aspects of the question
    3: The system_answer is mostly helpful: provides support, but still could be improved
    4: The system_answer is excellent: relevant, direct, detailed, and addresses all the concerns raised in the question

    Respond in the following JSON format:
    {{
        "score": <int>,
        "explanation": "<string>"
    }}

    You MUST provide values for 'evaluation:' and 'score:' in your answer.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an AI assistant tasked with evaluating the compliance of model outputs to given prompts and conversation context."},
            {"role": "user", "content": evaluation_prompt}
        ],
        temperature=0.2
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return {
            "key": "prompt_compliance",
            "score": result["score"],
            "reason": result["explanation"]
        }
    except json.JSONDecodeError:
        return {
            "key": "prompt_compliance",
            "score": 0,
            "reason": "Failed to parse evaluator response"
        }

# The name or UUID of the LangSmith dataset to evaluate on.
data = "Consumer Researcher"

# A string to prefix the experiment name with.
experiment_prefix = "Consumer researcher prompt compliance"

# List of evaluators to score the outputs of target task
evaluators = [
    prompt_compliance_evaluator
]

# Evaluate the target task
results = evaluate(
    lambda inputs: inputs,
    data=data,
    evaluators=evaluators,
    experiment_prefix=experiment_prefix,
)

print(results)