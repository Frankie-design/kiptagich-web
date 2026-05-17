<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kiptagich Irrigation Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css">
    <style>
        body { background-color: #1a252f; color: #ecf0f1; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .sidebar { background-color: #2c3e50; min-height: 100vh; padding: 25px; box-shadow: 2px 0 5px rgba(0,0,0,0.2); }
        .map-container { height: 100vh; width: 100%; position: relative; }
        .card-custom { background-color: #34495e; border: none; color: #ecf0f1; margin-bottom: 25px; margin-top: 15px; }
        .status-dot { height: 12px; width: 12px; display: inline-block; border-radius: 50%; margin-right: 8px; }
        .btn-search { background-color: #2ecc71; color: white; border: none; }
        .btn-search:hover { background-color: #27ae60; color: white; }
        
        /* Specific Color Rules */
        .text-bold-black-sub { color: #000000 !important; font-weight: 700; }
        .text-white-heading { color: #ffffff !important; font-weight: bold; font-size: 0.85rem; letter-spacing: 0.05rem; }
        .text-white-label { color: #ffffff !important; }
    </style>
</head>
<body>

<div class="container-fluid p-0">
    <div class="row g-0">
        <div class="col-md-3 sidebar d-flex flex-column justify-content-between">
            <div>
                <h2 class="text-success fw-bold m-0">Kiptagich Ward</h2>
                <p class="text-bold-black-sub small mb-4">GNSS-R Irrigation System</p>
                
                <form action="/" method="GET" class="mb-4">
                    <label class="form-label small text-uppercase text-white-heading">Search Registry</label>
                    <div class="input-group">
                        <input type="text" name="search_id" class="form-control bg-dark text-white border-secondary" placeholder="Enter National ID..." value="{{ current_search }}">
                        <button class="btn btn-search px-3 fw-bold" type="submit">Search</button>
                    </div>
                </form>

                {% if error_msg %}
                    <div class="alert alert-danger small py-2 my-2" role="alert">{{ error_msg }}</div>
                {% endif %}

                <div class="my-4">
                    <label class="form-label small text-uppercase text-white-heading">Registry Match</label>
                    {% if farm_data %}
                        <div class="card card-custom p-3 shadow-sm" style="border-left: 4px solid {% if farm_data.status == 'Critical' %}#e74c3c{% elif farm_data.status == 'Monitor' %}#f39c12{% else %}#2ecc71{% endif %};">
                            <div class="card-body p-0">
                                <p class="mb-2 small text-white">Owner Name: <strong class="text-white">{{ farm_data.owner }}</strong></p>
                                <p class="mb-2 small text-white">Owner's ID No: <span class="text-white">{{ farm_data.id }}</span></p>
                                <p class="mb-0 small text-white">Status: 
                                    <span class="fw-bold" style="color: {% if farm_data.status == 'Critical' %}#e74c3c{% elif farm_data.status == 'Monitor' %}#f39c12{% else %}#2ecc71{% endif %}; font-weight: 800;">
                                        {{ farm_data.status }}
                                    </span>
                                </p>
                            </div>
                        </div>
                    {% else %}
                        <div class="text-white-label small italic p-3 bg-dark bg-opacity-25 rounded text-center my-2">
                            No target query currently selected.
                        </div>
                    {% endif %}
                </div>
            </div>

            <div class="mt-4 pt-3 border-top border-secondary">
                <label class="form-label small text-uppercase text-white-heading d-block mb-2">Irrigation Status</label>
                <div class="d-flex align-items-center mb-1"><span class="status-dot" style="background-color: #2ecc71;"></span> <span class="small text-white-label">Satisfactory</span></div>
                <div class="d-flex align-items-center mb-1"><span class="status-dot" style="background-color: #f39c12;"></span> <span class="small text-white-label">Monitor</span></div>
                <div class="d-flex align-items-center mb-0"><span class="status-dot" style="background-color: #e74c3c;"></span> <span class="small text-white-label">Critical (Irrigate)</span></div>
            </div>
        </div>

        <div class="col-md-9">
            <div class="map-container">
                {{ map_html|safe }}
            </div>
        </div>
    </div>
</div>

</body>
</html>
