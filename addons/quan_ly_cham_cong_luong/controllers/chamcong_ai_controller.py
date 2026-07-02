# -*- coding: utf-8 -*-
"""Controller cham cong AI - nhan dien khuon mat"""
import json
import logging
from datetime import datetime
import pytz
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)
ICT = pytz.timezone('Asia/Ho_Chi_Minh')


def now_utc():
    return datetime.utcnow().replace(tzinfo=None)


def to_ict(dt_utc):
    if not dt_utc:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = pytz.utc.localize(dt_utc)
    return dt_utc.astimezone(ICT)


class ChamCongAIController(http.Controller):

    @http.route('/cham_cong_ai', type='http', auth='user', website=False)
    def trang_cham_cong_ai(self, **kwargs):
        """Trang nhan dien khuon mat cham cong."""
        html = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cham Cong AI</title>
<style>
  :root{--g50:#F1FCF3;--g100:#DFF9E4;--g200:#C1F1CA;--g300:#9DE7AC;--g400:#59CF71;
    --g500:#33B44E;--g600:#25943C;--g700:#207532;--g800:#1E5D2C;--g900:#1B4C27;--g950:#092A11}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',system-ui,sans-serif;color:var(--g950);min-height:100vh;
    background:linear-gradient(160deg,#F1FCF3 0%,#DFF9E4 60%,#C1F1CA 100%)}
  .header{width:100%;background:linear-gradient(120deg,var(--g700),var(--g500));background-size:200% 200%;
    animation:shimmer 8s ease infinite;padding:16px 26px;display:flex;align-items:center;gap:13px;
    color:#fff;box-shadow:0 4px 24px rgba(32,117,50,.28)}
  @keyframes shimmer{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
  .header .logo{width:42px;height:42px;border-radius:13px;background:rgba(255,255,255,.18);
    display:flex;align-items:center;justify-content:center;font-size:1.5rem;backdrop-filter:blur(4px)}
  .header h1{font-size:1.4rem;font-weight:700;letter-spacing:.3px;text-shadow:0 1px 4px rgba(0,0,0,.15)}
  .clock{margin-left:auto;font-size:1.5rem;font-weight:800;background:rgba(255,255,255,.2);
    padding:6px 16px;border-radius:14px;letter-spacing:1px}
  .main{display:flex;gap:24px;padding:26px 24px;max-width:1100px;margin:0 auto;flex-wrap:wrap}
  .camera-panel{flex:1;min-width:360px}
  .info-panel{width:330px}
  .camera-box{position:relative;background:#fff;border-radius:20px;overflow:hidden;
    border:3px solid var(--g300);margin-bottom:14px;box-shadow:0 10px 36px rgba(37,148,60,.18)}
  #webcam{width:100%;display:block;transform:scaleX(-1)}
  .scan-line{position:absolute;left:0;right:0;height:3px;
    background:linear-gradient(90deg,transparent,var(--g400),transparent);
    box-shadow:0 0 12px var(--g400);animation:scan 2.4s linear infinite;pointer-events:none}
  @keyframes scan{0%{top:0}100%{top:100%}}
  .btn{padding:13px 24px;border:none;border-radius:13px;font-size:1rem;font-weight:700;
    cursor:pointer;transition:all 0.2s;width:100%;margin-top:10px;color:#fff}
  .btn-scan{background:linear-gradient(135deg,var(--g500),var(--g600));box-shadow:0 5px 16px rgba(37,148,60,.32)}
  .btn-checkin{background:linear-gradient(135deg,var(--g400),var(--g500));box-shadow:0 5px 16px rgba(51,180,78,.32)}
  .btn-checkout{background:linear-gradient(135deg,#F0A93B,#E08A1E);box-shadow:0 5px 16px rgba(224,138,30,.3)}
  .btn:hover{transform:translateY(-2px);filter:brightness(1.05);box-shadow:0 9px 24px rgba(37,148,60,.35)}
  .btn:disabled{opacity:.45;cursor:not-allowed;transform:none;filter:none}
  .card{background:#fff;border-radius:18px;padding:20px;border:1px solid var(--g200);margin-bottom:16px;
    box-shadow:0 6px 22px rgba(37,148,60,.10)}
  .card h3{font-size:.8rem;color:var(--g600);text-transform:uppercase;letter-spacing:1.2px;
    font-weight:700;margin-bottom:12px}
  .nv-name{font-size:1.3rem;font-weight:800;text-align:center;color:var(--g700)}
  .nv-detail{font-size:.85rem;color:var(--g600);text-align:center;margin-top:4px}
  .conf-bar{height:9px;background:var(--g100);border-radius:5px;overflow:hidden;margin:10px 0}
  .conf-fill{height:100%;border-radius:5px;transition:width .6s;
    background:linear-gradient(90deg,var(--g400),var(--g600))}
  .log-list{max-height:260px;overflow-y:auto}
  .log-item{padding:11px;border-radius:10px;margin-bottom:7px;
    background:var(--g50);border-left:4px solid var(--g400);font-size:.85rem}
  .log-item.ci{border-left-color:var(--g500)}
  .log-item.co{border-left-color:#E08A1E}
  .log-time{font-weight:800;color:var(--g600)}
  .log-item.ci .log-time{color:var(--g500)}
  .log-item.co .log-time{color:#E08A1E}
  .idle{color:#7a9c84;text-align:center;padding:16px;font-size:.95rem}
  .scanning{color:var(--g600);text-align:center;font-weight:700;animation:pulse 1s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
  .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.75rem;font-weight:700}
  .b-ok{background:var(--g100);color:var(--g600)}
  .b-err{background:#fde8ee;color:#e53170}
  #status{text-align:center;padding:10px;border-radius:10px;margin:8px 0;font-size:.9rem;
    background:var(--g50);font-weight:600}
</style>
</head>
<body>
<div class="header">
  <div class="logo">&#129302;</div>
  <h1>Chấm Công AI &mdash; Nhận Diện Khuôn Mặt</h1>
  <div class="clock" id="clock">00:00:00</div>
</div>
<div class="main">
  <div class="camera-panel">
    <div class="camera-box">
      <video id="webcam" autoplay playsinline></video>
      <div class="scan-line"></div>
    </div>
    <div id="status" class="idle">&#128247; Nhan nut de nhan dien khuon mat</div>
    <button class="btn btn-scan" onclick="scanFace()">&#128269; Nhan Dien</button>
    <button class="btn btn-checkin" id="btn-ci" onclick="doAction('checkin')" disabled>&#9989; Check-In</button>
    <button class="btn btn-checkout" id="btn-co" onclick="doAction('checkout')" disabled>&#128682; Check-Out</button>
  </div>
  <div class="info-panel">
    <div class="card">
      <h3>&#128100; Ket qua nhan dien</h3>
      <div id="rec-result"><div class="idle">Chua nhan dien</div></div>
    </div>
    <div class="card">
      <h3>&#128203; Log hom nay</h3>
      <div class="log-list" id="log-list"><div class="idle">Chua co log</div></div>
    </div>
  </div>
</div>
<script>
let recognizedNV = null;
function updateClock(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString('vi-VN',{hour12:false});
}
setInterval(updateClock,1000);updateClock();

async function initCamera(){
  try{
    const s=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480,facingMode:'user'}});
    document.getElementById('webcam').srcObject=s;
  }catch(e){
    setStatus('Khong mo duoc camera: '+e.message,'#ff6b6b');
  }
}

function captureFrame(){
  const v=document.getElementById('webcam');
  const c=document.createElement('canvas');
  c.width=v.videoWidth;c.height=v.videoHeight;
  const ctx=c.getContext('2d');
  ctx.translate(c.width,0);ctx.scale(-1,1);
  ctx.drawImage(v,0,0);
  return c.toDataURL('image/jpeg',0.85);
}

function setStatus(msg,color){
  const el=document.getElementById('status');
  el.textContent=msg;el.style.color=color||'#25943C';
}

async function scanFace(){
  recognizedNV=null;
  document.getElementById('btn-ci').disabled=true;
  document.getElementById('btn-co').disabled=true;
  document.getElementById('rec-result').innerHTML='<div class="scanning">&#9203; Dang xu ly...</div>';
  setStatus('Đang nhận diện...','#25943C');
  const img=captureFrame();
  try{
    const r=await fetch('/nhan_su/nhan_dien_khuon_mat',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{image_data:img}})
    });
    const d=await r.json();
    const res=d.result||{};
    if(res.success){
      recognizedNV=res;
      const conf=Math.min(100,Math.max(0,res.confidence||0));
      document.getElementById('rec-result').innerHTML=`
        <div class="nv-name">${res.ho_va_ten}</div>
        <div class="nv-detail">Ma: ${res.ma_dinh_danh} &bull; ${res.chuc_vu}</div>
        <div style="margin:10px 0">
          <div style="font-size:.8rem;color:#25943C;margin-bottom:4px">Độ tin cậy: ${conf.toFixed(1)}%</div>
          <div class="conf-bar"><div class="conf-fill" style="width:${conf}%"></div></div>
        </div>
        <span class="badge b-ok">&#9989; Đã xác nhận</span>`;
      setStatus('Nhận diện thành công!','#25943C');
      document.getElementById('btn-ci').disabled=false;
      document.getElementById('btn-co').disabled=false;
      loadLog(res.nhan_vien_id);
    }else{
      document.getElementById('rec-result').innerHTML=
        `<div class="idle" style="color:#ff6b6b">&#10060; ${res.error||'Khong nhan dien duoc'}</div>
         <span class="badge b-err">That bai</span>`;
      setStatus(res.error||'Khong nhan dien duoc','#ff6b6b');
    }
  }catch(e){setStatus('Loi: '+e.message,'#ff6b6b');}
}

async function doAction(action){
  if(!recognizedNV)return;
  const r=await fetch('/cham_cong_ai/check_action',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{nhan_vien_id:recognizedNV.nhan_vien_id,action:action}})
  });
  const d=await r.json();
  const res=d.result||{};
  if(res.success){
    addLog(action==='checkin'?'ci':'co',recognizedNV.ho_va_ten,res.time,res.message);
    setStatus(res.message,action==='checkin'?'#25943C':'#E08A1E');
  }else{
    setStatus('Loi: '+(res.error||''),'#ffb347');
  }
}

async function loadLog(nvId){
  const r=await fetch('/cham_cong_ai/log_hom_nay',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{nhan_vien_id:nvId}})
  });
  const d=await r.json();
  const res=d.result||{};
  if(res.success&&res.logs){
    const el=document.getElementById('log-list');
    el.innerHTML=res.logs.length===0?'<div class="idle">Chua co log hom nay</div>':
      res.logs.map(l=>`<div class="log-item ${l.type}">
        <span class="log-time">${l.time}</span> &bull; ${l.name}
        ${l.note?`<br><small style="color:#7a9c84">${l.note}</small>`:''}
      </div>`).join('');
  }
}

