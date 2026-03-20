from fastapi import APIRouter, HTTPException
import os
from typing import List
from ..database import get_db

router = APIRouter(prefix="/api/logs", tags=["logs"])

@router.get("/files", response_model=List[str])
def get_log_files():
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    files = []
    if os.path.exists(log_dir):
        for f in os.listdir(log_dir):
            if f.endswith(".log") and os.path.isfile(os.path.join(log_dir, f)):
                files.append(f)
    files.sort()
    return files

@router.get("/content", response_model=List[str])
def get_log_content(filename: str):
    # Basic security check to prevent directory traversal
    if not filename.endswith(".log") or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid log filename")
    
    log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)
    if not os.path.exists(log_path):
        return []
    
    try:
        # Read the file and reverse the lines so newest are first
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        lines.reverse()
        return [line.rstrip('\n') for line in lines]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
