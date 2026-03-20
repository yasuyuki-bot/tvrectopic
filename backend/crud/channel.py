from typing import List
from sqlalchemy.orm import Session
import logging

try:
    from ..database import Channel
except ImportError:
    from database import Channel

logger = logging.getLogger(__name__)

def update_channel_config(db: Session, config: List[dict]):
    try:
        updated_count = 0
        for item in config:
            sid = item.get('service_id')
            nid = item.get('network_id')
            ctype = item.get('type')
            visible = item.get('visible', True)
            
            c = db.query(Channel).filter(
                Channel.sid == sid,
                Channel.network_id == nid,
                Channel.type == ctype
            ).first()
            
            if c:
                c.visible = visible
                updated_count += 1
            
        db.commit()
        return updated_count
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating channels: {e}")
        raise
