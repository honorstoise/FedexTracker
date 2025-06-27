from flask import Flask, render_template_string
import requests
from datetime import datetime, timedelta, timezone
import pytz
import os
from dateutil import parser

app = Flask(__name__)

API_KEY = os.environ.get('API_KEY')
BASE_URL = 'http://api.aviationstack.com/v1/flights'

def fetch_fedex_flights():
    params = {
        'access_key': API_KEY,
        'airline_icao': 'FDX',
        'limit': 100
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    flights = data.get('data', [])

    now = datetime.now(timezone.utc).replace(tzinfo=pytz.UTC)
    one_day = timedelta(days=1)

    filtered = []
    for f in flights:
        dep_time_str = f['departure'].get('scheduled')
        if not dep_time_str:
            continue
        try:
            dep_time = parser.isoparse(dep_time_str)
        except Exception as e:
            print(f"Failed to parse date {dep_time_str}: {e}")
            continue
        if now - one_day <= dep_time <= now + one_day:
            status = (f.get('flight_status') or '').lower()
            if status == 'active':
                f['flight_status'] = 'in-flight'
            filtered.append(f)
    return filtered

def calculate_statistics(flights):
    total_flights = len(flights)
    delayed_flights = sum(1 for f in flights if f['departure'].get('delay'))
    average_delay = sum(f['departure'].get('delay', 0) or 0 for f in flights) / total_flights if total_flights > 0 else 0
    return {
        'total_flights': total_flights,
        'delayed_flights': delayed_flights,
        'average_delay': round(average_delay, 2)
    }

def get_local_time(utc_str):
    if not utc_str:
        return 'N/A', ''
    try:
        dt_utc = parser.isoparse(utc_str)
        dt_utc = dt_utc.astimezone(pytz.UTC)
        local_tz = pytz.timezone('America/New_York')
        dt_local = dt_utc.astimezone(local_tz)
        return dt_local.strftime('%Y-%m-%d %H:%M'), dt_local.tzname()
    except Exception:
        return 'N/A', ''

def flight_sort_key(f):
    status_priority = {'landed': 0, 'in-flight': 1, 'scheduled': 2}
    status = (f.get('flight_status') or '').lower()
    priority = status_priority.get(status, 3)
    dep_time_str = f['departure'].get('scheduled')
    try:
        dep_time = parser.isoparse(dep_time_str) if dep_time_str else datetime.max.replace(tzinfo=pytz.UTC)
    except Exception:
        dep_time = datetime.max.replace(tzinfo=pytz.UTC)
    return (priority, dep_time)

@app.route('/')
def index():
    flights = fetch_fedex_flights()
    for f in flights:
        dep_local, dep_tz = get_local_time(f['departure'].get('scheduled'))
        arr_local, arr_tz = get_local_time(f['arrival'].get('scheduled'))
        f['departure']['local_time'] = dep_local
        f['departure']['local_tz'] = dep_tz
        f['arrival']['local_time'] = arr_local
        f['arrival']['local_tz'] = arr_tz

    flights.sort(key=flight_sort_key)

    stats = calculate_statistics(flights)
    return render_template_string(TEMPLATE, flights=flights, stats=stats)

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>FedEx Aircraft Tracker</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #121212;
            color: #f0f0f0;
        }

        h1 {
            color: #e67e22;  /* Darker orange */
        }

        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 20px;
            background-color: #1e1e1e;
        }

        th, td {
            border: 1px solid #333;
            padding: 10px;
            text-align: left;
        }

        th {
            background-color: #2c2c2c;
            color: #e67e22;
        }

        td {
            color: #f0f0f0;
        }

        tr:nth-child(even) {
            background-color: #1a1a1a;
        }

        tr:hover {
            background-color: #2a2a2a;
        }

        strong {
            color: #e67e22;
        }

        a {
            color: #e67e22;
        }
    </style>
</head>
<body>
    <h1>FedEx Aircraft Tracker</h1>
    <p><strong>Total Flights:</strong> {{ stats.total_flights }}</p>
    <p><strong>Delayed Flights:</strong> {{ stats.delayed_flights }}</p>
    <p><strong>Average Delay (min):</strong> {{ stats.average_delay }}</p>

    <table>
        <thead>
            <tr>
                <th>Flight</th>
                <th>Departure Airport</th>
                <th>Arrival Airport</th>
                <th>Departure</th>
                <th>Arrival</th>
                <th>Status</th>
                <th>Delay (min)</th>
            </tr>
        </thead>
        <tbody>
            {% for flight in flights %}
            <tr>
                <td>{{ flight.flight.iata }}</td>
                <td>{{ flight.departure.airport or 'N/A' }} ({{ flight.departure.iata or 'N/A' }})</td>
                <td>{{ flight.arrival.airport or 'N/A' }} ({{ flight.arrival.iata or 'N/A' }})</td>
                <td title="Scheduled UTC: {{ flight.departure.scheduled }}">
                    {{ flight.departure.local_time }}
                    {% if flight.departure.local_tz %} ({{ flight.departure.local_tz }}){% endif %}
                </td>
                <td title="Scheduled UTC: {{ flight.arrival.scheduled }}">
                    {{ flight.arrival.local_time }}
                    {% if flight.arrival.local_tz %} ({{ flight.arrival.local_tz }}){% endif %}
                </td>
                <td>{{ flight.flight_status }}</td>
                <td>{{ flight.departure.delay or 0 }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True)
