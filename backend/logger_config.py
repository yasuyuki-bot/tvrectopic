import logging
from logging.handlers import RotatingFileHandler
import sys
import os

def get_logger(name, log_filename=None, level=logging.INFO, max_bytes=5*1024*1024, backup_count=3):
    """
    Get a configured logger with standard formatting and optional file rotation.
    
    Args:
        name (str): Logger name (usually __name__)
        log_filename (str, optional): Filename for log output. If None, only logs to stdout.
        level (int): Logging level (e.g., logging.INFO, logging.DEBUG)
        max_bytes (int): Maximum size of log file before rotating
        backup_count (int): Number of old log files to keep
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s - %(process)d - %(processName)s - %(levelname)s - %(message)s')

    # Stream Handler (Console)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # File Handler (Rotating)
    if log_filename:
        # Standardize log directory to the backend root (parent of this file's dir if in utils)
        # Actually logger_config is in backend root now based on list_dir output
        dest_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(dest_dir, log_filename)
        
        try:
            fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as e:
            # Fallback to direct print if logging setup fails
            print(f"CRITICAL: Failed to setup file logging to {log_path}: {e}")
        
    return logger
