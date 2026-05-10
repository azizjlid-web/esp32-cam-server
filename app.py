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
mp_draw = mp.solutions.drawing_utils

mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.7)

# ========== قاعدة بيانات الوجوه البسيطة ==========
known_faces = {}

def load_known_faces():
    faces_dir = "known_faces"
    if not os.path.exists(faces_dir):
        os.makedirs(faces_dir)
        print(f"تم إنشاء مجلد '{faces_dir}'. ضع فيه صور الوجوه.")
        return
    
    for filename in os.listdir(faces_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            name = os.path.splitext(filename)[0]
            known_faces[name] = os.path.join(faces_dir, filename)
            print(f"تم تحميل وجه: {name}")

load_known_faces()

@app.route('/')
def home():
    return """
    <html>
    <head><title>ESP32-CAM Server</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>سيرفر ESP32-CAM يشتغل!</h1>
        <p>الـ API: <code>POST /process</code></p>
    </body>
    </html>
    """

@app.route('/process', methods=['POST'])
def process_image():
    try:
        print("تم استقبال طلب جديد!")
        
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({
                'success': False,
                'error': 'لا توجد صورة في الطلب. أرسل {"image": "base64_string"}'
            }), 400
        
        image_b64 = data['image']
        
        try:
            image_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_bytes))
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            print(f"حجم الصورة: {frame.shape}")
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'خطأ في فك تشفير الصورة: {str(e)}'
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
        face_results = face_detection.process(rgb_frame)
        
        if face_results.detections:
            result['face_detected'] = True
            print("تم اكتشاف وجه!")
            
            if known_faces:
                result['face_recognized'] = True
                result['person_name'] = list(known_faces.keys())[0]
                print(f"تم التعرف على: {result['person_name']}")
        
        hand_results = hands.process(rgb_frame)
        
        if hand_results.multi_hand_landmarks:
            total_fingers = 0
            
            for hand_landmarks in hand_results.multi_hand_landmarks:
                fingers = count_fingers(hand_landmarks)
                total_fingers += fingers
                print(f"يد: {fingers} أصابع")
            
            result['finger_count'] = total_fingers
            print(f"إجمالي الأصابع: {total_fingers}")
        
        if result['face_detected'] and result['finger_count'] >= 1:
            result['approval'] = True
            result['message'] = 'تمت الموافقة!'
        elif not result['face_detected']:
            result['message'] = 'لم يتم اكتشاف وجه'
        else:
            result['message'] = 'تم اكتشاف وجه لكن لا توجد أصابع مرفوعة'
        
        print(f"النتيجة: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"خطأ: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'خطأ غير متوقع: {str(e)}'
        }), 500

def count_fingers(hand_landmarks):
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]
    
    fingers = 0
    
    for tip, pip in zip(finger_tips, finger_pips):
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
            fingers += 1
    
    thumb_tip = hand_landmarks.landmark[4]
    thumb_ip = hand_landmarks.landmark[3]
    thumb_mcp = hand_landmarks.landmark[2]
    
    if abs(thumb_tip.x - thumb_mcp.x) > 0.05:
        fingers += 1
    
    return fingers

@app.route('/add_face', methods=['POST'])
def add_face():
    try:
        data = request.get_json()
        name = data.get('name')
        image_b64 = data.get('image')
        
        if not name or not image_b64:
            return jsonify({'success': False, 'error': 'اسم وصورة مطلوبين'})
        
        image_bytes = base64.b64decode(image_b64)
        face_path = f"known_faces/{name}.jpg"
        
        with open(face_path, 'wb') as f:
            f.write(image_bytes)
        
        known_faces[name] = face_path
        
        return jsonify({
            'success': True,
            'message': f'تم إضافة وجه: {name}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)