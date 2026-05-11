import requests
import base64
import io
from PIL import Image

# رابط السيرفر على Render
SERVER_URL = "https://esp32-cam-server-gsps.onrender.com/process"

# اختبار الصفحة الرئيسية
print("=== اختبار الصفحة الرئيسية ===")
response = requests.get("https://esp32-cam-server-gsps.onrender.com")
print(f"Status: {response.status_code}")
print("✅ يشتغل!" if response.status_code == 200 else "❌ مشكلة")

# اختبار API
print("\n=== اختبار API ===")
img = Image.new('RGB', (320, 240), color='red')
buffer = io.BytesIO()
img.save(buffer, format='JPEG')
img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

response = requests.post(
    SERVER_URL,
    json={"image": img_b64},
    timeout=60  # Render يحتاج وقت للاستيقاظ
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")