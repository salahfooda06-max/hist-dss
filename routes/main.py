from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from auth.models import role_required, log_action
from ml.engine import train_and_compare_models, predict_risk, get_feature_importance, load_model, train_recommendation_model, predict_recommendation, generate_recommendation_text, load_recommendation_model
from sync.sync_service import check_connection, queue_for_sync, get_sync_status, sync_to_cloud, sync_all_local_data
from models.db import Student, ServiceRequest, Recommendation, MLModel, AuditLog, AIRecommendation, db
import pandas as pd
import os
import tempfile
from datetime import datetime

main_bp = Blueprint('main', __name__, template_folder='../templates')

@main_bp.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@main_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    log_action('View dashboard')
    sync_status = get_sync_status()
    students_count = Student.query.count()
    requests_count = ServiceRequest.query.count()
    recommendations_count = Recommendation.query.count()
    
    latest_model = MLModel.query.order_by(MLModel.trained_on.desc()).first()
    
    return render_template('dashboard.html',
        sync_status=sync_status,
        students_count=students_count,
        requests_count=requests_count,
        recommendations_count=recommendations_count,
        latest_model=latest_model)

@main_bp.route('/data-integration', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Extension Officer', 'Faculty Lead')
def data_integration():
    log_action('Access data integration')
    
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('No file was uploaded', 'danger')
            return redirect(url_for('main.data_integration'))
        
        df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_json(file)
        
        duplicates = df.duplicated().sum()
        missing = df.isnull().sum().to_dict()
        
        for _, row in df.iterrows():
            existing = Student.query.filter_by(
                student_id=row.get('student_id', row.get('id'))
            ).first()
            
            if not existing:
                student = Student(
                    student_id=row.get('student_id', row.get('id')),
                    name=row.get('name', row.get('student_name')),
                    program=row.get('program', row.get('major')),
                    gpa=row.get('gpa', 0.0),
                    status=row.get('status', 'active')
                )
                db.session.add(student)
            else:
                db.session.merge(existing)
        
        db.session.commit()
        
        if not check_connection():
            queue_for_sync(df.to_dict())
        
        flash(f'Data imported successfully. Duplicates found: {duplicates}', 'success')
        log_action(f'Imported {len(df)} records')
    
    return render_template('data_integration.html')

@main_bp.route('/predict', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Extension Officer', 'Faculty Lead')
def predict():
    log_action('Access predict page')

    students = Student.query.order_by(Student.name.asc()).all()
    students_data = {
        s.student_id: {
            'name': s.name,
            'gpa': s.gpa or 0.0,
            'courses_count': s.courses_count or 0,
            'service_requests_count': s.service_requests_count or 0,
            'financial_status': s.financial_status or 0,
            'attendance_rate': s.attendance_rate or 0.0
        } for s in students
    }

    if request.method == 'POST':
        data = {
            'gpa': float(request.form.get('gpa', 0)),
            'courses_count': int(request.form.get('courses_count', 0)),
            'service_requests_count': int(request.form.get('service_requests_count', 0)),
            'financial_status': int(request.form.get('financial_status', 0)),
            'attendance_rate': float(request.form.get('attendance_rate', 0))
        }

        try:
            predictions, probabilities = predict_risk(data)
            feature_importance = get_feature_importance()

            prob_arr = probabilities[0]
            probability = float(prob_arr[1]) if len(prob_arr) > 1 else float(prob_arr[0])

            if not check_connection():
                queue_for_sync({'prediction': data, 'result': predictions[0]})

            return render_template('predict.html',
                prediction=predictions[0],
                probability=probability,
                feature_importance=feature_importance,
                input_data=data,
                students=students,
                students_data_json=students_data)
        except Exception as e:
            flash(f'Prediction error: {str(e)}', 'error')

    return render_template('predict.html',
        feature_importance=get_feature_importance(),
        students=students,
        students_data_json=students_data)

@main_bp.route('/student-grid')
@login_required
def student_grid():
    log_action('View student grid')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Student.query
    if search:
        query = query.filter(
            db.or_(
                Student.name.contains(search),
                Student.student_id.contains(search),
                Student.program.contains(search)
            )
        )
    
    students_page = query.order_by(Student.student_id.asc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('student_grid.html', students=students_page.items, search=search, pagination=students_page)

@main_bp.route('/api/search-students')
@login_required
def api_search_students():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'students': []})
    
    students = Student.query.filter(
        db.or_(
            Student.name.contains(query),
            Student.student_id.contains(query),
            Student.program.contains(query)
        )
    ).limit(50).all()
    
    result = []
    for s in students:
        result.append({
            'student_id': s.student_id,
            'name': s.name,
            'program': s.program,
            'gpa': s.gpa,
            'status': s.status,
            'attendance_rate': s.attendance_rate,
            'financial_status': s.financial_status,
            'courses_count': s.courses_count,
            'service_requests_count': s.service_requests_count
        })
    
    return jsonify({'students': result})

@main_bp.route('/api/generate-recommendation/<int:student_id>', methods=['POST'])
@login_required
def api_generate_recommendation(student_id):
    student = Student.query.get_or_404(student_id)
    
    data = {
        'gpa': student.gpa or 0.0,
        'courses_count': student.courses_count or 0,
        'service_requests_count': student.service_requests_count or 0,
        'financial_status': student.financial_status or 0,
        'attendance_rate': student.attendance_rate or 0.0
    }
    
    try:
        risk_predictions, risk_probabilities = predict_risk(data)
        rec_predictions, rec_probabilities = predict_recommendation(data)
        
        risk_pred = int(risk_predictions[0])
        risk_prob = risk_probabilities[0]
        rec_pred = int(rec_predictions[0])
        rec_proba = rec_probabilities[0]
        
        recommendation_text = generate_recommendation_text(data, risk_pred, risk_prob, rec_pred, rec_proba)
        
        try:
            latest_model = MLModel.query.order_by(MLModel.trained_on.desc()).first()
            model_id = latest_model.model_id if latest_model else 1
            
            ai_rec = AIRecommendation(
                student_id=student_id,
                model_id=model_id,
                score=float(rec_proba[rec_pred]),
                recommendation_text=recommendation_text
            )
            db.session.add(ai_rec)
            db.session.commit()
        except:
            pass
        
        rec_levels = {0: "No intervention needed", 1: "Mild intervention", 2: "Medium intervention", 3: "Urgent intervention"}
        
        return jsonify({
            'success': True,
            'student_id': student_id,
            'student_name': student.name,
            'program': student.program,
            'gpa': student.gpa,
            'attendance_rate': student.attendance_rate,
            'financial_status': student.financial_status,
            'service_requests_count': student.service_requests_count,
            'risk_level': 'High Risk' if risk_pred == 1 else 'Low Risk',
            'risk_probability': float(risk_prob[1]) if len(risk_prob) > 1 else float(risk_prob[0]),
            'recommendation_level': rec_levels.get(rec_pred, 'Not specified'),
            'recommendation_score': float(max(rec_proba)),
            'recommendation_text': recommendation_text
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/predict-student/<int:student_id>', methods=['POST'])
@login_required
def api_predict_student(student_id):
    student = Student.query.get_or_404(student_id)

    data = {
        'gpa': student.gpa or 0.0,
        'courses_count': student.courses_count or 0,
        'service_requests_count': student.service_requests_count or 0,
        'financial_status': student.financial_status or 0,
        'attendance_rate': student.attendance_rate or 0.0
    }

    try:
        risk_predictions, risk_probabilities = predict_risk(data)

        risk_pred = int(risk_predictions[0])
        risk_prob = float(risk_probabilities[0][1]) if len(risk_probabilities[0]) > 1 else float(risk_probabilities[0][0])

        if not check_connection():
            queue_for_sync({'prediction_student': data, 'result': risk_pred})

        return jsonify({
            'success': True,
            'student_id': student_id,
            'student_name': student.name,
            'gpa': student.gpa,
            'attendance_rate': student.attendance_rate,
            'financial_status': student.financial_status,
            'risk_level': 'High Risk' if risk_pred == 1 else 'Low Risk',
            'risk_probability': risk_prob
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/service-requests', methods=['GET', 'POST'])
@login_required
def service_requests():
    log_action('Access service requests')

    students = Student.query.order_by(Student.name.asc()).all()
    requests = ServiceRequest.query.order_by(ServiceRequest.date.desc()).all()

    if request.method == 'POST':
        if current_user.role not in ['Administrator', 'Extension Officer', 'Faculty Lead']:
            flash('Access denied', 'error')
            return redirect(url_for('main.service_requests'))

        student_id = request.form.get('student_id')
        req_type = request.form.get('type')
        description = request.form.get('description')
        status = request.form.get('status', 'open')

        student = Student.query.get(student_id)
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('main.service_requests'))

        if not req_type:
            flash('Please select a request type', 'error')
            return redirect(url_for('main.service_requests'))

        new_request = ServiceRequest(
            student_id=student_id,
            type=req_type,
            description=description,
            status=status
        )
        db.session.add(new_request)
        student.service_requests_count = (student.service_requests_count or 0) + 1
        db.session.commit()

        log_action(f'Created service request for student: {student_id}')
        flash('Service request created successfully', 'success')
        return redirect(url_for('main.service_requests'))

    return render_template('service_requests.html', students=students, requests=requests)

@main_bp.route('/service-requests/delete/<int:request_id>', methods=['POST'])
@login_required
@role_required('Administrator', 'Extension Officer', 'Faculty Lead')
def delete_service_request(request_id):
    req = ServiceRequest.query.get_or_404(request_id)
    student = req.student
    db.session.delete(req)
    if student and student.service_requests_count and student.service_requests_count > 0:
        student.service_requests_count -= 1
    db.session.commit()
    log_action(f'Deleted service request: {request_id}')
    flash('Service request deleted', 'success')
    return redirect(url_for('main.service_requests'))

@main_bp.route('/recommendations')
@login_required
def recommendations():
    log_action('View recommendations')
    recommendations = AIRecommendation.query.order_by(AIRecommendation.generated_at.desc()).all()
    return render_template('recommendations.html', recommendations=recommendations, status_filter='all')

@main_bp.route('/reports')
@login_required
def reports():
    log_action('Access reports')
    return render_template('reports.html')

@main_bp.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    report_type = request.form.get('report_type', 'students')
    
    if report_type == 'students':
        data = Student.query.all()
        content = [['ID', 'Name', 'Program', 'GPA', 'Status']]
        for s in data:
            content.append([s.student_id, s.name, s.program, s.gpa, s.status])
    else:
        data = AIRecommendation.query.order_by(AIRecommendation.generated_at.desc()).all()
        content = [['ID', 'Student', 'Program', 'Score', 'Recommendation', 'Date']]
        for r in data:
            student_name = r.student.name if r.student else '-'
            program = r.student.program if r.student else '-'
            generated = r.generated_at.strftime('%Y-%m-%d %H:%M') if r.generated_at else '-'
            content.append([r.rec_id, student_name, program, r.score, r.recommendation_text or '-', generated])
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display
    
    def fix_arabic_text(text):
        if isinstance(text, str) and any('\u0600' <= c <= '\u06FF' for c in text):
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        return text
    
    arabic_font_path = 'C:\\Windows\\Fonts\\ARIALUNI.TTF'
    if os.path.exists(arabic_font_path):
        pdfmetrics.registerFont(TTFont('ArabicFont', arabic_font_path))
        font_name = 'ArabicFont'
    else:
        font_name = 'Helvetica'
    
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    doc = SimpleDocTemplate(tmp_file.name, pagesize=letter)
    
    fixed_content = [[fix_arabic_text(str(cell)) for cell in row] for row in content]
    table = Table(fixed_content)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT')
    ]))
    doc.build([table])
    
    log_action(f'Generated {report_type} report')
    return send_file(tmp_file.name, as_attachment=True, download_name=f'{report_type}_report.pdf')

@main_bp.route('/sync-status')
@login_required
@role_required('Administrator', 'IT Infrastructure Lead')
def sync_status():
    log_action('View sync status')
    status = get_sync_status()
    return render_template('sync_status.html', status=status)

@main_bp.route('/sync-now', methods=['POST'])
@login_required
@role_required('Administrator', 'IT Infrastructure Lead')
def sync_now():
    log_action('Manual sync triggered')
    try:
        success, message = sync_all_local_data()
        if success:
            flash(f'Sync completed: {message}', 'success')
        else:
            flash(f'Sync failed: {message}', 'warning')
    except Exception as e:
        flash(f'Error during sync: {str(e)}', 'danger')
    return redirect(url_for('main.sync_status'))

@main_bp.route('/api/sync', methods=['POST'])
def api_sync_receive():
    from sync.sync_service import decrypt_payload, receive_sync
    body = request.get_json(silent=True) or {}
    payload = body.get('data')
    if not payload:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    try:
        data = decrypt_payload(payload)
        receive_sync(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@main_bp.route('/audit')
@login_required
@role_required('Administrator', 'Institute Director')
def audit():
    log_action('View audit log')
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('audit.html', logs=logs)

@main_bp.route('/retrain', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def retrain():
    log_action('Initiate model retraining')
    
    if request.method == 'POST':
        results, model_id = train_and_compare_models()
        best_name = max(results, key=lambda k: results[k]['f1'])
        best_f1 = results[best_name]['f1']
        accuracy = results[best_name]['accuracy']
        flash(f'Model retrained successfully. Best model: {best_name} (Accuracy: {accuracy:.2f}, F1: {best_f1:.2f})', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('retrain.html')

@main_bp.route('/student/register', methods=['GET', 'POST'])
@login_required
@role_required('Administrator', 'Extension Officer', 'Faculty Lead')
def register_student():
    log_action('Access student registration')
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        program = request.form.get('program')
        gpa = float(request.form.get('gpa', 0))
        attendance_rate = float(request.form.get('attendance_rate', 0))
        financial_status = int(request.form.get('financial_status', 0))
        courses_count = int(request.form.get('courses_count', 0))
        service_requests_count = int(request.form.get('service_requests_count', 0))
        
        existing = Student.query.filter_by(student_id=student_id).first()
        if existing:
            flash('Student already exists', 'error')
            return redirect(url_for('main.register_student'))
        
        student = Student(
            student_id=student_id,
            name=name,
            program=program,
            gpa=gpa,
            attendance_rate=attendance_rate,
            financial_status=financial_status,
            courses_count=courses_count,
            service_requests_count=service_requests_count,
            status='active'
        )
        db.session.add(student)
        db.session.commit()
        
        log_action(f'Registered new student: {student_id}')
        flash(f'Student {name} registered successfully', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('register_student.html')