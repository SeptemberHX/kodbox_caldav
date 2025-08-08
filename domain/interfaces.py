"""Domain interfaces for the KodBox CalDAV server."""

from abc import ABC, abstractmethod
from typing import List, Optional

from .entities import Project, Task


class ProjectRepository(ABC):
    """Abstract repository for project data."""
    
    @abstractmethod
    async def get_all_projects(self) -> List[Project]:
        """Get all projects."""
        pass
    
    @abstractmethod
    async def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by ID."""
        pass
    
    @abstractmethod
    async def get_project_tasks(self, project_id: str) -> List[Task]:
        """Get tasks for a project."""
        pass


class CalendarRepository(ABC):
    """Abstract repository for calendar data."""
    
    @abstractmethod
    async def get_calendar_data(self, project: Project) -> str:
        """Generate iCalendar data for project."""
        pass
    
    @abstractmethod
    async def get_task_calendar_data(self, task: Task, project: Project) -> str:
        """Generate iCalendar data for a single task."""
        pass