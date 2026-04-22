from src.services.database import SessionLocal, DBTask, init_db
from datetime import datetime

class TaskStore:
    """
    An enterprise-grade task store using SQLAlchemy and SQLite.
    Optimized for thread-safe operations in FastAPI.
    """
    def __init__(self):
        pass

    def init(self):
        init_db()

    def set_status(self, task_id: str, status: str, error: str = None, domain: str = None):
        with SessionLocal() as db:
            task = db.query(DBTask).filter(DBTask.task_id == task_id).first()
            if not task:
                task = DBTask(task_id=task_id, domain=domain)
                db.add(task)
            
            task.status = status
            if error:
                task.state = "error"
                task.error = error
            elif "Completed" in status or "finished" in status:
                task.state = "completed"
            else:
                task.state = "running"
            
            task.updated_at = datetime.utcnow()
            db.commit()

    def get_status(self, task_id: str):
        with SessionLocal() as db:
            task = db.query(DBTask).filter(DBTask.task_id == task_id).first()
            if not task:
                return {"status": "running", "status_msg": "Initializing...", "state": "running"}
            return {
                "status": task.status,
                "status_msg": task.status, # Legacy compatibility
                "state": task.state,
                "error": task.error
            }

    def save_results(self, task_id: str, results: dict):
        with SessionLocal() as db:
            task = db.query(DBTask).filter(DBTask.task_id == task_id).first()
            if not task:
                task = DBTask(task_id=task_id)
                db.add(task)
            
            task.results_json = results
            task.state = "completed"
            task.status = "Completed"
            task.updated_at = datetime.utcnow()
            db.commit()

    def get_results(self, task_id: str):
        with SessionLocal() as db:
            task = db.query(DBTask).filter(DBTask.task_id == task_id).first()
            return task.results_json if task else None

task_store = TaskStore()
