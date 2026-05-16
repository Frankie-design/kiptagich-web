from flask import Flask, render_template, request, jsonify
import folium
from pykml import parser
import os

app = Flask(__name__)

# ==========================================
# 1. NATIONAL ID FARM DATABASE BLOCK
# ==========================================
FARM_DATABASE = {
    "29485731": {"owner": "John Chepkwony", "lat": -0.528, "lon": 35.585, "status": "Satisfactory"},
    "32019485": {"owner": "Mary Cherotich", "lat": -0.531, "lon": 35.592, "status": "Monitor"},
    "11405938": {"owner": "David Kiprono", "lat": -0.522, "lon": 35.579, "status": "Critical"},
    "27495811": {"owner": "Grace Kipkemoi", "lat": -0.535, "lon": 35.588, "status": "Satisfactory"}
}

@app.route('/')
def index():
    # Create the base map with scale bar
    m = folium.Map(location=[-0.526, 35.587], zoom_start=13, control_scale=True)

    # Add Google Satellite Imagery
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Satellite View',
        overlay=False,
        control=True
    ).add_to(m)

    # Keep the standard map as an option
    folium.TileLayer('openstreetmap', name='Street Map').add_to(m)

    # Path to your KML
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
            
            # Add the boundary with Purple color
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

    # Add the Layer Selector to the top-right corner
    folium.LayerControl().add_to(m)

    map_html = m._repr_html_()
    return render_template('dashboard.html', map_html=map_html)

# ==========================================
# 2. INTERACTIVE SEARCH ENDPOINT ROUTE
# ==========================================
@app.route('/search_farm')
def search_farm():
    farm_id = request.args.get('id', '').strip()
    
    if farm_id in FARM_DATABASE:
        farm_info = FARM_DATABASE[farm_id]
        return jsonify({
            "id": farm_id,
            "owner": farm_info["owner"],
            "lat": farm_info["lat"],
            "lon": farm_info["lon"],
            "status": farm_info["status"]
        })
    else:
        return jsonify({"error": f"National ID '{farm_id}' not found in Kiptagich registry."}), 404

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
