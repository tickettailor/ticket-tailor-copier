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
        'Accept': 'application/json'
    }

def make_api_request(method, url, api_key, **kwargs):
    """Make an API request with proper authentication"""
    return requests.request(
        method,
        url,
        auth=(api_key, ''),  # API key as username, empty password
        headers=get_auth_header(api_key),
        **kwargs
    )

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
        url = f"{TICKET_TAILOR_API_BASE}/event_series"
        response = make_api_request('GET', url, source_api_key)
        response.raise_for_status()
        data = response.json()
        # Handle pagination if needed
        if 'data' in data:
            return data['data']
        return data
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'text'):
            error_msg = f"API Error: {e.response.text}"
            if e.response.status_code == 404:
                error_msg += f" (URL: {url})"
            return {"error": error_msg}
        return {"error": str(e)}

def copy_event_series(source_api_key, target_api_key, series_id):
    """Copy an event series from source to target box office"""
    try:
        # Get the event series details
        series_url = f"{TICKET_TAILOR_API_BASE}/event_series/{series_id}"
        series_response = make_api_request('GET', series_url, source_api_key)
        series_response.raise_for_status()
        series_data = series_response.json()
        if 'data' in series_data:
            series_data = series_data['data']

        # Remove voucher_ids from series data
        if 'voucher_ids' in series_data:
            del series_data['voucher_ids']

        # Format the data for API
        formatted_series_data = format_data_for_api(series_data)

        # Create the event series in target box office
        create_url = f"{TICKET_TAILOR_API_BASE}/event_series"
        create_response = make_api_request('POST', create_url, target_api_key, data=formatted_series_data)
        create_response.raise_for_status()
        new_series_data = create_response.json()
        if 'data' in new_series_data:
            new_series_id = new_series_data['data']['id']
        else:
            new_series_id = new_series_data['id']

        # Get all events in the series
        events_url = f"{TICKET_TAILOR_API_BASE}/events"
        events_response = make_api_request('GET', events_url, source_api_key, params={'event_series_id': series_id})
        events_response.raise_for_status()
        events_data = events_response.json()
        events = events_data['data'] if 'data' in events_data else events_data

        # Copy each event and its ticket types
        for event in events:
            # Create the event in target box office
            event_data = {k: v for k, v in event.items() if k != 'id'}
            event_data['event_series_id'] = new_series_id
            
            # Remove voucher_ids from event data
            if 'voucher_ids' in event_data:
                del event_data['voucher_ids']
                
            formatted_event_data = format_data_for_api(event_data)
            
            event_create_url = f"{TICKET_TAILOR_API_BASE}/events"
            new_event_response = make_api_request('POST', event_create_url, target_api_key, data=formatted_event_data)
            new_event_response.raise_for_status()
            new_event_data = new_event_response.json()
            if 'data' in new_event_data:
                new_event_id = new_event_data['data']['id']
            else:
                new_event_id = new_event_data['id']

            # Get and copy ticket types
            ticket_types_url = f"{TICKET_TAILOR_API_BASE}/ticket_types"
            ticket_types_response = make_api_request('GET', ticket_types_url, source_api_key, params={'event_id': event['id']})
            ticket_types_response.raise_for_status()
            ticket_types_data = ticket_types_response.json()
            ticket_types = ticket_types_data['data'] if 'data' in ticket_types_data else ticket_types_data

            for ticket_type in ticket_types:
                ticket_type_data = {k: v for k, v in ticket_type.items() if k != 'id'}
                ticket_type_data['event_id'] = new_event_id
                
                # Remove voucher_ids from ticket type data
                if 'voucher_ids' in ticket_type_data:
                    del ticket_type_data['voucher_ids']
                    
                formatted_ticket_type_data = format_data_for_api(ticket_type_data)
                
                ticket_type_create_url = f"{TICKET_TAILOR_API_BASE}/ticket_types"
                make_api_request('POST', ticket_type_create_url, target_api_key, data=formatted_ticket_type_data).raise_for_status()

        return {"success": True, "new_series_id": new_series_id}
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'text'):
            error_msg = f"API Error: {e.response.text}"
            if e.response.status_code == 404:
                # Get the URL from the exception
                url = e.response.url
                error_msg += f" (URL: {url})"
            return {"error": error_msg}
        return {"error": str(e)}

def test_api_connection(api_key):
    """Test the API connection and key"""
    try:
        # Try to get the box office details first
        url = f"{TICKET_TAILOR_API_BASE}/box_office"
        print(f"\nMaking GET request to: {url}")
        response = make_api_request('GET', url, api_key)
        response.raise_for_status()
        box_office_data = response.json()
        print(f"Box Office Data: {box_office_data}")

        # Then try to get events
        events_url = f"{TICKET_TAILOR_API_BASE}/events"
        print(f"\nMaking GET request to: {events_url}")
        events_response = make_api_request('GET', events_url, api_key)
        events_response.raise_for_status()
        events_data = events_response.json()
        print(f"Events Data: {events_data}")

        return True
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'text'):
            method = e.response.request.method
            error_msg = f"API Error ({method}): {e.response.text}"
            if e.response.status_code == 404:
                error_msg += f" (URL: {e.response.url})"
            print(f"Error: {error_msg}")
        return False

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

@app.route('/test-api', methods=['GET'])
def test_api():
    source_api_key = request.args.get('source_api_key')
    if not source_api_key:
        return jsonify({"error": "Source API key is required"}), 400
    
    result = test_api_connection(source_api_key)
    if result:
        return jsonify({"success": True, "message": "API connection successful"})
    return jsonify({"error": "API connection failed"}), 500

if __name__ == '__main__':
    app.run(debug=True) 