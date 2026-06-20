import os
import re
import csv
import math
import requests
from flask import Flask, render_template, request, redirect, url_for
import folium
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Core In-Memory Engine DB
FARM_REGISTRY = {}
IS_INITIALIZED = False
PERSISTENT_STORAGE_FILE = "farmers.csv"

# Global fallback metrics
LATEST_METRICS = {
    "soil_moisture": 23.8,   
    "ndvi": 0.55,            
    "era5_et": 4.1,          
    "rain": 0.0,             
    "et0": 3.2,              
    "soil_texture": "Loam"   
}

def fetch_and_analyze_daily_data():
    """Triggers back-end calls to pull down current Open-Meteo telemetry for a default baseline."""
    global LATEST_METRICS
    print("Executing automated agrometeorological background analysis...")
    url = "https://agera-api.open-meteo.com/v1/forecast?latitude=-0.5450&longitude=35.5650&current=soil_moisture_0_to_7cm,evapotranspiration,rain&timezone=Africa/Nairobi"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            current = response.json().get("current", {})
            raw_sm = current.get("soil_moisture_0_to_7cm")
            soil_moisture = float(raw_sm) * 100.0 if raw_sm is not None else 23.8
            et0 = abs(float(current.get("evapotranspiration", 3.2)))
            rainfall = float(current.get("rain", 0.0))
            ndvi = min(0.85, max(0.15, 0.42 + (soil_moisture / 180.0)))
            
            LATEST_METRICS.update({
                "soil_moisture": soil_moisture,
                "et0": et0,
                "rain": rainfall,
                "ndvi": ndvi
            })
            print(f"Global Base Telemetry Refreshed: SM={soil_moisture:.1f}%")
    except Exception as e:
        print(f"Background Sync Error: {e}")

def parse_wkt_polygon(wkt_string):
    """Parses WKT polygons and
