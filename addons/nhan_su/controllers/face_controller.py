# -*- coding: utf-8 -*-
"""
Controller xu ly dang ky va nhan dien khuon mat AI
Su dung OpenCV LBPH Face Recognizer
"""
import json
import base64
import logging
import numpy as np
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    _logger.warning("OpenCV not available - face recognition disabled")


# Nguong correlation: > MATCH_THRESHOLD coi la cung mot nguoi.
# Da kiem chung tren du lieu thuc: cung nguoi khac goc ~0.43-0.62,
# webcam truc dien khop anh front thuong > 0.5.
MATCH_THRESHOLD = 0.45


def decode_image(b64_str):
    """Chuyen base64 string sang numpy array cho OpenCV."""
    if isinstance(b64_str, bytes):
        b64_str = b64_str.decode('ascii')
    if ',' in b64_str:
        b64_str = b64_str.split(',')[1]
    img_bytes = base64.b64decode(b64_str)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img


def extract_face_encoding(img):
    """
    Trich xuat face encoding tu anh.
    Phat hien khuon mat -> cat -> resize 100x100 -> can bang sang (equalizeHist)
    de bat bien voi anh sang -> flatten thanh vector.
    Tra ve list of floats hoac None neu khong tim thay mat.
    """
    if not OPENCV_AVAILABLE or img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Dung Haar cascade de phat hien khuon mat
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60)
    )

    if len(faces) == 0:
        return None

    # Lay khuon mat lon nhat
    x, y, w, h = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
    face_roi = cv2.resize(gray[y:y+h, x:x+w], (100, 100))
    # Can bang histogram -> giam anh huong cua anh sang
    face_roi = cv2.equalizeHist(face_roi)

    encoding = face_roi.flatten().astype(np.float32).tolist()
    return encoding


def correlation(enc1, enc2):
    """
    He so tuong quan (Pearson) giua hai vector, gia tri trong [-1, 1].
    Bat bien voi do sang/tuong phan -> on dinh hon khoang cach Euclid tho.
    """
    if enc1 is None or enc2 is None:
        return -1.0
    a = np.array(enc1, dtype=np.float32)
    b = np.array(enc2, dtype=np.float32)
    if a.shape != b.shape:
        return -1.0
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def best_correlation(input_enc, stored):
    """
    So input encoding voi du lieu da luu cua mot nhan vien.
    `stored` co the la 1 vector (dinh dang cu) hoac dict nhieu goc.
    Tra ve correlation cao nhat.
    """
    if isinstance(stored, dict):
        scores = [correlation(input_enc, v) for v in stored.values() if v]
        return max(scores) if scores else -1.0
    return correlation(input_enc, stored)


