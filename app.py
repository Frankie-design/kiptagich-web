import os
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
# 2. CORE ROUTING & MAP GENERATION LOGIC
# ==========================================
@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    # Base Map Center Location
    if search_id and farm_data:
        center_lat, center_lon = farm_data["lat"], farm_data["lon"]
        start_zoom = 15
    else:
        center_lat, center_lon = -0.5490, 35.5720
        start_zoom = 13

    # Initialize map WITHOUT default tiles to allow clean layer switching
    m = folium.Map(location=[center_lat, center_lon], zoom_start=start_zoom, tiles=None, control_scale=True)

    # ------------------------------------------
    # MAP LAYERS (STREETS & SATELLITE VIEW)
    # ------------------------------------------
    folium.TileLayer(
        tiles="OpenStreetMap", 
        name="OpenStreetMap"
    ).add_to(m)
    
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    # ------------------------------------------
    # ORIGINAL DETAILED KIPTAGICH WARD BOUNDARY
    # ------------------------------------------
    real_kiptagich_boundary = [
        [-0.5332, 35.5458], [-0.5305, 35.5532], [-0.5284, 35.5654], 
        [-0.5321, 35.5712], [-0.5365, 35.5723], [-0.5401, 35.5784], 
        [-0.5421, 35.5802], [-0.5460, 35.5804], [-0.5495, 35.5760], 
        [-0.5512, 35.5714], [-0.5543, 35.5721], [-0.5574, 35.5778], 
        [-0.5582, 35.5824], [-0.5571, 35.5902], [-0.5580, 35.5976], 
        [-0.5595, 35.6021], [-0.5632, 35.6042], [-0.5668, 35.6035], 
        [-0.5694, 35.6001], [-0.5732, 35.5984], [-0.5824, 35.5982], 
        [-0.5826, 35.5932], [-0.5765, 35.5904], [-0.5741, 35.5851], 
        [-0.5744, 35.5782], [-0.5721, 35.5734], [-0.5725, 35.5645], 
        [-0.5748, 35.5582], [-0.5762, 35.5512], [-0.5721, 35.5424], 
        [-0.5642, 35.5342], [-0.5562, 35.5412], [-0.5521, 35.5484], 
        [-0.5482, 35.5451], [-0.5441, 35.5398], [-0.5385, 35.5402], 
        [-0.5332, 35.5458]
    ]

    folium.Polygon(
        locations=real_kiptagich_boundary,
        color="purple",
        weight=4,
        fill=True,
        fill_color="purple",
        fill_opacity=0.01,
        popup="Kiptagich Ward Boundary"
    ).add_to(m)

    # ------------------------------------------
    # RENDER STANDARD REGISTRY PINS
    # ------------------------------------------
    for fid, f in FARM_REGISTRY.items():
        if f["status"] == "Critical":
            p_color = "red"
        elif f["status"] == "Monitor":
            p_color = "orange"
        else:
            p_color = "green"

        folium.Marker(
            location=[f["lat"], f["lon"]],
            popup=f"Owner: {f['owner']}<br>ID: {f['id']}<br>Status: {f['status']}",
            icon=folium.Icon(color=p_color, icon="info-sign")
        ).add_to(m)

    # ------------------------------------------
    # TARGET SELECTION HIGHLIGHT MATCHING
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

    # Add the layer control panel back to the top right corner
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
