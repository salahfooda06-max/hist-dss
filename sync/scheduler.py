from apscheduler.schedulers.background import BackgroundScheduler
from flask import has_app_context

scheduler = None
_app_ref = None

def _sync_job():
    """Job wrapper that runs sync_to_cloud within app context."""
    global _app_ref
    if not has_app_context():
        if _app_ref:
            with _app_ref.app_context():
                _run_sync()

def _run_sync():
    """Internal sync function."""
    from sync.sync_service import sync_all_local_data, check_connection
    if check_connection():
        try:
            sync_all_local_data()
        except Exception:
            pass

def init_sync_scheduler(app):
    global scheduler, _app_ref
    _app_ref = app
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=_sync_job,
        trigger='interval',
        seconds=30,
        id='sync_to_cloud',
        max_instances=1,
        misfire_grace_time=60,
        coalesce=True
    )
    scheduler.start()

def get_scheduler():
    return scheduler