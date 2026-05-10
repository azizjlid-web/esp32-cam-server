import requests
import base64

# 1. اختبار الصفحة الرئيسية
print("=== اختبار الصفحة الرئيسية ===")
response = requests.get("http://localhost:5000")
print(response.status_code)
print("✅ يشتغل!" if response.status_code == 200 else "❌ مشكلة")

# 2. اختبار API بصورة وهمية
print("\n=== اختبار API ===")

# أنشئ صورة سوداء بسيطة (1x1 بكسل)
import io
from PIL import Image

img = Image.new('RGB', (320, 240), color='red')
buffer = io.BytesIO()
img.save(buffer, format='JPEG')
img_bytes = buffer.getvalue()

# حول لـ Base64
img_b64 = base64.b64encode(img_bytes).decode('utf-8')

# أرسل للسيرفر
response = requests.post(
    "http://localhost:5000/process",
    json={"image": img_b64}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")