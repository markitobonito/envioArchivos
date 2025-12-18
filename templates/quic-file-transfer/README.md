# QUIC File Transfer

This project implements a file transfer application using QUIC and TCP protocols. It allows users to upload files through a web interface and send them to peers over a secure connection.

## Features

- **File Upload**: Users can upload files through a web interface.
- **QUIC and TCP Support**: The application attempts to send files using QUIC first, falling back to TCP if necessary.
- **Flask Web Server**: A lightweight web server built with Flask to handle file uploads and user interactions.
- **Real-time Feedback**: Users receive notifications about the status of their file transfers.

## Project Structure

```
quic-file-transfer
├── app
│   ├── __init__.py
│   ├── client.py          # Client-side logic for sending files
│   ├── quic_server.py     # QUIC server implementation
│   ├── utils.py           # Utility functions
│   └── templates
│       └── index.html     # HTML template for the web interface
├── tests
│   ├── test_client.py     # Unit tests for client functionality
│   └── test_quic_server.py # Unit tests for QUIC server
├── certs
│   ├── cert.pem           # SSL certificate
│   └── key.pem            # Private key for SSL
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image instructions
├── docker-compose.yml      # Docker orchestration file
├── run.py                  # Entry point for running the application
├── .env.example            # Example environment variables
├── .gitignore              # Files to ignore in Git
└── README.md               # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd quic-file-transfer
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Ensure you have the necessary certificates in the `certs` directory (`cert.pem` and `key.pem`).

## Running the Application

To run the application, execute the following command:
```
python run.py
```

The application will start a Flask server on `http://localhost:5000` and a QUIC server on port `9999`.

## Usage

1. Open your web browser and navigate to `http://localhost:5000`.
2. Use the file upload form to select a file and send it to peers.
3. Ensure that your peers are online and ready to receive files.

## License

This project is licensed under the MIT License. See the LICENSE file for details.