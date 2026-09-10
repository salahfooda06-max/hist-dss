from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()

class Student(db.Model):
    student_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    program = db.Column(db.String(100))
    gpa = db.Column(db.Float)
    status = db.Column(db.String(50))
    attendance_rate = db.Column(db.Float, default=0.0)
    financial_status = db.Column(db.Integer, default=0)
    courses_count = db.Column(db.Integer, default=0)
    service_requests_count = db.Column(db.Integer, default=0)

class AcademicRecord(db.Model):
    record_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    term = db.Column(db.String(50))
    courses = db.Column(db.Text)
    gpa_term = db.Column(db.Float)
    student = db.relationship('Student', backref='academic_records')

class ServiceRequest(db.Model):
    request_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    type = db.Column(db.String(50))
    description = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))
    student = db.relationship('Student', backref='service_requests')

class MLModel(db.Model):
    model_id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    version = db.Column(db.String(20))
    accuracy = db.Column(db.Float)
    precision = db.Column(db.Float)
    recall = db.Column(db.Float)
    f1 = db.Column(db.Float)
    trained_on = db.Column(db.DateTime, default=datetime.utcnow)

class Recommendation(db.Model):
    rec_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('service_request.request_id'), nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey('ml_model.model_id'), nullable=False)
    score = db.Column(db.Float)
    action = db.Column(db.String(200))
    feedback = db.Column(db.String(50))
    service_request = db.relationship('ServiceRequest', backref='recommendations')
    model = db.relationship('MLModel', backref='recommendations')

class User(UserMixin, db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    
    def get_id(self):
        return str(self.user_id)

class AuditLog(db.Model):
    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SyncQueue(db.Model):
    queue_id = db.Column(db.Integer, primary_key=True)
    payload = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    synced_at = db.Column(db.DateTime)

class AIRecommendation(db.Model):
    rec_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey('ml_model.model_id'), nullable=False)
    score = db.Column(db.Float)
    recommendation_text = db.Column(db.Text)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('Student', backref='ai_recommendations')
    model = db.relationship('MLModel', backref='ai_recommendations')