# -*- coding: utf-8 -*-
import logging
import os
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

# So thang tuong ung voi tung loai hop dong (de tu tinh ngay ket thuc)
THOI_HAN_THANG = {
    'thu_viec': 2,
    'xac_dinh_1nam': 12,
    'xac_dinh_2nam': 24,
    'xac_dinh_3nam': 36,
    'khong_xac_dinh': 0,  # khong thoi han
}

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    _logger.warning("google-generativeai package not available - Gemini contract generation disabled")


class HRHopDong(models.Model):
    _name = 'hr_hop_dong'
    _description = 'Hop Dong Lao Dong AI'
    _rec_name = 'name'

    name = fields.Char("Tên hợp đồng", compute="_compute_name", store=True)
    nhan_vien_id = fields.Many2one('nhan_vien', string="Nhân viên", required=True, ondelete='cascade')
    gioi_tinh = fields.Selection(related='nhan_vien_id.gioi_tinh', string="Giới tính", readonly=True)
    email = fields.Char(related='nhan_vien_id.email', string="Email", readonly=True)
    so_dien_thoai = fields.Char(related='nhan_vien_id.so_dien_thoai', string="Số điện thoại", readonly=True)
    chuc_vu_id = fields.Many2one('chuc_vu', related='nhan_vien_id.chuc_vu_hien_tai_id', string="Chức vụ", readonly=True)

    loai_hop_dong = fields.Selection([
        ('khong_xac_dinh', 'Không xác định thời hạn'),
        ('xac_dinh_1nam', 'Xác định thời hạn 1 năm'),
        ('xac_dinh_2nam', 'Xác định thời hạn 2 năm'),
        ('xac_dinh_3nam', 'Xác định thời hạn 3 năm'),
        ('thu_viec', 'Thử việc'),
    ], string="Loại hợp đồng", default='xac_dinh_1nam', required=True)

    ngay_bat_dau = fields.Date("Ngày bắt đầu làm việc", required=True, default=fields.Date.context_today)
    ngay_ket_thuc = fields.Date("Ngày kết thúc hợp đồng")
    luong_thoa_thuan = fields.Float("Mức lương thỏa thuận (VND)", required=True, default=0.0)
    
    noi_dung_hop_dong = fields.Html("Nội dung hợp đồng (AI soạn thảo)")
    trang_thai = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirmed', 'Đã ký kết'),
    ], string="Trạng thái", default='draft', required=True)

    @api.depends('nhan_vien_id', 'loai_hop_dong')
    def _compute_name(self):
        for rec in self:
            if rec.nhan_vien_id:
                rec.name = f"HĐLD_{rec.nhan_vien_id.ho_va_ten}_{dict(self._fields['loai_hop_dong'].selection).get(rec.loai_hop_dong)}"
            else:
                rec.name = "Hợp đồng lao động mới"

    @api.onchange('loai_hop_dong', 'ngay_bat_dau')
    def _onchange_tu_tinh_ngay_ket_thuc(self):
        """Tu tinh ngay ket thuc theo loai hop dong (tru loai khong xac dinh)."""
        for rec in self:
            if not rec.ngay_bat_dau:
                continue
            so_thang = THOI_HAN_THANG.get(rec.loai_hop_dong, 0)
            if so_thang > 0:
                rec.ngay_ket_thuc = rec.ngay_bat_dau + relativedelta(months=so_thang, days=-1)
            else:
                # Hop dong khong xac dinh thoi han -> khong co ngay ket thuc
                rec.ngay_ket_thuc = False

    @api.constrains('luong_thoa_thuan')
    def _check_luong(self):
        for rec in self:
            if rec.luong_thoa_thuan < 0:
                raise ValidationError("Mức lương thỏa thuận không được âm!")

    @api.constrains('ngay_bat_dau', 'ngay_ket_thuc', 'loai_hop_dong')
    def _check_ngay_hop_dong(self):
        for rec in self:
            if rec.ngay_ket_thuc and rec.ngay_bat_dau and rec.ngay_ket_thuc < rec.ngay_bat_dau:
                raise ValidationError("Ngày kết thúc hợp đồng phải sau ngày bắt đầu!")
            # Hop dong xac dinh thoi han bat buoc co ngay ket thuc
            if rec.loai_hop_dong != 'khong_xac_dinh' and not rec.ngay_ket_thuc:
                raise ValidationError(
                    "Hợp đồng '%s' phải có ngày kết thúc!"
                    % dict(self._fields['loai_hop_dong'].selection).get(rec.loai_hop_dong)
                )

    def action_generate_contract_ai(self):
        """Su dung Gemini API de tu dong soan hop dong lao dong chuan phap ly."""
        self.ensure_one()
        if not GEMINI_AVAILABLE:
            raise UserError("Thư viện google-generativeai chưa được cài đặt trên server!")

        # Lay API Key tu Odoo System Parameters hoac environment variable
        api_key = self.env['ir.config_parameter'].sudo().get_param('gemini_api_key') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise UserError("Vui lòng cấu hình Gemini API Key trong System Parameters với key 'gemini_api_key'!")

        # Chuan bi du lieu de gui Gemini
        nv = self.nhan_vien_id
        gender_str = "Ông" if nv.gioi_tinh == 'nam' else ("Bà" if nv.gioi_tinh == 'nu' else "Anh/Chị")
        chuc_vu_str = nv.chuc_vu_hien_tai_id.ten_chuc_vu if nv.chuc_vu_hien_tai_id else "Nhân viên"
        loai_hd_str = dict(self._fields['loai_hop_dong'].selection).get(self.loai_hop_dong)
        ngay_bd_str = self.ngay_bat_dau.strftime('%d/%m/%Y')
        ngay_kt_str = self.ngay_ket_thuc.strftime('%d/%m/%Y') if self.ngay_ket_thuc else "Không thời hạn"
        luong_str = "{:,.0f}".format(self.luong_thoa_thuan).replace(",", ".") + " VND"

        prompt = f"""
        Hãy soạn thảo một Hợp đồng Lao động bằng Tiếng Việt chuẩn mực, chuyên nghiệp và có giá trị pháp lý theo luật lao động Việt Nam hiện hành.
        Yêu cầu trả về định dạng HTML sạch (chỉ dùng các thẻ basic như <h3>, <p>, <ul>, <li>, <strong>, <table>, <tr>, <td>, không có codeblock ```html hay markdown ```).

        Thông tin cụ thể của hợp đồng:
        - Tên đơn vị sử dụng lao động: CÔNG TY CỔ PHẦN CÔNG NGHỆ & ĐÀO TẠO FIT-DNU
        - Đại diện người sử dụng lao động: Ông Nguyễn Văn A - Chức vụ: Giám đốc
        - Người lao động ({gender_str}): {nv.ho_va_ten}
        - Ngày sinh: {nv.ngay_sinh.strftime('%d/%m/%Y') if nv.ngay_sinh else 'N/A'}
        - Quê quán: {nv.que_quan or 'N/A'}
        - Email: {nv.email or 'N/A'}
        - Số điện thoại: {nv.so_dien_thoai or 'N/A'}
        - Chức danh chuyên môn / Chức vụ: {chuc_vu_str}
        - Loại hợp đồng: {loai_hd_str}
        - Thời hạn hợp đồng: Từ ngày {ngay_bd_str} đến ngày {ngay_kt_str}
        - Mức lương chính thỏa thuận: {luong_str}

        Cấu trúc hợp đồng cần bao gồm các điều khoản cơ bản:
        1. Điều 1: Công việc, địa điểm làm việc và thời hạn hợp đồng
        2. Điều 2: Chế độ làm việc
        3. Điều 3: Nghĩa vụ và các quyền lợi của người lao động (Lương {luong_str}, bảo hiểm trích đóng theo luật định, phụ cấp ăn trưa và trách nhiệm nếu có)
        4. Điều 4: Nghĩa vụ và quyền hạn của người sử dụng lao động
        5. Điều 5: Điều khoản thi hành
        """

        try:
            genai.configure(api_key=api_key)
            # Thu lan luot cac model hien hanh (model cu nhu gemini-1.5-flash
            # da bi Google ngung ho tro). Cho phep tuy chinh qua System Parameter.
            configured_model = self.env['ir.config_parameter'].sudo().get_param('gemini_model')
            model_candidates = [m for m in [
                configured_model,
                'gemini-2.5-flash',
                'gemini-2.0-flash',
                'gemini-flash-latest',
            ] if m]

            response = None
            last_err = None
            for model_name in model_candidates:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        break
                except Exception as me:
                    last_err = me
                    _logger.warning("Gemini model %s failed: %s", model_name, me)
                    continue

            if response is None and last_err is not None:
                raise last_err

            if response and response.text:
                # Xoa cac ky tu block code ```html hoac ``` markdown neu co
                text = response.text.strip()
                if text.startswith("```html"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                self.write({
                    'noi_dung_hop_dong': text.strip()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Thành công',
                        'message': 'Đã tạo nội dung hợp đồng bằng AI thành công!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError("Gemini không trả về kết quả soạn thảo.")
        except Exception as e:
            _logger.error("Gemini contract generation failed: %s", e)
            raise UserError(f"Lỗi khi kết nối với Gemini AI: {str(e)}")

    def action_confirm_contract(self):
        """Xac nhan ky ket hop dong va dong bo du lieu sang cac bang lien quan."""
        self.ensure_one()

        # --- Kiem tra du lieu truoc khi ky ---
        if not self.nhan_vien_id:
            raise UserError("Hợp đồng chưa gắn nhân viên!")
        if self.luong_thoa_thuan <= 0:
            raise UserError(
                "Vui lòng nhập mức lương thỏa thuận (> 0) trước khi ký kết, "
                "để hệ thống đồng bộ sang cấu hình lương và tính lương được."
            )
        if self.loai_hop_dong != 'khong_xac_dinh' and not self.ngay_ket_thuc:
            raise UserError("Hợp đồng xác định thời hạn phải có ngày kết thúc!")

        self.write({'trang_thai': 'confirmed'})

        nv = self.nhan_vien_id
        ngay_ky = fields.Date.context_today(self)

        # --- 1. Dong bo thong tin hop dong sang ho so nhan vien ---
        nv.sudo().write({
            'loai_hop_dong': self.loai_hop_dong,
            'ngay_ky_hop_dong_cty': ngay_ky,
            'ngay_ky_hop_dong_nv': ngay_ky,
        })

        # --- 2. Tao/cap nhat cau hinh luong co ban (de tinh luong) ---
        phu_cap_tn = (nv.chuc_vu_hien_tai_id.phu_cap_trach_nhiem
                      if nv.chuc_vu_hien_tai_id else 0.0)
        luong_base = self.env['hr_luong_co_ban'].sudo().search(
            [('nhan_vien_id', '=', nv.id)], limit=1)
        if luong_base:
            # Cap nhat muc luong theo hop dong, giu cac cau hinh khac
            luong_vals = {
                'luong_co_ban': self.luong_thoa_thuan,
                'phu_cap_trach_nhiem': phu_cap_tn,
            }
            # Luong dong BH mac dinh bang luong co ban neu chua duoc dat rieng
            if not luong_base.luong_dong_bh:
                luong_vals['luong_dong_bh'] = self.luong_thoa_thuan
            luong_base.write(luong_vals)
            luong_action = "cập nhật"
        else:
            self.env['hr_luong_co_ban'].sudo().create({
                'nhan_vien_id': nv.id,
                'luong_co_ban': self.luong_thoa_thuan,
                'luong_dong_bh': self.luong_thoa_thuan,
                'phu_cap_trach_nhiem': phu_cap_tn,
            })
            luong_action = "tạo mới"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Ký kết thành công',
                'message': 'Đã ký hợp đồng, đồng bộ hồ sơ nhân viên và %s cấu hình '
                           'lương (lương cơ bản: %s VND). Bạn có thể tính lương ngay.'
                           % (luong_action,
                              "{:,.0f}".format(self.luong_thoa_thuan).replace(",", ".")),
                'type': 'success',
                'sticky': False,
            }
        }
