import os
import json
import gzip
import sqlite3
from datetime import datetime
from flask import current_app
import requests
from models.db import SyncQueue, db
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib

LOCAL_DB = 'instance/local.db'

def check_connection():
    try:
        requests.get('https://www.google.com', timeout=3)
        return True
    except:
        return False

def get_sync_queue():
    return SyncQueue.query.filter_by(status='pending').all()

def encrypt_payload(data):
    key = os.environ.get('AES_KEY', 'this-is-32-bytes-for-aes-256-key!').encode()[:32]
    cipher = AES.new(key, AES.MODE_CBC)
    json_data = json.dumps(data).encode()
    encrypted = cipher.encrypt(pad(json_data, AES.block_size))
    return base64.b64encode(cipher.iv + encrypted).decode()

def compress_data(data):
    json_str = json.dumps(data)
    compressed = gzip.compress(json_str.encode())
    return compressed

def decrypt_payload(b64_payload):
    raw = base64.b64decode(b64_payload)
    iv = raw[:AES.block_size]
    encrypted = raw[AES.block_size:]
    key = os.environ.get('AES_KEY', 'this-is-32-bytes-for-aes-256-key!').encode()[:32]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
    return json.loads(decrypted.decode())

def receive_sync(data):
    from models.db import Student, ServiceRequest, AIRecommendation, Recommendation, MLModel

    def _coerce(records, model, dt_fields):
        for rec in records:
            item = dict(rec)
            for f in dt_fields:
                if item.get(f):
                    try:
                        item[f] = datetime.fromisoformat(item[f])
                    except Exception:
                        item[f] = None
            db.session.merge(model(**item))
        db.session.commit()

    _coerce(data.get('students', []), Student,
            [])
    _coerce(data.get('service_requests', []), ServiceRequest,
            ['date'])
    _coerce(data.get('recommendations', []), Recommendation,
            [])
    _coerce(data.get('ai_recommendations', []), AIRecommendation,
            ['generated_at'])
    _coerce(data.get('models', []), MLModel,
            ['trained_on'])

    counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    print(f"[sync] merged into cloud DB: {counts}")
    return True

def decompress_data(compressed):
    return gzip.decompress(compressed).decode()

def queue_for_sync(data):
    compressed = compress_data(data)
    encrypted = encrypt_payload(data)
    
    queue_item = SyncQueue(
        payload=encrypted,
        status='pending',
        created_at=datetime.utcnow()
    )
    db.session.add(queue_item)
    db.session.commit()
    return queue_item.queue_id

def sync_to_cloud():
    if not check_connection():
        return False, "No internet connection"
    
    queue_items = get_sync_queue()
    success_count = 0
    
    for item in queue_items:
        try:
            payload = json.loads(item.payload)
            response = requests.post(
                f"{os.environ.get('CLOUD_API_URL', 'http://localhost:5000/api/sync')}",
                json={'data': payload},
                timeout=10
            )
            if response.status_code == 200:
                item.status = 'synced'
                item.synced_at = datetime.utcnow()
                db.session.commit()
                success_count += 1
        except Exception as e:
            item.status = 'failed'
            db.session.commit()
    
    return True, f"Synced {success_count} items"

def sync_from_cloud():
    if not check_connection():
        return False, "No internet connection"
    
    try:
        response = requests.get(
            f"{os.environ.get('CLOUD_API_URL', 'http://localhost:5000/api/sync')}?since={datetime.utcnow().isoformat()}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return True, data
    except Exception as e:
        return False, str(e)

def _serialize(obj, fields):
    result = {}
    for f in fields:
        value = getattr(obj, f, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[f] = value
    return result

def collect_local_data():
    from models.db import Student, ServiceRequest, AIRecommendation, Recommendation, MLModel

    students = [_serialize(s, [
        'student_id', 'name', 'program', 'gpa', 'status',
        'attendance_rate', 'financial_status', 'courses_count', 'service_requests_count'
    ]) for s in Student.query.all()]

    service_requests = [_serialize(r, [
        'request_id', 'student_id', 'type', 'description', 'date', 'status'
    ]) for r in ServiceRequest.query.all()]

    ai_recommendations = [_serialize(r, [
        'rec_id', 'student_id', 'model_id', 'score', 'recommendation_text', 'generated_at'
    ]) for r in AIRecommendation.query.all()]

    recommendations = [_serialize(r, [
        'rec_id', 'request_id', 'model_id', 'score', 'action', 'feedback'
    ]) for r in Recommendation.query.all()]

    models = [_serialize(m, [
        'model_id', 'type', 'version', 'accuracy', 'precision', 'recall', 'f1', 'trained_on'
    ]) for m in MLModel.query.all()]

    return {
        'students': students,
        'service_requests': service_requests,
        'ai_recommendations': ai_recommendations,
        'recommendations': recommendations,
        'models': models
    }

def sync_all_local_data():
    if not check_connection():
        return False, "No internet connection"

    data = collect_local_data()
    total_items = sum(len(v) for v in data.values())

    payload = encrypt_payload(data)

    cloud_url = os.environ.get('CLOUD_API_URL')
    try:
        if cloud_url:
            response = requests.post(
                cloud_url,
                json={'data': payload},
                timeout=30
            )
            if response.status_code != 200:
                return False, f"Cloud returned status {response.status_code}"
        else:
            receive_sync(data)

        queue_item = SyncQueue(
            payload=payload,
            status='synced',
            created_at=datetime.utcnow(),
            synced_at=datetime.utcnow()
        )
        db.session.add(queue_item)
        db.session.commit()
        return True, f"Synced {total_items} items"
    except Exception as e:
        queue_item = SyncQueue(
            payload=payload,
            status='failed',
            created_at=datetime.utcnow()
        )
        db.session.add(queue_item)
        db.session.commit()
        return False, f"Sync failed: {str(e)}"

def get_sync_status():
    total = SyncQueue.query.count()
    pending = SyncQueue.query.filter_by(status='pending').count()
    synced = SyncQueue.query.filter_by(status='synced').count()
    failed = SyncQueue.query.filter_by(status='failed').count()
    
    return {
        'connected': check_connection(),
        'total_queued': total,
        'pending': pending,
        'synced': synced,
        'failed': failed
    }