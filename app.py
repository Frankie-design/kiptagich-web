import os
import re
import csv
from flask import Flask, render_template, request
import folium
from shapely.wkt import loads as load_wkt
from pyproj import Transformer

app = Flask(__name__)

# Geodetic (WGS84 EPSG:4326) to Projected UTM Zone 36S (EPSG:32736) for Kenya
utm_transformer = Transformer.from_crs("epsg:4326", "epsg:32736", always_xy=True)

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
                # UPDATED: Matches your exact column header 'id number' with a space
                national_id = row.get("id number", "").strip()
                wkt_polygon = row.get("geom_polygon", "").strip()
                
                if not national_id or not wkt_polygon:
                    continue
                
                try:
                    # Strip Z dimension identifier if present for standard WKT reading
                    clean_wkt = wkt_polygon.replace("POLYGON Z", "POLYGON")
                    shapely_poly = load_wkt(clean_wkt)
                    
                    # 1. Calculate Centroid Point
                    centroid = shapely_poly.centroid
                    lon_deg, lat_deg = centroid.x, centroid.y
                    
                    # 2. Coordinate Transformation to UTM Zone 36S (Meters)
                    easting, northing = utm_transformer.transform(lon_deg, lat_deg)
                    
                    # 3. Flip coords (lon, lat) -> (lat, lon) for Folium drawing
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
                        "status": "Satisfactory"  # Gateway baseline status placeholder
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

    # Draw individual plot footprints and add markers
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
