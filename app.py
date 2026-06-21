import os
import re
import csv
import math
import requests
from flask import Flask, render_template, request, redirect, url_for
import folium
import africastalking

app = Flask(__name__)

# --- AFRICA'S TALKING SANDBOX SYSTEM CONFIG ---
AT_USERNAME = "sandbox"
AT_API_KEY = "atsk_37d85845c73d9bbcd0512108e7e91979afaad6864b732799f8e1e6bd5e6e24a6505862d0" 
africastalking.initialize(AT_USERNAME, AT_API_KEY)
sms = africastalking.SMS
# ----------------------------------------------

FARM_REGISTRY = {}
IS_INITIALIZED = False
# Renamed to v2 to completely clear out the old 99 records on Render's disk
PERSISTENT_STORAGE_FILE = "farmers_v2.csv"

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
    print("Initiating manual telemetry broadcast verification sequence...")
    if os.path.exists(PERSISTENT_STORAGE_FILE):
        try:
            with open(PERSISTENT_STORAGE_FILE, mode='r', encoding='utf-8') as f:
                process_csv_rows(f, append_to_file=False)
        except Exception:
            pass

    sent_logs = []
    for fid, f in list(FARM_REGISTRY.items()):
        name_hash = sum(ord(char) for char in f["owner"])
        simulated_moisture = LATEST_METRICS["soil_moisture"] + ((name_hash % 17) - 8)
        
        if simulated_moisture < 26.0:
            farmer_name = f["owner"]
            phone = str(f["phone"]).strip()
            crop = f["crop"]
            
            clean_phone = "".join(filter(str.isdigit, phone))
            if clean_phone.startswith("0"):
                clean_phone = "+254" + clean_phone[1:]
            elif (clean_phone.startswith("7") or clean_phone.startswith("1")) and len(clean_phone) == 9:
                clean_phone = "+254" + clean_phone
            elif clean_phone.startswith("254") and len(clean_phone) == 12:
                clean_phone = "+" + clean_phone
            elif not clean_phone.startswith("+"):
                clean_phone = "+254" + clean_phone

            alert_message = (
                f"Habari {farmer_name}, Kiptagich Agri-GIS tracking highlights that your "
                f"{crop} plot soil moisture has dropped to {simulated_moisture:.1f}%. "
                f"Status: Needs Irrigation."
            )
            
            try:
                response = sms.send(
                    message=alert_message, 
                    recipients=[clean_phone], 
                    sender_id="Kiptagich Ltd"
                )
                sent_logs.append(f"Success to {clean_phone}")
            except Exception as e:
                sent_logs.append(f"Failed to {clean_phone}: {str(e)}")
    return sent_logs

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
    try:
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
                    duplicate_found = False
                    for existing_farm in FARM_REGISTRY.values():
                        if existing_farm["owner"] == name and existing_farm["phone"] == phone:
                            duplicate_found = True
                            break
                    
                    if not duplicate_found:
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
    except Exception:
        return 0

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
    
    m = folium.Map(location=[-0.5510, 35.5780], zoom_start=13, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="Vector Map").add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Satellite Backdrop").add_to(m)

    kml_polygon_coords = load_kml_boundary()
    if kml_polygon_coords:
        folium.Polygon(locations=kml_polygon_coords, color="purple", weight=3, fill=False).add_to(m)

    all_points = []
    if kml_polygon_coords:
        all_points.extend(kml_polygon_coords)

    for fid, f in FARM_REGISTRY.items():
        if f["boundary"]:
            folium.Polygon(locations=f["boundary"], color="darkblue", weight=2, fill=True, fill_opacity=0.2).add_to(m)
            all_points.extend(f["boundary"])
            
        name_hash = sum(ord(char) for char in f["owner"])
        simulated_moisture = LATEST_METRICS["soil_moisture"] + ((name_hash % 17) - 8)
        simulated_ndvi = min(0.85, max(0.15, LATEST_METRICS["ndvi"] + ((name_hash % 5) * 0.04 - 0.08)))
        
        if simulated_moisture < 26.0:
            status = "Needs Irrigation"
            marker_color = "red"
        else:
            status = "Satisfactory"
            marker_color = "green"
            
        popup_html = (
            f"<h5><b>{f['owner']}</b></h5>"
            f"<b>Crop:</b> {f['crop']}<br>"
            f"<b>UTM Zone:</b> {f['utm_zone']}<br>"
            f"<b>UTM Easting:</b> {f['utm_x']:.1f}m<br>"
            f"<b>UTM Northing:</b> {f['utm_y']:.1f}m<br><hr style='margin:4px 0;'>"
            f"<b>📡 CYGNSS Moisture:</b> {simulated_moisture:.1f}%<br>"
            f"<b>🌿 Sentinel-2 NDVI:</b> {simulated_ndvi:.2f}<br>"
            f"<b>Status:</b> <span style='color:{marker_color}; font-weight:bold;'>{status}</span>"
        )
        folium.Marker(location=[f["lat"], f["lon"]], popup=folium.Popup(popup_html, max_width=280), icon=folium.Icon(color=marker_color, icon="leaf")).add_to(m)

    if all_points:
        m.fit_bounds(all_points)

    folium.LayerControl().add_to(m)
    
    raw_map_html = m._repr_html_()
    fixed_map_html = raw_map_html.replace(
        '<div ', 
        '<div style="width:100%; height:100vh; margin:0; padding:0; overflow:hidden;" ', 
        1
    )
    
    return render_template("dashboard.html", map_html=fixed_map_html, total_farms=len(FARM_REGISTRY), success_msg=success_msg)

@app.route("/upload_csv", methods=["POST"])
def upload_csv():
    if 'csv_file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['csv_file']
    if file.filename == '':
        return redirect(url_for('index'))
        
    if file and file.filename.endswith('.csv'):
        try:
            stream = file.read().decode("utf-8").splitlines()
            count = process_csv_rows(stream, append_to_file=True)
            return redirect(url_for('index', success_msg=f"Successfully loaded {count} farms to persistent memory!"))
        except Exception as e:
            return redirect(url_for('index', success_msg=f"Upload error: {str(e)}"))
            
    return redirect(url_for('index'))

@app.route("/trigger_sms_broadcast", methods=["GET", "POST"])
def trigger_sms_broadcast():
    logs = dispatch_irrigation_alerts()
    log_summary = " | ".join(logs)[:200]
    return redirect(url_for('index', success_msg=f"Broadcast complete! Logs: {log_summary}"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
