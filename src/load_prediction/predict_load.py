#!/usr/bin/env python3
"""
PV-Forecast → Connection-Point assignment
author : you
"""

import os
from pathlib import Path
import pandas as pd
import geopandas as gpd
import numpy as np
from sklearn.linear_model import LinearRegression
from shapely.geometry import Point
from tqdm import tqdm

# ---------------------------------------------------------------------
# 0 · Paths (edit if your folder names differ)
# ---------------------------------------------------------------------
DATA = Path("./data")
RESULTS = Path("./results").mkdir(exist_ok=True)

PV_HIST_CSV         = DATA / "Strom-Einspeiser-Export 1.csv"
LV_POINTS_SHP       = DATA / "Strom ST NS-HA-Kasten BP Position.shp"
LV_ATTR_XLSX        = DATA / "Hausanschlüsse an der Niederspannung 1.xlsx"
MV_CABLE_SHP        = DATA / "Strom ST MS-Kabelabschnitt BP Position.shp"
MV_OHL_SHP          = DATA / "Strom ST MS-Freileitungsabschnitt BP Position.shp"
MV_STATIONS_XLSX    = DATA / "20250221_ST_Stationen 1.xlsx"
SOLARPOT_ZIPS       = list((DATA / "Daten Hackaton (ALKIS,Nexiga,PV,HK)/Datenquellen/Solarpotenzial").glob("*.zip"))

FORECAST_HORIZON_YEARS = 5           # how far into the future to predict
SEED = 42
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------
# 1 · Historic PV adoption  →  municipality-year table
# ---------------------------------------------------------------------
print("Loading historic PV systems …")
hist = pd.read_csv(PV_HIST_CSV, sep=";")   # semicolon-separated
hist["Einbaudatum"] = pd.to_datetime(hist["Einbaudatum"], errors="coerce")
hist = hist.dropna(subset=["Einbaudatum"])
hist["year"] = hist["Einbaudatum"].dt.year
hist["Leistung_kW"] = hist["(Peak-)Leistung [kW]"].str.replace(",", ".", regex=False).astype(float)

agg_hist = (
    hist.groupby(["Gemeinde", "year"])
        .agg(n_systems=("ID", "count"),
             total_kWp=("Leistung_kW", "sum"))
        .reset_index()
)

# ---------------------------------------------------------------------
# 2 · Very simple linear-trend forecast per municipality
#     (swap for better model later)
# ---------------------------------------------------------------------
print("Fitting linear trend forecast …")
def forecast_linear(df, target, horizon):
    """fit y = a·year + b  → predict next horizon years"""
    X = df["year"].values.reshape(-1, 1)
    y = df[target].values
    if len(df) < 2:                       # not enough history → flat
        future = np.full(horizon, y[-1] if len(y) else 0.0)
    else:
        model = LinearRegression().fit(X, y)
        years_fwd = np.arange(df["year"].max()+1,
                              df["year"].max()+1+horizon).reshape(-1, 1)
        future = model.predict(years_fwd).clip(min=0)
    return future

records = []
for muni, sub in agg_hist.groupby("Gemeinde"):
    n_f = forecast_linear(sub, "n_systems", FORECAST_HORIZON_YEARS)
    p_f = forecast_linear(sub, "total_kWp", FORECAST_HORIZON_YEARS)
    years = np.arange(sub["year"].max()+1,
                      sub["year"].max()+1+FORECAST_HORIZON_YEARS)
    for y, n_new, p_new in zip(years, n_f, p_f):
        records.append({"Gemeinde": muni,
                        "year": y,
                        "n_new": int(round(n_new)),
                        "kWp_new": max(p_new, 0)})
demand = pd.DataFrame(records)

# ---------------------------------------------------------------------
# 3 · Load solar-potential polygons – each polygon = candidate site
#     (assumes each ZIP contains a shapefile with field 'POT_KWP')
# ---------------------------------------------------------------------
print("Loading solar-potential layers …")
gdfs = []
for z in SOLARPOT_ZIPS:
    gdf = gpd.read_file(f"zip://{z}")     # geopandas can read from zip
    # rename any field containing 'kwp'
    kwp_col = next(c for c in gdf.columns if "kwp" in c.lower())
    gdf = gdf.rename(columns={kwp_col: "pot_kWp"})
    gdf = gdf[["pot_kWp", "geometry"]].to_crs(4326)  # WGS84
    gdfs.append(gdf)
pot = pd.concat(gdfs, ignore_index=True)

# Spatial join: assign municipality using hist PV points as proxy CRS
print("Assigning municipality to potential polygons (centroid+nearest)…")
hist_points = gpd.GeoDataFrame(hist,
    geometry=gpd.points_from_xy(hist["B Position"].str.split(",").str[0].astype(float),
                                hist["B Position"].str.split(",").str[1].astype(float)),
    crs=4326)

