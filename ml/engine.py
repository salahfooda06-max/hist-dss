import os
import joblib
from datetime import datetime
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np

MODEL_DIR = 'instance/models'
LOCAL_MODEL_DIR = 'instance/local_models'
RECOMMENDATION_MODEL_DIR = 'instance/recommendation_models'
LOCAL_RECOMMENDATION_MODEL_DIR = 'instance/local_recommendation_models'

def ensure_model_dirs():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    os.makedirs(RECOMMENDATION_MODEL_DIR, exist_ok=True)
    os.makedirs(LOCAL_RECOMMENDATION_MODEL_DIR, exist_ok=True)

ensure_model_dirs()

def generate_synthetic_data(n_samples=1000):
    np.random.seed(42)
    data = {
        'gpa': np.random.uniform(0, 4.0, n_samples),
        'courses_count': np.random.randint(1, 8, n_samples),
        'service_requests_count': np.random.randint(0, 10, n_samples),
        'financial_status': np.random.choice([0, 1], n_samples, p=[0.3, 0.7]),
        'attendance_rate': np.random.uniform(0.5, 1.0, n_samples),
    }
    df = pd.DataFrame(data)
    df['risk_level'] = ((df['gpa'] < 2.0) | (df['attendance_rate'] < 0.7)).astype(int)
    return df

def generate_recommendation_data(n_samples=1000):
    np.random.seed(42)
    data = {
        'gpa': np.random.uniform(0, 4.0, n_samples),
        'courses_count': np.random.randint(1, 8, n_samples),
        'service_requests_count': np.random.randint(0, 10, n_samples),
        'financial_status': np.random.choice([0, 1], n_samples, p=[0.3, 0.7]),
        'attendance_rate': np.random.uniform(0.5, 1.0, n_samples),
    }
    df = pd.DataFrame(data)
    df['recommendation_level'] = np.select(
        [df['gpa'] < 2.0, df['attendance_rate'] < 0.7, df['financial_status'] == 1, df['service_requests_count'] > 3],
        [3, 2, 2, 1],
        default=0
    )
    return df

def train_models_offline():
    df = generate_synthetic_data()
    X = df.drop('risk_level', axis=1)
    y = df['risk_level']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    models = {
        'decision_tree': DecisionTreeClassifier(random_state=42),
        'random_forest': RandomForestClassifier(random_state=42, n_estimators=100),
        'gradient_boosting': GradientBoostingClassifier(random_state=42, n_estimators=100)
    }
    
    results = {}
    best_model_name = None
    best_model = None
    best_f1 = 0
    
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        results[name] = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, zero_division=0)),
            'feature_importance': dict(zip(X.columns, model.feature_importances_.tolist()))
        }
        
        if results[name]['f1'] > best_f1:
            best_f1 = results[name]['f1']
            best_model = model
            best_model_name = name
    
    model_path = os.path.join(MODEL_DIR, 'best_model.joblib')
    joblib.dump({'model': best_model, 'features': list(X.columns), 'results': results}, model_path)
    
    local_path = os.path.join(LOCAL_MODEL_DIR, 'best_model.joblib')
    joblib.dump({'model': best_model, 'features': list(X.columns), 'results': results}, local_path)
    
    return results, best_model_name

def train_and_compare_models():
    results, best_model_name = train_models_offline()
    
    try:
        from models.db import MLModel, db
        model_record = MLModel(
            type=best_model_name,
            version='1.0',
            accuracy=results[best_model_name]['accuracy'],
            precision=results[best_model_name]['precision'],
            recall=results[best_model_name]['recall'],
            f1=results[best_model_name]['f1'],
            trained_on=datetime.utcnow()
        )
        db.session.add(model_record)
        db.session.commit()
    except:
        pass
    
    return results, None

