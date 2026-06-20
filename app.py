import os
import re
import csv
import math
from flask import Flask, render_template, request
import folium
from shapely.wkt import loads as load_wkt

app = Flask(__name__)

# ==========================================
# PURE MATH GEODETIC TO UTM ZONE 36S ENGINE
# ==========================================
def wgs84_to_utm36s(lon, lat):
    """
    Mathematical transformation formula to convert Geodetic Lat/Lon 
    directly to UTM Zone 36S (meters) without requiring external pyproj binaries.
    """
    # Zone 36S central meridian is 33 degrees East
    lon_origin = 33.0
    deg_to_rad = math.pi / 180.0
    
    lat_rad = lat * deg_to_rad
    lon_rad = (lon - lon_origin) * deg_to_rad
    
    # WGS84 Ellipsoid constants
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e_sq = (a**2 - b**2) / (a**2)
    
    k0 = 0.9996
    false_easting = 500000.0
    false_northing = 10000000.0 # Southern Hemisphere
    
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
# 1. LIVE DATA SOURCE LOADER (CSV)
# ==========================================
def load_farmers_database():
    csv_file = "farmers.csv"
    database = {}
    
    if not os.path.exists(csv_file):
        print(f"CRITICAL: '{csv_file}' not found.")
        return database

    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Matches your manual space column header exactly
                national_id = row.get("id number", "").strip()
                wkt_polygon = row.get("geom_polygon", "").strip()
                
                if not national_id or not wkt_polygon:
                    continue
                
                try:
                    clean_wkt = wkt_polygon.replace("POLYGON Z", "POLYGON")
                    shapely_poly = load_wkt(clean_wkt)
                    
                    centroid = shapely_poly.centroid
                    lon_deg, lat_deg = centroid.x, centroid.y
                    
                    # Compute UTM via pure mathematical formula
                    easting, northing = wgs84_to_utm36s(lon_deg, lat_deg)
                    
                    folium_coords = [[pt[1], pt[0]] for pt in shapely_poly.exterior.coords]
                    
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
                except Exception as geom_err:
                    print(f"Skipping geometry parse error on row: {geom_err}")
                    
        print(f"SUCCESS: Loaded {len(database)} records from CSV.")
    except Exception as e:
        print(f"Database read failure: {e}")
    return database

FARM_REGISTRY = load_farmers_database()

# ==========================================
# 2. KML REGIONAL BOUNDARY PARSER
# ==========================================
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
        print(f"Error parsing KML: {e}")
    return None

# ==========================================
# 3. ROUTING & MAP GENERATION LOGIC
# ==========================================
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

    folium.LayerControl(position
