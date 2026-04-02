from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from src.services.task_store import task_store
from src.utils.security import is_safe_path
from src.config import config
import os
import psutil
import time
from datetime import datetime

router = APIRouter()

@router.get("/progress")
def get_progress(task_id: str):
    task_info = task_store.get_status(task_id)
    return {
        "status": task_info.get("status", "Starting..."), # Refactored to match new task_store keys
        "state": task_info.get("state", "running"),
        "error": task_info.get("error", None)
    }

@router.get("/health")
def health_check():
    process = psutil.Process(os.getpid())
    return {
        "status": "healthy",
        "uptime": time.time(), # Placeholder for actual start time if needed
        "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/download")
def download_file(file: str):
    base_dir = os.getcwd()
    if not is_safe_path(file, base_dir):
        raise HTTPException(status_code=403, detail="Access denied")
        
    file_path = os.path.abspath(os.path.join(base_dir, file))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(file_path, filename=os.path.basename(file_path))