def train_recommendation_model():
    df = generate_recommendation_data()
    X = df.drop('recommendation_level', axis=1)
    y = df['recommendation_level']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    models = {
        'random_forest': RandomForestClassifier(random_state=42, n_estimators=100),
        'gradient_boosting': GradientBoostingClassifier(random_state=42, n_estimators=100)
    }
    
    results = {}
    best_model_name = None
    best_model = None
    best_f1 = 0
    
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        accuracy = accuracy_score(y_test, y_pred) if len(np.unique(y_test)) > 1 else 1.0
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
        
        results[name] = {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1': float(f1),
            'feature_importance': dict(zip(X.columns, model.feature_importances_.tolist()))
        }
        
        if f1 > best_f1:
            best_f1 = f1
            best_model = model
            best_model_name = name
    
    model_data = {'model': best_model, 'features': list(X.columns), 'results': results}
    
    model_path = os.path.join(RECOMMENDATION_MODEL_DIR, 'recommendation_model.joblib')
    joblib.dump(model_data, model_path)
    
    local_path = os.path.join(LOCAL_RECOMMENDATION_MODEL_DIR, 'recommendation_model.joblib')
    joblib.dump(model_data, local_path)
    
    try:
        from models.db import MLModel, db
        model_record = MLModel(
            type='recommendation_' + best_model_name,
            version='1.0',
            accuracy=results[best_model_name]['accuracy'],
            precision=results[best_model_name]['precision'],
            recall=results[best_model_name]['recall'],
            f1=results[best_model_name]['f1'],
            trained_on=datetime.utcnow()
        )
        db.session.add(model_record)
        db.session.commit()
    except:
        pass
    
    return results, best_model_name

def load_model():
    model_path = os.path.join(MODEL_DIR, 'best_model.joblib')
    local_path = os.path.join(LOCAL_MODEL_DIR, 'best_model.joblib')
    
    if os.path.exists(model_path):
        model_data = joblib.load(model_path)
    elif os.path.exists(local_path):
        model_data = joblib.load(local_path)
    else:
        train_models_offline()
        model_data = joblib.load(model_path)
    
    return model_data

def load_recommendation_model():
    model_path = os.path.join(RECOMMENDATION_MODEL_DIR, 'recommendation_model.joblib')
    local_path = os.path.join(LOCAL_RECOMMENDATION_MODEL_DIR, 'recommendation_model.joblib')
    
    if os.path.exists(model_path):
        return joblib.load(model_path)
    elif os.path.exists(local_path):
        return joblib.load(local_path)
    else:
        train_recommendation_model()
        return joblib.load(model_path)

def predict_risk(data):
    model_data = load_model()
    model = model_data['model']
    features = model_data['features']
    
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    else:
        df = pd.DataFrame(data)
    
    for f in features:
        if f not in df.columns:
            raise ValueError(f"Missing required feature: {f}")
    
    X = df[features]
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    
    return predictions, probabilities

def predict_recommendation(data):
    model_data = load_recommendation_model()
    model = model_data['model']
    features = model_data['features']
    
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    else:
        df = pd.DataFrame(data)
    
    for f in features:
        if f not in df.columns:
            raise ValueError(f"Missing required feature: {f}")
    
    X = df[features]
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    
    return predictions, probabilities

def generate_recommendation_text(student_data, risk_pred, risk_prob, rec_pred, rec_proba):
    recommendations = []
    
    if student_data.get('gpa', 0) < 2.0:
        recommendations.append("Low GPA - suggests remedial courses and additional meetings with academic advisor")
    if student_data.get('attendance_rate', 0) < 0.7:
        recommendations.append("Low attendance rate - suggests attendance follow-up and analyzing absence reasons")
    if student_data.get('financial_status', 0) == 1:
        recommendations.append("Student is facing financial difficulties - suggests contacting financial and social affairs services")
    if student_data.get('service_requests_count', 0) > 3:
        recommendations.append("High number of service requests - suggests reviewing counseling support services")
    if student_data.get('courses_count', 0) < 3:
        recommendations.append("Low registered courses count - suggests reviewing the study plan and full registration")
    
    if not recommendations:
        recommendations.append("Student is performing well - suggests periodic follow-up to ensure continued performance")
    
    risk_level = "High Risk" if risk_pred == 1 else "Low Risk"
    risk_percent = (risk_prob[1] * 100) if len(risk_prob) > 1 else (risk_prob[0] * 100)
    rec_levels = {0: "No intervention needed", 1: "Mild intervention", 2: "Medium intervention", 3: "Urgent intervention"}
    rec_level_text = rec_levels.get(int(rec_pred), "Not specified")
    
    text = f"Smart recommendation for the student:\n"
    text += f"Risk level: {risk_level} ({risk_percent:.1f}%)\n"
    text += f"Recommended intervention level: {rec_level_text}\n\n"
    text += "Suggested actions:\n"
    for i, rec in enumerate(recommendations, 1):
        text += f"{i}. {rec}\n"
    
    return text

def get_feature_importance():
    model_data = load_model()
    return model_data.get('feature_importance', {})

def should_retrain():
    try:
        from models.db import MLModel
        latest_model = MLModel.query.order_by(MLModel.trained_on.desc()).first()
        if not latest_model or latest_model.accuracy < 0.85:
            return True
    except:
        pass
    return False