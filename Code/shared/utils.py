# shared/utils.py

import threading

_log_handlers = []
_log_lock = threading.Lock()

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

def log(category, message):
    """
    Print the log to console and broadcast it to all registered log handlers.
    """
    formatted = f"[{category:<7}] {message}"
    print(formatted)
    
    # Broadcast to registered handlers
    with _log_lock:
        handlers = list(_log_handlers)
        
    for handler in handlers:
        try:
            handler(category, message)
        except Exception as e:
            # Prevent log handler failures from affecting the main execution flow
            print(f"[LOGGER] Error in log handler: {e}")
