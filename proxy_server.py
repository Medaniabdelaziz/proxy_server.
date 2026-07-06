import os
import io
import gzip
import requests
from flask import Flask, request, Response, stream_with_context
import urllib3

# تعطيل تحذيرات SSL لأننا قد نتجاوز التحقق في بعض الطلبات
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# إعداد الجلسة لطلبات الويب وتجنب الحظر
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

@app.route('/')
def home():
    return "🚀 خادم الوكيل الاحترافي يعمل بكفاءة! استخدم /proxy?url= للوصول للمواقع."

@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def secure_http_proxy():
    # استخراج الرابط المستهدف
    url = request.args.get('url')
    
    if not url:
        return "❌ يرجى تحديد الوجهة المستهدفة عبر ?url=", 400

    # إضافة https إذا لم تكن موجودة
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        # نقل الـ Headers من العميل وتجنب تكرار الـ Host
        req_headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'content-length', 'connection']}
        
        # إعداد بيانات الطلب
        req_kwargs = {
            'headers': req_headers,
            'stream': True,
            'timeout': 30,
            'verify': False,
            'allow_redirects': True
        }
        
        # إضافة البيانات إذا كان الطلب POST أو PUT
        if request.method in ['POST', 'PUT', 'PATCH']:
            req_kwargs['data'] = request.get_data()
            
        # تنفيذ الطلب
        r = session.request(request.method, url, **req_kwargs)
        
        # فحص نوع المحتوى لتجنب ضغط الملفات المضغوطة مسبقاً
        content_type = r.headers.get('Content-Type', '').lower()
        should_compress = any(t in content_type for t in ['text', 'json', 'javascript', 'xml', 'html']) and 'gzip' not in r.headers.get('Content-Encoding', '')

        # نظام التدفق المستمر (Streaming) لتقليل استهلاك الذاكرة
        @stream_with_context
        def generate():
            if should_compress:
                # طريقة صحيحة لضغط Gzip أثناء البث
                compressor = gzip.compressobj(level=4, wbits=16 + gzip.MAX_WBITS)
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        compressed_chunk = compressor.compress(chunk)
                        if compressed_chunk:
                            yield compressed_chunk
                # إرسال ما تبقى في الذاكرة
                remaining = compressor.flush()
                if remaining:
                    yield remaining
            else:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk

        # تنظيف الـ Headers لضمان عدم حدوث تعارض
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