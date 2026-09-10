import bcrypt
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please login first', 'error')
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('Access denied', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_action(action):
    from models.db import AuditLog, db
    if current_user.is_authenticated:
        audit = AuditLog(
            user_id=current_user.user_id,
            action=action
        )
        db.session.add(audit)
        db.session.commit()