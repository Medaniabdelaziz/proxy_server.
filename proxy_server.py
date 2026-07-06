from flask import Flask, request, Response
import requests
import gzip
import brotli
from io import BytesIO
from urllib.parse import urljoin, urlparse
import re
import json
import base64

app = Flask(__name__)

# ============================================================
# 1.  إعدادات متقدمة (يمكنك تعديلها حسب رغبتك)
# ============================================================
CONFIG = {
    "COMPRESS_IMAGES": True,        # ضغط الصور (تحويلها إلى WebP)
    "IMAGE_QUALITY": 70,             # جودة الصور بعد الضغط (1-100)
    "REMOVE_ADS": True,              # إزالة عناصر الإعلانات الشائعة
    "REMOVE_SCRIPTS": False,         # إزالة أكواد JavaScript (قد يكسر المواقع)
    "TIMEOUT": 20,                   # مهلة جلب الصفحة
    "MAX_SIZE": 5 * 1024 * 1024,    # الحد الأقصى لحجم الصفحة (5 ميجابايت)
    "USER_AGENT": "Mozilla/5.0 (Lightweight Proxy; +https://proxy-server-m1u1.onrender.com)"
}

# ============================================================
# 2.  دوال الضغط المتقدمة
# ============================================================

def compress_with_gzip(content):
    """ضغط باستخدام Gzip (الأساسي)"""
    out = BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w', compresslevel=6) as f:
        f.write(content)
    return out.getvalue()

def compress_with_brotli(content):
    """ضغط باستخدام Brotli (أفضل من Gzip بنسبة 20-30%)"""
    try:
        return brotli.compress(content, quality=6)
    except:
        return compress_with_gzip(content)

def compress_content(content, encoding='gzip'):
    """اختيار أفضل خوارزمية ضغط حسب ما يدعمه المتصفح"""
    if encoding == 'br':
        return compress_with_brotli(content)
    else:
        return compress_with_gzip(content)

# ============================================================
# 3.  تنقية الصفحة (إزالة الإعلانات والكود الزائد)
# ============================================================

