import os

def read_product_record(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist. Creating a new file with default content.")
        default_content = """
# Product Record

## Product Information
**Name:** Dyson Vacuum

## Alerts
_No alerts yet._

"""
        with open(file_path, "w") as file:
            file.write(default_content)
        return default_content

    with open(file_path, "r") as file:
        return file.read()

def write_product_record(file_path, content):
    with open(file_path, "w") as file:
        file.write(content)

def format_product_record(product_info, alerts, knowledge):
    record = "# Product Record\n\n## Product Information\n"
    for key, value in product_info.items():
        record += f"**{key}:** {value}\n"
    
    record += "\n## Alerts\n"
    if alerts:
        for alert in alerts:
            record += f"- **{alert['date']}:** {alert['note']}\n"
    else:
        record += "_No alerts yet._\n"
    
    return record

def parse_product_record(markdown_content):
    product_info = {}
    alerts = []
    knowledge = {}
    
    current_section = None
    lines = markdown_content.split("\n")
    
    for line in lines:
        line = line.strip()  # Strip leading/trailing whitespace
        if line.startswith("## "):
            current_section = line[3:].strip()
        elif current_section == "Product Information" and line.startswith("**"):
            if ":** " in line:
                key, value = line.split(":** ", 1)
                key = key.strip("**").strip()
                value = value.strip()
                product_info[key] = value
        elif current_section == "Alerts":
            if "_No alerts yet._" in line:
                alerts = []
            elif line.startswith("- **"):
                if ":** " in line:
                    date, note = line.split(":** ", 1)
                    date = date.strip("- **").strip()
                    note = note.strip()
                    alerts.append({"date": date, "note": note})
    
    final_record = {
        "Product Information": product_info,
        "Alerts": alerts,
    }
    print(f"Final parsed record: {final_record}")
    return final_record