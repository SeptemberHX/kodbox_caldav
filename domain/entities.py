"""Domain entities for the KodBox CalDAV server."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from enum import Enum


class TaskStatus(Enum):
    """Task status enumeration."""
    READY = "ready"
    DOING = "doing" 
    FINISHED = "finished"
    CLOSED = "closed"


class TaskPriority(Enum):
    """Task priority enumeration."""
    VERY_LOW = "very-low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "hight"  # Keep original typo for compatibility
    VERY_HIGH = "very-hight"  # Keep original typo for compatibility


@dataclass
class Task:
    """Domain entity representing a task."""
    
    id: str
    name: str
    project_id: str
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    owner_id: Optional[str] = None
    tags: List[str] = None
    is_list: bool = False  # True for kanban board groups
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
    
    @property
    def is_kanban_group(self) -> bool:
        """Check if this task is a kanban board group."""
        return self.is_list
    
    @property
    def has_time_range(self) -> bool:
        """Check if task has a defined time range."""
        return self.start_time is not None or self.end_time is not None
    
    @classmethod
    def from_kodbox_data(cls, task_id: str, data: Dict[str, Any], project_id: str) -> 'Task':
        """Create Task instance from KodBox API data."""
        meta_info = data.get('metaInfo', {}) or {}
        
        # Handle time fields
        start_time = None
        end_time = None
        created_at = None
        modified_at = None
        
        if meta_info.get('timeFrom'):
            try:
                # KodBox timestamps are in UTC, convert to timezone-aware datetime
                start_time = datetime.fromtimestamp(int(meta_info['timeFrom']), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
                
        if meta_info.get('timeTo'):
            try:
                # KodBox timestamps are in UTC, convert to timezone-aware datetime
                end_time = datetime.fromtimestamp(int(meta_info['timeTo']), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        
        if data.get('createTime'):
            try:
                # KodBox timestamps are in UTC, convert to timezone-aware datetime
                created_at = datetime.fromtimestamp(int(data['createTime']), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
                
        if data.get('modifyTime'):
            try:
                # KodBox timestamps are in UTC, convert to timezone-aware datetime
                modified_at = datetime.fromtimestamp(int(data['modifyTime']), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        
        # If no time range but have created_at, use it as start_time
        if not start_time and not end_time and created_at:
            start_time = created_at
            
        # Parse status (from the real data format)
        status = None
        task_status = data.get('status')
        if task_status:
            # Map numeric status to our enum
            status_mapping = {
                '0': TaskStatus.READY,     # 未开始
                '1': TaskStatus.FINISHED,  # 已完成 
                '2': TaskStatus.DOING,     # 进行中
                '3': TaskStatus.CLOSED     # 已关闭
            }
            status = status_mapping.get(task_status)
                
        priority = None
        if meta_info.get('taskLevel'):
            try:
                priority = TaskPriority(meta_info['taskLevel'])
            except ValueError:
                pass
        
        # Parse tags from metaInfo (真实数据格式)
        tags = []
        if meta_info.get('tags'):
            # tags字段是字符串ID，需要从项目的tagList中查找名称
            tag_id = meta_info['tags']
            if tag_id:
                tags = [f"tag-{tag_id}"]  # 临时使用ID，稍后可以通过项目数据映射到实际名称
        
        return cls(
            id=task_id,
            name=data.get('name', 'Untitled Task'),
            project_id=project_id,
            description=data.get('desc'),
            status=status,
            priority=priority,
            start_time=start_time,
            end_time=end_time,
            created_at=created_at,
            modified_at=modified_at,
            owner_id=data.get('ownerUser'),
            tags=tags,
            is_list=data.get('isList') == '1'
        )


@dataclass
class Project:
    """Domain entity representing a project."""
    
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    owner_id: Optional[str] = None
    tasks: List[Task] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tasks is None:
            self.tasks = []
    
    @property
    def active_tasks(self) -> List[Task]:
        """Get non-kanban group tasks."""
        return [task for task in self.tasks if not task.is_kanban_group]
    
    @classmethod
    def from_kodbox_data(cls, project_id: str, data: Dict[str, Any]) -> 'Project':
        """Create Project instance from KodBox API data."""
        created_at = None
        modified_at = None
        
        if data.get('createTime'):
            try:
                # KodBox timestamps are in UTC, convert to timezone-aware datetime
                created_at = datetime.fromtimestamp(int(data['createTime']), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
                
        if data.get('modifyTime'):
            try:
                # KodBox timestamps are in UTC, convert to timezone-aware datetime
                modified_at = datetime.fromtimestamp(int(data['modifyTime']), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        
        return cls(
            id=project_id,
            name=data.get('name', 'Untitled Project'),
            description=data.get('desc'),
            created_at=created_at,
            modified_at=modified_at,
            owner_id=data.get('ownerUser')
        )


@dataclass
class Calendar:
    """Domain entity representing a calendar."""
    
    id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    project: Optional[Project] = None
    
    @property
    def display_name(self) -> str:
        """Get display name for calendar."""
        return self.name or f"Project {self.id}"