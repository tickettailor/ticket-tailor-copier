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
    # Log request details
    print(f"\n=== API Request Details ===")
    print(f"Method: {method}")
    print(f"URL: {url}")
    print(f"Headers: {get_auth_header(api_key)}")
    if 'data' in kwargs:
        print(f"Request Data: {kwargs['data']}")
    if 'params' in kwargs:
        print(f"Query Params: {kwargs['params']}")
    print("========================\n")
    
    response = requests.request(
        method,
        url,
        auth=(api_key, ''),  # API key as username, empty password
        headers=get_auth_header(api_key),
        **kwargs
    )
    
    # Log response details
    print(f"\n=== API Response Details ===")
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    print("========================\n")
    
    return response

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
        print(f"API Success (GET, source): Retrieved event series {series_id}")
        series_data = series_response.json()
        if 'data' in series_data:
            series_data = series_data['data']

        # Create the event series in target box office with all fields except voucher_ids
        create_url = f"{TICKET_TAILOR_API_BASE}/event_series"
        series_create_data = {k: v for k, v in series_data.items() if k not in ['id', 'voucher_ids']}
        create_response = make_api_request('POST', create_url, target_api_key, data=series_create_data)
        create_response.raise_for_status()
        print(f"API Success (POST, target): Created new event series")
        new_series_data = create_response.json()
        if 'data' in new_series_data:
            new_series_id = new_series_data['data']['id']
        else:
            new_series_id = new_series_data['id']

        # Get all events in the series
        events_url = f"{TICKET_TAILOR_API_BASE}/events"
        events_response = make_api_request('GET', events_url, source_api_key, params={'event_series_id': series_id})
        events_response.raise_for_status()
        print(f"API Success (GET, source): Retrieved events for series {series_id}")
        events_data = events_response.json()
        events = events_data['data'] if 'data' in events_data else events_data

        # Copy each event and its ticket types
        for event in events:
            # Create the event in target box office with only the allowed fields
            event_data = {}
            
            # Copy only the allowed fields
            allowed_fields = {
                'end_date': None,
                'end_time': None,
                'hidden': None,
                'override_id': None,
                'start_date': None,
                'start_time': None,
                'unavailable': None,
                'unavailable_status': None
            }
            
            # Flatten date fields and copy allowed fields
            if 'start' in event:
                event_data['start_date'] = event['start']['date']
                event_data['start_time'] = event['start']['time'] + ':00'  # Ensure H:i:s format
            if 'end' in event:
                event_data['end_date'] = event['end']['date']
                event_data['end_time'] = event['end']['time'] + ':00'  # Ensure H:i:s format
            
            # Copy other allowed fields if they exist
            for field in allowed_fields:
                if field in event:
                    event_data[field] = event[field]
            
            event_create_url = f"{TICKET_TAILOR_API_BASE}/event_series/{new_series_id}/events"
            new_event_response = make_api_request('POST', event_create_url, target_api_key, data=event_data)
            new_event_response.raise_for_status()
            print(f"API Success (POST, target): Created new event in series {new_series_id}")
            new_event_data = new_event_response.json()
            if 'data' in new_event_data:
                new_event_id = new_event_data['data']['id']
            else:
                new_event_id = new_event_data['id']

            # Copy ticket types from the event data
            for ticket_type in event['ticket_types']:
                # Create ticket type with all fields except voucher_ids
                ticket_type_data = {k: v for k, v in ticket_type.items() if k not in ['id', 'voucher_ids']}
                
                # Debug log the ticket type data before validation
                print(f"Debug: Original ticket type data: {ticket_type_data}")
                
                # Validate and handle min_per_order and max_per_order
                for field in ['min_per_order', 'max_per_order']:
                    if field in ticket_type_data:
                        try:
                            # Convert to string first to handle any non-string values
                            value_str = str(ticket_type_data[field])
                            # Remove any non-numeric characters
                            value_str = ''.join(filter(str.isdigit, value_str))
                            value = int(value_str) if value_str else 1
                            
                            if value < 1:
                                value = 1
                            elif value > 500:
                                value = 500
                            
                            ticket_type_data[field] = value
                        except (ValueError, TypeError) as e:
                            print(f"Debug: Error converting {field}: {e}")
                            ticket_type_data[field] = 1
                
                # Ensure min_per_order is not greater than max_per_order
                if 'min_per_order' in ticket_type_data and 'max_per_order' in ticket_type_data:
                    if ticket_type_data['min_per_order'] > ticket_type_data['max_per_order']:
                        ticket_type_data['min_per_order'] = ticket_type_data['max_per_order']
                
                # Debug log the ticket type data after validation
                print(f"Debug: Validated ticket type data: {ticket_type_data}")
                
                # Create ticket type in the event series
                ticket_type_create_url = f"{TICKET_TAILOR_API_BASE}/event_series/{new_series_id}/ticket_types"
                print(f"Debug: Creating ticket type at URL: {ticket_type_create_url}")
                make_api_request('POST', ticket_type_create_url, target_api_key, data=ticket_type_data).raise_for_status()
                print(f"API Success (POST, target): Created ticket type for event series {new_series_id}")

        return {"success": True, "new_series_id": new_series_id}
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'text'):
            method = e.response.request.method
            # Determine which API key was used
            api_key_used = source_api_key if e.response.request.url.endswith(f"/{series_id}") or "event_series_id" in str(e.response.request.url) else target_api_key
            api_type = "source" if api_key_used == source_api_key else "target"
            error_msg = f"API Error ({method}, {api_type}): {e.response.text}"
            if e.response.status_code == 404:
                error_msg += f" (URL: {e.response.url})"
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