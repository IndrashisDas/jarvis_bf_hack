"""
Create a single master CSV that consolidates all data needed to forecast future
photovoltaic (PV) systems and assign them to the appropriate grid-connection
points.

Datasets used (relative paths):
  • data/20250221_ST_Stationen 1.xlsx  (Sheet: Tabelle1)
  • data/Hausanschlüsse an der Niederspannung 1.xlsx  (Sheet: Tabelle1)
  • data/Strom ST NS-HA-Kasten BP Position.shp         (LV connection boxes)
  • data/Strom ST MS-Freileitungsabschnitt BP Position.shp  (MV overhead)
  • data/Strom ST MS-Kabelabschnitt BP Position.shp           (MV underground)
  • data/nexiga_all.shp                                        (building meta)
  • data/8311_Solarpotenzial_Dachseiten_Freiburg_Stadt/...
  • data/8315_Solarpotenzial_Dachseiten_LK_Breisgau_Hochschwarzwald/...
  • data/8316_Solarpotenzial_Dachseiten_LK_Emmendingen/...
  • data/8337_Solarpotenzial_Dachseiten_LK_Waldshut/...

The script performs the following steps:
  1. Load and concatenate the four solar-potential shapefiles.
  2. Load Nexiga building data and merge with solar roofs on BuildingID → id.
  3. Load LV connection boxes; keep coordinates & IDs.
  4. Load MV overhead and cable sections; dissolve into a single GeoDataFrame.
  5. Load transformer stations (ST_Stationen) and convert to GeoDataFrame
     (expects latitude / longitude or WKT in column "Standort").
  6. Spatially assign each solar roof to:
       • its nearest LV connection (≤50 m)          → column lv_id
       • its nearest MV cable/line (≤250 m)         → column mv_line_id
       • its nearest transformer station (≤500 m)   → column mv_station_id
  7. Derive connection_type, final_connection_id, is_connectable
  8. Save the consolidated master table to CSV   → master_pv_forecast_input.csv

Required Python packages:
  pandas, geopandas, shapely, pyproj, openpyxl, tqdm

Usage:
  python build_master_dataframe.py --data_root ./data \
                                   --crs "EPSG:25832" \
                                   --out master_pv_forecast_input.csv
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

def read_solar_shapefiles(root: Path, crs: str) -> gpd.GeoDataFrame:
    solar_dirs = [
        f"{root}/8311_Solarpotenzial_Dachseiten_Freiburg_Stadt/Solarpotenziale_Dachseiten_Freiburg_Stadt.shp",
        f"{root}/8315_Solarpotenzial_Dachseiten_Breisgau_Hochschwarzwald/Solarpotenziale_Dachseiten_LK_Breisgau_Hochschwarzwald.shp",
        f"{root}/8316_Solarpotenzial_Dachseiten_Emmendingen/Solarpotenziale_Dachseiten_LK_Emmendingen.shp",
        f"{root}/8337_Solarpotenzial_Dachseiten_Waldshut/Solarpotenziale_Dachseiten_LK_Waldshut.shp",
    ]
    frames = [gpd.read_file(shp).to_crs(crs) for shp in solar_dirs]
    return pd.concat(frames, ignore_index=True)


def read_nexiga(path: Path, crs: str) -> gpd.GeoDataFrame:
    return gpd.read_file(path).to_crs(crs)


def merge_solar_nexiga(solar: gpd.GeoDataFrame, nexiga: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    solar["BuildingID"] = solar["BuildingID"].astype(str)
    nexiga["id"] = nexiga["id"].astype(str)
    return solar.merge(nexiga.drop(columns="geometry"), left_on="BuildingID", right_on="id", how="left")


def load_lv_connections(shp_path: Path, xlsx_path: Path, crs: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shp_path).to_crs(crs)
    gdf = gdf.rename(columns={"ID": "lv_id", "NS_HAUSANS": "connection_key"})
    lv_meta = pd.read_excel(xlsx_path, sheet_name="Tabelle1")
    lv_meta = lv_meta.rename(columns={"NS-Hausanschluss": "connection_key"})
    merged = gdf.merge(lv_meta, on="connection_key", how="left")
    return merged[["lv_id", "connection_key", "Anschlusstyp", "Status", "geometry"]]


def load_mv_lines(overhead_path: Path, cable_path: Path, crs: str) -> gpd.GeoDataFrame:
    overhead = gpd.read_file(overhead_path).to_crs(crs)
    cable = gpd.read_file(cable_path).to_crs(crs)
    mv = pd.concat([overhead, cable], ignore_index=True)
    return mv[["ID", "geometry"]].rename(columns={"ID": "mv_line_id"})


def load_stations(xlsx_path: Path, crs: str) -> gpd.GeoDataFrame:
    df = pd.read_excel(xlsx_path, sheet_name="Tabelle1")
    def parse_geom(val):
        try:
            if isinstance(val, str) and "," in val and "POINT" not in val.upper():
                lat, lon = map(float, val.split(","))
                return Point(lon, lat)
        except Exception:
            return None
    df["geometry"] = df["Standort"].apply(parse_geom)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326").to_crs(crs)
    return gdf[["Id", "geometry"]].rename(columns={"Id": "station_id"}).dropna(subset=["geometry"])


def spatial_join_nearest(left: gpd.GeoDataFrame, right: gpd.GeoDataFrame, right_label: str, max_dist: float) -> pd.Series:
    joined = gpd.sjoin_nearest(left[["geometry"]], right, how="left", max_distance=max_dist, distance_col="dist")
    joined = joined.reset_index(drop=True)
    return joined[right_label].where(joined["dist"].notna())

def build_master(args):
    crs = args.crs
    root = Path(args.data_root)

    print("Loading solar potential shapefiles…")
    solar = read_solar_shapefiles(f"{root}/Daten Hackaton (ALKIS,Nexiga,PV,HK)/Datenquellen/Solarpotenzial", crs)

    print("Loading Nexiga building metadata…")
    nexiga_path = f"{root}/Daten Hackaton (ALKIS,Nexiga,PV,HK)/Datenquellen/Nexiga Daten/nexiga_all.shp"
    nexiga = read_nexiga(nexiga_path, crs)

    print("Merging solar and Nexiga on building IDs…")
    roofs = merge_solar_nexiga(solar, nexiga)

    print("Loading LV connection boxes and metadata…")
    lv_shp = Path("./data/Strom ST NS-HA-Kasten BP Position.shp")
    lv_xlsx = Path("./data/Hausanschlüsse an der Niederspannung 1.xlsx")
    lv = load_lv_connections(lv_shp, lv_xlsx, crs)

    print("Loading MV overhead & cable lines…")
    mv_over = Path("./data/Strom ST MS-Freileitungsabschnitt BP Position.shp")
    mv_cabl = Path("./data/Strom ST MS-Kabelabschnitt BP Position.shp")
    mv = load_mv_lines(mv_over, mv_cabl, crs)

    print("Loading transformer stations…")
    st_path = Path("./data/20250221_ST_Stationen 1.xlsx")
    stations = load_stations(st_path, crs)

    print("Assigning nearest LV connection ≤50 m…")
    roofs["lv_id"] = spatial_join_nearest(roofs, lv, "lv_id", max_dist=50)

    print("Assigning nearest MV line ≤250 m…")
    roofs["mv_line_id"] = spatial_join_nearest(roofs, mv, "mv_line_id", max_dist=250)

    print("Assigning nearest transformer station ≤500 m…")
    roofs["station_id"] = spatial_join_nearest(roofs, stations, "station_id", max_dist=500)

    roofs["centroid_x"] = roofs.geometry.centroid.x
    roofs["centroid_y"] = roofs.geometry.centroid.y

    roofs = roofs.rename(columns={
        "Power": "potential_kwp",
        "PvArea": "pv_area_m2",
        "Eignung": "suitability",
    })

    def classify_connection(row):
        if row["potential_kwp"] < 30:
            return "LV"
        elif row["potential_kwp"] >= 30:
            return "MV"
        else:
            return "Uncertain"

    def assign_connection_id(row):
        if row["connection_type"] == "LV":
            return row["lv_id"]
        elif row["connection_type"] == "MV":
            return row["station_id"] or row["mv_line_id"]
        else:
            return None

    roofs["connection_type"] = roofs.apply(classify_connection, axis=1)
    roofs["final_connection_id"] = roofs.apply(assign_connection_id, axis=1)
    roofs["is_connectable"] = roofs["final_connection_id"].notnull()

    print(f"Saving master CSV to {args.out}…")
    roofs.to_csv(f"{args.data_root}/{args.out}", index=False)
    print("Done! Master dataframe created.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build master PV forecast dataframe")
    parser.add_argument("--data_root", default="./data", help="Root folder containing all data files")
    parser.add_argument("--crs", default="EPSG:25832", help="Target CRS for all spatial operations")
    parser.add_argument("--out", default="master_pv_forecast_input.csv", help="Output CSV path")
    args = parser.parse_args()

    build_master(args)
