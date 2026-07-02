# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date
import json
import base64

_logger = logging.getLogger(__name__)


class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Bang chua thong tin nhan vien'
    _rec_name = 'ho_va_ten'
    _order = 'ten asc, tuoi desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Thong tin co ban ---
    ma_dinh_danh = fields.Char("Mã định danh", required=True)
    ho_ten_dem = fields.Char("Họ tên đệm", required=True)
    ten = fields.Char("Tên", required=True)
    ho_va_ten = fields.Char("Họ và tên", compute="_compute_ho_va_ten", store=True)
    ngay_sinh = fields.Date("Ngày sinh")
    que_quan = fields.Char("Quê quán")
    email = fields.Char("Email")
    so_dien_thoai = fields.Char("Số điện thoại")
    anh = fields.Binary("Ảnh")
    tuoi = fields.Integer("Tuổi", compute="_compute_tuoi", store=True)
    so_nguoi_bang_tuoi = fields.Integer(
        "Số người bằng tuổi",
        compute="_compute_so_nguoi_bang_tuoi",
        store=True
    )

    # --- Gioi tinh (MOI) ---
    gioi_tinh = fields.Selection([
        ('nam', 'Nam'),
        ('nu', 'Nữ'),
        ('khac', 'Khác'),
    ], string="Giới tính", default='nam')

    # --- Hop dong (MOI) ---
    ngay_ky_hop_dong_cty = fields.Date(
        "Ngày ký HĐ (Công ty)",
        help="Ngày công ty ký hợp đồng lao động"
    )
    ngay_ky_hop_dong_nv = fields.Date(
        "Ngày ký HĐ (Nhân viên)",
        help="Ngày nhân viên ký hợp đồng lao động"
    )
    loai_hop_dong = fields.Selection([
        ('khong_xac_dinh', 'Không xác định thời hạn'),
        ('xac_dinh_1nam', 'Xác định thời hạn 1 năm'),
        ('xac_dinh_2nam', 'Xác định thời hạn 2 năm'),
        ('xac_dinh_3nam', 'Xác định thời hạn 3 năm'),
        ('thu_viec', 'Thử việc'),
    ], string="Loại hợp đồng", default='xac_dinh_1nam')

    # --- Khuon mat AI (MOI) ---
    face_image_front = fields.Binary(
        "Ảnh mặt thẳng",
        attachment=True,
        help="Ảnh khuôn mặt nhìn thẳng để nhận diện AI"
    )
    face_image_left = fields.Binary(
        "Ảnh mặt trái",
        attachment=True,
        help="Ảnh khuôn mặt nghiêng trái"
    )
    face_image_right = fields.Binary(
        "Ảnh mặt phải",
        attachment=True,
        help="Ảnh khuôn mặt nghiêng phải"
    )
    face_encoding = fields.Text(
        "Face Encoding (JSON)",
        help="Dữ liệu encoding khuôn mặt dạng JSON, dùng cho nhận diện AI"
    )
    da_dang_ky_khuon_mat = fields.Boolean(
        "Đã đăng ký khuôn mặt",
        compute="_compute_da_dang_ky_khuon_mat",
        store=False
    )

    # --- Tai khoan Odoo lien ket ---
    user_id = fields.Many2one(
        'res.users',
        string="Tài khoản đăng nhập",
        ondelete='set null',
        copy=False,
        help="Tài khoản Odoo của nhân viên. Tự động tạo khi nhân viên có email."
    )

    # --- Thong tin Telegram ---
    telegram_chat_id = fields.Char(
        "Telegram Chat ID",
        help="ID người dùng Telegram để nhận thông báo tự động"
    )

    # --- Chuc vu hien tai ---
    chuc_vu_hien_tai_id = fields.Many2one(
        'chuc_vu',
        string="Chức vụ hiện tại",
        compute="_compute_chuc_vu_hien_tai",
        store=True,
    )
    phu_cap_trach_nhiem_tu_chuc_vu = fields.Float(
        "Phụ cấp trách nhiệm từ chức vụ",
        related="chuc_vu_hien_tai_id.phu_cap_trach_nhiem",
        store=True,
        readonly=True
    )

    # --- Quan he ---
    lich_su_cong_tac_ids = fields.One2many(
        "lich_su_cong_tac",
        inverse_name="nhan_vien_id",
        string="Lịch sử công tác"
    )
    danh_sach_chung_chi_bang_cap_ids = fields.One2many(
        "danh_sach_chung_chi_bang_cap",
        inverse_name="nhan_vien_id",
        string="Chứng chỉ, bằng cấp"
    )

    _sql_constraints = [
        ('ma_dinh_danh_unique', 'UNIQUE(ma_dinh_danh)', 'Mã định danh phải là duy nhất!')
    ]

    # =========================================
    # COMPUTED FIELDS
    # =========================================

    @api.depends("ho_ten_dem", "ten")
    def _compute_ho_va_ten(self):
        for rec in self:
            if rec.ho_ten_dem and rec.ten:
                rec.ho_va_ten = rec.ho_ten_dem + ' ' + rec.ten
            else:
                rec.ho_va_ten = rec.ten or rec.ho_ten_dem or ''

    @api.depends("ngay_sinh")
    def _compute_tuoi(self):
        for rec in self:
            if rec.ngay_sinh:
                rec.tuoi = date.today().year - rec.ngay_sinh.year
            else:
                rec.tuoi = 0

    @api.depends("tuoi")
    def _compute_so_nguoi_bang_tuoi(self):
        for rec in self:
            if rec.tuoi:
                others = self.env['nhan_vien'].search([
                    ('tuoi', '=', rec.tuoi),
                    ('ma_dinh_danh', '!=', rec.ma_dinh_danh)
                ])
                rec.so_nguoi_bang_tuoi = len(others)
            else:
                rec.so_nguoi_bang_tuoi = 0

    @api.depends("lich_su_cong_tac_ids", "lich_su_cong_tac_ids.chuc_vu_id",
                 "lich_su_cong_tac_ids.loai_chuc_vu")
    def _compute_chuc_vu_hien_tai(self):
        for rec in self:
            chuc_vu = None
            for ls in rec.lich_su_cong_tac_ids:
                if ls.loai_chuc_vu == 'Chinh' and ls.chuc_vu_id:
                    chuc_vu = ls.chuc_vu_id
                    break
            if not chuc_vu:
                for ls in rec.lich_su_cong_tac_ids:
                    if ls.chuc_vu_id:
                        chuc_vu = ls.chuc_vu_id
                        break
            rec.chuc_vu_hien_tai_id = chuc_vu

    def _compute_da_dang_ky_khuon_mat(self):
        for rec in self:
            rec.da_dang_ky_khuon_mat = bool(
                rec.face_image_front and rec.face_image_left and rec.face_image_right
            )

    # =========================================
    # ONCHANGE
    # =========================================

    @api.onchange("ten", "ho_ten_dem")
    def _default_ma_dinh_danh(self):
        for rec in self:
            if rec.ho_ten_dem and rec.ten:
                chu_cai_dau = ''.join([tu[0] for tu in rec.ho_ten_dem.lower().split() if tu])
                rec.ma_dinh_danh = rec.ten.lower() + chu_cai_dau

    # =========================================
    # CONSTRAINTS
    # =========================================

    @api.constrains('tuoi')
    def _check_tuoi(self):
        for rec in self:
            if rec.tuoi and rec.tuoi < 18:
                raise ValidationError("Tuổi không được bé hơn 18!")

    # =========================================
    # ACTIONS
    # =========================================

    def action_tao_tai_khoan(self):
        """Tao tai khoan Odoo cho nhan vien neu chua co."""
        for rec in self:
            if rec.user_id:
                raise UserError(
                    f"Nhân viên {rec.ho_va_ten} đã có tài khoản: {rec.user_id.login}"
                )
            if not rec.email:
                raise UserError(
                    f"Nhân viên {rec.ho_va_ten} chưa có email. Vui lòng nhập email trước."
                )
            existing = self.env['res.users'].search([('login', '=', rec.email)], limit=1)
            if existing:
                rec.user_id = existing
                continue
            group_employee = self.env.ref('quan_ly_cham_cong_luong.group_nhan_vien', raise_if_not_found=False)
            groups = [(4, group_employee.id)] if group_employee else []
            new_user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': rec.ho_va_ten,
                'login': rec.email,
                'email': rec.email,
                'groups_id': groups,
                'tz': 'Asia/Ho_Chi_Minh',
            })
            rec.user_id = new_user
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã tạo tài khoản thành công!',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_mo_dang_ky_khuon_mat(self):
        """Mo trang dang ky khuon mat."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/nhan_su/dang_ky_khuon_mat/{self.id}',
            'target': 'new',
        }

    def action_xoa_khuon_mat(self):
        """Xoa du lieu khuon mat."""
        self.ensure_one()
        self.write({
            'face_image_front': False,
            'face_image_left': False,
            'face_image_right': False,
            'face_encoding': False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đã xóa',
                'message': 'Đã xóa dữ liệu khuôn mặt!',
                'type': 'warning',
                'sticky': False,
            }
        }

    # =========================================
    # TELEGRAM
    # =========================================

    TELEGRAM_BOT_TOKEN = "8870304096:AAHQ-oC4HuttiSiaaXmPxCxzSN6PnQNmud4"

    def send_telegram_notification(self, message):
        """Gui tin nhan Telegram den nhan vien.

        Tra ve list (rec, ok, error) de ben goi biet ket qua that su.
        Khong raise de khong chan luong check-in/out neu loi.
        """
        import requests
        token = self.TELEGRAM_BOT_TOKEN
        results = []
        for rec in self:
            if not rec.telegram_chat_id:
                results.append((rec, False, "Chưa cấu hình Telegram Chat ID"))
                continue
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                'chat_id': rec.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                data = resp.json()
                if data.get('ok'):
                    results.append((rec, True, None))
                else:
                    err = data.get('description', 'Lỗi không xác định')
                    _logger.warning("Telegram send failed for %s (chat_id=%s): %s",
                                    rec.ho_va_ten, rec.telegram_chat_id, err)
                    results.append((rec, False, err))
            except Exception as e:
                _logger.warning("Telegram send exception for %s: %s", rec.ho_va_ten, e)
                results.append((rec, False, str(e)))
        return results

    def action_lay_chat_id_telegram(self):
        """Tu dong lay Telegram Chat ID:
        Nhan vien gui dung MA DINH DANH cua minh cho bot @odoovananhbot,
        he thong doc getUpdates va gan chat_id tuong ung.
        """
        self.ensure_one()
        import requests
        if not self.ma_dinh_danh:
            raise UserError("Nhân viên chưa có mã định danh!")
        token = self.TELEGRAM_BOT_TOKEN
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
            data = resp.json()
        except Exception as e:
            raise UserError(f"Không kết nối được Telegram: {e}")
        if not data.get('ok'):
            raise UserError(f"Lỗi Telegram: {data.get('description', data)}")

        found_chat_id = None
        ma = self.ma_dinh_danh.strip().lower()
        for upd in reversed(data.get('result', [])):
            msg = upd.get('message') or upd.get('edited_message') or {}
            text = (msg.get('text') or '').strip().lower()
            if text == ma and msg.get('chat', {}).get('id'):
                found_chat_id = str(msg['chat']['id'])
                break

        if not found_chat_id:
            raise UserError(
                "Chưa tìm thấy tin nhắn. Hãy yêu cầu nhân viên %s:\n"
                "1. Mở Telegram, tìm bot @odoovananhbot\n"
                "2. Bấm Start và gửi đúng mã định danh: '%s'\n"
                "3. Quay lại bấm nút này một lần nữa."
                % (self.ho_va_ten, self.ma_dinh_danh)
            )

        self.telegram_chat_id = found_chat_id
        # Gui xac nhan cho nhan vien
        self.send_telegram_notification(
            "✅ <b>Kết nối thành công!</b>\nBạn (%s) sẽ nhận được thông báo "
            "chấm công và phiếu lương qua đây." % self.ho_va_ten
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã lấy Chat ID (%s) cho %s!' % (found_chat_id, self.ho_va_ten),
                'type': 'success',
                'sticky': False,
            }
        }

    # =========================================
    # SYNC
    # =========================================

    def _sync_phu_cap_luong_co_ban(self):
        for rec in self:
            luong_base = self.env['hr_luong_co_ban'].search(
                [('nhan_vien_id', '=', rec.id)], limit=1
            )
            if luong_base and rec.chuc_vu_hien_tai_id:
                luong_base.phu_cap_trach_nhiem = rec.chuc_vu_hien_tai_id.phu_cap_trach_nhiem

    @api.model
    def create(self, vals):
        rec = super(NhanVien, self).create(vals)
        if rec.email:
            try:
                rec.action_tao_tai_khoan()
            except Exception:
                pass
        return rec

    def write(self, vals):
        res = super(NhanVien, self).write(vals)
        if 'lich_su_cong_tac_ids' in vals:
            self._sync_phu_cap_luong_co_ban()
        if 'email' in vals:
            for rec in self:
                if rec.email and not rec.user_id:
                    try:
                        rec.action_tao_tai_khoan()
                    except Exception:
                        pass
        return res
