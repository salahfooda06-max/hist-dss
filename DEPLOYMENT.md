# Permanent Hosting Guide - HIST DSS

## Option 1: Deploy to Render.com (Free Tier - Recommended)

Render أسرع طريقة للحصول على استضافة دائمة مع URL ثابت.

### الخطوات:
1. أنشئ حساب على [render.com](https://render.com/signup) (مجاني)
2. ارفع هذا المستودع على [GitHub](https://github.com/new) (سحب أو رفع الكود)
3. من لوحة Render، اضغط **"New +"** → **"Web Service"**
4. اربط حسابك بـ GitHub واختر المستودع
5. الإعدادات الموصى بها:
   - **Environment**: Docker
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --timeout 120 "app:create_app()"`
   - **Plan**: Free

6. أضف قاعدة البيانات PostgreSQL:
   - **"New +"** → **"PostgreSQL"**
   - **Plan**: Free
   - دمجها مع الخدمة عبر `DATABASE_URL`

7. عيّن المتغيّرات البيئية:
   ```
   SECRET_KEY=<random-32-char-string>
   AES_KEY=32-bytes-encryption-key-for-aes-256!!
   FLASK_DEBUG=0
   ```

بعد النشر، سيحصل التطبيق على URL ثابت مثل:
```
https://hist-dss.onrender.com
```

---

## Option 2: رفع ملف ZIP مباشرة (بدون GitHub)

بعض المنصات تقبل رفع ملف ZIP:
- **Railway.app**: ارفع الكود مباشرة
- **PythonAnywhere**: يتيح ربط GitHub أو رفع ملفات

---

## Option 3: VPS خاص (Docker)

على أي خادم (DigitalOcean, AWS EC2, Azure، إلخ):

```bash
# 1. تثبيت Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. تشغيل التطبيق
git clone <repo-url> hist_dss
cd hist_dss
cp .env.example .env
# عدّل .env بالقيم الخاصة بك
docker-compose up --build -d
```

الوصول عبر: `http://<your-server-ip>:5000`

لربط نطاق مخصص (HTTPS)، أضف Nginx مع Let's Encrypt:
```bash
docker run -d --name nginx-proxy \
  -v /var/run/docker.sock:/tmp/docker.sock:ro \
  -v /etc/nginx/certs \
  -p 80:80 -p 443:443 \
  nginxproxy/nginx-proxy
```

---

## Troubleshooting

- **ERR_CONNECTION_REFUSED**: تأكد أن العملية مايموتش (Render يعيد تشغيلها تلقائياً)
- **Database errors**: تأكد أن `DATABASE_URL` صحيح وـ PostgreSQL يعمل
- **Login page لا يظهر**: تحقق أن `SECRET_KEY` مُعيّن في المتغيّرات البيئية

## بيانات الدخول الافتراضية
جميع الأدوار: `password123`
- administrator@hist.edu.ly
- extension.officer@hist.edu.ly
- faculty.lead@hist.edu.ly
- institute.director@hist.edu.ly
- it.infrastructure.lead@hist.edu.ly
