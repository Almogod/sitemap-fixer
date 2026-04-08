from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from src.services.gsc_service import GSCService
from src.services.task_store import task_store
from src.config import config
import os

router = APIRouter(prefix="/gsc", tags=["GSC"])

@router.get("/check-credentials")
async def check_credentials():
    """Verify if GSC service account is available."""
    service = GSCService()
    return {"available": service.is_available(), "path": service.service_account_path}

@router.get("/download_report")
def download_indexing_report(task_id: str):
    """Download the generated Excel indexing report."""
    if ".." in task_id or "/" in task_id:
         raise HTTPException(status_code=400, detail="Invalid task_id")
         
    report_file = f"indexing_report_{task_id}.xlsx"
    file_path = os.path.join(os.getcwd(), report_file)
    
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "Report not found"})
        
    return FileResponse(file_path, filename=report_file)