function addLog(type,name,time,note){
  const el=document.getElementById('log-list');
  if(el.querySelector('.idle'))el.innerHTML='';
  const item=document.createElement('div');
  item.className='log-item '+type;
  item.innerHTML=`<span class="log-time">${time||new Date().toLocaleTimeString('vi-VN')}</span> &bull; ${name}
    ${note?`<br><small style="color:#7a9c84">${note}</small>`:''}`;
  el.insertBefore(item,el.firstChild);
}

initCamera();
</script>
</body>
</html>"""
        return Response(html, content_type='text/html;charset=utf-8')

    @http.route('/cham_cong_ai/check_action', type='json', auth='user', methods=['POST'])
    def check_action(self, nhan_vien_id, action, **kwargs):
        """Xu ly check-in/out tu AI."""
        try:
            nv = request.env['nhan_vien'].sudo().browse(int(nhan_vien_id))
            if not nv.exists():
                return {'success': False, 'error': 'Khong tim thay nhan vien'}

            today = fields.Date.today()
            now = now_utc()
            local_now = to_ict(now)

            if action == 'checkin':
                existing = request.env['hr_cham_cong'].sudo().search([
                    ('nhan_vien_id', '=', nv.id),
                    ('ngay_cham_cong', '=', today),
                ], limit=1)
                if existing:
                    if existing.gio_vao and now < existing.gio_vao:
                        existing.sudo().write({'gio_vao': now})
                        msg = "Cap nhat check-in som hon: " + local_now.strftime('%H:%M:%S')
                    elif existing.gio_vao:
                        msg = "Da check-in tu " + to_ict(existing.gio_vao).strftime('%H:%M') + " - giu nguyen"
                    else:
                        existing.sudo().write({'gio_vao': now, 'trang_thai': 'di_lam'})
                        msg = "Check-in luc " + local_now.strftime('%H:%M:%S')
                else:
                    request.env['hr_cham_cong'].sudo().create({
                        'nhan_vien_id': nv.id,
                        'ngay_cham_cong': today,
                        'trang_thai': 'di_lam',
                        'gio_vao': now,
                        'nguoi_xac_nhan': 'AI Face Recognition',
                    })
                    msg = "Check-in luc " + local_now.strftime('%H:%M:%S')
                nv.send_telegram_notification(
                    "<b>CHECK-IN AI</b>\nNhan vien: <b>" + nv.ho_va_ten + "</b>\nGio: " +
                    local_now.strftime('%H:%M:%S') + "\nNgay: " + today.strftime('%d/%m/%Y')
                )
                return {'success': True, 'time': local_now.strftime('%H:%M:%S'), 'message': msg}

            elif action == 'checkout':
                existing = request.env['hr_cham_cong'].sudo().search([
                    ('nhan_vien_id', '=', nv.id),
                    ('ngay_cham_cong', '=', today),
                    ('trang_thai', '=', 'di_lam'),
                ], limit=1)
                if not existing:
                    return {'success': False, 'error': 'Chua check-in hom nay!'}
                if existing.gio_ra and now <= existing.gio_ra:
                    msg = "Da check-out luc " + to_ict(existing.gio_ra).strftime('%H:%M') + " - giu nguyen"
                else:
                    existing.sudo().write({'gio_ra': now})
                    msg = "Check-out luc " + local_now.strftime('%H:%M:%S')
                nv.send_telegram_notification(
                    "<b>CHECK-OUT AI</b>\nNhan vien: <b>" + nv.ho_va_ten + "</b>\nGio: " +
                    local_now.strftime('%H:%M:%S') + "\nNgay: " + today.strftime('%d/%m/%Y')
                )
                return {'success': True, 'time': local_now.strftime('%H:%M:%S'), 'message': msg}

            return {'success': False, 'error': 'Action khong hop le'}
        except Exception as e:
            _logger.error("Check action error: %s", e)
            return {'success': False, 'error': str(e)}

    @http.route('/cham_cong_ai/log_hom_nay', type='json', auth='user', methods=['POST'])
    def log_hom_nay(self, nhan_vien_id, **kwargs):
        """Lay log cham cong hom nay."""
        try:
            today = fields.Date.today()
            records = request.env['hr_cham_cong'].sudo().search([
                ('nhan_vien_id', '=', int(nhan_vien_id)),
                ('ngay_cham_cong', '=', today),
            ])
            logs = []
            for r in records:
                if r.gio_vao:
                    logs.append({
                        'type': 'ci',
                        'name': r.nhan_vien_id.ho_va_ten,
                        'time': to_ict(r.gio_vao).strftime('%H:%M:%S'),
                        'note': ("Gio cong: %.1fh" % r.so_gio_cong) if r.gio_ra else None,
                    })
                if r.gio_ra:
                    logs.append({
                        'type': 'co',
                        'name': r.nhan_vien_id.ho_va_ten,
                        'time': to_ict(r.gio_ra).strftime('%H:%M:%S'),
                        'note': ("OT: %.1fh" % r.so_gio_tang_ca) if r.gio_vao else None,
                    })
            return {'success': True, 'logs': logs}
        except Exception as e:
            return {'success': False, 'error': str(e)}
