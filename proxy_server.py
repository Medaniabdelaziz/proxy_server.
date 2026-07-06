# استيراد المكتبات الأساسية (تأكد من كتابتها كما هي)
from flask import Flask, request, Response
import requests
import gzip
from io import BytesIO

# إنشاء تطبيق Flask
app = Flask(__name__)

# دالة الضغط: تقوم بتقليص حجم النصوص باستخدام خوارزمية Gzip
def compress_content(content):
    out = BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(content)
    return out.getvalue()

# الصفحة الرئيسية (لمجرد التأكد أن الخادم شغال)
@app.route('/')
def home():
    return "✅ خادم الضغط الخاص بي يعمل! استخدم: /proxy?url=example.com"

# الصفحة التي ستستقبل طلبات التصفح
@app.route('/proxy')
def proxy():
    # 1. المستخدم يرسل رابط الموقع الذي يريد زيارته (مثال: ?url=news.com)
    target_url = request.args.get('url')
    if not target_url:
        return "⚠️ يرجى إدخال رابط في ?url=", 400

    try:
        # 2. الخادم يذهب بنفسه إلى الموقع الأصلي ويجلب البيانات
        response = requests.get(target_url, timeout=15)
        
        # 3. قياس الحجم الأصلي قبل الضغط
        original_size = len(response.text)
        
        # 4. ضغط المحتوى النصي (تحويله إلى Bytes مضغوطة)
        compressed_data = compress_content(response.text.encode('utf-8'))
        compressed_size = len(compressed_data)
        
        # 5. إرسال البيانات المضغوطة إلى المستخدم مع إضافة ترويسات (Headers) توضح التوفير
        return Response(
            compressed_data,
            status=200,
            headers={
                'Content-Type': 'text/html; charset=utf-8',
                'Content-Encoding': 'gzip',  # إعلام المتصفح بأن البيانات مضغوطة
                'X-Original-Size': str(original_size),
                'X-Compressed-Size': str(compressed_size)
            }
        )
    except Exception as e:
        return f"❌ حدث خطأ: {str(e)}", 500

# تشغيل الخادم محلياً (للتجربة قبل النشر)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)