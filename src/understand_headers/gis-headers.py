import geopandas as gpd
from pathlib import Path

# Define the base directory
shapefiles_dir = (Path(__file__).resolve().parent / "../../data/gis").resolve()

# Recursively find all .shp files
shapefiles = list(shapefiles_dir.rglob("*.shp"))

# Load each shapefile into a GeoDataFrame
geo_dataframes = {shp: gpd.read_file(shp) for shp in shapefiles}

output_lines = []

# Check if any shapefiles were loaded
if not geo_dataframes:
    output_lines.append("No shapefiles found in the directory.")
else:
    output_lines.append(f"Loaded {len(geo_dataframes)} shapefiles.\n")

    for path, gdf in geo_dataframes.items():
        output_lines.append(f"--- {path.name} ---")
        output_lines.append(f"File Name: {path.name}")
        output_lines.append(f"Path: {path.relative_to(shapefiles_dir)}")  # Relative to gis folder
        output_lines.append(f"Number of features: {len(gdf)}")
        output_lines.append(f"Columns: {list(gdf.columns)}")
        output_lines.append("\n")

# Write results to output.txt
output_file = Path(__file__).resolve().parent / "output.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))
