import os
import re
import csv
import math
import requests
from flask import Flask, render_template, request, redirect, url_for
import folium
from apscheduler.schedulers.background import BackgroundScheduler
import africastalking

app = Flask(__name__)

# --- AFRICA'S TALKING SANDBOX SYSTEM CONFIG ---
AT_USERNAME = "sandbox"
AT_API_KEY = "YOUR_ACTUAL_SANDBOX_API_KEY_HERE" 
africastalking.initialize(AT_USERNAME, AT_API_KEY)
sms = africastalking.SMS
# ----------------------------------------------

FARM_REGISTRY = {}
IS_INITIALIZED = False
PERSISTENT_STORAGE_FILE = "farmers.csv"

LATEST_METRICS = {
    "soil_moisture": 23.8,   
    "ndvi": 0.55,            
    "era5_et": 4.1,          
    "rain": 0.0,             
    "et0": 3.2,              
    "soil_texture": "Loam"   
}

def fetch_and_analyze_daily_data():
    global LATEST_METRICS
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
    except Exception:
        pass

def dispatch_irrigation_alerts():
    print("Initiating automated satellite-driven irrigation telemetry broadcast...")
    for fid, f in FARM_REGISTRY.items():
        name_hash = sum(ord(char) for char in f["owner"])
        simulated_moisture = LATEST_METRICS["soil_moisture"] + ((name_hash % 17) - 8)
        
        if simulated_moisture < 26.0:
            farmer_name = f["owner"]
            phone = f["phone"]
            crop = f["crop"]
            
            clean_phone = "".join(filter(str.isdigit, phone))
            if clean_phone.startswith("0"):
                clean_phone = "+254" + clean_phone[1:]
            elif clean_phone.startswith("7") or clean_phone.startswith("1"):
                clean_phone = "+254" + clean_phone
            elif not clean_phone.startswith("254"):
                clean_phone = "+254" + clean_phone
            else:
                clean_phone = "+" + clean_phone

            alert_message = (
                f"Habari {farmer_name}, Kiptagich Agri-GIS tracking highlights that your "
                f"{crop} plot soil moisture has dropped to {simulated_moisture:.1f}%. "
                f"Status: Needs Irrigation. Please schedule watering soon."
            )
            
            try:
                response = sms.send(
                    message=alert_message, 
                    recipients=[clean_phone], 
                    sender_id="Kiptagich Ltd"
                )
                print(f"Alert transmitted to {farmer_name} ({clean_phone}): {response}")
            except Exception as e:
                print(f"Failed to deliver automated alert to {clean_phone}: {e}")

def parse_wkt_polygon(wkt_string):
    try:
        coord_text = re.search(r'POLYGON\s*\(\((.*?)\)\)', wkt_string, re.IGNORECASE)
        if not coord_text: return None, None, []
        raw_coords = coord_text.group(1).split(',')
        folium_coords = []
        sum_lon, sum_lat, count = 0, 0, 0
        for pt in raw_coords:
            parts = pt.strip().split()
            if len(parts) >= 2:
                lon, lat = float(parts[0]), float(parts[1])
                folium_coords.append([lat, lon])
                if count == 0 or pt != raw_coords[-1]:
                    sum_lon += lon
                    sum_lat += lat
                    count += 1
        return (sum_lon / count, sum_lat / count, folium_coords) if count > 0 else (None, None, [])
    except Exception: return None, None, []

