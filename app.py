from flask import Flask, request, jsonify
import cv2
import numpy as np
import mediapipe as mp
from PIL import Image
import io
import base64
import os

app = Flask(__name__)

# ========== تهيئة MediaPipe ==========
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=2,
    min_detection_confidence=0.7
)

mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.7)

# ========== قاعدة بيانات الوجوه ==========
known_faces = {}

def load_known_faces():
    """
    تحميل الوجوه المعروفة من مجلد known_faces
    كل صورة اسمها = اسم الشخص
    """
    faces_dir = "known_faces"
    if not os.path.exists(faces_dir):
        os.makedirs(faces_dir)
        print(f"📁 تم إنشاء مجلد '{faces_dir}'. ضع فيه صور الوجوه.")
        return
    
    for filename in os.listdir(faces_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            name = os.path.splitext(filename)[0]
            filepath = os.path.join(faces_dir, filename)
            
            # قراءة الصورة واستخراج الوجه
            img = cv2.imread(filepath)
            if img is not None:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = face_detection.process(rgb)
                
                if results.detections:
                    # نستخدم الـ encoding البسيط (اللون المتوسط)
                    encoding = np.mean(rgb, axis=(0,1))
                    known_faces[name] = {
                        'encoding': encoding,
                        'filepath': filepath
                    }
                    print(f"✅ تم تحميل وجه: {name}")
                else:
                    print(f"⚠️ ما فيه وجه بصورة: {filename}")

# تحميل الوجوه عند البدء
load_known_faces()

@app.route('/')
def home():
    return """
    <html>
    <head><title>ESP32-CAM Server</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>🚀 سيرفر ESP32-CAM يشتغل!</h1>
        <p>الأشخاص المعروفين: """ + ", ".join(known_faces.keys()) + """</p>
        <p>الـ API: <code>POST /process</code></p>
    </body>
    </html>
    """

@app.route('/process', methods=['POST'])
def process_image():
    try:
        print("📥 تم استقبال طلب جديد!")
        
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({
                'success': False,
                'error': 'لا توجد صورة'
            }), 400
        
        image_b64 = data['image']
        
        try:
            image_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_bytes))
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            print(f"📸 حجم الصورة: {frame.shape}")
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطأ في الصورة: {str(e)}'
            }), 400
        
        result = {
            'success': True,
            'face_detected': False,
            'face_recognized': False,
            'person_name': None,
            'finger_count': 0,
            'approval': False,
            'message': ''
        }
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # ========== 1. كشف الوجه ==========
        face_results = face_detection.process(rgb_frame)
        
        if face_results.detections:
            result['face_detected'] = True
            print("👤 تم اكتشاف وجه!")
            
            # ========== 2. التعرف على الوجه ==========
            if known_faces:
                # استخراج encoding الوجه الحالي
                current_encoding = np.mean(rgb_frame, axis=(0,1))
                
                # مقارنة مع الوجوه المعروفة
                best_match = None
                best_score = float('inf')
                
                for name, data in known_faces.items():
                    # حساب الفرق (MSE)
                    score = np.mean((current_encoding - data['encoding']) ** 2)
                    print(f"📝 مقارنة مع {name}: score = {score:.2f}")
                    
                    if score < best_score:
                        best_score = score
                        best_match = name
                
                # إذا الفرق صغير = نفس الشخص
                threshold = 50.0  # يمكن تعديله
                if best_score < threshold:
                    result['face_recognized'] = True
                    result['person_name'] = best_match
                    print(f"✅ تم التعرف على: {best_match} (score: {best_score:.2f})")
                else:
                    print(f"❌ وجه غير معروف (score: {best_score:.2f})")
            else:
                print("⚠️ لا توجد وجوه معروفة بالمجلد")
        
        # ========== 3. عد الأصابع ==========
        hand_results = hands.process(rgb_frame)
        
        if hand_results.multi_hand_landmarks:
            total_fingers = 0
            
            for hand_landmarks in hand_results.multi_hand_landmarks:
                fingers = count_fingers(hand_landmarks)
                total_fingers += fingers
                print(f"🖐️ يد: {fingers} أصابع")
            
            result['finger_count'] = total_fingers
            print(f"🖐️ إجمالي الأصابع: {total_fingers}")
        
        # ========== 4. منطق الموافقة ==========
        if result['face_recognized'] and result['person_name']:
            if result['finger_count'] > 0:
                result['approval'] = True
                result['message'] = f"✅ مرحباً {result['person_name']}! تمت الموافقة ({result['finger_count']} أصابع)"
            else:
                result['message'] = f"👋 مرحباً {result['person_name']}! ارفع أصابعك للموافقة"
        elif result['face_detected'] and not result['face_recognized']:
            result['message'] = "❌ وجه غير معروف! الوصول مرفوض"
        elif not result['face_detected']:
            result['message'] = "⚠️ لم يتم اكتشاف وجه"
        
        print(f"📤 النتيجة: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def count_fingers(hand_landmarks):
    """
    عد الأصابع المرفوعة
    """
    finger_tips = [8, 12, 16, 20]   # Index, Middle, Ring, Pinky
    finger_pips = [6, 10, 14, 18]   # المفاصل السفلية
    
    fingers = 0
    
    # الأصابع الأربعة
    for tip, pip in zip(finger_tips, finger_pips):
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
            fingers += 1
    
    # الإبهام
    thumb_tip = hand_landmarks.landmark[4]
    thumb_ip = hand_landmarks.landmark[3]
    thumb_mcp = hand_landmarks.landmark[2]
    
    if abs(thumb_tip.x - thumb_mcp.x) > 0.05:
        fingers += 1
    
    return fingers

@app.route('/add_face', methods=['POST'])
def add_face():
    """
    API لإضافة وجه جديد
    """
    try:
        data = request.get_json()
        name = data.get('name')
        image_b64 = data.get('image')
        
        if not name or not image_b64:
            return jsonify({'success': False, 'error': 'اسم وصورة مطلوبين'})
        
        # حفظ الصورة
        image_bytes = base64.b64decode(image_b64)
        face_path = f"known_faces/{name}.jpg"
        
        with open(face_path, 'wb') as f:
            f.write(image_bytes)
        
        # إعادة تحميل الوجوه
        load_known_faces()
        
        return jsonify({
            'success': True,
            'message': f'تم إضافة وجه: {name}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)