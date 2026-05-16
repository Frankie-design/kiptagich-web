from flask import Flask, render_template, request, jsonify
import folium
from pykml import parser
import os
import math

app = Flask(__name__)

# ==========================================
# 1. UTM ZONE 36S TO LAT/LON CONVERTER FUNCTION
# ==========================================
def utm_36s_to_latlon(easting, northing):
    """
    Converts UTM Zone 36 South coordinates (used in Kenya/Kiptagich) 
    into standard decimal degrees Latitude and Longitude.
    """
    # WGS84 Ellipsoid constants
    a = 6378137.0         # Semi-major axis
    f = 1.0 / 298.257223563 # Flattening
    b = a * (1.0 - f)     # Semi-minor axis
    
    e2 = (a**2 - b**2) / (a**2) # First eccentricity squared
    ePrime2 = (a**2 - b**2) / (b**2) # Second eccentricity squared
    
    # UTM parameters for Zone 36S
    k0 = 0.9996
    false_easting = 500000.0
    false_northing = 10000000.0 # Southern Hemisphere false northing
    
    x = easting - false_easting
    y = northing - false_northing  # Will be negative for Southern hemisphere
    
    # Calculate footprint latitude
    M = y / k0
    mu = M / (a * (1.0 - e2/4.0 - 3.0*e2**2/64.0 - 5.0*e2**3/256.0))
    
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    J1 = (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0)
    J2 = (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0)
    J3 = (151.0 * e1**3 / 96.0)
    
    fp = mu + J1*math.sin(2.0*mu) + J2*math.sin(4.0*mu) + J3*math.sin(6.0*mu)
    
    # Calculate Latitude and Longitude
    C1 = ePrime2 * math.cos(fp)**2
    T1 = math.tan(fp)**2
    R1 = a * (1.0 - e2) / (1.0 - e2 * math.sin(fp)**2)**1.5
    N1 = a / math.sqrt(1.0 - e2 * math.sin(fp)**2)
    D = x / (N1 * k0)
    
    # Latitude calculation
    lat = fp - (N1 * math.tan(fp) / R1) * (D**2/2.0 - (5.0 + 3.0*T1 + 10.0*C1 - 4.0*C1**2 - 9.0*ePrime2)*D**4/24.0 + (61.0 + 90.0*T1 + 298.0*C1 + 45.0*T1**2 - 252.0*ePrime2 - 3.0*C1**2)*D**6/720.0)
    
    # Longitude calculation (Zone 36 central meridian is 33 degrees East)
    lon_origin = 33.0
    lon = lon_origin + ((D - (1.0 + 2.0*T1 + C1)*D**3/6.0 + (5.0 - 2.0*C1 + 28.0*T1 - 3.0*C1**2 + 8.0*ePrime2 + 24.0*T1**2)*D**5/120.0) / math.cos(fp))
    
    return math.degrees(lat), math.degrees(lon)

# ==========================================
# 2. GROUND TRUTH REALISTIC DATABASE (UTM METERS)
# ==========================================
# Ground-truth metric database registry (Updated with your exact Google Earth points!)
FARM_DATABASE = {
    "29485731": {"owner": "John Chepkwony", "east": 787900, "north": 9941700, "status": "Satisfactory"},
    "32019485": {"owner": "Mary Cherotich", "east": 795945.90, "north": 9939533.48, "status": "Monitor"},
    "11405938": {"owner": "David Kiprono", "east": 787200, "north": 9942400, "status": "Critical"},
    "27495811": {"owner": "Grace Kipkemoi", "east": 788200, "north": 9940900, "status": "Satisfactory"}
}
@app.route('/')
def index():
    # Create base map safely centered over Kiptagich (-0.526, 35.587)
    m = folium.Map(location=[-0.526, 35.587], zoom_start=13, control_scale=True)

    # Base layers
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Satellite View',
        overlay=False,
        control=True
    ).add_to(m)
    folium.TileLayer('openstreetmap', name='Street Map').add_to(m)

    # KML Parser
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

    folium.LayerControl().add_to(m)
    map_html = m._repr_html_()
    return render_template('dashboard.html', map_html=map_html)

# ==========================================
# 3. CONVERTING SEARCH ENDPOINT
# ==========================================
@app.route('/search_farm')
def search_farm():
    farm_id = request.args.get('id', '').strip()
    
    if farm_id in FARM_DATABASE:
        farm_info = FARM_DATABASE[farm_id]
        
        # Safely convert the metrics behind the scenes before serving the web client
        lat, lon = utm_36s_to_latlon(farm_info["east"], farm_info["north"])
        
        return jsonify({
            "id": farm_id,
            "owner": farm_info["owner"],
            "lat": lat,
            "lon": lon,
            "status": farm_info["status"]
        })
    else:
        return jsonify({"error": f"National ID '{farm_id}' not found in registry."}), 404

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
