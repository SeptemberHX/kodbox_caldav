"""Presentation layer for KodBox CalDAV Server."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import wraps
from threading import Thread

from flask import Flask, request, Response, jsonify
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from config import Config
from application import CalDAVService, DataSyncService
from infrastructure import KodBoxRepository, CalendarRepository
from .routes import register_caldav_routes


# CalDAV namespace constants
DAV_NS = 'DAV:'
CALDAV_NS = 'urn:ietf:params:xml:ns:caldav'
CARDDAV_NS = 'urn:ietf:params:xml:ns:carddav'
ICAL_NS = 'http://apple.com/ns/ical/'
CALSERVER_NS = 'http://calendarserver.org/ns/'

# Register namespaces for proper XML output
register_namespace('D', DAV_NS)
register_namespace('C', CALDAV_NS)
register_namespace('CARD', CARDDAV_NS)
register_namespace('CS', CALSERVER_NS)


class AsyncExecutor:
    """Helper to run async functions in Flask (sync) context."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.loop = None
        self._setup_event_loop()
    
    def _setup_event_loop(self):
        """Set up event loop in background thread."""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        thread = Thread(target=run_loop, daemon=True)
        thread.start()
        
        # Wait for loop to be ready
        import time
        while self.loop is None:
            time.sleep(0.01)
    
    def run_async(self, coro):
        """Run async coroutine in background loop."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=30)


def create_app(config: Config) -> Flask:
    """Create Flask application with dependency injection."""
    app = Flask(__name__)
    app.config['CONFIG'] = config
    
    # Set up logging
    config.setup_logging()
    logger = logging.getLogger(__name__)
    
    # Initialize async executor
    async_executor = AsyncExecutor()
    
    # Initialize repositories and services
    kodbox_repo = KodBoxRepository(
        base_url=config.kodbox.base_url,
        access_token=config.kodbox.access_token,
        username=config.kodbox.username,
        password=config.kodbox.password
    )
    calendar_repo = CalendarRepository()
    
    data_sync_service = DataSyncService(
        project_repository=kodbox_repo,
        calendar_repository=calendar_repo,
        sync_interval=config.sync.interval_seconds
    )
    
    caldav_service = CalDAVService(
        data_sync_service=data_sync_service,
        calendar_repository=calendar_repo
    )
    
    # Start background synchronization
    def start_background_sync():
        """Start background data synchronization."""
        async def sync_loop():
            while True:
                try:
                    await data_sync_service.sync_all_data()
                    await asyncio.sleep(config.sync.interval_seconds)
                except Exception as e:
                    logger.error(f"Background sync failed: {e}")
                    await asyncio.sleep(config.sync.retry_delay_seconds)
        
        asyncio.run_coroutine_threadsafe(sync_loop(), async_executor.loop)
    
    # Initial sync and start background sync
    try:
        async_executor.run_async(data_sync_service.sync_all_data())
        start_background_sync()
        logger.info("Background data synchronization started")
    except Exception as e:
        logger.error(f"Failed to start data synchronization: {e}")
    
    # Authentication
    def check_auth(username: str, password: str) -> bool:
        """Check CalDAV authentication."""
        return (username == config.caldav.username and 
                password == config.caldav.password)
    
    def authenticate():
        """Send 401 authentication challenge."""
        return Response(
            'Authentication required',
            401,
            {'WWW-Authenticate': f'Basic realm="{config.caldav.realm}"'}
        )
    
    def requires_auth(f):
        """Authentication decorator."""
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password):
                return authenticate()
            return f(*args, **kwargs)
        return decorated
    
    # XML helpers
    def create_xml_response(root_element):
        """Create properly formatted XML response."""
        xml_str = tostring(root_element, encoding='unicode', xml_declaration=False)
        full_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
        
        return Response(
            full_xml,
            status=207,  # Multi-Status
            mimetype='application/xml; charset=utf-8',
            headers={
                'DAV': '1, 2, 3, calendar-access, calendar-schedule',
                'Cache-Control': 'max-age=300'
            }
        )
    
    def create_propfind_response(href: str, properties: dict, status_code: str = 'HTTP/1.1 200 OK'):
        """Create standardized PROPFIND response element."""
        response = Element('{DAV:}response')
        
        href_elem = SubElement(response, '{DAV:}href')
        href_elem.text = href
        
        propstat = SubElement(response, '{DAV:}propstat')
        prop = SubElement(propstat, '{DAV:}prop')
        
        # Add properties
        for prop_name, prop_value in properties.items():
            if isinstance(prop_value, Element):
                prop.append(prop_value)
            else:
                prop_elem = SubElement(prop, prop_name)
                if prop_value is not None:
                    prop_elem.text = str(prop_value)
        
        status = SubElement(propstat, '{DAV:}status')
        status.text = status_code
        
        return response
    
    def parse_depth_header() -> int:
        """Parse Depth header from request."""
        depth = request.headers.get('Depth', '0')
        if depth == 'infinity':
            return float('inf')
        try:
            return int(depth)
        except (ValueError, TypeError):
            return 0
    
    # Routes
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        last_sync = data_sync_service.get_last_sync_time()
        return jsonify({
            'status': 'healthy',
            'service': 'KodBox CalDAV Server',
            'version': '1.0.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'last_sync': last_sync.isoformat() if last_sync else None,
            'cache_fresh': data_sync_service.is_cache_fresh()
        })
    
    # CalDAV service discovery
    @app.route('/.well-known/caldav', methods=['GET', 'PROPFIND'])
    def caldav_discovery():
        """CalDAV service discovery."""
        return Response(status=301, headers={'Location': '/'})
    
    @app.route('/.well-known/carddav', methods=['GET', 'PROPFIND'])
    def carddav_discovery():
        """CardDAV service discovery."""
        return Response(status=301, headers={'Location': '/'})
    
    # OPTIONS handlers
    @app.route('/', methods=['OPTIONS'])
    @app.route('/calendars/', methods=['OPTIONS'])
    @app.route('/calendars/<project_id>/', methods=['OPTIONS'])
    @app.route('/principals/', methods=['OPTIONS'])
    @app.route('/principals/<username>/', methods=['OPTIONS'])
    def options_handler(**kwargs):
        """Universal OPTIONS handler."""
        response = Response()
        response.headers['Allow'] = 'OPTIONS, GET, HEAD, POST, PUT, DELETE, PROPFIND, PROPPATCH, MKCALENDAR, REPORT'
        response.headers['DAV'] = '1, 2, 3, calendar-access, calendar-schedule'
        response.headers['Content-Length'] = '0'
        return response
    
    # Root PROPFIND
    @app.route('/', methods=['PROPFIND'])
    @requires_auth
    def propfind_root():
        """Handle PROPFIND for root."""
        depth = parse_depth_header()
        multistatus = Element('{DAV:}multistatus')
        
        # Root collection properties
        resourcetype = Element('{DAV:}resourcetype')
        SubElement(resourcetype, '{DAV:}collection')
        
        cal_home_set = Element('{urn:ietf:params:xml:ns:caldav}calendar-home-set')
        cal_href = SubElement(cal_home_set, '{DAV:}href')
        cal_href.text = '/calendars/'
        
        current_user = Element('{DAV:}current-user-principal')
        user_href = SubElement(current_user, '{DAV:}href')
        user_href.text = f'/principals/{config.caldav.username}/'
        
        principal_set = Element('{DAV:}principal-collection-set')
        principal_href = SubElement(principal_set, '{DAV:}href')
        principal_href.text = '/principals/'
        
        root_props = {
            '{DAV:}resourcetype': resourcetype,
            '{DAV:}displayname': 'KodBox CalDAV Root',
            '{urn:ietf:params:xml:ns:caldav}calendar-home-set': cal_home_set,
            '{DAV:}current-user-principal': current_user,
            '{DAV:}principal-collection-set': principal_set
        }
        
        root_response = create_propfind_response('/', root_props)
        multistatus.append(root_response)
        
        # Include calendars collection if depth > 0
        if depth > 0:
            cal_resourcetype = Element('{DAV:}resourcetype')
            SubElement(cal_resourcetype, '{DAV:}collection')
            
            cal_props = {
                '{DAV:}resourcetype': cal_resourcetype,
                '{DAV:}displayname': 'Calendars'
            }
            
            cal_response = create_propfind_response('/calendars/', cal_props)
            multistatus.append(cal_response)
        
        return create_xml_response(multistatus)
    
    # Register CalDAV routes
    register_caldav_routes(
        app, caldav_service, async_executor, 
        create_xml_response, create_propfind_response, 
        parse_depth_header, requires_auth
    )
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return Response(status=404)
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return Response(status=500)
    
    return app