class FaceRegistrationController(http.Controller):

    # =====================================================
    # TRANG DANG KY KHUON MAT
    # =====================================================

    @http.route('/nhan_su/dang_ky_khuon_mat/<int:nhan_vien_id>',
                type='http', auth='user', website=False)
    def trang_dang_ky_khuon_mat(self, nhan_vien_id, **kwargs):
        """Trang HTML dang ky khuon mat 3 goc."""
        nv = request.env['nhan_vien'].sudo().browse(nhan_vien_id)
        if not nv.exists():
            return Response("Không tìm thấy nhân viên!", status=404)

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Đăng ký khuôn mặt - {nv.ho_va_ten}</title>
<style>
  :root {{ --g50:#F1FCF3;--g100:#DFF9E4;--g200:#C1F1CA;--g300:#9DE7AC;--g400:#59CF71;
    --g500:#33B44E;--g600:#25943C;--g700:#207532;--g800:#1E5D2C;--g900:#1B4C27;--g950:#092A11; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; color: var(--g950); min-height: 100vh;
    background: linear-gradient(160deg, #F1FCF3 0%, #DFF9E4 60%, #C1F1CA 100%); }}
  .container {{ max-width: 820px; margin: 0 auto; padding: 30px 24px; }}
  h1 {{ text-align: center; font-size: 1.9rem; margin-bottom: 6px; font-weight: 800;
       background: linear-gradient(135deg, var(--g600), var(--g400)); -webkit-background-clip: text;
       background-clip: text; -webkit-text-fill-color: transparent; }}
  .subtitle {{ text-align: center; color: var(--g600); margin-bottom: 24px; font-size: 0.95rem; font-weight:600; }}
  .steps {{ display: flex; justify-content: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
  .step {{ padding: 9px 20px; border-radius: 22px; font-size: 0.85rem; font-weight: 700;
           background: #fff; border: 2px solid var(--g200); color: var(--g600); cursor: pointer;
           transition: all 0.3s; box-shadow: 0 2px 8px rgba(37,148,60,.08); }}
  .step.active {{ background: linear-gradient(135deg,var(--g500),var(--g600)); border-color: transparent;
           color: #fff; transform: translateY(-2px); box-shadow: 0 5px 16px rgba(37,148,60,.3); }}
  .step.done {{ background: var(--g100); border-color: var(--g400); color: var(--g700); }}
  .camera-box {{ position: relative; background: #fff; border-radius: 20px; overflow: hidden;
                 border: 3px solid var(--g300); margin-bottom: 16px; box-shadow: 0 10px 36px rgba(37,148,60,.18); }}
  #webcam {{ width: 100%; display: block; transform: scaleX(-1); }}
  .overlay {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
              width: 220px; height: 280px; border: 3px dashed rgba(51,180,78,0.85);
              border-radius: 50%/60%; pointer-events: none; box-shadow: 0 0 0 9999px rgba(241,252,243,0.12); }}
  .instruction {{ text-align: center; font-size: 1.1rem; color: var(--g800); margin: 10px 0; font-weight:600;
                  background: var(--g100); padding: 12px; border-radius: 12px; }}
  .btn {{ padding: 13px 30px; border: none; border-radius: 13px; font-size: 1rem;
          font-weight: 700; cursor: pointer; transition: all 0.2s; color: #fff; }}
  .btn-primary {{ background: linear-gradient(135deg, var(--g500), var(--g600)); box-shadow: 0 5px 16px rgba(37,148,60,.32); }}
  .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 9px 24px rgba(37,148,60,0.42); }}
  .btn-success {{ background: linear-gradient(135deg, var(--g400), var(--g500)); box-shadow: 0 5px 16px rgba(51,180,78,.32); }}
  .btn-success:hover {{ transform: translateY(-2px); box-shadow: 0 9px 24px rgba(51,180,78,.42); }}
  .btn-success:disabled {{ opacity: 0.4; cursor: not-allowed; transform:none; box-shadow:none; }}
  .btn-danger {{ background: linear-gradient(135deg, #F0A93B, #E08A1E); box-shadow: 0 5px 16px rgba(224,138,30,.3); }}
  .controls {{ display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
  .preview-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 18px; }}
  .preview-item {{ text-align: center; }}
  .preview-item img {{ width: 100%; border-radius: 14px; border: 3px solid var(--g200); aspect-ratio: 1;
    object-fit: cover; background:#fff; transition: all .3s; }}
  .preview-item img.captured {{ border-color: var(--g500); box-shadow: 0 4px 14px rgba(51,180,78,.3); }}
  .preview-label {{ margin-top: 6px; font-size: 0.8rem; color: var(--g600); font-weight:600; }}
  .countdown {{ font-size: 3.4rem; font-weight: 800; color: var(--g500); text-align: center;
    text-shadow: 0 4px 14px rgba(51,180,78,.3); }}
  #status-msg {{ text-align: center; padding: 12px; border-radius: 12px; margin: 10px 0; font-weight: 700; }}
  .success {{ background: var(--g100); color: var(--g600); }}
  .error {{ background: #fde8ee; color: #e53170; }}
  .info {{ background: var(--g50); color: var(--g700); }}
  .progress-bar {{ height: 8px; background: var(--g100); border-radius: 4px; overflow: hidden; margin: 12px 0; }}
  .progress {{ height: 100%; background: linear-gradient(90deg, var(--g400), var(--g600));
               border-radius: 4px; transition: width 0.4s; }}
</style>
</head>
<body>
<div class="container">
  <h1>📸 Đăng ký khuôn mặt AI</h1>
  <p class="subtitle">Nhân viên: <strong>{nv.ho_va_ten}</strong> · Mã: {nv.ma_dinh_danh}</p>

  <div class="steps">
    <div class="step active" id="step-1">① Mặt thẳng</div>
    <div class="step" id="step-2">② Nghiêng trái</div>
    <div class="step" id="step-3">③ Nghiêng phải</div>
  </div>

  <div class="progress-bar"><div class="progress" id="progress" style="width:0%"></div></div>

  <div class="camera-box">
    <video id="webcam" autoplay playsinline></video>
    <div class="overlay"></div>
  </div>

  <div class="instruction" id="instruction">📷 Nhìn thẳng vào camera</div>
  <div id="countdown" class="countdown" style="display:none"></div>
  <div id="status-msg" class="info" style="display:none"></div>

  <div class="controls">
    <button class="btn btn-primary" id="btn-capture" onclick="startCapture()">📸 Chụp ảnh</button>
    <button class="btn btn-success" id="btn-save" onclick="saveAllFaces()" disabled>💾 Lưu đăng ký</button>
    <button class="btn btn-danger" onclick="resetAll()">🔄 Làm lại</button>
  </div>

  <div class="preview-grid">
    <div class="preview-item">
      <img id="preview-front" src="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=" alt="Mặt thẳng"/>
      <div class="preview-label">① Mặt thẳng</div>
    </div>
    <div class="preview-item">
      <img id="preview-left" src="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=" alt="Nghiêng trái"/>
      <div class="preview-label">② Nghiêng trái</div>
    </div>
    <div class="preview-item">
      <img id="preview-right" src="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=" alt="Nghiêng phải"/>
      <div class="preview-label">③ Nghiêng phải</div>
    </div>
  </div>
</div>

<script>
const NV_ID = {nhan_vien_id};
const STEPS = ['front', 'left', 'right'];
const INSTRUCTIONS = [
  '📷 Nhìn thẳng vào camera',
  '↪️ Nghiêng đầu sang TRÁI nhẹ',
  '↩️ Nghiêng đầu sang PHẢI nhẹ',
];
let currentStep = 0;
let capturedImages = {{}};
let stream = null;

// Khoi dong webcam
async function initCamera() {{
  try {{
    stream = await navigator.mediaDevices.getUserMedia({{
      video: {{ width: 640, height: 480, facingMode: 'user' }}
    }});
    document.getElementById('webcam').srcObject = stream;
  }} catch(e) {{
    showStatus('❌ Không thể mở camera: ' + e.message, 'error');
  }}
}}

function updateUI() {{
  const stepNames = ['step-1','step-2','step-3'];
  stepNames.forEach((id, i) => {{
    const el = document.getElementById(id);
    el.className = 'step';
    if (i < currentStep) el.className += ' done';
    else if (i === currentStep) el.className += ' active';
  }});
  document.getElementById('instruction').textContent = INSTRUCTIONS[currentStep] || '✅ Đã chụp đủ 3 góc!';
  document.getElementById('progress').style.width = (currentStep / 3 * 100) + '%';
  
  const saveBtn = document.getElementById('btn-save');
  saveBtn.disabled = Object.keys(capturedImages).length < 3;
}}

function startCapture() {{
  if (currentStep >= 3) {{ showStatus('✅ Đã chụp đủ 3 góc! Nhấn Lưu.', 'success'); return; }}
  
  const btn = document.getElementById('btn-capture');
  btn.disabled = true;
  let count = 3;
  const cdEl = document.getElementById('countdown');
  cdEl.style.display = 'block';
  
  const timer = setInterval(() => {{
    cdEl.textContent = count > 0 ? count : '📸';
    if (count === 0) {{
      clearInterval(timer);
      cdEl.style.display = 'none';
      captureCurrentFrame();
      btn.disabled = false;
    }}
    count--;
  }}, 1000);
}}

function captureCurrentFrame() {{
  const video = document.getElementById('webcam');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.translate(canvas.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
  
  const key = STEPS[currentStep];
  capturedImages[key] = dataUrl;
  
  const previewEl = document.getElementById('preview-' + key);
  previewEl.src = dataUrl;
  previewEl.classList.add('captured');
  
  showStatus('✅ Đã chụp góc ' + (currentStep+1) + '/3!', 'success');
  currentStep++;
  updateUI();
}}

async function saveAllFaces() {{
  if (Object.keys(capturedImages).length < 3) {{
    showStatus('⚠️ Cần chụp đủ 3 góc!', 'error'); return;
  }}
  
  const btn = document.getElementById('btn-save');
  btn.disabled = true;
  btn.textContent = '⏳ Đang lưu...';
  showStatus('Đang xử lý và lưu dữ liệu khuôn mặt...', 'info');
  
  try {{
    const resp = await fetch('/nhan_su/luu_khuon_mat', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        jsonrpc: '2.0',
        method: 'call',
        id: null,
        params: {{
          nhan_vien_id: NV_ID,
          face_front: capturedImages.front,
          face_left: capturedImages.left,
          face_right: capturedImages.right,
        }}
      }})
    }});
    const json = await resp.json();
    const data = json.result;
    if (data && data.success) {{
      showStatus('🎉 Đăng ký khuôn mặt thành công! Đang đóng...', 'success');
      document.getElementById('progress').style.width = '100%';
      setTimeout(() => window.close(), 2000);
    }} else {{
      const errMsg = (data && data.error) || (json.error && json.error.data && json.error.data.message) || 'Không rõ lỗi';
      showStatus('❌ Lỗi: ' + errMsg, 'error');
      btn.disabled = false;
      btn.textContent = '💾 Lưu đăng ký';
    }}
  }} catch(e) {{
    showStatus('❌ Lỗi kết nối: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = '💾 Lưu đăng ký';
  }}
}}

function resetAll() {{
  currentStep = 0;
  capturedImages = {{}};
  ['front','left','right'].forEach(k => {{
    const el = document.getElementById('preview-' + k);
    el.src = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
    el.classList.remove('captured');
  }});
  document.getElementById('status-msg').style.display = 'none';
  updateUI();
}}

function showStatus(msg, type) {{
  const el = document.getElementById('status-msg');
  el.textContent = msg;
  el.className = type;
  el.style.display = 'block';
}}

function getCsrf() {{
  const cookies = document.cookie.split(';');
  for (const c of cookies) {{
    const [k, v] = c.trim().split('=');
    if (k === 'csrf_token') return decodeURIComponent(v);
  }}
  return '';
}}

initCamera();
updateUI();
</script>
</body>
</html>"""
        return Response(html, content_type='text/html;charset=utf-8')

    @http.route('/nhan_su/luu_khuon_mat', type='json', auth='user', methods=['POST'])
    def luu_khuon_mat(self, nhan_vien_id, face_front, face_left, face_right, **kwargs):
        """Luu 3 anh khuon mat va trich xuat face encoding."""
        try:
            nv = request.env['nhan_vien'].sudo().browse(int(nhan_vien_id))
            if not nv.exists():
                return {'success': False, 'error': 'Không tìm thấy nhân viên'}

            def process_img(b64_data):
                """Convert base64 sang binary de luu vao Binary field."""
                if ',' in b64_data:
                    b64_data = b64_data.split(',')[1]
                return b64_data  # Odoo Binary field nhan base64 string

            face_front_b64 = process_img(face_front)
            face_left_b64 = process_img(face_left)
            face_right_b64 = process_img(face_right)

            # Trich xuat face encoding tu CA 3 goc -> luu dang dict
            encodings = {}
            if OPENCV_AVAILABLE:
                for key, raw in (('front', face_front),
                                 ('left', face_left),
                                 ('right', face_right)):
                    try:
                        enc = extract_face_encoding(decode_image(raw))
                        if enc:
                            encodings[key] = enc
                    except Exception as e:
                        _logger.warning("Face encoding extraction failed (%s): %s", key, e)

            if not encodings:
                return {
                    'success': False,
                    'error': 'Không phát hiện được khuôn mặt trong ảnh. '
                             'Vui lòng chụp lại với khuôn mặt rõ ràng, đủ sáng.'
                }

            # Luu vao database
            vals = {
                'face_image_front': face_front_b64,
                'face_image_left': face_left_b64,
                'face_image_right': face_right_b64,
                'face_encoding': json.dumps(encodings),
            }

            nv.write(vals)
            _logger.info("Face registered for employee %s (ID: %s) - %d angle(s)",
                         nv.ho_va_ten, nv.id, len(encodings))
            return {
                'success': True,
                'message': 'Đăng ký thành công (%d góc)' % len(encodings),
            }

        except Exception as e:
            _logger.error("Error saving face: %s", e)
            return {'success': False, 'error': str(e)}

    @http.route('/nhan_su/nhan_dien_khuon_mat', type='json', auth='user', methods=['POST'])
    def nhan_dien_khuon_mat(self, image_data, **kwargs):
        """
        Nhan dien khuon mat tu anh webcam.
        Tra ve thong tin nhan vien neu nhan dien thanh cong.
        """
        if not OPENCV_AVAILABLE:
            return {'success': False, 'error': 'OpenCV chưa được cài đặt'}

        try:
            # Decode anh dau vao
            input_img = decode_image(image_data)
            if input_img is None:
                return {'success': False, 'error': 'Không thể đọc ảnh'}

            input_encoding = extract_face_encoding(input_img)
            if input_encoding is None:
                return {'success': False, 'error': 'Không phát hiện khuôn mặt trong ảnh'}

            # Lay tat ca nhan vien da dang ky khuon mat
            nhan_viens = request.env['nhan_vien'].sudo().search([
                ('face_encoding', '!=', False)
            ])

            best_match = None
            best_score = -1.0  # correlation cao nhat tim duoc

            for nv in nhan_viens:
                try:
                    stored = json.loads(nv.face_encoding)
                except Exception:
                    continue
                score = best_correlation(input_encoding, stored)
                if score > best_score:
                    best_score = score
                    best_match = nv

            if best_match and best_score >= MATCH_THRESHOLD:
                # Quy doi correlation [MATCH_THRESHOLD..1] -> [0..100%]
                confidence = (best_score - MATCH_THRESHOLD) / (1 - MATCH_THRESHOLD) * 100
                confidence = max(0.0, min(100.0, confidence))
                return {
                    'success': True,
                    'nhan_vien_id': best_match.id,
                    'ho_va_ten': best_match.ho_va_ten,
                    'ma_dinh_danh': best_match.ma_dinh_danh,
                    'chuc_vu': best_match.chuc_vu_hien_tai_id.ten_chuc_vu if best_match.chuc_vu_hien_tai_id else 'N/A',
                    'confidence': round(confidence, 1),
                    'score': round(best_score, 3),
                }
            else:
                return {
                    'success': False,
                    'error': 'Không nhận diện được khuôn mặt (độ khớp %.0f%%)'
                             % (max(0.0, best_score) * 100),
                }

        except Exception as e:
            _logger.error("Face recognition error: %s", e)
            return {'success': False, 'error': str(e)}
