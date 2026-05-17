from flask import Flask, render_template, request
import folium
from pykml import parser
import os
import africastalking

app = Flask(__name__)

# ==========================================
# AFRICA'S TALKING ACCOUNT CONFIGURATION
# ==========================================
# To go live later: Change "sandbox" to your real username, and swap the API key
AT_USERNAME = "sandbox"
AT_API_KEY = "atsk_f2466c6356562f03cd3bb0db88084508d08c1cecfe1b2afa079b69287c38a8c76f4c8c57" 

sms_gateway = None
try:
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    sms_gateway = africastalking.SMS
    print("SMS Gateway ready to handle automated background requests.")
except Exception as e:
    print(f"SMS Framework bypassed safely: {e}")

# ==========================================
# SYSTEM DATABASE REGISTRY
# ==========================================
FARM_DATABASE = {
    "29485731": {"owner": "John Chepkwony", "phone": "+254768911014", "lat": -0.528, "lon": 35.585, "status": "Satisfactory"},
    "32019485": {"owner": "Mary Cherotich", "phone": "+254702970192", "lat": -0.546811, "lon": 35.659836, "status": "Monitor"},
    "11405938": {"owner": "David Kiprono", "phone": "+254798992348", "lat": -0.522, "lon": 35.579, "status": "Critical"},
    "27495811": {"owner": "Grace Kipkemoi", "phone": "+254115690209", "lat": -0.535, "lon": 35.588, "status": "Satisfactory"}
}

@app.route('/')
def index():
    search_id = request.args.get('search_id', '').strip()
    error_msg = None
    farm_sidebar_data = None
    background_sms_sent = False
    
    map_center = [-0.526, 35.587]
    zoom_level = 13
    
    farm_info = None
    if search_id:
        if search_id in FARM_DATABASE:
            farm_info = FARM_DATABASE[search_id]
            map_center = [farm_info["lat"], farm_info["lon"]]
            zoom_level = 16  
            
            # ---------------------------------------------------------------
            # AUTOMATED BACKGROUND SMS LOGIC
            # ---------------------------------------------------------------
            # If the remote sensing analysis evaluates to Critical, dispatch SMS instantly!
            if farm_info["status"] == "Critical" and sms_gateway:
                try:
                    message_body = f"Kiptagich System Alert: Hello {farm_info['owner']}, GNSS-R data shows soil moisture drops below threshold on your plot. Please irrigate immediately."
                    sms_gateway.send(message=message_body, recipients=[farm_info['phone']])
                    background_sms_sent = True
                    print(f"Background alert automatically sent to {farm_info['owner']}.")
                except Exception as e:
                    print(f"Background automatic transmission error: {e}")
            
            farm_sidebar_data = {
                "id": search_id,
                "owner": farm_info["owner"],
                "phone": farm_info["phone"],
                "status": farm_info["status"]
            }
        else:
            error_msg = f"National ID '{search_id}' not found in registry."

    m = folium.Map(location=map_center, zoom_start=zoom_level, control_scale=True)

    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Satellite View',
        overlay=False,
        control=True
    ).add_to(m)
    folium.TileLayer('openstreetmap', name='Street Map').add_to(m)

    kml_file = 'Kiptagich_Ward_Offline.kml'
    try:
        if os.path.exists(kml_file):
            with open(kml_file, 'rb') as f:
                root = parser.parse(f).getroot()
            namespace = {"kml": "http://www.opengis.net/kml/2.2"}
            coords_text = root.xpath("//kml:coordinates", namespaces=namespace)[0].text.strip()
            
            points = []
            for pair in coords_text.split():
                if ',' in pair:
                    c = pair.split(',')
                    points.append([float(c[1]), float(c[0])])
            
            folium.Polygon(
                locations=points,
                color="#800080", 
                weight=4,
                fill=True,
                fill_opacity=0.05,
                popup="Kiptagich Ward Boundary"
            ).add_to(m)
    except Exception as e:
        print(f"Error loading KML: {e}")

    if farm_info:
        color_map = {"Satisfactory": "green", "Monitor": "orange", "Critical": "red"}
        marker_color = color_map.get(farm_info["status"], "blue")
        
        popup_content = f"""
        <div style='font-family: sans-serif; font-size:13px;'>
            <b>Owner's ID No:</b> {search_id}<br>
            <b>Farmer:</b> {farm_info['owner']}<br>
            <b>Status:</b> <span style='color:{marker_color};font-weight:bold;'>{farm_info['status']}</span>
        </div>
        """
        folium.Marker(
            location=[farm_info["lat"], farm_info["lon"]],
            popup=folium.Popup(popup_content, max_width=250),
            icon=folium.Icon(color=marker_color, icon="info-sign")
        ).add_to(m)

    folium.LayerControl().add_to(m)
    map_html = m._repr_html_()
    
    return render_template(
        'dashboard.html', 
        map_html=map_html, 
        error_msg=error_msg, 
        current_search=search_id,
        farm_data=farm_sidebar_data,
        background_sms_sent=background_sms_sent
    )

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
