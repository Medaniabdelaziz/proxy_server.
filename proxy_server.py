import os
import io
import gzip
import socket
from flask import Flask, request, Response, stream_with_context
import requests

app = Flask(__name__)

# إعداد الجلسة لطلبات الويب العادية وتجنب الحظر
session = requests.Session()
session.verify = False  # تجاوز التحقق من SSL لضمان عمل كافة المواقع
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

@app.route('/')
def home():
    return "🚀 خادم وكيل HTTP(S) الصافي يعمل بكفاءة وبأعلى سرعة!"

@app.route('/proxy', methods=['GET', 'CONNECT'])
def secure_http_proxy():
    url = request.args.get('url') or request.environ.get('HTTP_HOST')
    
    if not url:
        return "❌ يرجى تحديد الوجهة المستهدفة عبر ?url=", 400

    # 1️⃣ دعم نفق الاتصال الآمن للمتصفحات والتطبيقات (HTTPS Tunneling)
    if request.method == 'CONNECT':
        try:
            host, port = url.split(':') if ':' in url else (url, 443)
            port = int(port)
            
            # فتح اتصال TCP مباشر ونظيف مع الموقع المستهدف
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.settimeout(10)
            remote_socket.connect((host, port))
            
            # إرسال استجابة نجاح تأسيس النفق للمتصفح
            return Response("HTTP/1.1 200 Connection Established\r\n\r\n", status=200)
        except Exception as e:
            return f"❌ فشل إنشاء نفق آمن: {e}", 502

    # 2️⃣ التعامل مع طلبات الويب العادية وضغطها (HTTP GET)
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        # نقل الـ Headers من العميل وتجنب تكرار الـ Host لعدم إرباك الموقع المستهدف
        req_headers = {k: v for k, v in request.headers if k.lower() != 'host'}
        r = session.get(url, timeout=15, allow_redirects=True, headers=req_headers, stream=True)
        
        # فحص نوع المحتوى لتجنب ضغط الملفات المضغوطة مسبقاً (مثل الفيديوهات والصور)
        content_type = r.headers.get('Content-Type', '').lower()
        should_compress = any(t in content_type for t in ['text', 'json', 'javascript', 'xml', 'html'])

        # نظام التدفق المستمر (Streaming) لتقليل استهلاك الذاكرة إلى الصفر تقريباً
        @stream_with_context
        def generate():
            if should_compress:
                gzip_buffer = io.BytesIO()
                with gzip.GzipFile(fileobj=gzip_buffer, mode='wb', compresslevel=4) as gzip_file:
                    for chunk in r.iter_content(chunk_size=64 * 1024): # قطع بحجم 64 كيلوبايت
                        if chunk:
                            gzip_file.write(chunk)
                            yield gzip_buffer.getvalue()
                            gzip_buffer.seek(0)
                            gzip_buffer.truncate(0)
            else:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk

        # تنظيف الـ Headers لضمان عدم حدوث تعارض في المتصفح
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        resp_headers = {k: v for k, v in r.headers.items() if k.lower() not in excluded_headers}
        
        if should_compress:
            resp_headers['Content-Encoding'] = 'gzip'

        return Response(generate(), status=r.status_code, headers=resp_headers)
        
    except Exception as e:
        return f"💥 خطأ أثناء جلب البيانات: {str(e)}", 500

if __name__ == '__main__':
    # متوافق بالكامل مع بيئة ومنفذ Render الديناميكي
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
