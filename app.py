
from flask import Flask, render_template, request
import pandas as pd
import os

app = Flask(__name__)

FLIGHTS_FILE = 'flights_data.csv'

def load_flight_data():
    if not os.path.exists(FLIGHTS_FILE):
        return pd.DataFrame()
    try:
        return pd.read_csv(FLIGHTS_FILE)
    except Exception as e:
        print(f"Error loading flight data: {e}")
        return pd.DataFrame()

def filter_flights(data, departure, arrival, date):
    if data.empty:
        return []
    filtered = data[
        data['departure'].str.lower().str.strip() == departure.lower().strip()
    ]
    if arrival:
        filtered = filtered[
            filtered['arrival'].str.lower().str.strip() == arrival.lower().strip()
        ]
    if date:
        filtered = filtered[filtered['date'] == date]
    return filtered.to_dict(orient='records')

@app.route('/', methods=['GET', 'POST'])
def index():
    import logging
    from datetime import datetime as dt
    flights = []
    error = None
    if request.method == 'POST':
        departure = request.form.get('departure', '').strip()
        arrival = request.form.get('arrival', '').strip()
        date = request.form.get('date', '').strip()
        logger = logging.getLogger('App')
        try:
            if not departure:
                error = "Por favor, ingresa una ciudad de salida."
            elif date and not _is_valid_date(date):
                error = "Formato de fecha inválido. Usa AAAA-MM-DD."
            else:
                data = load_flight_data()
                flights = filter_flights(data, departure, arrival, date)
        except Exception as e:
            logger.error(f"Error procesando formulario: {e}")
            error = "Ocurrió un error procesando la solicitud."
    return render_template('index.html', flights=flights, error=error)

def _is_valid_date(date_str):
    try:
        dt.strptime(date_str, "%Y-%m-%d")
        return True
    except Exception:
        return False

from flask import jsonify

@app.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    # Simulación de redes WiFi encontradas
    networks = [
        {"ssid": "HostBerry-5G", "signal": 82, "security": "WPA2"},
        {"ssid": "Casa", "signal": 67, "security": "WPA/WPA2"},
        {"ssid": "Invitados", "signal": 54, "security": "Open"},
        {"ssid": "Oficina", "signal": 39, "security": "WPA2"}
    ]
    return jsonify({"networks": networks})

if __name__ == '__main__':
    app.run(debug=True)
