# KodBox CalDAV Server

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A modern CalDAV server that bridges KodBox project management data into standard CalDAV format, allowing you to view your KodBox projects and tasks in any CalDAV-compatible calendar client.

## Features

- ✨ **Modern Architecture**: Clean domain-driven design with proper separation of concerns
- 🔄 **Background Sync**: Automatic data synchronization with configurable intervals
- 🛡️ **Robust Error Handling**: Comprehensive error handling and monitoring
- 🐳 **Docker Ready**: Full Docker and Docker Compose support
- 📊 **Health Monitoring**: Built-in health checks and status endpoints
- 🔧 **Flexible Configuration**: Support for environment variables, JSON config, and CLI arguments
- 📱 **CalDAV Compatible**: Works with Apple Calendar, Thunderbird, DAVx5, and more
- 🚀 **Production Ready**: Systemd service, log rotation, and deployment scripts included

## Quick Start

### Using Docker (Recommended)

1. **Clone and configure**:
   ```bash
   git clone <repository-url>
   cd kodbox-caldav
   cp .env.example .env
   # Edit .env with your KodBox server details
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

3. **Check health**:
   ```bash
   curl http://localhost:5082/health
   ```

### Manual Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create configuration**:
   ```bash
   python main.py --create-config
   # Edit config.json with your KodBox details
   ```

3. **Run the server**:
   ```bash
   python main.py
   ```

## Configuration

The server supports multiple configuration methods (in order of precedence):

1. **Command line arguments**
2. **Environment variables**  
3. **JSON configuration file**
4. **Default values**

### Environment Variables

```bash
# KodBox Configuration
KODBOX_BASE_URL=https://your-kodbox.com/
KODBOX_USERNAME=your_kodbox_username
KODBOX_PASSWORD=your_kodbox_password
KODBOX_TIMEOUT=30

# CalDAV Authentication
CALDAV_USERNAME=kodbox
CALDAV_PASSWORD=calendar123

# Server Settings
SERVER_HOST=0.0.0.0
SERVER_PORT=5082
SERVER_DEBUG=false

# Sync Settings
SYNC_INTERVAL=300  # 5 minutes
```

### JSON Configuration

```json
{
  "kodbox": {
    "base_url": "https://your-kodbox.com/",
    "username": "your_kodbox_username",
    "password": "your_kodbox_password",
    "timeout": 30
  },
  "caldav": {
    "username": "kodbox",
    "password": "calendar123"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 5082,
    "debug": false
  }
}
```

## CalDAV Client Setup

### iOS/macOS Calendar

1. Go to Settings → Calendar → Accounts → Add Account → Other
2. Select "Add CalDAV Account"
3. Server: `http://your-server:5082/`
4. Username: `kodbox` (or your configured username)
5. Password: `calendar123` (or your configured password)

### Android (DAVx5)

1. Install DAVx5 from Google Play Store
2. Add new account → Login with URL and username
3. Base URL: `http://your-server:5082/`
4. Username and password as configured

### Thunderbird

1. Go to Calendar → New Calendar → On the Network
2. Choose CalDAV
3. Location: `http://your-server:5082/calendars/`
4. Enter credentials when prompted

## Development

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd kodbox-caldav

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Start development server
python main.py --debug
```

### Project Structure

```
kodbox-caldav/
├── src/kodbox_caldav/          # Main application package
│   ├── domain/                 # Domain entities and interfaces
│   ├── application/            # Application services and use cases
│   ├── infrastructure/         # External integrations
│   ├── presentation/           # HTTP/CalDAV protocol handlers
│   ├── config.py              # Configuration management
│   └── monitoring/            # Error handling and monitoring
├── tests/                     # Test suite
├── deploy/                    # Deployment configurations
├── main.py                    # Application entry point
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Docker image definition
└── pyproject.toml            # Project metadata and tool configuration
```

### Architecture

The application follows Clean Architecture principles:

- **Domain Layer**: Core business logic and entities (`Project`, `Task`, `Calendar`)
- **Application Layer**: Use cases and services (`CalDAVService`, `DataSyncService`)
- **Infrastructure Layer**: External integrations (`KodBoxRepository`, `CalendarRepository`)
- **Presentation Layer**: HTTP/CalDAV protocol handlers (Flask routes)

## Deployment

### Production Deployment

1. **Using the deployment script**:
   ```bash
   sudo ./deploy/install.sh
   ```

2. **Configure the service**:
   ```bash
   sudo nano /etc/kodbox-caldav/config.json
   ```

3. **Start the service**:
   ```bash
   sudo systemctl start kodbox-caldav
   sudo systemctl status kodbox-caldav
   ```

### Docker Production

Use the included `docker-compose.yml` with production profiles:

```bash
# With Nginx reverse proxy
docker-compose --profile nginx up -d

# With monitoring stack
docker-compose --profile monitoring up -d
```

### Kubernetes

Example Kubernetes manifests are available in the `deploy/k8s/` directory.

## Monitoring

### Health Checks

- **Health endpoint**: `GET /health`
- **Prometheus metrics**: `GET /metrics` (when monitoring enabled)

### Logging

Logs are written to:
- Console output (structured JSON in production)
- File: `logs/kodbox-caldav.log` (with rotation)
- Systemd journal: `journalctl -u kodbox-caldav`

### Error Handling

The application includes comprehensive error handling:
- Automatic retry mechanisms for API failures
- Graceful degradation when KodBox is unavailable
- Detailed error tracking and monitoring

## API Reference

### CalDAV Endpoints

- `PROPFIND /` - Root collection discovery
- `PROPFIND /calendars/` - Calendar collection listing
- `PROPFIND /calendars/{project_id}/` - Project calendar details
- `REPORT /calendars/{project_id}/` - Calendar queries
- `GET /calendars/{project_id}/{task_id}.ics` - Individual task
- `GET /calendars/{project_id}/calendar.ics` - Full project calendar

### Management Endpoints

- `GET /health` - Health status and diagnostics
- `GET /.well-known/caldav` - CalDAV service discovery

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Ensure tests pass: `pytest`
5. Format code: `black . && isort .`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](https://kodbox-caldav.readthedocs.io/)
- 🐛 [Issue Tracker](https://github.com/your-org/kodbox-caldav/issues)
- 💬 [Discussions](https://github.com/your-org/kodbox-caldav/discussions)

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- CalDAV protocol implementation
- [iCalendar](https://github.com/collective/icalendar) library for calendar generation
- Inspired by modern Python application architecture patterns