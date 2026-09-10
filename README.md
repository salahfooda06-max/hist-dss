# Decision Support System for Counseling Services - HIST Tripoli

A web system built with Python for decision support at the Counseling Institute, based on tree-based machine learning models and hybrid cloud computing.

## Requirements

```bash
pip install -r requirements.txt
```

## Run the System

```bash
python run.py
```

## Available Pages

- `/login` - Login
- `/logout` - Logout
- `/dashboard` - Dashboard
- `/data-integration` - Upload CSV files
- `/predict` - Prediction page
- `/recommendations` - View Recommendations
- `/reports` - Generate PDF Reports
- `/sync-status` - Sync Status (Admin only)
- `/audit` - Audit Log (Admin/Director only)
- `/retrain` - Retrain Model (Admin only)

## User Roles

- Administrator
- Extension Officer
- Faculty Lead
- Institute Director
- IT Infrastructure Lead

## Environment Settings

```bash
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/hist_dss
AES_KEY=32-bytes-encryption-key-for-aes-256!!
CLOUD_API_URL=http://localhost:5000/api/sync
```

## Initial Data

Default users will be created for each role with password: `password123`