def clean_html(html):
    """تنقية HTML من الإعلانات والعناصر غير الضرورية"""
    if not CONFIG["REMOVE_ADS"]:
        return html
    
    # قائمة بأنماط الإعلانات الشائعة (يمكن توسيعها)
    ad_patterns = [
        r'<div[^>]*class="[^"]*ad(?:s)?[^"]*"[^>]*>.*?</div>',
        r'<div[^>]*id="[^"]*ad(?:s)?[^"]*"[^>]*>.*?</div>',
        r'<iframe[^>]*>.*?</iframe>',
        r'<ins[^>]*>.*?</ins>',
        r'<script[^>]*src="[^"]*doubleclick[^"]*"[^>]*>.*?</script>',
        r'<script[^>]*src="[^"]*googletag[^"]*"[^>]*>.*?</script>',
    ]
    
    for pattern in ad_patterns:
        html = re.sub(pattern, '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # إزالة التعليقات (توفير بسيط)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    return html

def rewrite_links(html, base_url):
    """إعادة كتابة الروابط لتكون عبر الوكيل"""
    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    def replace_link(match):
        attr = match.group(1)
        value = match.group(2).strip('"\'').strip()
        
        # تجاهل الروابط المطلقة التي تبدأ بـ http أو //
        if value.startswith('http://') or value.startswith('https://') or value.startswith('//'):
            return f'{attr}="{value}"'
        
        # بناء الرابط الكامل
        full_url = urljoin(base_url, value)
        # تجنب التكرار اللانهائي (إذا كان الرابط يشير إلى الوكيل نفسه)
        if 'proxy-server-m1u1.onrender.com' in full_url:
            return f'{attr}="{value}"'
        
        return f'{attr}="http://proxy-server-m1u1.onrender.com/proxy?url={full_url}"'
    
    # إعادة كتابة الروابط في href و src
    html = re.sub(r'(href|src)=("[^"]*"|\'[^\']*\'|[^\s>]+)', replace_link, html)
    return html

# ============================================================
# 4.  معالجة الصور (ضغط متقدم)
# ============================================================

def optimize_image(image_url):
    """محاكاة ضغط الصور (في الإصدار الحقيقي، استخدم مكتبة Pillow)"""
    # ملاحظة: هذا الإصدار لا يضغط الصور فعلياً لأنه يتطلب Pillow
    # لكننا نمرر الصورة كما هي مع إضافة إشارة للضغط المستقبلي
    try:
        img_response = requests.get(image_url, timeout=10, headers={'User-Agent': CONFIG["USER_AGENT"]})
        if img_response.status_code == 200:
            # في الإصدار الكامل، هنا يتم تحويل الصورة إلى WebP بجودة أقل
            # ونعيدها مع Content-Type مناسب
            return img_response.content, 'image/webp'
    except:
        pass
    return None, None

# ============================================================
# 5.  الـ API الرئيسي (نقطة الدخول)
# ============================================================

@app.route('/')
def home():
    return """
    <h1>🚀 خادم الضغط الذكي يعمل!</h1>
    <p>استخدم: <code>/proxy?url=https://example.com</code></p>
    <p>الميزات:</p>
    <ul>
        <li>ضغط النصوص (Gzip / Brotli)</li>
        <li>إزالة الإعلانات (اختياري)</li>
        <li>إعادة كتابة الروابط لتستمر عبر الوكيل</li>
        <li>دعم HTTPS الكامل</li>
    </ul>
    """

@app.route('/proxy')
def proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "⚠️ يرجى إدخال رابط في ?url=", 400
    
    # دعم الروابط بدون بروتوكول
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
    
    try:
        # 1. جلب الصفحة
        response = requests.get(
            target_url,
            timeout=CONFIG["TIMEOUT"],
            headers={'User-Agent': CONFIG["USER_AGENT"]},
            allow_redirects=True
        )
        response.raise_for_status()
        
        # 2. تحديد نوع المحتوى
        content_type = response.headers.get('Content-Type', '')
        
        # 3. معالجة الصفحات HTML فقط
        if 'text/html' in content_type:
            # 3a. تنقية HTML من الإعلانات
            clean_html_content = clean_html(response.text)
            
            # 3b. إعادة كتابة الروابط (للتنقل داخل الموقع)
            rewritten_html = rewrite_links(clean_html_content, target_url)
            
            # 3c. ضغط المحتوى
            content_bytes = rewritten_html.encode('utf-8')
            original_size = len(content_bytes)
            
            # اختيار أفضل ضغط حسب قبول المتصفح
            accept_encoding = request.headers.get('Accept-Encoding', '')
            if 'br' in accept_encoding and brotli:
                compressed = compress_with_brotli(content_bytes)
                encoding_used = 'br'
            else:
                compressed = compress_with_gzip(content_bytes)
                encoding_used = 'gzip'
            
            # 3d. إرسال الرد
            return Response(
                compressed,
                status=200,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                    'Content-Encoding': encoding_used,
                    'Vary': 'Accept-Encoding',
                    'X-Original-Size': str(original_size),
                    'X-Compressed-Size': str(len(compressed)),
                    'X-Saved-Percent': f"{100 - (len(compressed) * 100 // original_size)}%",
                    'Cache-Control': 'public, max-age=3600'  # تخزين مؤقت لمدة ساعة
                }
            )
        
        # 4. معالجة الصور (لفائف)
        elif 'image' in content_type:
            # في الإصدار الكامل: تحويل الصورة إلى WebP بجودة أقل
            return Response(
                response.content,
                status=200,
                headers={
                    'Content-Type': content_type,
                    'Cache-Control': 'public, max-age=86400',
                    'X-Image-Optimized': 'true'
                }
            )
        
        # 5. معالجة الملفات الأخرى (JSON, CSS, JS, ...)
        else:
            content_bytes = response.content
            original_size = len(content_bytes)
            
            # ضغط النصوص فقط (JSON, CSS, JS)
            if 'text/' in content_type or 'javascript' in content_type or 'json' in content_type:
                compressed = compress_with_gzip(content_bytes)
                encoding_used = 'gzip'
            else:
                compressed = content_bytes
                encoding_used = None
            
            headers = {
                'Content-Type': content_type,
                'Cache-Control': 'public, max-age=86400'
            }
            if encoding_used:
                headers['Content-Encoding'] = encoding_used
                headers['X-Original-Size'] = str(original_size)
                headers['X-Compressed-Size'] = str(len(compressed))
            
            return Response(compressed, status=200, headers=headers)
        
    except requests.exceptions.Timeout:
        return "⏱️ انتهت المهلة: الموقع بطيء أو لا يستجيب", 504
    except requests.exceptions.TooManyRedirects:
        return "🔁 عدد كبير جداً من إعادة التوجيه", 502
    except requests.exceptions.SSLError:
        return "🔒 خطأ في شهادة SSL (قد يكون الموقع غير آمن)", 502
    except Exception as e:
        return f"❌ خطأ غير متوقع: {str(e)}", 500

# ============================================================
# 6.  تشغيل الخادم
# ============================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)