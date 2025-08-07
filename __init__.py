"""
KodBox CalDAV Server

A modern CalDAV server implementation that bridges KodBox project management
data into standard CalDAV format for calendar clients.

Architecture:
- Domain Layer: Core business logic and entities
- Application Layer: Use cases and services  
- Infrastructure Layer: External integrations (KodBox API, persistence)
- Presentation Layer: HTTP/CalDAV protocol handlers
"""

from .domain import Project, Task, Calendar
from .application import CalDAVService, DataSyncService
from .infrastructure import KodBoxRepository, CalendarRepository
from .presentation import create_app

__version__ = "1.0.0"
__author__ = "KodBox CalDAV Team"
__description__ = "A CalDAV server that bridges KodBox project management data"

__all__ = [
    'Project', 'Task', 'Calendar',
    'CalDAVService', 'DataSyncService', 
    'KodBoxRepository', 'CalendarRepository',
    'create_app'
]