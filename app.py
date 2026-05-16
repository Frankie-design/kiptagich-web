from flask import Flask, render_template
from flask import Flask, render_template
import folium
from pykml import parser
import os

app = Flask(__name__)

@app.route('/')
def index():
    # 1. Create the base map with scale bar
    m = folium.Map(location=[-0.526, 35.587], zoom_start=13, control_scale=True)

    # 2. Add Google Satellite Imagery (The layer you need for GIS analysis)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Satellite View',
        overlay=False,
        control=True
    ).add_to(m)

    # Keep the standard map as an option
    folium.TileLayer('openstreetmap', name='Street Map').add_to(m)

    # 3. Path to your KML
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
            
            # Add the boundary with JKUAT Green color
            folium.Polygon(
                locations=points,
                color="#2ecc71", 
                weight=4,
                fill=True,
                fill_opacity=0.1,
                popup="Kiptagich Ward Boundary"
            ).add_to(m)
            
    except Exception as e:
        print(f"Error loading KML: {e}")

    # 4. Add the Layer Selector to the top-right corner
    folium.LayerControl().add_to(m)

    map_html = m._repr_html_()
    return render_template('dashboard.html', map_html=map_html)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)