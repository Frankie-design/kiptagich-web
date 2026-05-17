import os
from flask import Flask, render_template, request
import folium
from fastkml import kml
from shapely.geometry import shape

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

# Helper function to extract coordinate paths directly from your repo's KML
def load_kml_boundary():
    # Looks for any .kml file inside your project directory
    kml_files = [f for f in os.listdir('.') if f.endswith('.kml')]
    if not kml_files:
        return None
    
    try:
        with open(kml_files[0], 'rb') as f:
            doc = f.read()
        k = kml.KML()
        k.from_string(doc)
        
        # Dig into the KML structure to extract geometries
        features = list(k.features())
        if hasattr(features[0], 'features'):
            sub_features = list(features[0].features())
            for feature in sub_features:
                if feature.geometry:
                    geom = shape(feature.geometry)
                    if geom.geom_type == 'Polygon':
                        # Convert (lon, lat) to Folium's required (lat, lon)
                        return [[lat, lon] for lon, lat in geom.exterior.coords]
    except Exception as e:
        print(f"Error parsing KML: {e}")
    return None

# ==========================================
# 2. ROUTING & MAP GENERATION LOGIC
# ==========================================
@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    # Determine default zoom orientation based on user searching behavior
    if search_id and farm_data:
        map_center = [farm_data["lat"], farm_data["lon"]]
        zoom_level = 16
    else:
        map_center = [-0.5450, 35.5650]
        zoom_level = 14

    # Initialize map canvas without standard hardcoded backgrounds
    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles=None, control_scale=True)

    # ------------------------------------------
    # RESTORE SATELLITE & STREET CONTROL LAYERS
    # ------------------------------------------
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap Map").add_to(m)
    
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite View",
        overlay=False,
        control=True
    ).add_to(m)

    # ------------------------------------------
    # INJECT ORIGINAL KML LAYER BOUNDARY
    # ------------------------------------------
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
    else:
        # Emergency backup shape if the repository KML file name is misplaced
        backup_boundary = [[-0.5332, 35.5458], [-0.5305, 35.5532], [-0.5595, 35.6021], [-0.5826, 35.5932], [-0.5332, 35.5458]]
        folium.Polygon(locations=backup_boundary, color="purple", weight=2, fill=False).add_to(m)

    # ------------------------------------------
    # RENDER STANDARD REGISTRY PINS
    # ------------------------------------------
    for fid, f in FARM_REGISTRY.items():
        p_color = "red" if f["status"] == "Critical" else ("orange" if f["status"] == "Monitor" else "green")
        folium.Marker(
            location=[f["lat"], f["lon"]],
            popup=f"Owner: {f['owner']}<br>ID: {f['id']}<br>Status: {f['status']}",
            icon=folium.Icon(color=p_color, icon="info-sign")
        ).add_to(m)

    # ------------------------------------------
    # HIGHLIGHT SEARCH TARGET
    # ------------------------------------------
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

    # Turn layer selection map switcher widget back on
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
