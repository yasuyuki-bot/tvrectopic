import logging
logger = logging.getLogger(__name__)
try:
    from ..database import SessionLocal, Program, Topic
    from .gemini_client import GeminiClient
    from .video import convert_ts_to_mp4_and_delete
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from database import SessionLocal, Program, Topic
    from extract_modules.gemini_client import GeminiClient
    from extract_modules.video import convert_ts_to_mp4_and_delete

def process_topic_batch(batch_data, custom_prompt=None, model_name=None, api_key=None):
    if not batch_data:
        return
        
    logger.info(f"Processing topic batch for {len(batch_data)} files...")
    client = GeminiClient(api_key=api_key, model_name=model_name or "gemini-2.5-flash")
    results = client.segment_batch(batch_data, custom_prompt)
    
    session = SessionLocal()
    try:
        for filepath, topics_list in results.items():
            prog = session.query(Program).filter(Program.filepath == filepath).first()
            if not prog:
                continue
            
            for t in topics_list:
                new_topic = Topic(
                    program_id=prog.id,
                    start_time=t.get('start'),
                    end_time=t.get('end'),
                    title=t.get('title')
                )
                session.add(new_topic)
        session.commit()
        
        try:
            from ..settings_manager import load_settings
        except (ImportError, ValueError):
            from settings_manager import load_settings
        settings = load_settings()
        
        if settings.get("auto_mp4_convert"):
             logger.info("Auto MP4 Conversion triggered.")
             opts = settings.get("mp4_convert_options", "-c:v libx264 -preset fast -crf 23 -c:a aac")
             delete_ts = settings.get("delete_ts_after_convert", False)
             
             for filepath in results.keys():
                 convert_ts_to_mp4_and_delete(filepath, options=opts, delete_original=delete_ts)
            
    except Exception as e:
        logger.error(f"Error saving topics: {e}")
        session.rollback()
    finally:
        session.close()
