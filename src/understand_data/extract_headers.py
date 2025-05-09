import os
import pandas as pd

# Create results directory if it doesn't exist
os.makedirs("results", exist_ok=True)

results = []

# Walk through all directories and subdirectories
for root, dirs, files in os.walk("./data"):
    for file in files:
        file_path = os.path.join(root, file)

        if file.lower().endswith(".xlsx"):
            print(f"Extracting headers for Excel: {file_path}")
            try:
                xls = pd.ExcelFile(file_path)
                for sheet_name in xls.sheet_names:
                    df = xls.parse(sheet_name, nrows=1)  # Just load header row
                    headers = df.columns.tolist()  # Get the headers
                    results.append({
                        "file": file_path,
                        "sheet": sheet_name,
                        "headers": headers
                    })
                    del df  # Clean memory
            except Exception as e:
                print(f"Failed to process Excel file {file_path}: {e}")

        elif file.lower().endswith(".csv"):
            print(f"Extracting headers for CSV: {file_path}")
            try:
                # Try UTF-8 first
                df = pd.read_csv(file_path, nrows=1)
            except UnicodeDecodeError:
                try:
                    # Fallback to ISO-8859-1 (Latin-1)
                    df = pd.read_csv(file_path, nrows=1, encoding='ISO-8859-1')
                except Exception as e:
                    print(f"Failed to process CSV file {file_path} with fallback encoding: {e}")
                    continue  # Skip to next file

            headers = df.columns.tolist()
            results.append({
                "file": file_path,
                "sheet": "N/A",
                "headers": headers
            })
            del df

# Prepare prompt format text
prompt_text = (
    "Please translate the following German column headers to English and provide a short data description for each:\n\n"
)

for entry in results:
    prompt_text += f"File: {entry['file']}\n"
    prompt_text += f"Sheet: {entry['sheet']}\n"
    prompt_text += "Headers:\n"
    for header in entry["headers"]:
        prompt_text += f" - {header}\n"
    prompt_text += "\n"

# Save the prompt
with open("./results/headers_prompt.txt", "w", encoding="utf-8") as f:
    f.write(prompt_text)

print("Prompt saved to ./results/headers_prompt.txt")
