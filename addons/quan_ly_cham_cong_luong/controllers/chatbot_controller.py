# -*- coding: utf-8 -*-
"""HR Chatbot AI - tra loi cau hoi ve luong & thong tin cong ty bang Gemini."""
import json
import logging
import os
from datetime import datetime
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def _fmt(v):
    try:
        return "{:,.0f}".format(v).replace(",", ".") + " VND"
    except Exception:
        return str(v)


# Kien thuc co dinh ve cong ty & quy che luong (de chatbot tra loi chinh xac)
COMPANY_KB = """
THONG TIN CHUNG VE CONG TY:
- Ten cong ty: CONG TY CO PHAN CONG NGHE & DAO TAO FIT-DNU
- Gio lam viec: 08:00 - 17:30 (nghi trua 1 tieng). Lam du 8 tieng/ngay.
- Check-in sau 09:00 bi tinh di muon; check-out truoc 17:30 bi tinh ve som.

QUY CHE TINH LUONG:
- Luong theo gio = (Luong co ban / 208 gio) x So gio cong thuc te.
  (Quy chuan 1 thang = 26 ngay x 8 gio = 208 gio)
- Tang ca (OT) duoc tinh he so x1.5 don gia gio.
- Phat di muon/ve som: tinh theo so phut x don gia phat (mac dinh 2.000 VND/phut).
- Khen thuong: cong them vao luong. Ky luat: tru vao luong.

BAO HIEM TRICH DONG (theo luat lao dong Viet Nam):
- Nhan vien dong tong 10.5%: BHXH 8% + BHYT 1.5% + BHTN 1% (tru vao luong).
- Cong ty dong tong 21.5%: BHXH 17.5% + BHYT 3% + BHTN 1%.
- Tinh tren "muc luong dong bao hiem".

CONG THUC THUC LINH:
Thuc linh = Luong theo gio + Tien OT + Phu cap an trua + Phu cap trach nhiem
          + Tong thuong - Tong phat ky luat - Tien phat cham cong - BH nhan vien (10.5%)
"""


