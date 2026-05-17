import os
from flask import Flask, render_template, request
import folium

app = Flask(__name__)

# ==========================================
# 1. DATABASE REGISTRY
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
# 2. CORE ROUTING & MAP GENERATION
# ==========================================
@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    # 1. Create the primary map view centered on Kiptagich
    # If a farm is searched, zoom into it; otherwise, show the full ward overview
    if search_id and farm_data:
        m = folium.Map(
            location=[farm_data["lat"], farm_data["lon"]], 
            zoom_start=16, 
            control_scale=True
        )
    else:
        m = folium.Map(
            location=[-0.5450, 35.5650], 
            zoom_start=14, 
            control_scale=True
        )

    # 2. LOAD WARD BOUNDARY
    # If your original code read a GeoJSON file (e.g., 'kiptagich.geojson'), 
    # it gets safely injected right here:
    geojson_path = os.path.join("static", "kiptagich.geojson")
    if os.path.exists(geojson_path):
        folium.GeoJson(
            geojson_path,
            name="Kiptagich Ward Boundary",
            style_function=lambda x: {
                "color": "purple",
                "weight": 3,
                "fillColor": "purple",
                "fillOpacity": 0.05
            }
        ).add_to(m)
    else:
        # Fallback detailed coordinate trace to loop the ward boundary if file isn't used
        detailed_ward_coords = [
            [-0.5350, 35.5500], [-0.5320, 35.5700], [-0.5400, 35.5850],
            [-0.5420, 35.5950], [-0.5500, 35.5980], [-0.5550, 35.5800],
            [-0.5650, 35.5750], [-0.5600, 35.5600], [-0.5500, 35.5450],
            [-0.5400, 35.5420], [-0.5350, 35.5500]
        ]
        folium.Polygon(
            locations=detailed_ward_coords,
            color="purple",
            weight=3,
            fill=True,
            fill_color="purple",
            fill_opacity=0.05,
            popup="Kiptagich Ward"
        ).add_to(m)

    # 3. PLOT THE FARM MARKERS
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

    # 4. HIGHLIGHT SEARCH TARGET IF ACTIVE
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
