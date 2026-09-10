from flask import Flask
from flask_login import LoginManager
import os
from sqlalchemy import inspect, text

from models.db import db

def migrate_database(app):
    with app.app_context():
        inspector = inspect(db.engine)
        
        if 'student' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('student')]
            new_columns = ['attendance_rate', 'financial_status', 'courses_count', 'service_requests_count']
            
            with db.engine.connect() as conn:
                for column in new_columns:
                    if column not in existing_columns:
                        column_type = 'REAL' if column in ['attendance_rate', 'gpa'] else 'INTEGER'
                        default_val = 'DEFAULT 0.0' if column in ['attendance_rate', 'gpa'] else 'DEFAULT 0'
                        sql = f'ALTER TABLE student ADD COLUMN {column} {column_type} {default_val}'
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                        except Exception as e:
                            print(f'Migration warning: {e}')

        if 'service_request' in inspector.get_table_names():
            sr_columns = [col['name'] for col in inspector.get_columns('service_request')]
            if 'description' not in sr_columns:
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE service_request ADD COLUMN description TEXT'))
                        conn.commit()
                except Exception as e:
                    print(f'Migration warning: {e}')

def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True,
                static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static'),
                static_url_path='/static')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    from models.db import init_db, User
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        migrate_database(app)
        
        roles = ['Administrator', 'Extension Officer', 'Faculty Lead', 'Institute Director', 'IT Infrastructure Lead']
        from auth.models import hash_password
        for role in roles:
            if not User.query.filter_by(role=role).first():
                user = User(
                    name=f'{role} User',
                    role=role,
                    email=f'{role.lower().replace(" ", ".")}@hist.edu.ly',
                    password_hash=hash_password('password123')
                )
                db.session.add(user)
        db.session.commit()
    
    from auth.views import auth_bp
    app.register_blueprint(auth_bp)
    
    from routes.main import main_bp
    app.register_blueprint(main_bp)
    
    from sync.scheduler import init_sync_scheduler
    init_sync_scheduler(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    return app

app = None

if __name__ == '__main__':
    app = create_app()
    if app:
        app.run(debug=True)