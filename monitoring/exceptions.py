"""Exception handling for KodBox CalDAV Server."""

import logging
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from functools import wraps
from dataclasses import dataclass
from enum import Enum


class ErrorCode(Enum):
    """Standard error codes for the application."""
    
    # Configuration errors
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING = "CONFIG_MISSING"
    
    # Authentication errors
    AUTH_FAILED = "AUTH_FAILED"
    AUTH_MISSING = "AUTH_MISSING"
    
    # KodBox API errors
    KODBOX_CONNECTION_ERROR = "KODBOX_CONNECTION_ERROR"
    KODBOX_AUTH_ERROR = "KODBOX_AUTH_ERROR"
    KODBOX_API_ERROR = "KODBOX_API_ERROR"
    KODBOX_TIMEOUT = "KODBOX_TIMEOUT"
    
    # Data processing errors
    DATA_PARSING_ERROR = "DATA_PARSING_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    
    # Calendar generation errors
    CALENDAR_GENERATION_ERROR = "CALENDAR_GENERATION_ERROR"
    
    # Internal errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ASYNC_ERROR = "ASYNC_ERROR"


class KodBoxCalDAVError(Exception):
    """Base exception for KodBox CalDAV Server."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/monitoring."""
        return {
            'error_code': self.error_code.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'cause': str(self.cause) if self.cause else None,
            'traceback': traceback.format_exc() if self.cause else None
        }


class ConfigurationError(KodBoxCalDAVError):
    """Configuration related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.CONFIG_INVALID, details)


class AuthenticationError(KodBoxCalDAVError):
    """Authentication related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_FAILED, details)


class KodBoxAPIError(KodBoxCalDAVError):
    """KodBox API related errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.KODBOX_API_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, cause)


class DataProcessingError(KodBoxCalDAVError):
    """Data processing related errors."""
    
    def __init__(
        self, 
        message: str,
        error_code: ErrorCode = ErrorCode.DATA_PARSING_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, error_code, details, cause)


class CalendarGenerationError(KodBoxCalDAVError):
    """Calendar generation related errors."""
    
    def __init__(
        self, 
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, ErrorCode.CALENDAR_GENERATION_ERROR, details, cause)


class ErrorHandler:
    """Centralized error handling and logging."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._error_counts = {}
        self._last_errors = {}
    
    def handle_error(
        self,
        error: Exception,
        context: str = "unknown",
        extra_details: Optional[Dict[str, Any]] = None
    ) -> KodBoxCalDAVError:
        """Handle and log an error, converting to KodBoxCalDAVError if needed."""
        
        # Convert to our custom exception type if needed
        if isinstance(error, KodBoxCalDAVError):
            kodbox_error = error
        else:
            kodbox_error = KodBoxCalDAVError(
                message=str(error),
                error_code=ErrorCode.INTERNAL_ERROR,
                details=extra_details or {},
                cause=error
            )
        
        # Add context to details
        kodbox_error.details['context'] = context
        if extra_details:
            kodbox_error.details.update(extra_details)
        
        # Track error statistics
        error_key = f"{context}:{kodbox_error.error_code.value}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        self._last_errors[error_key] = kodbox_error.to_dict()
        
        # Log the error
        if kodbox_error.error_code in [ErrorCode.INTERNAL_ERROR, ErrorCode.ASYNC_ERROR]:
            self.logger.error(
                f"[{context}] {kodbox_error.message}",
                extra={
                    'error_code': kodbox_error.error_code.value,
                    'details': kodbox_error.details,
                    'error_count': self._error_counts[error_key]
                },
                exc_info=kodbox_error.cause
            )
        else:
            self.logger.warning(
                f"[{context}] {kodbox_error.message}",
                extra={
                    'error_code': kodbox_error.error_code.value,
                    'details': kodbox_error.details,
                    'error_count': self._error_counts[error_key]
                }
            )
        
        return kodbox_error
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        return {
            'error_counts': self._error_counts.copy(),
            'last_errors': self._last_errors.copy(),
            'total_errors': sum(self._error_counts.values())
        }
    
    def reset_stats(self):
        """Reset error statistics."""
        self._error_counts.clear()
        self._last_errors.clear()


# Global error handler instance
error_handler = ErrorHandler()


def handle_exceptions(context: str = "unknown", reraise: bool = True):
    """Decorator for automatic exception handling."""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handled_error = error_handler.handle_error(e, context)
                if reraise:
                    raise handled_error
                return None
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                handled_error = error_handler.handle_error(e, context)
                if reraise:
                    raise handled_error
                return None
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return wrapper
    
    return decorator