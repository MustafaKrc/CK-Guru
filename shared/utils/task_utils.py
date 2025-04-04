from typing import Optional

from celery import Task

def update_task_state(task: Task, state: str, status: str, progress: int, warning: Optional[str] = None):
    """Helper to update Celery task state."""
    meta = {'status': status, 'progress': progress}
    if warning:
        meta['warning'] = warning
    task.update_state(state=state, meta=meta)