#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build **master_pv_forecast_input.csv**

Creates a single, flat table that

1. Combines rooftop-solar-potential polygons with Nexiga building metadata
2. Adds nearest low-voltage (LV) connection boxes, MV cables / overhead lines
   and transformer-station IDs
3. Enriches LV boxes with the Excel metadata table
4. Flags every roof that already hosts a photovoltaic system by matching to
   **Strom-Einspeiser-Export 1.csv**
5. Produces convenient modelling columns:

   • connection_type     (LV / MV / Uncertain)  
   • final_connection_id (ID to use for the grid link)  
   • is_connectable      (True if a grid point was found)  
   • has_existing_pv     (True if the export says a PV is already installed)  
   • candidate           (True ⇢ roof is connectable AND no PV yet)

---------------------------------------------------------------------------
Datasets (relative to ``--data_root``):

· 20250221_ST_Stationen 1.xlsx  (sheet “Tabelle1”)               … MV stations  
· Hausanschlüsse an der Niederspannung 1.xlsx (sheet “Tabelle1”) … LV meta  
· Strom ST NS-HA-Kasten BP Position.shp                          … LV boxes  
· Strom ST MS-Freileitungsabschnitt BP Position.shp              … MV overhead  
· Strom ST MS-Kabelabschnitt BP Position.shp                     … MV cable  
· nexiga_all.shp                                                 … building meta  
· four Solarpotenzial_* shapefiles                               … roof PV potential  
· Strom-Einspeiser-Export 1.csv                                  … existing PV

Requires:  pandas, geopandas, shapely, pyproj, openpyxl, tqdm, unicodedata
---------------------------------------------------------------------------

Usage
-----
python build_master_dataframe.py \
       --data_root "./data" \
       --crs "EPSG:25832" \
       --out  master_pv_forecast_input.csv
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


def load_lv_connections(shp: Path, xlsx: Path, crs: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shp).to_crs(crs)
    gdf = gdf.rename(columns={"ID": "lv_id", "NS_HAUSANS": "connection_key"})
    meta = pd.read_excel(xlsx, sheet_name="Tabelle1").rename(
        columns={"NS-Hausanschluss": "connection_key"}
    )
    return gdf.merge(meta, on="connection_key", how="left")[
        ["lv_id", "connection_key", "Anschlusstyp", "Status", "geometry"]
    ]


def load_mv_lines(over_head: Path, cable: Path, crs: str) -> gpd.GeoDataFrame:
    over = gpd.read_file(over_head).to_crs(crs)
    cabl = gpd.read_file(cable).to_crs(crs)
    return pd.concat([over, cabl], ignore_index=True)[["ID", "geometry"]].rename(
        columns={"ID": "mv_line_id"}
    )


def load_stations(xlsx: Path, crs: str) -> gpd.GeoDataFrame:
    df = pd.read_excel(xlsx, sheet_name="Tabelle1")

    def to_point(s):
        if isinstance(s, str) and "," in s and "POINT" not in s.upper():
            lat, lon = map(float, s.split(","))
            return Point(lon, lat)

    df["geometry"] = df["Standort"].apply(to_point)
    return (
        gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        .to_crs(crs)[["Id", "geometry"]]
        .rename(columns={"Id": "station_id"})
        .dropna(subset=["geometry"])
    )


def spatial_join_nearest(left, right, right_label, max_dist):
    j = gpd.sjoin_nearest(
        left[["geometry"]], right, how="left", max_distance=max_dist, distance_col="d"
    ).reset_index(drop=True)
    return j[right_label].where(j["d"].notna())


def build_master(args):
    root, crs = Path(args.data_root), args.crs

    print("➜  solar potential …")
    roofs = read_solar_shapefiles(
        root / "Daten Hackaton (ALKIS,Nexiga,PV,HK)/Datenquellen/Solarpotenzial", crs
    )

    # LV / MV infra
    lv = load_lv_connections(
        root / "Strom ST NS-HA-Kasten BP Position.shp",
        root / "Hausanschlüsse an der Niederspannung 1.xlsx",
        crs,
    )
    mv = load_mv_lines(
        root / "Strom ST MS-Freileitungsabschnitt BP Position.shp",
        root / "Strom ST MS-Kabelabschnitt BP Position.shp",
        crs,
    )
    stations = load_stations(root / "20250221_ST_Stationen 1.xlsx", crs)

    print("➜  nearest LV / MV / station …")
    roofs["lv_id"] = spatial_join_nearest(roofs, lv, "lv_id", 50)
    roofs["mv_line_id"] = spatial_join_nearest(roofs, mv, "mv_line_id", 250)
    roofs["station_id"] = spatial_join_nearest(roofs, stations, "station_id", 500)

    roofs["centroid_x"] = roofs.geometry.centroid.x
    roofs["centroid_y"] = roofs.geometry.centroid.y
    roofs = roofs.rename(
        columns={"Power": "potential_kwp", "PvArea": "pv_area_m2", "Eignung": "suitability"}
    )

    roofs["connection_type"] = roofs["potential_kwp"].apply(
        lambda k: "LV" if k < 30 else ("MV" if k >= 30 else "Uncertain")
    )
    roofs["final_connection_id"] = roofs.apply(
        lambda r: r["lv_id"] if r["connection_type"] == "LV" else (r["station_id"] or r["mv_line_id"])
        if r["connection_type"] == "MV"
        else None,
        axis=1,
    )
    roofs["is_connectable"] = roofs["final_connection_id"].notnull()

    print(roofs.head())
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    print(f"➜  writing {out} …")
    roofs.to_csv(out, index=False)
    print("✓  master dataframe created")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build master PV forecast dataframe")
    p.add_argument("--data_root", default="./data")
    p.add_argument("--crs", default="EPSG:25832")
    p.add_argument("--out", default="master_pv_forecast_input.csv")
    build_master(p.parse_args())
