
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
    flights = []
    error = None
    if request.method == 'POST':
        departure = request.form.get('departure')
        arrival = request.form.get('arrival')
        date = request.form.get('date')

        if not departure:
            error = "Por favor, ingresa una ciudad de salida."
        else:
            data = load_flight_data()
            flights = filter_flights(data, departure, arrival, date)

    return render_template('index.html', flights=flights, error=error)

if __name__ == '__main__':
    app.run(debug=True)
