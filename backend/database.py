import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, event
from datetime import datetime
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

logger = logging.getLogger(__name__)

Base = declarative_base()

class Channel(Base):
    __tablename__ = 'channels'

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True)
    channel_id = Column(String, unique=True, index=True)
    tsid = Column(Integer, nullable=True)
    network_id = Column(Integer, nullable=True)
    sid = Column(Integer, nullable=True)
    service_name = Column(String)
    TP = Column(String, nullable=True)
    slot = Column(Integer, nullable=True)
    visible = Column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "channel_id": self.channel_id,
            "tsid": self.tsid,
            "network_id": self.network_id,
            "sid": self.sid,
            "service_name": self.service_name,
            "TP": self.TP,
            "slot": self.slot,
            "visible": self.visible
        }

class Program(Base):
    __tablename__ = 'programs'
    
    id = Column(Integer, primary_key=True)
    filepath = Column(String, unique=True, index=True)
    title = Column(String)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime)
    channel = Column(String, index=True)
    description = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    subtitle_status = Column(Integer, default=0) # 0: Unknown, 1: Extracted, 2: No Subtitles

    topics = relationship("Topic", back_populates="program", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "filepath": self.filepath,
            "title": self.title,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "channel": self.channel,
            "description": self.description,
            "duration": self.duration,
            "subtitle_status": self.subtitle_status,
            "topics": [t.to_dict() for t in self.topics]
        }

class Topic(Base):
    __tablename__ = 'topics'
    
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey('programs.id'), nullable=False, index=True)
    start_time = Column(String)
    end_time = Column(String)
    title = Column(String)
    
    program = relationship("Program", back_populates="topics")

    def to_dict(self):
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "title": self.title
        }

class AutoReservation(Base):
    __tablename__ = 'auto_reservations'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    keyword = Column(String, nullable=True) 
    days_of_week = Column(String, default="0,1,2,3,4,5,6") 
    genres = Column(String, nullable=True) 
    types = Column(String, default="GR,BS,CS")
    channels = Column(String, nullable=True) 
    time_range_start = Column(String, nullable=True) 
    time_range_end = Column(String, nullable=True) 
    recording_folder = Column(String, nullable=True)
    search_target = Column(String, default="title") # "title" or "title_and_description"
    active = Column(Boolean, default=True)
    allow_duplicates = Column(Boolean, default=True)
    priority = Column(Integer, default=5) # 1: Highest, larger = lower
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "keyword": self.keyword,
            "days_of_week": self.days_of_week,
            "genres": self.genres,
            "types": self.types,
            "channels": self.channels,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "recording_folder": self.recording_folder,
            "search_target": self.search_target,
            "active": self.active,
            "allow_duplicates": self.allow_duplicates,
            "priority": self.priority
        }

class EPGProgram(Base):
    __tablename__ = 'epg_programs'
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    duration = Column(Integer)
    title = Column(String)
    description = Column(String)
    channel = Column(String, index=True) # Channel.channel_id value (e.g. "CS_296", "24")
    genre_major = Column(String, nullable=True, index=True)
    genre_minor = Column(String, nullable=True)
    
    channel_info = relationship('Channel', primaryjoin='foreign(EPGProgram.channel) == Channel.channel_id', uselist=False, backref='epg_programs')

    @property
    def service_id(self):
        return self.channel_info.sid if self.channel_info else 0

    @property
    def network_id(self):
        return self.channel_info.network_id if self.channel_info else 0

    @property
    def tsid(self):
        return self.channel_info.tsid if self.channel_info else 0

    @property
    def service_name(self):
        return self.channel_info.service_name if self.channel_info else ""
        
    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "title": self.title,
            "description": self.description,
            "channel": self.channel,
            "genre_major": self.genre_major,
            "genre_minor": self.genre_minor,
            "service_id": self.service_id,
            "network_id": self.network_id,
            "tsid": self.tsid,
            "service_name": self.service_name
        }

