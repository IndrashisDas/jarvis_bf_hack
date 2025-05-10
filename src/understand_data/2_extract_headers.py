"""
This script finds and reads all the XLSX, CSV, and Shapefile (.shp) files 
(including associated .dbf/.prj/.shx/etc.) and extracts their column headers.
Given the headers are in German, they require English translation.
"""

import os
import pandas as pd
import geopandas as gpd

# Create results directory
os.makedirs("./results/understand_data", exist_ok=True)

results = []

# Walk through all directories and subdirectories
for root, dirs, files in os.walk("./data"):
    for file in files:
        file_path = os.path.join(root, file)
        lower = file.lower()

        # Excel files
        if lower.endswith(".xlsx"):
            print(f"Extracting headers for Excel: {file_path}")
            try:
                xls = pd.ExcelFile(file_path)
                for sheet_name in xls.sheet_names:
                    df = xls.parse(sheet_name, nrows=1)
                    headers = df.columns.tolist()
                    results.append({
                        "file": file_path,
                        "sheet": sheet_name,
                        "headers": headers
                    })
                    del df
            except Exception as e:
                print(f"Failed to process Excel file {file_path}: {e}")

        # CSV files
        elif lower.endswith(".csv"):
            print(f"Extracting headers for CSV: {file_path}")
            try:
                df = pd.read_csv(file_path, nrows=1)
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_path, nrows=1, encoding='ISO-8859-1')
                except Exception as e:
                    print(f"Failed to process CSV file {file_path} with fallback encoding: {e}")
                    continue
            headers = df.columns.tolist()
            results.append({
                "file": file_path,
                "sheet": "N/A",
                "headers": headers
            })
            del df

        # Shapefiles
        elif lower.endswith(".shp"):
            print(f"Extracting headers for Shapefile: {file_path}")
            try:
                gdf = gpd.read_file(file_path)
                headers = list(gdf.columns)
                results.append({
                    "file": file_path,
                    "sheet": "N/A",
                    "headers": headers
                })
                del gdf
            except Exception as e:
                print(f"Failed to process Shapefile {file_path}: {e}")

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
with open("./results/understand_data/headers_prompt.txt", "w", encoding="utf-8") as f:
    f.write(prompt_text)

print("Prompt saved to ./results/understand_data/headers_prompt.txt")
