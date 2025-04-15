# Ticket Tailor Copier

A web application that allows copying event series between Ticket Tailor box offices. This tool simplifies the process of duplicating event series configurations, including events, ticket types, and associated bundles.

## Features

- Copy event series between different Ticket Tailor box offices
- Preserve all event series configurations
- Copy all events within the series
- Copy all ticket types for each event
- User-friendly web interface
- Secure API key handling
- Comprehensive error handling

## Prerequisites

- Python 3.x
- Ticket Tailor API keys for both source and target box offices
- Required permissions in both box offices

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ticket-tailor-copier.git
cd ticket-tailor-copier
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your web browser and navigate to `http://localhost:5000`

3. Enter the API keys:
   - Source Box Office API Key: The API key from the box office containing the event series you want to copy
   - Target Box Office API Key: The API key from the box office where you want to create the copy

4. Click "Load Event Series" to see available series from the source box office

5. Click "Copy" next to any event series to copy it to the target box office

## API Key Requirements

Your API keys must have the following permissions:
- Read access to event series, events, and ticket types in the source box office
- Write access to create event series, events, and ticket types in the target box office

## Error Handling

The application handles various error scenarios:

- Invalid API keys
- Missing permissions
- Network connectivity issues
- Invalid event series IDs
- Missing required parameters

Error messages will be displayed in the web interface when issues occur.

## Deployment

For production deployment, it's recommended to:

1. Use Gunicorn as the WSGI server:
```bash
gunicorn app:app
```

2. Set up a reverse proxy (e.g., Nginx) in front of the application

3. Use environment variables for sensitive configuration

4. Enable HTTPS for secure API key transmission

## Security Considerations

- API keys are never stored on the server
- All API key transmission is done over HTTPS
- Input validation is performed on both client and server side
- Error messages are sanitized to prevent information leakage

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers. # ticket-tailor-copier
