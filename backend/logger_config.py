import logging
from logging.handlers import RotatingFileHandler
import sys
import os

def get_logger(name, log_filename=None, level=logging.INFO, max_bytes=5*1024*1024, backup_count=3, configure_root=False):
    """
    Get a configured logger with standard formatting and optional file rotation.
    If configure_root is True, handlers are also added to the root logger.
    """
    if configure_root:
        logger = logging.getLogger()
    else:
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
        dest_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(dest_dir, log_filename)
        
        try:
            fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as e:
            print(f"CRITICAL: Failed to setup file logging to {log_path}: {e}")
        
    return logger
