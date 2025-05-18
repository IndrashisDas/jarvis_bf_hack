"""
The following file crawls through the ./data folder and extracts all the file names here.
This metadata could be useful for identifying the target files required for building our solution.
"""

import os

# Set the root directory you want to search
root_dir = "./data"  # Change this to your target directory
output_file = "./results/understand_data/all_file_paths.txt"

# Open the output file for writing
with open(output_file, "w", encoding="utf-8") as f:
    # Walk through all subdirectories and files
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            full_path = os.path.join(root, file)
            f.write(full_path + "\n")

print(f"All file paths have been saved to {output_file}")
