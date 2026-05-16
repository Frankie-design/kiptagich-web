from flask import Flask, render_template, request
import folium
from pykml import parser
import os

app = Flask(__name__)

# ==========================================
# DIRECT DECIMAL DEGREES DATABASE REGISTRY
# ==========================================
FARM_DATABASE = {
    "29485731": {"owner": "John Chepkwony", "lat": -0.528, "lon": 35.585, "status": "Satisfactory"},
    # This entry points exactly to your Ainamoi point from Google Earth!
    "32019485": {"owner": "Mary Cherotich", "lat": -0.546811, "lon": 35.659836, "status": "Monitor"},
    "11405938": {"owner": "David Kiprono", "lat": -0.522, "lon": 35.579, "status": "Critical"},
    "27495811": {"owner": "Grace Kipkemoi", "lat": -0.535, "lon": 35.588, "status": "Satisfactory"}
}

@app.route('/')
def index():
    # Read search parameter from URL if it exists
    search_id = request.args.get('search_id', '').strip()
    error_msg = None
    
    # Default center coordinates over Kiptagich Ward
    map_center = [-0.526, 35.587]
    zoom_level = 13
    
    farm_info = None
    if search_id:
        if search_id in FARM_DATABASE:
            farm_info = FARM_DATABASE[search_id]
            map_center = [farm_info["lat"], farm_info["lon"]]
            zoom_level = 16  # Zoom in close to show the searched farm plot
        else:
            error_msg = f"National ID '{search_id}' not found in registry."

    # Build the Folium instance safely
    m = folium.Map(location=map_center, zoom_start=zoom_level, control_scale=True)

    # Base Tile layers
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Satellite View',
        overlay=False,
        control=True
    ).add_to(m)
    folium.TileLayer('openstreetmap', name='Street Map').add_to(m)

    # Load and render KML Boundary Line Layout
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
        print(f"Error loading KML boundary layout: {e}")

    # If an ID matches, add the marker pin cleanly inside Python before rendering
    if farm_info:
        color_map = {"Satisfactory": "green", "Monitor": "orange", "Critical": "red"}
        marker_color = color_map.get(farm_info["status"], "blue")
        
        popup_content = f"""
        <div style='font-family: sans-serif; font-size:13px;'>
            <b>National ID:</b> {search_id}<br>
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
    
    return render_template('dashboard.html', map_html=map_html, error_msg=error_msg, current_search=search_id)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
