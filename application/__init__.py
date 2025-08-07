"""Application services for KodBox CalDAV server."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from threading import RLock

from domain import Project, Task, Calendar, ProjectRepository, CalendarRepository


class DataSyncService:
    """Service for managing data synchronization with KodBox."""
    
    def __init__(
        self, 
        project_repository: ProjectRepository,
        calendar_repository: CalendarRepository,
        sync_interval: int = 300  # 5 minutes
    ):
        self.project_repository = project_repository
        self.calendar_repository = calendar_repository
        self.sync_interval = sync_interval
        self.logger = logging.getLogger(__name__)
        
        # Thread-safe cache
        self._cache_lock = RLock()
        self._projects_cache: Dict[str, Project] = {}
        self._calendars_cache: Dict[str, str] = {}
        self._last_sync: Optional[datetime] = None
        
    async def sync_all_data(self) -> None:
        """Synchronize all project and task data."""
        try:
            self.logger.info("Starting data synchronization...")
            
            # Fetch all projects
            projects = await self.project_repository.get_all_projects()
            
            new_projects = {}
            new_calendars = {}
            
            # Process each project (tasks are already included via get_all_projects)
            for project in projects:
                try:
                    # Tasks are already populated by get_all_projects(), no need to fetch separately
                    new_projects[project.id] = project
                    
                    # Generate calendar data
                    calendar_data = await self.calendar_repository.get_calendar_data(project)
                    new_calendars[project.id] = calendar_data
                    
                    self.logger.debug(f"Processed project {project.id} '{project.name}' with {len(project.tasks)} tasks")
                except Exception as e:
                    self.logger.warning(f"Failed to process project {project.id}: {e}")
                    # Still cache the project even if calendar generation failed
                    new_projects[project.id] = project
                    
                    # Generate empty calendar for failed projects
                    try:
                        calendar_data = await self.calendar_repository.get_calendar_data(project)
                        new_calendars[project.id] = calendar_data
                    except Exception as cal_e:
                        self.logger.warning(f"Failed to generate calendar for project {project.id}: {cal_e}")
            
            # Update cache atomically
            with self._cache_lock:
                self._projects_cache = new_projects
                self._calendars_cache = new_calendars
                self._last_sync = datetime.now(timezone.utc)
                
            self.logger.info(f"Data sync completed. {len(new_projects)} projects cached.")
            
        except Exception as e:
            self.logger.error(f"Data synchronization failed: {e}")
            raise
    
    def get_all_projects(self) -> List[Project]:
        """Get all cached projects."""
        with self._cache_lock:
            return list(self._projects_cache.values())
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID from cache."""
        with self._cache_lock:
            return self._projects_cache.get(project_id)
    
    def get_project_calendar(self, project_id: str) -> Optional[str]:
        """Get cached calendar data for project."""
        with self._cache_lock:
            return self._calendars_cache.get(project_id)
    
    def get_project_tasks(self, project_id: str) -> List[Task]:
        """Get tasks for a project."""
        project = self.get_project(project_id)
        # Return all tasks, not just active ones - CalDAV clients may want to see completed tasks too
        return project.tasks if project else []
    
    def get_task(self, project_id: str, task_id: str) -> Optional[Task]:
        """Get specific task from project."""
        project = self.get_project(project_id)
        if not project:
            return None
            
        for task in project.tasks:
            if task.id == task_id:
                return task
        return None
    
    def is_cache_fresh(self, max_age_minutes: int = 10) -> bool:
        """Check if cache is fresh."""
        if not self._last_sync:
            return False
        return datetime.now(timezone.utc) - self._last_sync < timedelta(minutes=max_age_minutes)
    
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get last synchronization time."""
        return self._last_sync


class CalDAVService:
    """Service for CalDAV protocol operations."""
    
    def __init__(
        self,
        data_sync_service: DataSyncService,
        calendar_repository: CalendarRepository
    ):
        self.data_sync = data_sync_service
        self.calendar_repository = calendar_repository
        self.logger = logging.getLogger(__name__)
    
    async def get_calendars(self) -> List[Calendar]:
        """Get all available calendars (projects)."""
        projects = self.data_sync.get_all_projects()
        
        calendars = []
        for project in projects:
            calendar = Calendar(
                id=project.id,
                name=project.name,
                description=project.description,
                project=project
            )
            calendars.append(calendar)
            
        return calendars
    
    async def get_calendar(self, calendar_id: str) -> Optional[Calendar]:
        """Get specific calendar by ID."""
        project = self.data_sync.get_project(calendar_id)
        if not project:
            return None
            
        return Calendar(
            id=project.id,
            name=project.name,
            description=project.description,
            project=project
        )
    
    async def get_calendar_events(self, calendar_id: str) -> List[Task]:
        """Get all events (tasks) in a calendar."""
        return self.data_sync.get_project_tasks(calendar_id)
    
    async def get_event(self, calendar_id: str, event_id: str) -> Optional[Task]:
        """Get specific event (task) from calendar."""
        return self.data_sync.get_task(calendar_id, event_id)
    
    async def get_calendar_data(self, calendar_id: str) -> Optional[str]:
        """Get iCalendar data for entire calendar."""
        return self.data_sync.get_project_calendar(calendar_id)
    
    async def get_event_data(self, calendar_id: str, event_id: str) -> Optional[str]:
        """Get iCalendar data for specific event."""
        project = self.data_sync.get_project(calendar_id)
        task = self.data_sync.get_task(calendar_id, event_id)
        
        if not project or not task:
            return None
            
        return await self.calendar_repository.get_task_calendar_data(task, project)
    
    def get_etag(self, calendar_id: str, event_id: Optional[str] = None) -> str:
        """Generate ETag for calendar or event."""
        if event_id:
            task = self.data_sync.get_task(calendar_id, event_id)
            if task and task.modified_at:
                return f'"{int(task.modified_at.timestamp())}"'
            return '"0"'
        else:
            project = self.data_sync.get_project(calendar_id)
            if project:
                # Calculate CTag based on the most recent task modification time
                latest_timestamp = 0
                
                # Check project modification time
                if project.modified_at:
                    latest_timestamp = max(latest_timestamp, int(project.modified_at.timestamp()))
                
                # Check all task modification times
                for task in project.tasks:
                    if task.modified_at:
                        latest_timestamp = max(latest_timestamp, int(task.modified_at.timestamp()))
                
                if latest_timestamp > 0:
                    return f'"{latest_timestamp}"'
                
                # Fallback: use current time if no timestamps available
                from datetime import datetime, timezone
                return f'"{int(datetime.now(timezone.utc).timestamp())}"'
            return '"0"'