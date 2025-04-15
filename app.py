from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv
import base64

app = Flask(__name__)
load_dotenv()

TICKET_TAILOR_API_BASE = "https://api.tickettailor.com/v1"

def get_auth_header(api_key):
    """Create the Authorization header for Ticket Tailor API requests"""
    return {
        'Authorization': f'Basic {base64.b64encode(api_key.encode()).decode()}',
        'Accept': 'application/json'
    }

def format_data_for_api(data):
    """Format data to match API requirements"""
    formatted_data = {}
    for key, value in data.items():
        if key in ['voucher_ids', 'ticket_type_ids']:
            # For array fields, send each value as a separate key
            if isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    formatted_data[f"{key}[]"] = v
            elif isinstance(value, str):
                values = value.split(',')
                for i, v in enumerate(values):
                    formatted_data[f"{key}[]"] = v
            elif value is None:
                formatted_data[f"{key}[]"] = ""
        else:
            formatted_data[key] = value
    return formatted_data

def get_event_series(source_api_key):
    """Fetch event series from source box office"""
    try:
        response = requests.get(
            f"{TICKET_TAILOR_API_BASE}/event_series",
            headers=get_auth_header(source_api_key)
        )
        response.raise_for_status()
        data = response.json()
        # Handle pagination if needed
        if 'data' in data:
            return data['data']
        return data
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'text'):
            return {"error": f"API Error: {e.response.text}"}
        return {"error": str(e)}

def copy_event_series(source_api_key, target_api_key, series_id):
    """Copy an event series from source to target box office"""
    try:
        # Get the event series details
        series_response = requests.get(
            f"{TICKET_TAILOR_API_BASE}/event_series/{series_id}",
            headers=get_auth_header(source_api_key)
        )
        series_response.raise_for_status()
        series_data = series_response.json()
        if 'data' in series_data:
            series_data = series_data['data']

        # Format the data for API
        formatted_series_data = format_data_for_api(series_data)

        # Create the event series in target box office
        create_response = requests.post(
            f"{TICKET_TAILOR_API_BASE}/event_series",
            headers=get_auth_header(target_api_key),
            data=formatted_series_data
        )
        create_response.raise_for_status()
        new_series_data = create_response.json()
        if 'data' in new_series_data:
            new_series_id = new_series_data['data']['id']
        else:
            new_series_id = new_series_data['id']

        # Get all events in the series
        events_response = requests.get(
            f"{TICKET_TAILOR_API_BASE}/events",
            headers=get_auth_header(source_api_key),
            params={'event_series_id': series_id}
        )
        events_response.raise_for_status()
        events_data = events_response.json()
        events = events_data['data'] if 'data' in events_data else events_data

        # Copy each event and its ticket types
        for event in events:
            # Create the event in target box office
            event_data = {k: v for k, v in event.items() if k != 'id'}
            event_data['event_series_id'] = new_series_id
            formatted_event_data = format_data_for_api(event_data)
            
            new_event_response = requests.post(
                f"{TICKET_TAILOR_API_BASE}/events",
                headers=get_auth_header(target_api_key),
                data=formatted_event_data
            )
            new_event_response.raise_for_status()
            new_event_data = new_event_response.json()
            if 'data' in new_event_data:
                new_event_id = new_event_data['data']['id']
            else:
                new_event_id = new_event_data['id']

            # Get and copy ticket types
            ticket_types_response = requests.get(
                f"{TICKET_TAILOR_API_BASE}/ticket_types",
                headers=get_auth_header(source_api_key),
                params={'event_id': event['id']}
            )
            ticket_types_response.raise_for_status()
            ticket_types_data = ticket_types_response.json()
            ticket_types = ticket_types_data['data'] if 'data' in ticket_types_data else ticket_types_data

            for ticket_type in ticket_types:
                ticket_type_data = {k: v for k, v in ticket_type.items() if k != 'id'}
                ticket_type_data['event_id'] = new_event_id
                formatted_ticket_type_data = format_data_for_api(ticket_type_data)
                
                requests.post(
                    f"{TICKET_TAILOR_API_BASE}/ticket_types",
                    headers=get_auth_header(target_api_key),
                    data=formatted_ticket_type_data
                ).raise_for_status()

        return {"success": True, "new_series_id": new_series_id}
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'text'):
            return {"error": f"API Error: {e.response.text}"}
        return {"error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/event-series', methods=['GET'])
def list_event_series():
    source_api_key = request.args.get('source_api_key')
    if not source_api_key:
        return jsonify({"error": "Source API key is required"}), 400
    
    result = get_event_series(source_api_key)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/copy-event-series', methods=['POST'])
def copy_series():
    data = request.json
    source_api_key = data.get('source_api_key')
    target_api_key = data.get('target_api_key')
    series_id = data.get('series_id')

    if not all([source_api_key, target_api_key, series_id]):
        return jsonify({"error": "Missing required parameters"}), 400

    result = copy_event_series(source_api_key, target_api_key, series_id)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True) 