import os
import re
import csv
import math
from flask import Flask, render_template, request
import folium

app = Flask(__name__)

# ==========================================
# PURE PYTHON GEOSPATIAL ENGINE (NO SHAPELY)
# ==========================================
def parse_wkt_polygon(wkt_string):
    """
    Parses a WKT POLYGON string into a list of [lat, lon] coordinates
    and calculates the centroid using basic math.
    """
    try:
        coord_text = re.search(r'POLYGON(?:\s+Z)?\s*\(\((.*?)\)\)', wkt_string, re.IGNORECASE)
        if not coord_text:
            return None, None, []
        
        raw_coords = coord_text.group(1).split(',')
        folium_coords = []
        sum_lon = 0
        sum_lat = 0
        count = 0
        
        for pt in raw_coords:
            parts = pt.strip().split()
            if len(parts) >= 2:
                lon = float(parts[0])
                lat = float(parts[1])
                folium_coords.append([lat, lon])
                
                if count == 0 or pt != raw_coords[-1]:
                    sum_lon += lon
                    sum_lat += lat
                    count += 1
                    
        if count == 0:
            return None, None, []
            
        centroid_lon = sum_lon / count
        centroid_lat = sum_lat / count
        return centroid_lon, centroid_lat, folium_coords
    except Exception as e:
        print(f"WKT Parsing Error: {e}")
        return None, None, []

def wgs84_to_utm36s(lon, lat):
    """Converts Geodetic Lat/Lon to UTM Zone 36S (meters) via pure math."""
    lon_origin = 33.0
    deg_to_rad = math.pi / 180.0
    lat_rad = lat * deg_to_rad
    lon_rad = (lon - lon_origin) * deg_to_rad
    
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e_sq = (a**2 - b**2) / (a**2)
    
    k0 = 0.9996
    false_easting = 500000.0
    false_northing = 10000000.0
    
    N = a / math.sqrt(1.0 - e_sq * math.sin(lat_rad)**2)
    T = math.tan(lat_rad)**2
    C = e_sq * math.cos(lat_rad)**2 / (1.0 - e_sq)
    A = lon_rad * math.cos(lat_rad)
    
    M = a * ((1.0 - e_sq/4.0 - 3.0*e_sq**2/64.0 - 5.0*e_sq**3/256.0) * lat_rad
             - (3.0*e_sq/8.0 + 3.0*e_sq**2/32.0 + 45.0*e_sq**3/1024.0) * math.sin(2.0*lat_rad)
             + (15.0*e_sq**2/256.0 + 45.0*e_sq**3/1024.0) * math.sin(4.0*lat_rad)
             - (35.0*e_sq**3/3072.0) * math.sin(6.0*lat_rad))
    
    easting = false_easting + k0 * N * (A + (1.0 - T + C) * A**3 / 6.0 + (5.0 - 18.0 * T + T**2 + 72.0 * C - 58.0 * e_sq) * A**5 / 120.0)
    northing = false_northing + k0 * (M + N * math.tan(lat_rad) * (A**2 / 2.0 + (5.0 - T + 9.0 * C + 4.0 * C**2) * A**4 / 24.0 + (61.0 - 58.0 * T + T**2 + 600.0 * C - 330.0 * e_sq) * A**6 / 720.0))
    return easting, northing

# ==========================================
# DATA LOADING AND ROUTING
# ==========================================
def load_farmers_database():
    csv_file = "farmers.csv"
    database = {}
    if not os.path.exists(csv_file):
        return database

    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                national_id = row.get("id number", "").strip()
                wkt_polygon = row.get("geom_polygon", "").strip()
                
                if not national_id or not wkt_polygon:
                    continue
                
                lon_deg, lat_deg, folium_coords = parse_wkt_polygon(wkt_polygon)
                if lon_deg is None or lat_deg is None:
                    continue
                
                easting, northing = wgs84_to_utm36s(lon_deg, lat_deg)
                
                database[national_id] = {
                    "id": national_id,
                    "owner": row.get("farmer_name", "Unknown").strip(),
                    "phone": row.get("phone_number", "N/A").strip(),
                    "crop": row.get("crop_type", "N/A").strip(),
                    "lat": lat_deg,
                    "lon": lon_deg,
                    "utm_x": easting,
                    "utm_y": northing,
                    "boundary": folium_coords,
                    "status": "Satisfactory"
                }
        print(f"SUCCESS: Loaded {len(database)} records.")
    except Exception as e:
        print(f"Database error: {e}")
    return database

FARM_REGISTRY = load_farmers_database()

def load_kml_boundary():
    target_file = "Kiptagich_Ward_Offline.kml"
    if not os.path.exists(target_file):
        return None
    try:
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            kml_content = f.read()
        coord_match = re.search(r'<coordinates>(.*?)</coordinates>', kml_content, re.DOTALL)
        if coord_match:
            coord_string = coord_match.group(1).strip()
            coordinates_list = []
            for chunk in coord_string.split():
                if ',' in chunk:
                    parts = chunk.split(',')
                    coordinates_list.append([float(parts[1]), float(parts[0])])
            return coordinates_list
    except Exception as e:
        print(f"KML error: {e}")
    return None

@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    global FARM_REGISTRY
    FARM_REGISTRY = load_farmers_database()
    
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    if search_id and farm_data:
        map_center = [farm_data["lat"], farm_data["lon"]]
        zoom_level = 16
    else:
        map_center = [-0.5450, 35.5650]
        zoom_level = 13

    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap Map").add_to(m)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite View",
        overlay=False,
        control=True
    ).add_to(m)

    kml_polygon_coords = load_kml_boundary()
    if kml_polygon_coords:
        folium.Polygon(
            locations=kml_polygon_coords,
            color="purple",
            weight=4,
            fill=True,
            fill_color="purple",
            fill_opacity=0.02,
            popup="Kiptagich Ward Reference Boundary"
        ).add_to(m)

    for fid, f in FARM_REGISTRY.items():
        if f["boundary"]:
            folium.Polygon(
                locations=f["boundary"],
                color="cyan",
                weight=2,
                fill=True,
                fill_color="cyan",
                fill_opacity=0.1,
                popup=f"Plot Owner: {f['owner']}<br>Crop: {f['crop']}"
            ).add_to(m)
            
        folium.Marker(
            location=[f["lat"], f["lon"]],
            popup=f"<b>Owner:</b> {f['owner']}<br><b>Crop:</b> {f['crop']}<br><b>UTM_E:</b> {f['utm_x']:.1f}m<br><b>UTM_N:</b> {f['utm_y']:.1f}m",
            icon=folium.Icon(color="green", icon="leaf")
        ).add_to(m)

    if search_id:
        if farm_data:
            folium.Marker(
                location=[farm_data["lat"], farm_data["lon"]],
                popup=f"<b>TARGET MATCH</b><br>Owner: {farm_data['owner']}",
                icon=folium.Icon(color="darkpurple", icon="star")
            ).add_to(m)
        else:
            error_msg = f"ID '{search_id}' not found in database."

    folium.LayerControl(position="topright").add_to(m)
    map_html = m._repr_html_()
    return render_template(
        "dashboard.html", 
        map_html=map_html, 
        farm_data=farm_data, 
        error_msg=error_msg, 
        current_search=search_id
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