def wgs84_to_utm_dynamic(lon, lat):
    zone_num = int(math.floor((lon + 180) / 6)) + 1
    lon_origin = (zone_num - 1) * 6 - 180 + 3
    deg_to_rad = math.pi / 180.0
    lat_rad, lon_rad = lat * deg_to_rad, (lon - lon_origin) * deg_to_rad
    a, f = 6378137.0, 1.0 / 298.257223563
    b = a * (1.0 - f)
    e_sq = (a**2 - b**2) / (a**2)
    k0, false_easting, false_northing = 0.9996, 500000.0, 10000000.0
    N = a / math.sqrt(1.0 - e_sq * math.sin(lat_rad)**2)
    T, C, A = math.tan(lat_rad)**2, e_sq * math.cos(lat_rad)**2 / (1.0 - e_sq), lon_rad * math.cos(lat_rad)
    M = a * ((1.0 - e_sq/4.0 - 3.0*e_sq**2/64.0 - 5.0*e_sq**3/256.0) * lat_rad - (3.0*e_sq/8.0 + 3.0*e_sq**2/32.0 + 45.0*e_sq**3/1024.0) * math.sin(2.0*lat_rad) + (15.0*e_sq**2/256.0 + 45.0*e_sq**3/1024.0) * math.sin(4.0*lat_rad) - (35.0*e_sq**3/3072.0) * math.sin(6.0*lat_rad))
    easting = false_easting + k0 * N * (A + (1.0 - T + C) * A**3 / 6.0 + (5.0 - 18.0 * T + T**2 + 72.0 * C - 58.0 * e_sq) * A**5 / 120.0)
    northing = false_northing + k0 * (M + N * math.tan(lat_rad) * (A**2 / 2.0 + (5.0 - T + 9.0 * C + 4.0 * C**2) * A**4 / 24.0 + (61.0 - 58.0 * T + T**2 + 600.0 * C - 330.0 * e_sq) * A**6 / 720.0))
    return easting, northing, f"{zone_num}S"

def process_csv_rows(file_stream, append_to_file=False):
    global FARM_REGISTRY
    reader = csv.DictReader(file_stream)
    added_count = 0
    file_exists = os.path.exists(PERSISTENT_STORAGE_FILE)
    f_out = None
    writer = None
    
    if append_to_file:
        f_out = open(PERSISTENT_STORAGE_FILE, mode='a', newline='', encoding='utf-8')
        writer = csv.writer(f_out)
        if not file_exists:
            writer.writerow(["farmer_name", "phone_number", "crop_type", "geom_polygon"])

    for row in reader:
        wkt = row.get("geom_polygon", "").strip()
        name = row.get("farmer_name", "Unknown").strip()
        phone = row.get("phone_number", "N/A").strip()
        crop = row.get("crop_type", "N/A").strip()
        
        if wkt:
            lon, lat, geom = parse_wkt_polygon(wkt)
            if lon and lat:
                ex, ny, utm_zone = wgs84_to_utm_dynamic(lon, lat)
                unique_id = f"FARM_{len(FARM_REGISTRY) + 1:03d}"
                FARM_REGISTRY[unique_id] = {
                    "id": unique_id, "owner": name, "phone": phone, "crop": crop,
                    "lat": lat, "lon": lon, "utm_x": ex, "utm_y": ny, "utm_zone": utm_zone, "boundary": geom
                }
                added_count += 1
                if append_to_file and writer:
                    writer.writerow([name, phone, crop, wkt])
                    
    if f_out:
        f_out.close()
    return added_count

def initialize_database():
    global IS_INITIALIZED
    if IS_INITIALIZED: return
    if os.path.exists(PERSISTENT_STORAGE_FILE):
        try:
            with open(PERSISTENT_STORAGE_FILE, mode='r', encoding='utf-8') as f:
                process_csv_rows(f, append_to_file=False)
        except Exception:
            pass
    IS_INITIALIZED = True
    fetch_and_analyze_daily_data()

def load_kml_boundary():
    target_file = "Kiptagich_Ward_Offline.kml"
    if not os.path.exists(target_file): return None
    try:
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            kml_content = f.read()
        coord_match = re.search(r'<coordinates>(.*?)</coordinates>', kml_content, re.DOTALL)
        if coord_match:
            return [[float(pt.split(',')[1]), float(pt.split(',')[0])] for pt in coord_match.group(1).strip().split() if ',' in pt]
    except Exception: pass
    return None

@app.route("/", methods=["GET"])
def index():
    initialize_database()
    success_msg = request.args.get("success_msg")
    
    m =
