# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, date
import calendar

class HRPhieuLuong(models.Model):
    _name = 'hr_phieu_luong'
    _description = 'Phiếu lương tháng nhân viên'
    _rec_name = 'nhan_vien_id'

    nhan_vien_id = fields.Many2one('nhan_vien', string="Nhân viên", required=True)
    thang = fields.Integer("Tháng", required=True, default=lambda self: datetime.now().month)
    nam = fields.Integer("Năm", required=True, default=lambda self: datetime.now().year)
    
    # Các trường tổng hợp giờ công & ngày công quy đổi
    tong_gio_cong = fields.Float("Tổng giờ công thực tế", compute="_compute_du_lieu_luong", store=True)
    so_ngay_cong = fields.Float("Số ngày công quy đổi (8h/ngày)", compute="_compute_du_lieu_luong", store=True)
    
    # Cấu hình lương lấy từ Cấu hình lương gốc
    luong_co_ban = fields.Float("Lương cơ bản (VND)", compute="_compute_du_lieu_luong", store=True)
    phu_cap_an_trua = fields.Float("Phụ cấp ăn trưa (VND)", compute="_compute_du_lieu_luong", store=True)
    phu_cap_trach_nhiem = fields.Float("Phụ cấp trách nhiệm (VND)", compute="_compute_du_lieu_luong", store=True)
    
    # Chi tiết tính lương giờ công & tăng ca
    luong_theo_gio = fields.Float("Lương tính theo giờ (VND)", compute="_compute_du_lieu_luong", store=True)
    tong_gio_ot = fields.Float("Tổng giờ tăng ca (OT)", compute="_compute_du_lieu_luong", store=True)
    luong_ot = fields.Float("Tiền tăng ca (OT) (VND)", compute="_compute_du_lieu_luong", store=True)
    
    # Biến động thu nhập
    tong_thuong = fields.Float("Tổng thưởng (VND)", compute="_compute_du_lieu_luong", store=True)
    tong_phat = fields.Float("Tổng phạt kỷ luật (VND)", compute="_compute_du_lieu_luong", store=True)
    tong_phat_cham_cong = fields.Float("Tổng phạt đi muộn/về sớm (VND)", compute="_compute_du_lieu_luong", store=True)
    
    # Bảo hiểm trích đóng
    luong_dong_bh = fields.Float("Mức lương đóng BH (VND)", compute="_compute_du_lieu_luong", store=True)
    
    # Chi tiết phần nhân viên chịu (10.5%)
    bhxh_nhan_vien = fields.Float("BHXH nhân viên (8%)", compute="_compute_du_lieu_luong", store=True)
    bhyt_nhan_vien = fields.Float("BHYT nhân viên (1.5%)", compute="_compute_du_lieu_luong", store=True)
    bhtn_nhan_vien = fields.Float("BHTN nhân viên (1%)", compute="_compute_du_lieu_luong", store=True)
    tong_bh_nhan_vien = fields.Float("Tổng BH nhân viên đóng (10.5%)", compute="_compute_du_lieu_luong", store=True)
    
    # Chi tiết phần doanh nghiệp chịu (21.5%)
    bhxh_cong_ty = fields.Float("BHXH công ty (17.5%)", compute="_compute_du_lieu_luong", store=True)
    bhyt_cong_ty = fields.Float("BHYT công ty (3%)", compute="_compute_du_lieu_luong", store=True)
    bhtn_cong_ty = fields.Float("BHTN công ty (1%)", compute="_compute_du_lieu_luong", store=True)
    tong_bh_cong_ty = fields.Float("Tổng BH công ty đóng (21.5%)", compute="_compute_du_lieu_luong", store=True)
    
    # Lương thực nhận
    luong_thuc_linh = fields.Float("Thực lĩnh (VND)", compute="_compute_du_lieu_luong", store=True)

    @api.constrains('thang')
    def _check_thang(self):
        for rec in self:
            if rec.thang < 1 or rec.thang > 12:
                raise ValidationError("Tháng phải nằm trong khoảng từ 1 đến 12.")

    @api.constrains('nam')
    def _check_nam(self):
        for rec in self:
            if rec.nam < 2000:
                raise ValidationError("Năm phải lớn hơn hoặc bằng 2000.")

    def action_recompute_salary(self):
        self._compute_du_lieu_luong()
        return True

    @api.depends('nhan_vien_id', 'thang', 'nam')
    def _compute_du_lieu_luong(self):
        for rec in self:
            if not rec.nhan_vien_id or not rec.thang or not rec.nam:
                rec.tong_gio_cong = 0.0
                rec.so_ngay_cong = 0.0
                rec.luong_co_ban = 0.0
                rec.phu_cap_an_trua = 0.0
                rec.phu_cap_trach_nhiem = 0.0
                rec.luong_theo_gio = 0.0
                rec.tong_gio_ot = 0.0
                rec.luong_ot = 0.0
                rec.tong_thuong = 0.0
                rec.tong_phat = 0.0
                rec.tong_phat_cham_cong = 0.0
                rec.luong_dong_bh = 0.0
                rec.bhxh_nhan_vien = 0.0
                rec.bhyt_nhan_vien = 0.0
                rec.bhtn_nhan_vien = 0.0
                rec.tong_bh_nhan_vien = 0.0
                rec.bhxh_cong_ty = 0.0
                rec.bhyt_cong_ty = 0.0
                rec.bhtn_cong_ty = 0.0
                rec.tong_bh_cong_ty = 0.0
                rec.luong_thuc_linh = 0.0
                continue

            # 1. Tính toán ngày bắt đầu và kết thúc tháng
            try:
                start_date = date(rec.nam, rec.thang, 1)
                last_day = calendar.monthrange(rec.nam, rec.thang)[1]
                end_date = date(rec.nam, rec.thang, last_day)
            except Exception:
                raise ValidationError("Tháng hoặc năm không hợp lệ!")

            # 2. Tính tổng số giờ công, tăng ca và tiền phạt từ bảng chấm công
            cham_cong_records = self.env['hr_cham_cong'].search([
                ('nhan_vien_id', '=', rec.nhan_vien_id.id),
                ('ngay_cham_cong', '>=', start_date),
                ('ngay_cham_cong', '<=', end_date)
            ])
            
            tong_gio = 0.0
            tong_ot = 0.0
            tong_phat_cc = 0.0
            for cc in cham_cong_records:
                tong_gio += cc.so_gio_cong
                tong_ot += cc.so_gio_tang_ca
                tong_phat_cc += cc.tien_phat
            
            rec.tong_gio_cong = tong_gio
            rec.so_ngay_cong = round(tong_gio / 8.0, 2)
            rec.tong_gio_ot = tong_ot
            rec.tong_phat_cham_cong = tong_phat_cc

            # 3. Lấy cấu hình lương gốc
            luong_base = self.env['hr_luong_co_ban'].search([('nhan_vien_id', '=', rec.nhan_vien_id.id)], limit=1)
            rec.luong_co_ban = luong_base.luong_co_ban if luong_base else 0.0
            rec.phu_cap_an_trua = luong_base.phu_cap_an_trua if luong_base else 0.0
            rec.phu_cap_trach_nhiem = luong_base.phu_cap_trach_nhiem if luong_base else 0.0
            rec.luong_dong_bh = luong_base.luong_dong_bh if luong_base and luong_base.luong_dong_bh else rec.luong_co_ban

            # 4. Tính toán lương giờ công & OT
            # Quy chuẩn tháng làm việc 26 ngày, mỗi ngày 8 tiếng => 208 tiếng
            don_gia_gio = rec.luong_co_ban / 208.0 if rec.luong_co_ban else 0.0
            rec.luong_theo_gio = round(don_gia_gio * rec.tong_gio_cong, 2)
            rec.luong_ot = round(don_gia_gio * rec.tong_gio_ot * 1.5, 2)

            # 5. Tính tổng thưởng/phạt kỷ luật
            bien_dong_records = self.env['hr_khen_thuong_ky_luat'].search([
                ('nhan_vien_id', '=', rec.nhan_vien_id.id),
                ('ngay_ap_dung', '>=', start_date),
                ('ngay_ap_dung', '<=', end_date)
            ])
            
            tong_thuong = 0.0
            tong_phat_kl = 0.0
            for bd in bien_dong_records:
                if bd.loai_quyet_dinh == 'khen_thuong':
                    tong_thuong += bd.so_tien
                elif bd.loai_quyet_dinh == 'ky_luat':
                    tong_phat_kl += bd.so_tien
            
            rec.tong_thuong = tong_thuong
            rec.tong_phat = tong_phat_kl

            # 6. Tính bảo hiểm trích đóng
            rec.bhxh_nhan_vien = round(rec.luong_dong_bh * 0.08, 2)
            rec.bhyt_nhan_vien = round(rec.luong_dong_bh * 0.015, 2)
            rec.bhtn_nhan_vien = round(rec.luong_dong_bh * 0.01, 2)
            rec.tong_bh_nhan_vien = rec.bhxh_nhan_vien + rec.bhyt_nhan_vien + rec.bhtn_nhan_vien

            rec.bhxh_cong_ty = round(rec.luong_dong_bh * 0.175, 2)
            rec.bhyt_cong_ty = round(rec.luong_dong_bh * 0.03, 2)
            rec.bhtn_cong_ty = round(rec.luong_dong_bh * 0.01, 2)
            rec.tong_bh_cong_ty = rec.bhxh_cong_ty + rec.bhyt_cong_ty + rec.bhtn_cong_ty

            # 7. Tính lương thực lĩnh theo công thức
            rec.luong_thuc_linh = round(
                rec.luong_theo_gio + 
                rec.luong_ot + 
                rec.phu_cap_an_trua + 
                rec.phu_cap_trach_nhiem + 
                rec.tong_thuong - 
                rec.tong_phat - 
                rec.tong_phat_cham_cong - 
                rec.tong_bh_nhan_vien,
                2
            )

    def action_send_salary_telegram(self):
        """Gui bang luong chi tiet cho tung nhan vien qua Telegram."""
        for rec in self:
            if not rec.nhan_vien_id.telegram_chat_id:
                raise ValidationError(
                    f"Nhân viên {rec.nhan_vien_id.ho_va_ten} chưa cấu hình Telegram Chat ID! "
                    f"Vào hồ sơ nhân viên, bấm 'Lấy Chat ID từ Telegram'."
                )

            def fmt(val):
                return "{:,.0f}".format(val).replace(",", ".")

            msg = (
                f"📊 <b>PHIẾU LƯƠNG THÁNG {rec.thang}/{rec.nam}</b>\n"
                f"👤 Nhân viên: <b>{rec.nhan_vien_id.ho_va_ten}</b>\n"
                f"Chức vụ: {rec.nhan_vien_id.chuc_vu_hien_tai_id.ten_chuc_vu or 'N/A'}\n"
                f"──────────────────────\n"
                f"🕒 <b>Công làm việc:</b>\n"
                f"- Tổng giờ công: {rec.tong_gio_cong:.2f} giờ ({rec.so_ngay_cong:.2f} ngày quy đổi)\n"
                f"- Tổng giờ OT: {rec.tong_gio_ot:.2f} giờ\n"
                f"💰 <b>Các khoản Thu nhập:</b>\n"
                f"- Lương cơ bản: {fmt(rec.luong_co_ban)} VND\n"
                f"- Lương tính theo giờ công: {fmt(rec.luong_theo_gio)} VND\n"
                f"- Tiền tăng ca OT (x1.5): {fmt(rec.luong_ot)} VND\n"
                f"- Phụ cấp ăn trưa: {fmt(rec.phu_cap_an_trua)} VND\n"
                f"- Phụ cấp trách nhiệm: {fmt(rec.phu_cap_trach_nhiem)} VND\n"
                f"➕ Thưởng khen thưởng: {fmt(rec.tong_thuong)} VND\n"
                f"➖ Phạt kỷ luật: {fmt(rec.tong_phat)} VND\n"
                f"➖ Phạt đi muộn/về sớm: {fmt(rec.tong_phat_cham_cong)} VND\n"
                f"🛡️ <b>Bảo hiểm trích nộp nhân viên (10.5%):</b>\n"
                f"- Tổng tiền bảo hiểm: {fmt(rec.tong_bh_nhan_vien)} VND\n"
                f"  (BHXH 8%: {fmt(rec.bhxh_nhan_vien)} | BHYT 1.5%: {fmt(rec.bhyt_nhan_vien)} | BHTN 1%: {fmt(rec.bhtn_nhan_vien)})\n"
                f"──────────────────────\n"
                f"💵 <b>THỰC LĨNH CHUYỂN KHOẢN:</b>\n"
                f"👉 <b>{fmt(rec.luong_thuc_linh)} VND</b>"
            )
            results = rec.nhan_vien_id.send_telegram_notification(msg)
            # Kiem tra ket qua that su tu Telegram API
            for (nv, ok, err) in results:
                if not ok:
                    raise ValidationError(
                        "Gửi phiếu lương qua Telegram THẤT BẠI cho %s.\n"
                        "Lý do: %s\n\n"
                        "Chat ID hiện tại ('%s') có thể sai. Hãy vào hồ sơ nhân viên, "
                        "bấm 'Lấy Chat ID từ Telegram' để lấy đúng Chat ID."
                        % (nv.ho_va_ten, err, nv.telegram_chat_id or '')
                    )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã gửi phiếu lương chi tiết qua Telegram!',
                'type': 'success',
                'sticky': False,
            }
        }