muni_shapes = hist_points.dissolve(by="Gemeinde").reset_index()[["Gemeinde", "geometry"]]
pot_cent = pot.copy()
pot_cent["geometry"] = pot_cent.centroid
pot_muni = gpd.sjoin_nearest(pot_cent, muni_shapes[["Gemeinde", "geometry"]], how="left")
pot["Gemeinde"] = pot_muni["Gemeinde"]

# ---------------------------------------------------------------------
# 4 · Load LV & MV grid connection points
# ---------------------------------------------------------------------
print("Loading LV and MV connection points …")
lv_pts  = gpd.read_file(LV_POINTS_SHP).to_crs(4326)[["SAP_ID", "geometry"]]
lv_attr = pd.read_excel(LV_ATTR_XLSX, sheet_name="Tabelle1")
lv_attr = lv_attr.rename(columns={"SAP Id": "SAP_ID", "Kabelhausanschluss": "cable_flag"})
lv = lv_pts.merge(lv_attr[["SAP_ID", "cable_flag"]], on="SAP_ID", how="left")

mv_lines = pd.concat([
    gpd.read_file(MV_CABLE_SHP)[["geometry"]],
    gpd.read_file(MV_OHL_SHP)[["geometry"]],
], ignore_index=True).to_crs(4326)

mv_stn  = pd.read_excel(MV_STATIONS_XLSX, sheet_name="Tabelle1")
mv_stn_gdf = gpd.GeoDataFrame(
    mv_stn,
    geometry=gpd.points_from_xy(mv_stn["BP Position"].str.split(",").str[0].astype(float),
                                mv_stn["BP Position"].str.split(",").str[1].astype(float)),
    crs=4326)[["Id", "geometry"]]

# ---------------------------------------------------------------------
# 5 · Generate forecasted systems municipality-by-municipality
# ---------------------------------------------------------------------
print("Synthesising forecasted PV systems …")
systems = []
sys_id = 1

for _, row in demand.iterrows():
    muni = row["Gemeinde"]
    n_new = row["n_new"]
    kwp_new = row["kWp_new"]

    if n_new == 0:
        continue

    # candidate polygons in this municipality
    pool = pot.query("Gemeinde == @muni").sample(n=len(pot), random_state=SEED)  # shuffle copy
    pool_iter = iter(pool.itertuples())

    for _ in range(n_new):
        candidate = next(pool_iter)  # naïve – assumes enough polygons
        # size rule of thumb
        kwp_site = min(candidate.pot_kWp, max(3, rng.normal(10, 3)))
        if kwp_site > kwp_new: kwp_site = kwp_new   # fit remainder
        kwp_new -= kwp_site

        geom = candidate.geometry.centroid
        lon, lat = geom.x, geom.y

        # decide connection level
        if kwp_site <= 30:
            conn_level = "LV"
            # nearest LV point within 25 m
            lv_near = lv.distance(geom).sort_values().index[0]
            conn_id = lv.loc[lv_near, "SAP_ID"]
        elif kwp_site < 100:
            # LV if not 'cable' and within 40 m else MV
            lv_dists = lv.distance(geom)
            idx = lv_dists.idxmin()
            if lv.loc[idx, "cable_flag"] != "Ja" and lv_dists.min() <= 0.0004:
                conn_level = "LV"
                conn_id = lv.loc[idx, "SAP_ID"]
            else:
                conn_level = "MV"
                conn_id = mv_stn_gdf.distance(geom).idxmin()
        else:
            conn_level = "MV"
            conn_id = mv_stn_gdf.distance(geom).idxmin()

        systems.append({
            "PV_ID": f"PV_{sys_id:06d}",
            "Power_kWp": round(kwp_site, 1),
            "Municipality": muni,
            "Connection_Level": conn_level,
            "Grid_Connection_ID": conn_id,
            "Latitude": lat,
            "Longitude": lon,
        })
        sys_id += 1

print(f"Created {len(systems)} synthetic PV systems.")

# ---------------------------------------------------------------------
# 6 · Save outputs
# ---------------------------------------------------------------------
df_sys = pd.DataFrame(systems)
df_sys.to_csv(RESULTS / "pv_forecast_table.csv", index=False)

gdf_sys = gpd.GeoDataFrame(df_sys,
                           geometry=[Point(xy) for xy in zip(df_sys.Longitude,
                                                              df_sys.Latitude)],
                           crs=4326)
gdf_sys.to_file(RESULTS / "pv_forecast.gpkg", layer="pv_forecast", driver="GPKG")

print("✅ Forecast files written to ./results/")
