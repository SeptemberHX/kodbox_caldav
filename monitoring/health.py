"""Health monitoring for KodBox CalDAV Server."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from dataclasses import dataclass

from .exceptions import error_handler


@dataclass
class HealthStatus:
    """Health status information."""
    
    healthy: bool
    timestamp: datetime
    services: Dict[str, bool]
    last_error: Dict[str, Any] = None
    error_count: int = 0


class HealthChecker:
    """Health monitoring for the application."""
    
    def __init__(self, data_sync_service, kodbox_repo):
        self.data_sync_service = data_sync_service
        self.kodbox_repo = kodbox_repo
        self.logger = logging.getLogger(__name__)
    
    async def check_health(self) -> HealthStatus:
        """Perform comprehensive health check."""
        timestamp = datetime.now(timezone.utc)
        services = {}
        overall_healthy = True
        
        # Check data sync service
        try:
            last_sync = self.data_sync_service.get_last_sync_time()
            cache_fresh = self.data_sync_service.is_cache_fresh(max_age_minutes=15)
            services['data_sync'] = last_sync is not None and cache_fresh
        except Exception as e:
            services['data_sync'] = False
            error_handler.handle_error(e, "health_check:data_sync", reraise=False)
        
        # Check KodBox API connectivity
        try:
            # Simple connectivity test
            projects = await self.kodbox_repo.get_all_projects()
            services['kodbox_api'] = len(projects) >= 0  # Even 0 projects is a successful response
        except Exception as e:
            services['kodbox_api'] = False
            error_handler.handle_error(e, "health_check:kodbox_api", reraise=False)
        
        # Overall health
        overall_healthy = all(services.values())
        
        # Get latest error info
        error_stats = error_handler.get_error_stats()
        last_error = None
        if error_stats['last_errors']:
            # Get most recent error
            latest_key = max(error_stats['last_errors'].keys(), 
                           key=lambda k: error_stats['last_errors'][k]['timestamp'])
            last_error = error_stats['last_errors'][latest_key]
        
        return HealthStatus(
            healthy=overall_healthy,
            timestamp=timestamp,
            services=services,
            last_error=last_error,
            error_count=error_stats['total_errors']
        )
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for API responses."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            health_status = loop.run_until_complete(self.check_health())
        except Exception as e:
            error_handler.handle_error(e, "health_summary", reraise=False)
            return {
                'healthy': False,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': 'Health check failed'
            }
        
        return {
            'healthy': health_status.healthy,
            'timestamp': health_status.timestamp.isoformat(),
            'services': health_status.services,
            'last_error': health_status.last_error,
            'error_count': health_status.error_count
        }