class ScheduledRecording(Base):
    __tablename__ = 'scheduled_recordings'

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, nullable=True, index=True) # Link to EPGProgram.id if available (not foreign key to allow flexibility)
    event_id = Column(Integer, nullable=True, index=True)
    service_id = Column(Integer, nullable=True, index=True)
    network_id = Column(Integer, nullable=True)
    
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    
    title = Column(String)
    description = Column(String)
    channel = Column(String, index=True) # Channel.channel_id value
    service_name = Column(String)
    
    status = Column(String, default="scheduled", index=True) # scheduled, recording, completed, failed, cancelled
    skip_reason = Column(String, nullable=True, index=True) # duplicate, conflict
    
    result_path = Column(String, nullable=True)
    recording_folder = Column(String, nullable=True)
    auto_reservation_id = Column(Integer, nullable=True, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "program_id": self.program_id,
            "event_id": self.event_id,
            "service_id": self.service_id,
            "network_id": self.network_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "title": self.title,
            "channel": self.channel,
            "service_name": self.service_name,
            "status": self.status,
            "skip_reason": self.skip_reason,
            "result_path": self.result_path,
            "recording_folder": self.recording_folder,
            "auto_reservation_id": self.auto_reservation_id
        }

class ResumePosition(Base):
    __tablename__ = 'resume_positions'
    
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey('programs.id'), nullable=False, unique=True, index=True)
    position = Column(Integer, nullable=False) # seconds
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    program = relationship("Program")

    def to_dict(self):
        return {
            "id": self.id,
            "program_id": self.program_id,
            "position": self.position,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# Database Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.abspath(os.path.join(BASE_DIR, '..', 'schedule.db'))}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 60})

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=60000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    apply_indices_automatically()

def apply_indices_automatically():
    """
    Checks for the existence of indices and adds them if missing for existing databases.
    This ensures Phase 3 performance benefits apply to existing users automatically.
    """
    indices_to_add = [
        ("ix_topics_program_id", "topics", "program_id"),
        ("ix_epg_programs_event_id", "epg_programs", "event_id"),
        ("ix_epg_programs_genre_major", "epg_programs", "genre_major"),
        ("ix_scheduled_recordings_program_id", "scheduled_recordings", "program_id"),
        ("ix_scheduled_recordings_event_id", "scheduled_recordings", "event_id"),
        ("ix_scheduled_recordings_service_id", "scheduled_recordings", "service_id"),
        ("ix_scheduled_recordings_start_time", "scheduled_recordings", "start_time"),
        ("ix_scheduled_recordings_channel", "scheduled_recordings", "channel"),
        ("ix_scheduled_recordings_status", "scheduled_recordings", "status"),
        ("ix_scheduled_recordings_skip_reason", "scheduled_recordings", "skip_reason"),
        ("ix_scheduled_recordings_auto_reservation_id", "scheduled_recordings", "auto_reservation_id"),
    ]
    
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            for idx_name, table_name, column_name in indices_to_add:
                # Check if index exists by querying sqlite_master
                query = text("SELECT name FROM sqlite_master WHERE type='index' AND name=:idx_name")
                res = conn.execute(query, {"idx_name": idx_name}).fetchone()
                
                if not res:
                    try:
                        # Add missing index
                        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({column_name})"))
                        conn.commit()
                    except Exception as ie:
                        # Log but continue
                        pass
            
            # Check for missing columns (e.g. priority in auto_reservations)
            try:
                # auto_reservations.priority
                query = text("PRAGMA table_info(auto_reservations)")
                cols = conn.execute(query).fetchall()
                col_names = [c[1] for c in cols]
                if "priority" not in col_names:
                    logger.info("Adding missing column 'priority' to 'auto_reservations' table")
                    conn.execute(text("ALTER TABLE auto_reservations ADD COLUMN priority INTEGER DEFAULT 5"))
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to add columns: {e}")

            # Ensure resume_positions table exists (Base.metadata.create_all handles it usually, 
            # but sometimes explicit check is safer in these custom migrations)
            try:
                # Handled by Base.metadata.create_all(bind=engine) in init_db()
                pass
            except: pass

    except Exception as e:
        # DB might be locked or other issue, log it
        logger.error(f"Automatic Index Application failed: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
