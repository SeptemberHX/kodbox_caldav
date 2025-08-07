#!/usr/bin/env python3
"""KodBox CalDAV Server - Simple startup script."""

import sys
import os

# Add current directory to Python path for Docker compatibility
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from presentation import create_app

def main():
    """Main entry point."""
    try:
        # Load configuration
        config = load_config()
        
        # Setup logging
        config.setup_logging()
        
        # Create Flask application
        app = create_app(config)
        
        print(f"Starting KodBox CalDAV Server...")
        print(f"Server: http://{config.server.host}:{config.server.port}")
        print(f"CalDAV URL: http://{config.server.host}:{config.server.port}/")
        
        # Start server
        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.server.debug,
            use_reloader=False  # Disable reloader to avoid background sync issues
        )
        
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Failed to start server: {e}")
        raise


if __name__ == '__main__':
    main()
