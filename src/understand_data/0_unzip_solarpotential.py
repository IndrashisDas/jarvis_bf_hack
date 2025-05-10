"""
The following file unzips the zip files in ./data/Daten Hackaton (ALKIS,Nexiga,PV,HK)/Datenquellen/Solarpotenzial
"""

import zipfile
import os
from pathlib import Path

# Set the Solarpotential directory path
solar_dir = Path("./data/Daten Hackaton (ALKIS,Nexiga,PV,HK)/Datenquellen/Solarpotenzial")

# Make sure directory exists
assert solar_dir.exists(), f"{solar_dir} does not exist."

# Loop over all zip files in that folder
for zip_path in solar_dir.glob("*.zip"):
    extract_to = solar_dir / zip_path.stem  # Create folder with same name as zip
    extract_to.mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        print(f"Extracted {zip_path.name} → {extract_to}")

print("All Solarpotential ZIP files extracted.")
