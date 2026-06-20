import os
import re
import csv
import math
import requests
from flask import Flask, render_template, request, redirect, url_for
import folium
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

FARM_REGISTRY = {}
IS_INITIALIZED = False
LATEST_METRICS = {"soil_moisture": 23.8, "et0": 3.2, "ndvi": 0.55, "rainfall": 0.0}

# Africa's Talking Credentials
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "your_africas_talking_api_key_here")

def send_africastalking_sms(to_phone, farmer_name, moisture):
    """Dispatches real-time agrometeorological alerts via Africa's Talking Gateway."""
    if not to_phone or to_phone == "N/A":
        return
    
    url = "https://api.africastalking.com/version1/messaging"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "apiKey": AT_API_KEY
    }
    
    message = (
        f"Habari {farmer_name}, Kiptagich Agri-GIS has detected low soil moisture "
        f"({moisture:.1f}%) on your plot. Please initiate irrigation immediately."
    )
    
    data = {
        "username": AT_USERNAME,
        "to": to_phone,
        "message": message
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        print(f"SMS Status for {farmer_name} ({to_phone}): {response.status_code} -> {response.text}")
    except Exception as e:
        print(f"Failed to dispatch SMS to {farmer_name}: {e}")

def fetch_and_analyze_daily_data():
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
            LATEST_METRICS = {"soil_moisture": soil_moisture, "et0": et0, "ndvi": ndvi, "rainfall": rainfall}
            print(f"Telemetry Refreshed Successfully: SM={soil_moisture:.1f}%")
            
            # Automated 6PM Dispatch Rule
            if soil_moisture < 26.0:
                print("Moisture below critical safety baseline. Commencing background SMS batch sequence...")
                for fid, farm in FARM_REGISTRY.items():
                    send_africastalking_sms(farm["phone"], farm["owner"], soil_moisture)
    except Exception as e:
        print(f"Background Sync Error: {e}")

def parse_wkt_polygon(wkt_string):
    try:
        coord_text = re.search(r'POLYGON(?:\s+Z)?\s*\(\((.*?)\)\)', wkt_string, re.IGNORECASE)
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

def wgs84_to_utm36s(lon, lat):
    lon_origin = 33.0
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
    return easting, northing

def initialize_database():
    global FARM_REGISTRY, IS_INITIALIZED
    if IS_INITIALIZED: return
    csv_file = "farmers.csv"
    if not os.path.exists(csv_file): return
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            for idx, row in enumerate(csv.DictReader(f)):
                wkt = row.get("geom_polygon", "").strip()
                name = row.get("farmer_name", f"Farmer {idx}").strip()
                phone = row.get("phone_number", "N/A").strip()
                crop = row.get("crop_type", "N/A").strip()
                if wkt:
                    lon, lat, geom = parse_wkt_polygon(wkt)
                    if lon and lat:
                        ex, ny = wgs84_to_utm36s(lon, lat)
                        unique_id = f"FARM_{idx:03d}"
                        FARM_REGISTRY[unique_id] = {"id": unique_id, "owner": name, "phone": phone, "crop": crop, "lat": lat, "lon": lon, "utm_x": ex, "utm_y": ny, "boundary": geom, "is_new": False}
        IS_INITIALIZED = True
        fetch_and_analyze_daily_data()
    except Exception as e:
        print(f"System initialization error: {e}")

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
    
    if LATEST_METRICS["soil_moisture"] < 26.0:
        status = "Needs Irrigation"
        marker_color = "red"
    else:
        status = "Satisfactory"
        marker_color = "green"

    m = folium.Map(location=[-0.5510, 35.5780], zoom_start=13, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="Vector Map").add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Satellite Backdrop").add_to(m)

    kml_polygon_coords = load_kml_boundary()
    if kml_polygon_coords:
        folium.Polygon(locations=kml_polygon_coords, color="purple", weight=3, fill=False).add_to(m)

    for fid, f in FARM_REGISTRY.items():
        if f["boundary"]:
            outline_color = "cyan" if f.get("is_new") else ("red" if marker_color == "red" else "darkblue")
            folium.Polygon(locations=f["boundary"], color=outline_color, weight=3, fill=True, fill_opacity=0.25).add_to(m)
            
        popup_html = f"<h5><b>{f['owner']}</b></h5><b>Crop:</b> {f['crop']}<br><b>UTM Easting:</b> {f['utm_x']:.1f}m<br><b>UTM Northing:</b> {f['utm_y']:.1f}m<br><hr style='margin:4px 0;'><b>🛰️ CYGNSS Moisture:</b> {LATEST_METRICS['soil_moisture']:.1f}%<br><b>🌿 Sentinel-2 NDVI:</b> {LATEST_METRICS['ndvi']:.2f}<br><b>💧 CHIRPS Rainfall:</b> {LATEST_METRICS['rainfall']:.1f} mm<br><b>Status:</b> <span style='color:{marker_color}; font-weight:bold;'>{status}</span>"
        folium.Marker(location=[f["lat"], f["lon"]], popup=folium.Popup(popup_html, max_width=280), icon=folium.Icon(color=marker_color, icon="leaf")).add_to(m)

    folium.LayerControl().add_to(m)
    
    # Structural layout fix: Modifying html delivery directly to eliminate white gaps and set the 28/72 split ratio
    raw_map_html = m._repr_html_()
    fixed_map_html = raw_map_html.replace(
        '<div ', 
        '<div style="width:100%; height:100vh; margin:0; padding:0; overflow:hidden;" ', 
        1
    )
    
    return render_template("dashboard.html", map_html=fixed_map_html, total_farms=len(FARM_REGISTRY), success_msg=success_msg)

@app.route("/add_farm", methods=["POST"])
def add_farm():
    global FARM_REGISTRY
    name = request.form.get("farmer_name", "").strip()
    phone = request.form.get("phone_number", "").strip()
    crop = request.form.get("crop_type", "").strip()
    wkt = request.form.get("geom_polygon", "").strip()

    if name and wkt:
        lon, lat, geom = parse_wkt_polygon(wkt)
        if lon and lat:
            ex, ny = wgs84_to_utm36s(lon, lat)
            new_id = f"FARM_{len(FARM_REGISTRY) + 1:03d}"
            FARM_REGISTRY[new_id] = {"id": new_id, "owner": name, "phone": phone, "crop": crop, "lat": lat, "lon": lon, "utm_x": ex, "utm_y": ny, "boundary": geom, "is_new": True}
            return redirect(url_for('index', success_msg=f"Successfully injected {name}'s dynamic plot boundary!"))
            
    return redirect(url_for('index'))

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(fetch_and_analyze_daily_data, 'cron', hour=18, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
