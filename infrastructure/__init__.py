"""Infrastructure implementations for KodBox CalDAV server."""

import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from icalendar import Calendar, Event
import uuid

from domain import Project, Task, ProjectRepository, CalendarRepository


class KodBoxRepository(ProjectRepository):
    """KodBox API implementation of ProjectRepository."""
    
    def __init__(self, base_url: str, access_token: str = "", username: str = "", password: str = ""):
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
        # Set up session headers for KodBox API
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
        
        # Store CSRF token for API calls
        self.csrf_token = None
        
        # 不再支持预置 access_token，始终通过用户名密码登录获取
        if username and password:
            try:
                self.logger.info("开始登录获取 access token...")
                self._login_and_get_token()
            except Exception as e:
                self.logger.error(f"登录失败: {e}")
                raise
        else:
            raise ValueError("Username and password are required for authentication")
    
    def _login_and_get_token(self):
        """Login with username/password to get access token and CSRF token."""
        try:
            # 使用官方文档的 API 端点格式获取 accessToken
            # 格式: http://server/?user/index/loginSubmit&name=[用户名]&password=[密码]
            login_url = f"{self.base_url}/?user/index/loginSubmit&name={self.username}&password={self.password}"
            
            self.logger.info(f"Attempting to login to KodBox with username: {self.username}")
            
            # 发送 GET 请求获取 accessToken (官方文档指定使用GET方法)
            response = self.session.get(login_url, timeout=30)
            response.raise_for_status()
            
            # 解析响应获取 accessToken
            data = response.json()
            
            if data.get('code') is True and 'info' in data:
                # 从 info 字段获取 accessToken
                self.access_token = data['info']
                
                # 从cookies中获取CSRF token (如果有的话)
                if 'CSRF_TOKEN' in response.cookies:
                    self.csrf_token = response.cookies['CSRF_TOKEN']
                    self.logger.info(f"Got CSRF token: {self.csrf_token}")
                
                self.logger.info(f"Successfully obtained access token from KodBox: {self.access_token[:20]}...")
                return True
            else:
                error_msg = f"Login failed - API response: {data}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.logger.error(f"Failed to get access token: {e}")
            raise
    
    async def get_all_projects(self) -> List[Project]:
        """Fetch all projects from KodBox API using POST with correct format."""
        try:
            url = f"{self.base_url}/index.php"
            
            # 使用POST方式调用API，根据你提供的真实请求格式
            post_data = {
                'API_ROUTE': 'plugin/project/taskListSelf'
            }
            
            # 如果有CSRF token，添加它
            if self.csrf_token:
                post_data['CSRF_TOKEN'] = self.csrf_token
            
            self.logger.debug(f"Making POST request to {url} with data: {post_data}")
            response = self.session.post(url, data=post_data, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('code') or 'data' not in data:
                self.logger.error(f"KodBox API error: {data}")
                return []
                
            # 解析真实的KodBox API响应结构
            api_data = data['data']
            tasks_data = api_data.get('task', {})
            projects_data = api_data.get('project', {})
            
            self.logger.info(f"Found {len(projects_data)} projects and {len(tasks_data)} tasks")
            
            projects_dict = {}
            
            # 首先处理项目数据
            for project_id, project_data in projects_data.items():
                projects_dict[project_id] = {
                    'id': project_id,
                    'name': project_data.get('name', f'项目 {project_id}'),
                    'description': project_data.get('desc', ''),
                    'tasks': [],
                    'raw_data': project_data
                }
            
            # 然后处理任务数据并分配到对应项目
            for task_id, task_data in tasks_data.items():
                project_id = task_data.get('projectID')
                if not project_id:
                    continue
                    
                # 如果项目不存在（可能数据不一致），创建临时项目
                if project_id not in projects_dict:
                    self.logger.warning(f"Task {task_id} belongs to unknown project {project_id}, creating temporary project")
                    projects_dict[project_id] = {
                        'id': project_id,
                        'name': f'项目 {project_id}',
                        'description': '',
                        'tasks': [],
                        'raw_data': {}
                    }
                
                # 将任务添加到对应项目
                try:
                    task = Task.from_kodbox_data(task_id, task_data, project_id)
                    projects_dict[project_id]['tasks'].append(task)
                except Exception as e:
                    self.logger.warning(f"Failed to parse task {task_id}: {e}")
                    continue
            
            # 转换为Project对象
            projects = []
            for project_id, project_info in projects_dict.items():
                # Extract timestamps from raw project data
                created_at = None
                modified_at = None
                raw_data = project_info.get('raw_data', {})
                
                if raw_data.get('createTime'):
                    try:
                        created_at = datetime.fromtimestamp(int(raw_data['createTime']))
                    except (ValueError, TypeError):
                        pass
                        
                if raw_data.get('modifyTime'):
                    try:
                        modified_at = datetime.fromtimestamp(int(raw_data['modifyTime']))
                    except (ValueError, TypeError):
                        pass
                
                project = Project(
                    id=project_id,
                    name=project_info['name'],
                    description=project_info['description'],
                    created_at=created_at,
                    modified_at=modified_at,
                    tasks=project_info['tasks']
                )
                projects.append(project)
                
            self.logger.info(f"Fetched {len(projects)} projects from KodBox")
            return projects
            
        except Exception as e:
            self.logger.error(f"Failed to fetch projects: {e}")
            raise
    
    async def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get specific project by ID."""
        projects = await self.get_all_projects()
        for project in projects:
            if project.id == project_id:
                return project
        return None
    
    async def get_project_tasks(self, project_id: str) -> List[Task]:
        """Get tasks for a specific project. 
        
        Note: Tasks are now fetched together with projects in get_all_projects(),
        so this method is mainly for consistency with the interface.
        """
        try:
            # 任务数据已经通过 taskListSelf API 获取，这里返回空列表
            # 实际的任务数据会通过 get_all_projects() 中的逻辑处理
            self.logger.debug(f"get_project_tasks called for project {project_id} - tasks are fetched via taskListSelf API")
            return []
            
        except Exception as e:
            self.logger.error(f"Failed in get_project_tasks for project {project_id}: {e}")
            return []


class CalendarRepository(CalendarRepository):
    """iCalendar implementation of CalendarRepository."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def get_calendar_data(self, project: Project) -> str:
        """Generate iCalendar data for entire project."""
        try:
            cal = Calendar()
            cal.add('prodid', '-//KodBox CalDAV Server//kodbox_caldav//EN')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            cal.add('x-wr-calname', project.name)
            
            if project.description:
                cal.add('x-wr-caldesc', project.description)
            
            # Add all tasks as events (including completed ones for CalDAV clients)
            for task in project.tasks:
                event = self._create_event_from_task(task, project)
                if event:
                    cal.add_component(event)
            
            return cal.to_ical().decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Failed to generate calendar for project {project.id}: {e}")
            raise
    
    async def get_task_calendar_data(self, task: Task, project: Project) -> str:
        """Generate iCalendar data for single task."""
        try:
            cal = Calendar()
            cal.add('prodid', '-//KodBox CalDAV Server//kodbox_caldav//EN')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            cal.add('x-wr-calname', f'{project.name} - {task.name}')
            
            event = self._create_event_from_task(task, project)
            if event:
                cal.add_component(event)
            
            return cal.to_ical().decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Failed to generate calendar for task {task.id}: {e}")
            raise
    
    def _create_event_from_task(self, task: Task, project: Project) -> Optional[Event]:
        """Create iCalendar event from task."""
        try:
            event = Event()
            
            # Basic event info
            event.add('uid', f'kodbox-task-{task.id}@kodbox.local')
            event.add('summary', task.name)
            
            # Description with task details
            description_parts = []
            if task.description:
                description_parts.append(task.description)
            
            description_parts.append(f"Project: {project.name}")
            
            if task.priority:
                priority_map = {
                    'very-low': '最低',
                    'low': '较低', 
                    'normal': '普通',
                    'hight': '紧急',
                    'very-hight': '非常紧急'
                }
                priority_name = priority_map.get(task.priority.value, task.priority.value)
                description_parts.append(f"优先级: {priority_name}")
            
            if task.status:
                status_map = {
                    'ready': '未开始',
                    'doing': '进行中',
                    'finished': '已完成',
                    'closed': '已关闭'
                }
                status_name = status_map.get(task.status.value, task.status.value)
                description_parts.append(f"状态: {status_name}")
            
            if task.tags:
                description_parts.append(f"标签: {', '.join(task.tags)}")
            
            event.add('description', '\\n'.join(description_parts))
            
            # Time information
            china_tz = timezone(timedelta(hours=8))
            
            # Check if this should be an all-day event
            if (task.start_time and not task.end_time) or (task.end_time and not task.start_time):
                # All-day event: only one of start_time or end_time is set
                event_date = (task.start_time or task.end_time).date()
                
                # For all-day events, use VALUE=DATE and end date should be next day
                from icalendar import vDatetime, vDate
                event.add('dtstart', vDate(event_date))
                event['dtstart'].params['VALUE'] = 'DATE'  # Explicitly mark as date-only
                
                # End date should be the day after for all-day events per RFC5545
                next_day = event_date + timedelta(days=1)
                event.add('dtend', vDate(next_day))
                event['dtend'].params['VALUE'] = 'DATE'  # Explicitly mark as date-only
                
                # Add additional properties that some clients require for all-day events
                event.add('transp', 'TRANSPARENT')  # Mark as free time (not busy)
                event.add('class', 'PUBLIC')  # Mark as public event
                event.add('status', 'CONFIRMED')  # Event status
                event.add('sequence', 0)  # Version number
            elif task.start_time and task.end_time:
                # Timed event: both start and end times are set
                event.add('dtstart', task.start_time.replace(tzinfo=china_tz))
                event.add('dtend', task.end_time.replace(tzinfo=china_tz))
                
                # Add standard properties for timed events
                event.add('transp', 'OPAQUE')  # Mark as busy time
                event.add('class', 'PUBLIC')   # Mark as public event
                event.add('status', 'CONFIRMED')  # Event status
                event.add('sequence', 0)  # Version number
            
            # Creation and modification times
            if task.created_at:
                event.add('created', task.created_at.replace(tzinfo=timezone.utc))
            
            if task.modified_at:
                event.add('last-modified', task.modified_at.replace(tzinfo=timezone.utc))
            
            # Always set dtstamp to current time
            event.add('dtstamp', datetime.now(timezone.utc))
            
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to create event for task {task.id}: {e}")
            return None