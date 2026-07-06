from flask import Flask, request, Response
import requests
import gzip
from io import BytesIO
from urllib.parse import urljoin, urlparse
import re

app = Flask(__name__)

def compress_content(content):
    out = BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w', compresslevel=6) as f:
        f.write(content)
    return out.getvalue()

def rewrite_links(html, base_url):
    """إعادة كتابة الروابط لتستمر عبر الوكيل"""
    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    def replace_link(match):
        attr = match.group(1)
        value = match.group(2).strip('"\'')
        
        # تجاهل الروابط المطلقة
        if value.startswith(('http://', 'https://', '//', '#')):
            return f'{attr}="{value}"'
        
        # بناء الرابط الكامل
        full_url = urljoin(base_url, value)
        return f'{attr}="http://proxy-server-m1u1.onrender.com/proxy?url={full_url}"'
    
    # إعادة كتابة href و src
    html = re.sub(r'(href|src)=("[^"]*"|\'[^\']*\'|[^\s>]+)', replace_link, html)
    return html

@app.route('/')
def home():
    return "✅ خادم الضغط الخاص بي يعمل! استخدم: /proxy?url=example.com"

@app.route('/proxy')
def proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "⚠️ يرجى إدخال رابط في ?url=", 400
    
    # إضافة https إذا كان الرابط بدون بروتوكول
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    try:
        # جلب الصفحة مع تعطيل التحقق من SSL مؤقتاً (لتفادي أخطاء الشهادات)
        response = requests.get(target_url, timeout=20, verify=False, allow_redirects=True)
        response.raise_for_status()
        
        # معالجة فقط صفحات HTML
        if 'text/html' in response.headers.get('Content-Type', ''):
            # إعادة كتابة الروابط
            rewritten_html = rewrite_links(response.text, target_url)
            content_bytes = rewritten_html.encode('utf-8')
            original_size = len(content_bytes)
            compressed = compress_content(content_bytes)
            
            return Response(
                compressed,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                    'Content-Encoding': 'gzip',
                    'X-Original-Size': str(original_size),
                    'X-Compressed-Size': str(len(compressed)),
                    'X-Saved': f"{100 - (len(compressed) * 100 // original_size)}%"
                }
            )
        else:
            # للملفات الأخرى (صور، PDF، ...) نمررها كما هي بدون ضغط إضافي
            return Response(response.content, headers={'Content-Type': response.headers.get('Content-Type', '')})
            
    except Exception as e:
        return f"❌ خطأ: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)