from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from models.db import User, db
from auth.models import hash_password, check_password, role_required
from datetime import datetime

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password(password, user.password_hash):
            if not user.is_active:
                flash('Your account is not activated. Please contact the administrator.', 'warning')
                return render_template('login.html')
            
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

@auth_bp.route('/users')
@login_required
@role_required('Administrator', 'Institute Director')
def users():
    from auth.models import log_action
    log_action('View user management')
    users = User.query.order_by(User.user_id.desc()).all()
    return render_template('users.html', users=users)

@auth_bp.route('/users/register', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def register_user():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not name or not role or not email or not password:
            flash('All fields are required', 'danger')
            return redirect(url_for('auth.register_user'))
        
        if User.query.filter_by(email=email).first():
            flash(f'User with email {email} already exists', 'danger')
            return redirect(url_for('auth.register_user'))
        
        user = User(
            name=name,
            role=role,
            email=email,
            password_hash=hash_password(password),
            is_active=False
        )
        db.session.add(user)
        db.session.commit()
        
        from auth.models import log_action
        log_action(f'Created new user: {name} ({role})')
        flash(f'User "{name}" registered successfully. Account is pending activation.', 'success')
        return redirect(url_for('auth.users'))
    
    return render_template('register_user.html')

@auth_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        name = request.form.get('name', user.name).strip()
        role = request.form.get('role', user.role).strip()
        email = request.form.get('email', user.email).strip()
        password = request.form.get('password', '').strip()
        
        if name:
            user.name = name
        if role:
            user.role = role
        if email and email != user.email:
            if User.query.filter_by(email=email).first() and User.query.filter_by(email=email).first().user_id != user.user_id:
                flash('Another user with this email already exists', 'danger')
                return redirect(url_for('auth.edit_user', user_id=user_id))
            user.email = email
        if password:
            user.password_hash = hash_password(password)
        
        db.session.commit()
        
        from auth.models import log_action
        log_action(f'Updated user: {user.name}')
        flash(f'User "{user.name}" updated successfully', 'success')
        return redirect(url_for('auth.users'))
    
    return render_template('edit_user.html', user=user)

@auth_bp.route('/users/toggle/<int:user_id>', methods=['POST'])
@login_required
@role_required('Administrator')
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.role == 'Administrator' and not user.is_active:
        flash('Cannot deactivate an Administrator account', 'danger')
        return redirect(url_for('auth.users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    from auth.models import log_action
    status = 'activated' if user.is_active else 'deactivated'
    log_action(f'User {status}: {user.name}')
    flash(f'User "{user.name}" {status} successfully', 'success')
    return redirect(url_for('auth.users'))

@auth_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('Administrator')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.role == 'Administrator':
        flash('Cannot delete an Administrator account', 'danger')
        return redirect(url_for('auth.users'))
    
    from auth.models import log_action
    log_action(f'Deleted user: {user.name}')
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User "{user.name}" deleted successfully', 'success')
    return redirect(url_for('auth.users'))