def _build_employee_context(nv):
    """Xay dung ngu canh du lieu rieng cua mot nhan vien."""
    lines = ["THONG TIN NHAN VIEN DANG HOI:"]
    lines.append(f"- Ho ten: {nv.ho_va_ten}")
    lines.append(f"- Ma dinh danh: {nv.ma_dinh_danh}")
    if nv.chuc_vu_hien_tai_id:
        lines.append(f"- Chuc vu: {nv.chuc_vu_hien_tai_id.ten_chuc_vu}")
    if nv.loai_hop_dong:
        loai = dict(nv._fields['loai_hop_dong'].selection).get(nv.loai_hop_dong)
        lines.append(f"- Loai hop dong: {loai}")
    if nv.ngay_ky_hop_dong_cty:
        lines.append(f"- Ngay ky hop dong: {nv.ngay_ky_hop_dong_cty.strftime('%d/%m/%Y')}")

    # Cau hinh luong
    lc = request.env['hr_luong_co_ban'].sudo().search(
        [('nhan_vien_id', '=', nv.id)], limit=1)
    if lc:
        lines.append("\nCAU HINH LUONG:")
        lines.append(f"- Luong co ban: {_fmt(lc.luong_co_ban)}")
        lines.append(f"- Luong dong bao hiem: {_fmt(lc.luong_dong_bh)}")
        lines.append(f"- Phu cap an trua: {_fmt(lc.phu_cap_an_trua)}")
        lines.append(f"- Phu cap trach nhiem: {_fmt(lc.phu_cap_trach_nhiem)}")

    # Phieu luong gan nhat (toi da 3 thang)
    payslips = request.env['hr_phieu_luong'].sudo().search(
        [('nhan_vien_id', '=', nv.id)], order='nam desc, thang desc', limit=3)
    if payslips:
        lines.append("\nPHIEU LUONG GAN DAY:")
        for pl in payslips:
            lines.append(
                f"- Thang {pl.thang}/{pl.nam}: gio cong {pl.tong_gio_cong:.1f}h, "
                f"OT {pl.tong_gio_ot:.1f}h, thuong {_fmt(pl.tong_thuong)}, "
                f"phat ky luat {_fmt(pl.tong_phat)}, phat cham cong {_fmt(pl.tong_phat_cham_cong)}, "
                f"BH nhan vien {_fmt(pl.tong_bh_nhan_vien)}, "
                f"THUC LINH {_fmt(pl.luong_thuc_linh)}")

    # Tom tat cham cong thang hien tai
    now = datetime.now()
    from datetime import date
    import calendar
    start = date(now.year, now.month, 1)
    end = date(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
    ccs = request.env['hr_cham_cong'].sudo().search([
        ('nhan_vien_id', '=', nv.id),
        ('ngay_cham_cong', '>=', start),
        ('ngay_cham_cong', '<=', end),
    ])
    if ccs:
        di_lam = sum(1 for c in ccs if c.trang_thai == 'di_lam')
        nghi = sum(1 for c in ccs if c.trang_thai != 'di_lam')
        tong_gio = sum(c.so_gio_cong for c in ccs)
        tong_phat = sum(c.tien_phat for c in ccs)
        lines.append(f"\nCHAM CONG THANG {now.month}/{now.year}:")
        lines.append(f"- So ngay di lam: {di_lam}, nghi: {nghi}")
        lines.append(f"- Tong gio cong: {tong_gio:.1f}h, tong tien phat cham cong: {_fmt(tong_phat)}")

    return "\n".join(lines)


def _build_manager_context():
    """Ngu canh tong hop cho quan ly (khong gan voi 1 nhan vien)."""
    lines = ["NGUOI HOI LA QUAN LY / ADMIN - co the xem du lieu toan cong ty."]
    nvs = request.env['nhan_vien'].sudo().search([])
    lines.append(f"\nTong so nhan vien: {len(nvs)}")
    now = datetime.now()
    payslips = request.env['hr_phieu_luong'].sudo().search(
        [('thang', '=', now.month), ('nam', '=', now.year)])
    if payslips:
        tong_quy = sum(p.luong_thuc_linh for p in payslips)
        lines.append(f"\nPHIEU LUONG THANG {now.month}/{now.year} ({len(payslips)} phieu):")
        for p in payslips:
            lines.append(f"- {p.nhan_vien_id.ho_va_ten}: thuc linh {_fmt(p.luong_thuc_linh)}")
        lines.append(f"=> Tong quy luong thuc linh: {_fmt(tong_quy)}")
    return "\n".join(lines)


class HRChatbotController(http.Controller):

    @http.route('/hr_chatbot', type='http', auth='user', website=False)
    def trang_chatbot(self, **kwargs):
        """Trang giao dien chatbot."""
        nv = request.env['nhan_vien'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1)
        ten = nv.ho_va_ten if nv else request.env.user.name
        html = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HR Chatbot AI</title>
<style>
  :root{--g50:#F1FCF3;--g100:#DFF9E4;--g200:#C1F1CA;--g300:#9DE7AC;--g400:#59CF71;
    --g500:#33B44E;--g600:#25943C;--g700:#207532;--g800:#1E5D2C;--g900:#1B4C27;--g950:#092A11}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',system-ui,sans-serif;color:var(--g950);height:100vh;
    display:flex;flex-direction:column;
    background:linear-gradient(160deg,#F1FCF3 0%,#DFF9E4 55%,#C1F1CA 100%)}
  .header{background:linear-gradient(120deg,var(--g700),var(--g500));background-size:200% 200%;
    animation:shimmer 8s ease infinite;padding:16px 26px;display:flex;align-items:center;gap:13px;
    box-shadow:0 4px 24px rgba(32,117,50,.28);color:#fff;position:relative;z-index:2}
  @keyframes shimmer{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
  .header .logo{width:42px;height:42px;border-radius:13px;background:rgba(255,255,255,.18);
    display:flex;align-items:center;justify-content:center;font-size:1.5rem;
    backdrop-filter:blur(4px);box-shadow:0 2px 10px rgba(0,0,0,.12)}
  .header h1{font-size:1.35rem;font-weight:700;letter-spacing:.3px;text-shadow:0 1px 4px rgba(0,0,0,.15)}
  .header .who{margin-left:auto;font-size:.85rem;background:rgba(255,255,255,.2);
    padding:6px 14px;border-radius:20px;font-weight:600}
  .chat{flex:1;overflow-y:auto;padding:26px 20px;max-width:920px;width:100%;margin:0 auto}
  .chat::-webkit-scrollbar{width:8px}
  .chat::-webkit-scrollbar-thumb{background:var(--g300);border-radius:4px}
  .msg{display:flex;gap:11px;margin-bottom:18px;align-items:flex-start;animation:fadeUp .35s ease}
  @keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
  .msg .avatar{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:1.1rem;flex-shrink:0;box-shadow:0 3px 10px rgba(37,148,60,.25)}
  .msg.bot .avatar{background:linear-gradient(135deg,var(--g500),var(--g700));color:#fff}
  .msg.user{flex-direction:row-reverse}
  .msg.user .avatar{background:#fff;border:2px solid var(--g300)}
  .bubble{padding:13px 17px;border-radius:16px;line-height:1.6;font-size:.95rem;max-width:78%;
    white-space:pre-wrap;word-wrap:break-word;box-shadow:0 4px 16px rgba(37,148,60,.10)}
  .msg.bot .bubble{background:#fff;border:1px solid var(--g200);border-top-left-radius:5px;color:var(--g950)}
  .msg.user .bubble{background:linear-gradient(135deg,var(--g500),var(--g600));color:#fff;border-top-right-radius:5px}
  .bubble h1,.bubble h2,.bubble h3{font-size:1rem;margin:6px 0}
  .bubble ul,.bubble ol{margin:6px 0 6px 20px}
  .bubble strong{color:var(--g600)}
  .msg.user .bubble strong{color:#fff}
  .bubble table{border-collapse:collapse;margin:6px 0;width:100%}
  .bubble td,.bubble th{border:1px solid var(--g200);padding:4px 8px;font-size:.85rem}
  .typing{color:var(--g600);font-style:italic}
  .suggestions{display:flex;gap:9px;flex-wrap:wrap;padding:0 20px 14px;max-width:920px;width:100%;margin:0 auto}
  .chip{background:#fff;border:1.5px solid var(--g300);color:var(--g700);padding:9px 15px;
    border-radius:22px;font-size:.83rem;font-weight:600;cursor:pointer;transition:all .2s;
    box-shadow:0 2px 8px rgba(37,148,60,.08)}
  .chip:hover{background:linear-gradient(135deg,var(--g500),var(--g600));color:#fff;
    border-color:transparent;transform:translateY(-2px);box-shadow:0 6px 16px rgba(37,148,60,.3)}
  .input-bar{display:flex;gap:10px;padding:16px 24px;background:rgba(255,255,255,.85);
    backdrop-filter:blur(10px);border-top:1px solid var(--g200);align-items:center;
    max-width:920px;width:100%;margin:0 auto;box-shadow:0 -4px 20px rgba(37,148,60,.07)}
  #q{flex:1;background:var(--g50);border:1.5px solid var(--g200);border-radius:24px;padding:13px 18px;
    color:var(--g950);font-size:.95rem;outline:none;transition:all .2s}
  #q:focus{border-color:var(--g500);box-shadow:0 0 0 3px rgba(51,180,78,.15)}
  #send{background:linear-gradient(135deg,var(--g500),var(--g600));border:none;border-radius:50%;
    width:48px;height:48px;cursor:pointer;color:#fff;font-size:1.2rem;flex-shrink:0;transition:all .2s;
    box-shadow:0 4px 14px rgba(37,148,60,.35)}
  #send:hover{transform:translateY(-2px) scale(1.05);box-shadow:0 7px 20px rgba(37,148,60,.45)}
  #send:disabled{opacity:.4;cursor:not-allowed;transform:none}
  #mic,#spk{background:#fff;border:1.5px solid var(--g200);border-radius:50%;
    width:48px;height:48px;cursor:pointer;font-size:1.15rem;flex-shrink:0;transition:all .2s}
  #mic:hover,#spk:hover{border-color:var(--g500);transform:translateY(-2px);box-shadow:0 5px 14px rgba(37,148,60,.2)}
  #mic.recording{background:linear-gradient(135deg,#ff5c5c,#e53170);border-color:transparent;
    color:#fff;animation:pulse 1.2s infinite}
  #spk.on{background:linear-gradient(135deg,var(--g500),var(--g600));border-color:transparent;color:#fff}
  @keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(229,49,112,.5)}
    50%{opacity:.85;box-shadow:0 0 0 8px rgba(229,49,112,0)}}
</style>
</head>
<body>
<div class="header">
  <div class="logo">&#129302;</div>
  <h1>HR Chatbot AI</h1>
  <div class="who">&#128100; __TEN__</div>
</div>
<div class="chat" id="chat">
  <div class="msg bot">
    <div class="avatar">&#129302;</div>
    <div class="bubble">Xin ch&agrave;o <strong>__TEN__</strong>! T&ocirc;i l&agrave; tr&#7907; l&yacute; HR AI.
Bạn c&oacute; thể hỏi t&ocirc;i về:
&bull; Lương, phụ cấp, bảo hiểm, thực lĩnh của bạn
&bull; Số giờ c&ocirc;ng, đi muộn, tăng ca trong th&aacute;ng
&bull; Quy chế lương, giờ l&agrave;m việc, ch&iacute;nh s&aacute;ch c&ocirc;ng ty
H&atilde;y đặt c&acirc;u hỏi b&ecirc;n dưới nh&eacute;!</div>
  </div>
</div>
<div class="suggestions" id="sugg">
  <div class="chip" onclick="ask(this.textContent)">Lương thực lĩnh tháng này của tôi là bao nhiêu?</div>
  <div class="chip" onclick="ask(this.textContent)">Tôi bị phạt đi muộn bao nhiêu tiền?</div>
  <div class="chip" onclick="ask(this.textContent)">Giải thích cách tính bảo hiểm của tôi</div>
  <div class="chip" onclick="ask(this.textContent)">Giờ làm việc của công ty thế nào?</div>
</div>
<div class="input-bar">
  <button id="mic" onclick="toggleMic()" title="Hỏi bằng giọng nói">&#127908;</button>
  <button id="spk" onclick="toggleSpeak()" title="Đọc câu trả lời (bật/tắt)">&#128264;</button>
  <input id="q" placeholder="Nhập câu hỏi hoặc bấm micro để nói..." autocomplete="off"
         onkeydown="if(event.key==='Enter')doSend()"/>
  <button id="send" onclick="doSend()">&#10148;</button>
</div>
<script>
const chat=document.getElementById('chat');
let history=[];          // luu lich su hoi thoai {role,text}
let speakOn=false;       // doc tra loi bang giong noi
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}
// markdown nhe -> html
function md(t){
  let h=esc(t);
  h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  h=h.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^## (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^[\-\*] (.+)$/gm,'&bull; $1');
  return h;
}
function addMsg(text,who){
  const m=document.createElement('div');m.className='msg '+who;
  m.innerHTML='<div class="avatar">'+(who==='bot'?'&#129302;':'&#128100;')+'</div>'+
              '<div class="bubble">'+(who==='bot'?md(text):esc(text))+'</div>';
  chat.appendChild(m);chat.scrollTop=chat.scrollHeight;
  return m;
}
function ask(t){document.getElementById('q').value=t;doSend();}

// ===== Doc tra loi bang giong noi (Text-to-Speech) =====
function speak(text){
  if(!speakOn || !('speechSynthesis' in window))return;
  window.speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(text.replace(/[*#]/g,''));
  u.lang='vi-VN';u.rate=1.0;
  const v=window.speechSynthesis.getVoices().find(x=>x.lang&&x.lang.startsWith('vi'));
  if(v)u.voice=v;
  window.speechSynthesis.speak(u);
}
function toggleSpeak(){
  speakOn=!speakOn;
  document.getElementById('spk').classList.toggle('on',speakOn);
  if(!speakOn && 'speechSynthesis' in window)window.speechSynthesis.cancel();
}

// ===== Hoi bang giong noi (Speech-to-Text) =====
let recog=null,recording=false;
function initMic(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){document.getElementById('mic').style.display='none';return;}
  recog=new SR();recog.lang='vi-VN';recog.interimResults=false;recog.maxAlternatives=1;
  recog.onresult=e=>{
    const txt=e.results[0][0].transcript;
    document.getElementById('q').value=txt;
    stopMic();doSend();
  };
  recog.onerror=()=>stopMic();
  recog.onend=()=>stopMic();
}
function stopMic(){recording=false;document.getElementById('mic').classList.remove('recording');}
function toggleMic(){
  if(!recog){alert('Trình duyệt không hỗ trợ nhận diện giọng nói. Hãy dùng Chrome/Edge.');return;}
  if(recording){recog.stop();stopMic();return;}
  recording=true;document.getElementById('mic').classList.add('recording');
  document.getElementById('q').placeholder='Đang nghe... hãy nói câu hỏi';
  try{recog.start();}catch(e){stopMic();}
}

async function doSend(){
  const inp=document.getElementById('q');
  const q=inp.value.trim();
  if(!q)return;
  inp.value='';inp.placeholder='Nhập câu hỏi hoặc bấm micro để nói...';
  document.getElementById('send').disabled=true;
  document.getElementById('sugg').style.display='none';
  addMsg(q,'user');
  history.push({role:'user',text:q});
  const t=addMsg('Đang suy nghĩ...','bot');
  t.querySelector('.bubble').classList.add('typing');
  try{
    const r=await fetch('/hr_chatbot/ask',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{question:q,history:history.slice(0,-1)}})
    });
    const d=await r.json();
    const res=d.result||{};
    t.remove();
    if(res.success){
      addMsg(res.answer,'bot');
      history.push({role:'bot',text:res.answer});
      if(history.length>20)history=history.slice(-20);
      speak(res.answer);
    }else{addMsg('Xin lỗi, có lỗi: '+(res.error||'không rõ'),'bot');}
  }catch(e){t.remove();addMsg('Lỗi kết nối: '+e.message,'bot');}
  document.getElementById('send').disabled=false;
  inp.focus();
}
initMic();
if('speechSynthesis' in window)window.speechSynthesis.getVoices();
</script>
</body>
</html>"""
        html = html.replace('__TEN__', ten)
        return Response(html, content_type='text/html;charset=utf-8')

    @http.route('/hr_chatbot/ask', type='json', auth='user', methods=['POST'])
    def ask(self, question, history=None, **kwargs):
        """Nhan cau hoi (kem lich su hoi thoai), xay dung ngu canh va goi Gemini."""
        if not GEMINI_AVAILABLE:
            return {'success': False, 'error': 'Thư viện AI chưa được cài đặt.'}
        question = (question or '').strip()
        if not question:
            return {'success': False, 'error': 'Câu hỏi trống.'}

        api_key = request.env['ir.config_parameter'].sudo().get_param('gemini_api_key') \
            or os.getenv('GEMINI_API_KEY')
        if not api_key:
            return {'success': False, 'error': 'Chưa cấu hình Gemini API Key.'}

        # Xac dinh nguoi hoi
        nv = request.env['nhan_vien'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1)
        is_manager = request.env.user.has_group(
            'quan_ly_cham_cong_luong.group_hr_quan_ly')

        if nv:
            context = _build_employee_context(nv)
        elif is_manager:
            context = _build_manager_context()
        else:
            context = "Khong tim thay ho so nhan vien gan voi tai khoan nay."

        # Dung lai lich su hoi thoai (toi da 8 luot gan nhat) de AI nho ngu canh
        history_text = ""
        if history and isinstance(history, list):
            recent = history[-8:]
            parts = []
            for h in recent:
                role = (h.get('role') or '').strip()
                text = (h.get('text') or '').strip()
                if not text:
                    continue
                who = 'Nguoi dung' if role == 'user' else 'Tro ly'
                parts.append(f"{who}: {text}")
            if parts:
                history_text = ("\n=== LICH SU HOI THOAI (de hieu ngu canh) ===\n"
                                + "\n".join(parts) + "\n")

        prompt = f"""Ban la tro ly nhan su (HR) AI cua cong ty FIT-DNU, tra loi bang TIENG VIET than thien, ngan gon, ro rang.

QUY TAC:
- CHI dua tren du lieu duoc cung cap ben duoi de tra loi. Khong bia so lieu.
- Neu nguoi dung hoi ve du lieu khong co, hay noi chua co thong tin va goi y ho lien he HR.
- Khi tra loi ve tien, dinh dang co dau cham phan cach (vd 15.000.000 VND).
- Co the dung markdown nhe (in dam **...**, gach dau dong).
- Dua vao LICH SU HOI THOAI de hieu cac cau hoi noi tiep (vd "con thang truoc thi sao?").
- Tuyet doi KHONG tiet lo thong tin luong rieng cua nhan vien khac (tru khi nguoi hoi la quan ly).

=== KIEN THUC CONG TY ===
{COMPANY_KB}

=== DU LIEU NGU CANH ===
{context}
{history_text}
=== CAU HOI HIEN TAI ===
{question}
"""
        try:
            genai.configure(api_key=api_key)
            configured = request.env['ir.config_parameter'].sudo().get_param('gemini_model')
            candidates = [m for m in [configured, 'gemini-2.5-flash',
                                      'gemini-2.0-flash', 'gemini-flash-latest'] if m]
            answer = None
            last_err = None
            for name in candidates:
                try:
                    model = genai.GenerativeModel(name)
                    resp = model.generate_content(prompt)
                    if resp and resp.text:
                        answer = resp.text.strip()
                        break
                except Exception as me:
                    last_err = me
                    continue
            if not answer:
                raise last_err or Exception("Khong nhan duoc tra loi")
            return {'success': True, 'answer': answer}
        except Exception as e:
            _logger.error("HR Chatbot error: %s", e)
            return {'success': False, 'error': str(e)}
