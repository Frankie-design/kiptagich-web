import os
from flask import Flask, render_template, request
import folium
import africastalking

app = Flask(__name__)

# ==========================================
# 1. LIVE AFRICA'S TALKING INITIALIZATION
# ==========================================
# TODO: Replace these placeholders with your actual live production credentials
AT_USERNAME = "your_live_username"
AT_API_KEY = "your_live_api_key"

try:
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    sms = africastalking.SMS
    print("--- BACKGROUND LOG: Africa's Talking Production Gateway Initialized ---")
    live_sms_ready = True
except Exception as e:
    print(f"--- BACKGROUND LOG: Failed to initialize live gateway: {e} ---")
    live_sms_ready = False

# ==========================================
# 2. SEED DATABASE / REGISTRY
# ==========================================
# This holds your presentation cases. When your group members give you the real 
# data, you can simply append or edit the fields right here.
FARM_REGISTRY = {
    "11405938": {
        "owner": "David Kiprono",
        "id": "11405938",
        "status": "Critical",
        "phone": "+254712345678", # <-- Put your own phone number here to test live SMS!
        "lat": -0.5467,
        "lon": 35.5624
    },
    "22334455": {
        "owner": "Grace Chepngetich",
        "id": "22334455",
        "status": "Satisfactory",
        "phone": "+254700000000",
        "lat": -0.5412,
        "lon": 35.5691
    },
    "66778899": {
        "owner": "John Koech",
        "id": "66778899",
        "status": "Monitor",
        "phone": "+254711111111",
        "lat": -0.5498,
        "lon": 35.5550
    }
}

# ==========================================
# 3. BACKGROUND SMS ROUTINE
# ==========================================
def trigger_background_alert(farm):
    """Quietly handles the cellular message dispatch without cluttering the UI."""
    if not live_sms_ready:
        print(f"--- BACKGROUND LOG: SMS skipped for {farm['owner']} (Gateway not configured) ---")
        return False
        
    message = (
        f"Alert for {farm['owner']} (Plot ID: {farm['id']}): Your plot has reached a "
        f"CRITICAL moisture threshold based on GNSS-R analysis. Please initiate irrigation."
    )
    
    try:
        # Executes the background cellular network transmission instantly
        response = sms.send(message, [farm["phone"]])
        print(f"--- BACKGROUND LOG: Live SMS successfully dispatched to {farm['owner']} ({farm['phone']}) ---")
        print(f"Response Details: {response}")
        return True
    except Exception as e:
        print(f"--- BACKGROUND LOG: Silent cellular dispatch failed for {farm['owner']}. Error: {e} ---")
        return False

# ==========================================
# 4. CORE APP ROUTING & MAP GENERATION
# ==========================================
@app.route("/", methods=["GET"])
def index():
    search_id = request.args.get("search_id", "").strip()
    farm_data = FARM_REGISTRY.get(search_id)
    error_msg = None

    # Base interactive map centered right on Kiptagich Ward area
    m = folium.Map(
        location=[-0.5450, 35.5650], 
        zoom_start=14, 
        control_scale=True
    )

    # Automatically map out all available registry entries as foundational pins
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

    # Process explicit user searches
    if search_id:
        if farm_data:
            # Re-center the layout dynamic viewport to focus directly on the found plot
            m = folium.Map(
                location=[farm_data["lat"], farm_data["lon"]], 
                zoom_start=16, 
                control_scale=True
            )
            
            # Highlight chosen plot with a dynamic glowing pulse map ring
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

            # SENSITIVE CHECK: Trigger background alert system immediately if status is Critical
            if farm_data["status"] == "Critical":
                trigger_background_alert(farm_data)

        else:
            error_msg = f"National ID '{search_id}' not found in registry."

    # Render out frame structures to inject directly into the HTML panel layout
    map_html = m._repr_html_()
    return render_template(
        "dashboard.html", 
        map_html=map_html, 
        farm_data=farm_data, 
        error_msg=error_msg, 
        current_search=search_id
    )

if __name__ == "__main__":
    # Port configuration optimal for deployment infrastructure environments
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
