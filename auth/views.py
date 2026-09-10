from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from models.db import User, db
from auth.models import hash_password, check_password
from datetime import datetime

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password(password, user.password_hash):
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            from auth.models import log_action
            log_action('User login')
            return redirect(url_for('main.dashboard'))
        
        flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    from auth.models import log_action
    log_action('User logout')
    logout_user()
    return redirect(url_for('auth.login'))