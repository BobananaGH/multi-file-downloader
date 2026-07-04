# Code/shared/utils.py

import threading

_log_handlers = []
_log_lock = threading.Lock()

class LogLevel:
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40

CURRENT_LEVEL = LogLevel.INFO

def add_log_handler(handler):
    """
    Register a callback function to receive log events.
    The callback signature should be: callback(category, message)
    """
    with _log_lock:
        if handler not in _log_handlers:
            _log_handlers.append(handler)

def remove_log_handler(handler):
    """
    Remove a registered log callback.
    """
    with _log_lock:
        if handler in _log_handlers:
            _log_handlers.remove(handler)

def log(category, message, level=LogLevel.INFO):
    if level < CURRENT_LEVEL:
        return

    formatted = f"[{category:<7}] {message}"
    print(formatted)

    with _log_lock:
        handlers = list(_log_handlers)

    for handler in handlers:
        try:
            handler(category, message)
        except Exception as e:
            print(f"[LOGGER] Error in log handler: {e}")
