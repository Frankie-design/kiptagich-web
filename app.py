import os
from flask import Flask, render_template, request
import folium

app = Flask(__name__)

# ==========================================
# 1. CORE FARM REGISTRY DATABASE
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
# 2. ROUTING & INTERACTIVE MAP VIEW
# ==========================================
@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    # Focus map: zoom to farm if searched, otherwise display full ward view
    if search_id and farm_data:
        m = folium.Map(
            location=[farm_data["lat"], farm_data["lon"]], 
            zoom_start=16, 
            control_scale=True
        )
    else:
        m = folium.Map(
            location=[-0.5450, 35.5650], 
            zoom_start=13, 
            control_scale=True
        )

    # ------------------------------------------
    # DYNAMIC LAYER: TRUE KIPTAGICH WARD BOUNDARY
    # ------------------------------------------
    # Looking for 'kiptagich.geojson' or 'kiptagich.kml' inside the static/ folder
    geojson_path = os.path.join("static", "kiptagich.geojson")
    
    if os.path.exists(geojson_path):
        folium.GeoJson(
            geojson_path,
            name="Kiptagich Ward Boundary",
            style_function=lambda x: {
                "color": "purple",
                "weight": 4,
                "fillColor": "purple",
                "fillOpacity": 0.03
            }
        ).add_to(m)
    else:
        # If the file naming differs, this prints to your Render logs to track it down
        print(f"⚠️ Map warning: Looked for {geojson_path} but it was missing.")

    # Render data registry pins
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

    # Dynamic target highlight matching
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
            
            # Pure local print tracking for SMS workflow simulation
            if farm_data["status"] == "Critical":
                print(f"--- SIMULATION LOG: Critical status alert for {farm_data['owner']} triggered successfully. ---")
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
