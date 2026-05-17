import os
import re
from flask import Flask, render_template, request
import folium

app = Flask(__name__)

# ==========================================
# 1. CORE DATABASE REGISTRY
# ==========================================
FARM_REGISTRY = {
    "11405938": {
        "owner": "David Kiprono",
        "id": "11405938",
        "status": "Critical",
        "lat": -0.5467,
        "lon": 35.5624
    },
    "22334455": {
        "owner": "Grace Chepngetich",
        "id": "22334455",
        "status": "Satisfactory",
        "lat": -0.5412,
        "lon": 35.5691
    },
    "66778899": {
        "owner": "John Koech",
        "id": "66778899",
        "status": "Monitor",
        "lat": -0.5498,
        "lon": 35.5550
    }
}

# ==========================================
# 2. BULLETPROOF KML BOUNDARY PARSER
# ==========================================
def load_kml_boundary():
    # Targets your exact repository file name directly
    target_file = "Kiptagich_Ward_Offline.kml"
    
    if not os.path.exists(target_file):
        print(f"CRITICAL: {target_file} was not found in the root directory!")
        return None
        
    try:
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            kml_content = f.read()
        
        # Pulls the raw text inside the <coordinates> tags directly using regex.
        # This completely bypasses fastkml folder nesting structural failures.
        coord_match = re.search(r'<coordinates>(.*?)</coordinates>', kml_content, re.DOTALL)
        
        if coord_match:
            coord_string = coord_match.group(1).strip()
            coordinates_list = []
            
            # Split the coordinate pairs (separated by spaces or tabs in the KML file)
            for chunk in coord_string.split():
                if ',' in chunk:
                    parts = chunk.split(',')
                    # KML standard is (Longitude, Latitude). Folium requires (Latitude, Longitude).
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coordinates_list.append([lat, lon])
            
            if coordinates_list:
                print(f"SUCCESS: Extracted {len(coordinates_list)} boundary coordinates.")
                return coordinates_list
                
        print("WARNING: Found KML file, but could not locate a valid <coordinates> block.")
    except Exception as e:
        print(f"Error reading raw KML data: {e}")
    return None

# ==========================================
# 3. ROUTING & MAP GENERATION LOGIC
# ==========================================
@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    if search_id and farm_data:
        map_center = [farm_data["lat"], farm_data["lon"]]
        zoom_level = 16
    else:
        # Aligned map center view over Kiptagich Ward
        map_center = [-0.5450, 35.5650]
        zoom_level = 13

    # Initialize empty map canvas
    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles=None, control_scale=True)

    # Base Map Tiles
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap Map").add_to(m)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite View",
        overlay=False,
        control=True
    ).add_to(m)

    # Extract and inject the true Kiptagich Ward Boundary
    kml_polygon_coords = load_kml_boundary()
    if kml_polygon_coords:
        folium.Polygon(
            locations=kml_polygon_coords,
            color="purple",
            weight=4,
            fill=True,
            fill_color="purple",
            fill_opacity=0.05,
            popup="Kiptagich True Boundary"
        ).add_to(m)

    # Render Standard Registry Pins
    for fid, f in FARM_REGISTRY.items():
        p_color = "red" if f["status"] == "Critical" else ("orange" if f["status"] == "Monitor" else "green")
        folium.Marker(
            location=[f["lat"], f["lon"]],
            popup=f"Owner: {f['owner']}<br>ID: {f['id']}<br>Status: {f['status']}",
            icon=folium.Icon(color=p_color, icon="info-sign")
        ).add_to(m)

    # Highlight Search Target
    if search_id:
        if farm_data:
            folium.Marker(
                location=[farm_data["lat"], farm_data["lon"]],
                popup=f"<b>TARGET MATCH</b><br>Owner: {farm_data['owner']}",
                icon=folium.Icon(color="darkpurple", icon="star")
            ).add_to(m)
            
            folium.CircleMarker(
                location=[farm_data["lat"], farm_data["lon"]],
                radius=25,
                color="#9b59b6",
                fill=True,
                fill_color="#9b59b6",
                fill_opacity=0.3
            ).add_to(m)
        else:
            error_msg = f"National ID '{search_id}' not found in registry."

    # Turn layer selection widget back on
    folium.LayerControl(position="topright").add_to(m)

    # Render HTML map layer structure
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
