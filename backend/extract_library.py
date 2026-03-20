import os

player_py = r"c:\Users\rujas\Documents\GitHub\tvrectopic\backend\routers\player.py"
library_py = r"c:\Users\rujas\Documents\GitHub\tvrectopic\backend\routers\library.py"

with open(player_py, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if line.startswith("class FolderRequest"):
        start_idx = i
        break

for i in range(start_idx, len(lines)):
    if line.startswith("from .live_stream import live_manager") or line.startswith("try:\n    from ..live_stream"):
        pass # Not using these for end_idx anymore because it is modified
    
    # We want to end right before @player_router.post("/play") or the live_stream import if it exists.
    if "@player_router.post(\"/play\")" in lines[i]:
        # Backtrack to the live_stream import or keep it at i
        end_idx = i
        # Let's see if we see "from live_stream" before it
        for j in range(i-5, i):
            if "live_stream" in lines[j]:
                end_idx = j
                break
        break

if start_idx != -1 and end_idx != -1:
    extracted_lines = lines[start_idx:end_idx]
    
    header = """import os
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

try:
    from ..database import get_db, Program, SessionLocal, Channel, EPGProgram, ScheduledRecording
except (ImportError, ValueError):
    from database import get_db, Program, SessionLocal, Channel, EPGProgram, ScheduledRecording

logger = logging.getLogger(__name__)

library_router = APIRouter(prefix="/api", tags=["library"])

def load_settings():
    try:
        from ..settings_manager import load_settings as ls
    except (ImportError, ValueError):
        from settings_manager import load_settings as ls
    return ls()

"""
    
    with open(library_py, "w", encoding="utf-8") as f:
        f.write(header + "".join(extracted_lines))
        
    # Remove from player.py
    # also remove "library_router = APIRouter(prefix="/api", tags=["library"])" from player.py
    new_lines = []
    for i, line in enumerate(lines):
        if start_idx <= i < end_idx:
            continue
        if "library_router = APIRouter" in line:
            continue
        new_lines.append(line)
        
    with open(player_py, "w", encoding="utf-8") as f:
        f.write("".join(new_lines))
        
    logger.info(f"Extracted lines {start_idx} to {end_idx} from player.py to library.py")
else:
    logger.info("Could not find boundaries")
