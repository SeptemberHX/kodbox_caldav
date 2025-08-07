"""CalDAV route handlers for KodBox CalDAV Server."""

from flask import request, Response
from xml.etree.ElementTree import Element, SubElement
import xml.etree.ElementTree as ET


def register_caldav_routes(app, caldav_service, async_executor, create_xml_response, create_propfind_response, parse_depth_header, requires_auth):
    """Register CalDAV protocol routes."""
    
    # Principals PROPFIND
    @app.route('/principals/', methods=['PROPFIND'])
    @requires_auth
    def propfind_principals():
        """Handle PROPFIND for principals collection."""
        depth = parse_depth_header()
        multistatus = Element('{DAV:}multistatus')
        
        # Principals collection
        resourcetype = Element('{DAV:}resourcetype')
        SubElement(resourcetype, '{DAV:}collection')
        
        principals_props = {
            '{DAV:}resourcetype': resourcetype,
            '{DAV:}displayname': 'Principals'
        }
        
        principals_response = create_propfind_response('/principals/', principals_props)
        multistatus.append(principals_response)
        
        # Include user principal if depth > 0
        if depth > 0:
            config = app.config['CONFIG']
            
            user_resourcetype = Element('{DAV:}resourcetype')
            SubElement(user_resourcetype, '{DAV:}principal')
            
            cal_home_set = Element('{urn:ietf:params:xml:ns:caldav}calendar-home-set')
            cal_href = SubElement(cal_home_set, '{DAV:}href')
            cal_href.text = '/calendars/'
            
            user_props = {
                '{DAV:}resourcetype': user_resourcetype,
                '{DAV:}displayname': config.caldav.username,
                '{urn:ietf:params:xml:ns:caldav}calendar-home-set': cal_home_set
            }
            
            user_response = create_propfind_response(f'/principals/{config.caldav.username}/', user_props)
            multistatus.append(user_response)
        
        return create_xml_response(multistatus)
    
    @app.route('/principals/<username>/', methods=['PROPFIND'])
    @requires_auth
    def propfind_user_principal(username):
        """Handle PROPFIND for specific user principal."""
        config = app.config['CONFIG']
        multistatus = Element('{DAV:}multistatus')
        
        resourcetype = Element('{DAV:}resourcetype')
        SubElement(resourcetype, '{DAV:}principal')
        
        cal_home_set = Element('{urn:ietf:params:xml:ns:caldav}calendar-home-set')
        cal_href = SubElement(cal_home_set, '{DAV:}href')
        cal_href.text = '/calendars/'
        
        user_props = {
            '{DAV:}resourcetype': resourcetype,
            '{DAV:}displayname': username,
            '{urn:ietf:params:xml:ns:caldav}calendar-home-set': cal_home_set
        }
        
        user_response = create_propfind_response(f'/principals/{username}/', user_props)
        multistatus.append(user_response)
        
        return create_xml_response(multistatus)
    
    # Calendars PROPFIND
    @app.route('/calendars/', methods=['PROPFIND'])
    @requires_auth
    def propfind_calendars():
        """Handle PROPFIND for calendars collection."""
        depth = parse_depth_header()
        multistatus = Element('{DAV:}multistatus')
        
        # Calendars collection
        resourcetype = Element('{DAV:}resourcetype')
        SubElement(resourcetype, '{DAV:}collection')
        
        calendars_props = {
            '{DAV:}resourcetype': resourcetype,
            '{DAV:}displayname': 'Calendars'
        }
        
        calendars_response = create_propfind_response('/calendars/', calendars_props)
        multistatus.append(calendars_response)
        
        # Include individual calendars if depth > 0
        if depth > 0:
            calendars = async_executor.run_async(caldav_service.get_calendars())
            
            for calendar in calendars:
                resourcetype = Element('{DAV:}resourcetype')
                SubElement(resourcetype, '{DAV:}collection')
                SubElement(resourcetype, '{urn:ietf:params:xml:ns:caldav}calendar')
                
                comp_set = Element('{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set')
                vevent_comp = SubElement(comp_set, '{urn:ietf:params:xml:ns:caldav}comp')
                vevent_comp.set('name', 'VEVENT')
                vtodo_comp = SubElement(comp_set, '{urn:ietf:params:xml:ns:caldav}comp')
                vtodo_comp.set('name', 'VTODO')
                
                calendar_props = {
                    '{DAV:}resourcetype': resourcetype,
                    '{DAV:}displayname': calendar.display_name,
                    '{urn:ietf:params:xml:ns:caldav}calendar-description': calendar.description or '',
                    '{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set': comp_set,
                    '{http://calendarserver.org/ns/}getctag': caldav_service.get_etag(calendar.id)
                }
                
                calendar_response = create_propfind_response(f'/calendars/{calendar.id}/', calendar_props)
                multistatus.append(calendar_response)
        
        return create_xml_response(multistatus)
    
    @app.route('/calendars/<project_id>/', methods=['PROPFIND'])
    @requires_auth
    def propfind_calendar(project_id):
        """Handle PROPFIND for specific calendar."""
        depth = parse_depth_header()
        
        calendar = async_executor.run_async(caldav_service.get_calendar(project_id))
        if not calendar:
            return Response(status=404)
        
        multistatus = Element('{DAV:}multistatus')
        
        # Calendar collection properties
        resourcetype = Element('{DAV:}resourcetype')
        SubElement(resourcetype, '{DAV:}collection')
        SubElement(resourcetype, '{urn:ietf:params:xml:ns:caldav}calendar')
        
        comp_set = Element('{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set')
        vevent_comp = SubElement(comp_set, '{urn:ietf:params:xml:ns:caldav}comp')
        vevent_comp.set('name', 'VEVENT')
        vtodo_comp = SubElement(comp_set, '{urn:ietf:params:xml:ns:caldav}comp')
        vtodo_comp.set('name', 'VTODO')
        
        calendar_props = {
            '{DAV:}resourcetype': resourcetype,
            '{DAV:}displayname': calendar.display_name,
            '{urn:ietf:params:xml:ns:caldav}calendar-description': calendar.description or '',
            '{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set': comp_set,
            '{http://calendarserver.org/ns/}getctag': caldav_service.get_etag(project_id)
        }
        
        calendar_response = create_propfind_response(f'/calendars/{project_id}/', calendar_props)
        multistatus.append(calendar_response)
        
        # Include calendar events if depth > 0
        if depth > 0:
            events = async_executor.run_async(caldav_service.get_calendar_events(project_id))
            
            for event in events:
                event_props = {
                    '{DAV:}displayname': event.name,
                    '{DAV:}getetag': caldav_service.get_etag(project_id, event.id),
                    '{DAV:}getcontenttype': 'text/calendar; component=vevent'
                }
                
                event_response = create_propfind_response(f'/calendars/{project_id}/{event.id}.ics', event_props)
                multistatus.append(event_response)
        
        return create_xml_response(multistatus)
    
    # REPORT handlers
    @app.route('/calendars/<project_id>/', methods=['REPORT'])
    @requires_auth
    def report_calendar(project_id):
        """Handle REPORT requests for calendar collections."""
        calendar = async_executor.run_async(caldav_service.get_calendar(project_id))
        if not calendar:
            return Response(status=404)
        
        try:
            if request.data:
                root = ET.fromstring(request.data)
                report_type = root.tag
            else:
                report_type = None
        except ET.ParseError:
            return Response(status=400)
        
        multistatus = Element('{DAV:}multistatus')
        
        if report_type == '{urn:ietf:params:xml:ns:caldav}calendar-multiget':
            # Handle calendar-multiget REPORT
            hrefs = []
            for href_elem in root.findall('.//{DAV:}href'):
                if href_elem.text:
                    hrefs.append(href_elem.text)
            
            for href in hrefs:
                if href.endswith('.ics'):
                    task_id = href.split('/')[-1].replace('.ics', '')
                    event_data = async_executor.run_async(caldav_service.get_event_data(project_id, task_id))
                    
                    if event_data:
                        event_props = {
                            '{DAV:}getetag': caldav_service.get_etag(project_id, task_id),
                            '{urn:ietf:params:xml:ns:caldav}calendar-data': event_data
                        }
                        
                        event_response = create_propfind_response(href, event_props)
                        multistatus.append(event_response)
        
        elif report_type == '{urn:ietf:params:xml:ns:caldav}calendar-query':
            # Handle calendar-query REPORT
            events = async_executor.run_async(caldav_service.get_calendar_events(project_id))
            
            for event in events:
                event_data = async_executor.run_async(caldav_service.get_event_data(project_id, event.id))
                
                if event_data:
                    href = f'/calendars/{project_id}/{event.id}.ics'
                    event_props = {
                        '{DAV:}getetag': caldav_service.get_etag(project_id, event.id),
                        '{urn:ietf:params:xml:ns:caldav}calendar-data': event_data
                    }
                    
                    event_response = create_propfind_response(href, event_props)
                    multistatus.append(event_response)
        
        else:
            return Response(status=400)
        
        return create_xml_response(multistatus)
    
    # Calendar data handlers
    @app.route('/calendars/<project_id>/<task_id>.ics', methods=['GET'])
    @requires_auth
    def get_calendar_event(project_id, task_id):
        """Get specific calendar event."""
        event_data = async_executor.run_async(caldav_service.get_event_data(project_id, task_id))
        
        if not event_data:
            return Response(status=404)
        
        return Response(
            event_data,
            mimetype='text/calendar; charset=utf-8',
            headers={
                'ETag': caldav_service.get_etag(project_id, task_id),
                'Cache-Control': 'max-age=300'
            }
        )
    
    @app.route('/calendars/<project_id>/calendar.ics', methods=['GET'])
    @requires_auth
    def get_full_calendar(project_id):
        """Get full calendar for project."""
        calendar_data = async_executor.run_async(caldav_service.get_calendar_data(project_id))
        
        if not calendar_data:
            return Response(status=404)
        
        return Response(
            calendar_data,
            mimetype='text/calendar; charset=utf-8',
            headers={
                'ETag': caldav_service.get_etag(project_id),
                'Cache-Control': 'max-age=300'
            }
        )