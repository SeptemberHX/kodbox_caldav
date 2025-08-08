"""Configuration management for KodBox CalDAV Server."""

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse


@dataclass
class KodBoxConfig:
    """KodBox API configuration."""
    base_url: str
    access_token: str
    username: str = ""
    password: str = ""
    timeout: int = 30
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.base_url:
            raise ValueError("KodBox base_url is required")
        
        # 现在只要求用户名密码，不再要求预置 access_token
        if not (self.username and self.password):
            raise ValueError("Username and password are required for login")
        
        # Normalize URL
        self.base_url = self.base_url.rstrip('/')
        
        # Validate URL format
        try:
            parsed = urlparse(self.base_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid base_url format: {self.base_url}")
        except Exception as e:
            raise ValueError(f"Invalid base_url: {e}")


@dataclass
class CalDAVConfig:
    """CalDAV server configuration."""
    username: str = "kodbox"
    password: str = "calendar123"
    realm: str = "KodBox CalDAV Server"
    # Public subscription tokens for Outlook/webcal support
    public_tokens: str = ""  # Comma-separated list of tokens


@dataclass 
class ServerConfig:
    """HTTP server configuration."""
    host: str = "0.0.0.0"
    port: int = 5082
    debug: bool = False
    workers: int = 1


@dataclass
class SyncConfig:
    """Data synchronization configuration."""
    interval_seconds: int = 300  # 5 minutes
    max_retries: int = 3
    retry_delay_seconds: int = 60
    cache_max_age_minutes: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class Config:
    """Main application configuration."""
    kodbox: KodBoxConfig
    caldav: CalDAVConfig = field(default_factory=CalDAVConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables."""
        # KodBox configuration
        kodbox_config = KodBoxConfig(
            base_url=os.getenv('KODBOX_BASE_URL', ''),
            access_token='',  # 不预置 token，强制通过登录获取
            username=os.getenv('KODBOX_USERNAME', ''),
            password=os.getenv('KODBOX_PASSWORD', ''),
            timeout=int(os.getenv('KODBOX_TIMEOUT', '30'))
        )
        
        # CalDAV configuration
        caldav_config = CalDAVConfig(
            username=os.getenv('CALDAV_USERNAME', 'kodbox'),
            password=os.getenv('CALDAV_PASSWORD', 'calendar123'),
            realm=os.getenv('CALDAV_REALM', 'KodBox CalDAV Server'),
            public_tokens=os.getenv('CALDAV_PUBLIC_TOKENS', '')
        )
        
        # Server configuration
        server_config = ServerConfig(
            host=os.getenv('SERVER_HOST', '0.0.0.0'),
            port=int(os.getenv('SERVER_PORT', '5082')),
            debug=os.getenv('SERVER_DEBUG', '').lower() in ('true', '1', 'yes'),
            workers=int(os.getenv('SERVER_WORKERS', '1'))
        )
        
        # Sync configuration
        sync_config = SyncConfig(
            interval_seconds=int(os.getenv('SYNC_INTERVAL', '300')),
            max_retries=int(os.getenv('SYNC_MAX_RETRIES', '3')),
            retry_delay_seconds=int(os.getenv('SYNC_RETRY_DELAY', '60')),
            cache_max_age_minutes=int(os.getenv('SYNC_CACHE_MAX_AGE', '10'))
        )
        
        # Logging configuration
        logging_config = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'DEBUG').upper(),
            format=os.getenv('LOG_FORMAT', LoggingConfig.format),
            file_path=os.getenv('LOG_FILE'),
            max_bytes=int(os.getenv('LOG_MAX_BYTES', str(LoggingConfig.max_bytes))),
            backup_count=int(os.getenv('LOG_BACKUP_COUNT', str(LoggingConfig.backup_count)))
        )
        
        return cls(
            kodbox=kodbox_config,
            caldav=caldav_config,
            server=server_config,
            sync=sync_config,
            logging=logging_config
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'Config':
        """Create configuration from JSON file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # KodBox configuration
            kodbox_data = data.get('kodbox', {})
            kodbox_config = KodBoxConfig(
                base_url=kodbox_data.get('base_url', ''),
                access_token='',  # 不预置 token，强制通过登录获取
                username=kodbox_data.get('username', ''),
                password=kodbox_data.get('password', ''),
                timeout=kodbox_data.get('timeout', 30)
            )
            
            # CalDAV configuration
            caldav_data = data.get('caldav', {})
            caldav_config = CalDAVConfig(
                username=caldav_data.get('username', 'kodbox'),
                password=caldav_data.get('password', 'calendar123'),
                realm=caldav_data.get('realm', 'KodBox CalDAV Server'),
                public_tokens=caldav_data.get('public_tokens', '')
            )
            
            # Server configuration
            server_data = data.get('server', {})
            server_config = ServerConfig(
                host=server_data.get('host', '0.0.0.0'),
                port=server_data.get('port', 5082),
                debug=server_data.get('debug', False),
                workers=server_data.get('workers', 1)
            )
            
            # Sync configuration
            sync_data = data.get('sync', {})
            sync_config = SyncConfig(
                interval_seconds=sync_data.get('interval_seconds', 300),
                max_retries=sync_data.get('max_retries', 3),
                retry_delay_seconds=sync_data.get('retry_delay_seconds', 60),
                cache_max_age_minutes=sync_data.get('cache_max_age_minutes', 10)
            )
            
            # Logging configuration
            logging_data = data.get('logging', {})
            logging_config = LoggingConfig(
                level=logging_data.get('level', 'INFO').upper(),
                format=logging_data.get('format', LoggingConfig.format),
                file_path=logging_data.get('file_path'),
                max_bytes=logging_data.get('max_bytes', LoggingConfig.max_bytes),
                backup_count=logging_data.get('backup_count', LoggingConfig.backup_count)
            )
            
            return cls(
                kodbox=kodbox_config,
                caldav=caldav_config,
                server=server_config,
                sync=sync_config,
                logging=logging_config
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Invalid configuration file format: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'kodbox': {
                'base_url': self.kodbox.base_url,
                'access_token': self.kodbox.access_token,
                'username': self.kodbox.username,
                'password': self.kodbox.password,
                'timeout': self.kodbox.timeout
            },
            'caldav': {
                'username': self.caldav.username,
                'password': self.caldav.password,
                'realm': self.caldav.realm,
                'public_tokens': self.caldav.public_tokens
            },
            'server': {
                'host': self.server.host,
                'port': self.server.port,
                'debug': self.server.debug,
                'workers': self.server.workers
            },
            'sync': {
                'interval_seconds': self.sync.interval_seconds,
                'max_retries': self.sync.max_retries,
                'retry_delay_seconds': self.sync.retry_delay_seconds,
                'cache_max_age_minutes': self.sync.cache_max_age_minutes
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'file_path': self.logging.file_path,
                'max_bytes': self.logging.max_bytes,
                'backup_count': self.logging.backup_count
            }
        }
    
    def setup_logging(self) -> None:
        """Configure logging based on configuration."""
        log_level = getattr(logging, self.logging.level, logging.INFO)
        
        # Create formatters
        formatter = logging.Formatter(self.logging.format)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler if specified
        if self.logging.file_path:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                self.logging.file_path,
                maxBytes=self.logging.max_bytes,
                backupCount=self.logging.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)


def load_config() -> Config:
    """Load configuration from file or environment variables."""
    # Try to load from config file first
    config_files = [
        'config.json',
        'config/config.json',
        '/etc/kodbox-caldav/config.json'
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                return Config.from_file(config_file)
            except Exception as e:
                logging.warning(f"Failed to load config from {config_file}: {e}")
    
    # Fall back to environment variables
    return Config.from_env()
