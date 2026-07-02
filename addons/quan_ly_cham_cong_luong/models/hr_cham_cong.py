# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import pytz
from datetime import datetime

ICT = pytz.timezone('Asia/Ho_Chi_Minh')


def to_ict(dt_utc):
    """Chuyen UTC datetime sang Asia/Ho_Chi_Minh."""
    if not dt_utc:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = pytz.utc.localize(dt_utc)
    return dt_utc.astimezone(ICT)


def now_utc():
    """Lay thoi gian hien tai UTC naive (dung luu Odoo Datetime)."""
    return datetime.utcnow().replace(tzinfo=None)


class HRChamCong(models.Model):
    _name = 'hr_cham_cong'
    _description = 'Bang du lieu cham cong hang ngay'
    _order = 'ngay_cham_cong desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhan vien', required=True)
    ngay_cham_cong = fields.Date('Ngay cham cong', required=True, default=fields.Date.context_today)
    trang_thai = fields.Selection([
        ('di_lam', 'Di lam theo gio'),
        ('nghi_co_phep', 'Nghi co phep'),
        ('nghi_khong_phep', 'Nghi khong phep')
    ], string='Trang thai cong', default='di_lam', required=True)
    gio_vao = fields.Datetime('Gio Check-in')
    gio_ra = fields.Datetime('Gio Check-out')
    
    so_gio_cong = fields.Float('So gio cong thuc te', compute='_compute_thong_tin_cong', store=True)
    so_gio_tang_ca = fields.Float('So gio tang ca OT', compute='_compute_thong_tin_cong', store=True)
    
    so_phut_muon = fields.Integer('So phut di muon', compute='_compute_thong_tin_cong', store=True)
    so_phut_ve_som = fields.Integer('So phut ve som', compute='_compute_thong_tin_cong', store=True)
    tien_phat = fields.Float('Tien phat cham cong', compute='_compute_thong_tin_cong', store=True)
    nguoi_xac_nhan = fields.Char('Nguoi kiem tra xac nhan')

    # Trang thai check-in/check-out
    da_check_in = fields.Boolean('Da check-in', compute='_compute_da_check', store=False)
    da_check_out = fields.Boolean('Da check-out', compute='_compute_da_check', store=False)

    @api.depends('gio_vao', 'gio_ra')
    def _compute_da_check(self):
        for rec in self:
            rec.da_check_in = bool(rec.gio_vao)
            rec.da_check_out = bool(rec.gio_ra)

    @api.onchange('gio_vao')
    def _onchange_gio_vao(self):
        for rec in self:
            if rec.gio_vao:
                local_time = to_ict(rec.gio_vao)
                rec.ngay_cham_cong = local_time.date()

    @api.depends('gio_vao', 'gio_ra', 'trang_thai', 'nhan_vien_id')
    def _compute_thong_tin_cong(self):
        for rec in self:
            if rec.trang_thai != 'di_lam' or not rec.gio_vao or not rec.gio_ra:
                rec.so_gio_cong = 0.0
                rec.so_gio_tang_ca = 0.0
                rec.so_phut_muon = 0
                rec.so_phut_ve_som = 0
                rec.tien_phat = 0.0
                continue

            local_in = to_ict(rec.gio_vao)
            local_out = to_ict(rec.gio_ra)

            # 1. So gio lam viec
            duration = (local_out - local_in).total_seconds() / 3600.0
            work_hours = round(max(0.0, duration - 1.0), 2) if duration > 5.0 else round(max(0.0, duration), 2)
            
            # Cap regular hours at 8.0, the rest is OT
            rec.so_gio_cong = min(8.0, work_hours)
            rec.so_gio_tang_ca = max(0.0, round(work_hours - 8.0, 2))

            # 2. Phut di muon (gioi han check-in truoc 9:00 AM)
            limit_in = local_in.replace(hour=9, minute=0, second=0, microsecond=0)
            rec.so_phut_muon = max(0, int((local_in - limit_in).total_seconds() / 60)) if local_in > limit_in else 0

            # 3. Phut ve som (gioi han check-out sau 5:30 PM / 17:30)
            limit_out = local_out.replace(hour=17, minute=30, second=0, microsecond=0)
            rec.so_phut_ve_som = max(0, int((limit_out - local_out).total_seconds() / 60)) if local_out < limit_out else 0

            # 4. Tien phat
            luong_base = self.env['hr_luong_co_ban'].search(
                [('nhan_vien_id', '=', rec.nhan_vien_id.id)], limit=1
            )
            dg_muon = luong_base.phat_di_muon_phut if luong_base else 2000.0
            dg_som = luong_base.phat_ve_som_phut if luong_base else 2000.0
            rec.tien_phat = (rec.so_phut_muon * dg_muon) + (rec.so_phut_ve_som * dg_som)

    # =====================================================
    # SELF-SERVICE: Check-in / Check-out tu phuc vu
    # =====================================================

    def _get_nhan_vien_tu_user(self):
        """Lay nhan_vien record cua user hien tai dang nhap."""
        nv = self.env['nhan_vien'].search([('user_id', '=', self.env.uid)], limit=1)
        if not nv:
            raise UserError(
                "Tai khoan cua ban chua duoc lien ket voi ho so nhan vien.\n"
                "Vui long lien he HR de duoc cap quyen."
            )
        return nv

    def action_self_check_in(self):
        """Nhan vien tu check-in. Neu check-in nhieu lan, giu gio vao som nhat."""
        nv = self._get_nhan_vien_tu_user()
        today = fields.Date.context_today(self)
        now = now_utc()
        local_now = to_ict(now)

        existing = self.search([
            ('nhan_vien_id', '=', nv.id),
            ('ngay_cham_cong', '=', today),
        ], limit=1)

        if existing and existing.gio_vao:
            if now < existing.gio_vao:
                # Gio moi som hon → cap nhat (giu som nhat)
                existing.write({'gio_vao': now})
                msg_title = 'Cập nhật check-in'
                msg_body = f'Ghi nhận check-in sớm hơn: {local_now.strftime("%H:%M")} (thay thế {to_ict(existing.gio_vao).strftime("%H:%M")}).'
                notif_type = 'success'
            else:
                # Gio hien tai muon hon → giu nguyen gio cu (som nhat)
                gio_vao_ict = to_ict(existing.gio_vao)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Đã ghi nhận check-in',
                        'message': f'Giờ vào sớm nhất hôm nay: {gio_vao_ict.strftime("%H:%M")}. Không cập nhật vì giờ hiện tại muộn hơn.',
                        'type': 'info',
                        'sticky': False,
                    }
                }
        elif existing:
            existing.write({'gio_vao': now, 'trang_thai': 'di_lam'})
            msg_title = 'Check-in thành công!'
            msg_body = f'Xin chào {nv.ho_va_ten}! Check-in lúc {local_now.strftime("%H:%M")}.'
            notif_type = 'success'
        else:
            self.create({
                'nhan_vien_id': nv.id,
                'ngay_cham_cong': today,
                'trang_thai': 'di_lam',
                'gio_vao': now,
            })
            msg_title = 'Check-in thành công!'
            msg_body = f'Xin chào {nv.ho_va_ten}! Check-in lúc {local_now.strftime("%H:%M")} ngày {today.strftime("%d/%m/%Y")}.'
            notif_type = 'success'

        nv.send_telegram_notification(
            f"🔔 <b>CHECK-IN</b>\n"
            f"👤 Nhân viên: <b>{nv.ho_va_ten}</b>\n"
            f"⏰ Thời gian: {local_now.strftime('%H:%M:%S')}\n"
            f"📅 Ngày: {today.strftime('%d/%m/%Y')}"
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': msg_title,
                'message': msg_body,
                'type': notif_type,
                'sticky': False,
            }
        }

    def action_self_check_out(self):
        """Nhan vien tu check-out. Neu check-out nhieu lan, giu gio ra muon nhat."""
        nv = self._get_nhan_vien_tu_user()
        today = fields.Date.context_today(self)
        now = now_utc()
        local_now = to_ict(now)

        existing = self.search([
            ('nhan_vien_id', '=', nv.id),
            ('ngay_cham_cong', '=', today),
            ('trang_thai', '=', 'di_lam'),
        ], limit=1)

        if not existing:
            raise UserError("Bạn chưa check-in hôm nay. Vui lòng check-in trước!")

        if existing.gio_ra:
            if now > existing.gio_ra:
                # Gio moi muon hon → cap nhat (giu muon nhat)
                existing.write({'gio_ra': now})
                msg_title = 'Cập nhật check-out'
                msg_body = f'Ghi nhận check-out muộn hơn: {local_now.strftime("%H:%M")}.'
                notif_type = 'success'
            else:
                # Gio hien tai som hon → giu nguyen gio cu (muon nhat)
                gio_ra_ict = to_ict(existing.gio_ra)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Đã ghi nhận check-out',
                        'message': f'Giờ ra muộn nhất hôm nay: {gio_ra_ict.strftime("%H:%M")}. Không cập nhật vì giờ hiện tại sớm hơn.',
                        'type': 'info',
                        'sticky': False,
                    }
                }
        else:
            existing.write({'gio_ra': now})
            local_in = to_ict(existing.gio_vao)
            duration_h = (now - existing.gio_vao).total_seconds() / 3600.0
            msg_title = 'Check-out thành công!'
            msg_body = f'Check-out lúc {local_now.strftime("%H:%M")}. Check-in từ {local_in.strftime("%H:%M")}. Tổng: {duration_h:.1f} giờ.'
            notif_type = 'success'

        local_in = to_ict(existing.gio_vao) if existing.gio_vao else local_now
        gio_ra_final = to_ict(existing.gio_ra) if existing.gio_ra else local_now
        duration_h = (existing.gio_ra - existing.gio_vao).total_seconds() / 3600.0 if existing.gio_vao and existing.gio_ra else 0

        nv.send_telegram_notification(
            f"🔔 <b>CHECK-OUT</b>\n"
            f"👤 Nhân viên: <b>{nv.ho_va_ten}</b>\n"
            f"⏰ Thời gian: {local_now.strftime('%H:%M:%S')}\n"
            f"📅 Ngày: {today.strftime('%d/%m/%Y')}\n"
            f"⏱️ Tổng giờ làm: {duration_h:.2f}h (Công: {existing.so_gio_cong:.2f}h, OT: {existing.so_gio_tang_ca:.2f}h)"
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': msg_title,
                'message': msg_body,
                'type': notif_type,
                'sticky': False,
            }
        }

    # =====================================================
    # CRON: Gui tin nhan nhac nho hang ngay
    # =====================================================

    @api.model
    def cron_remind_check_in(self):
        """Gui tin nhan Telegram nhac nho check-in cho nhan vien chua check-in hom nay."""
        today = fields.Date.context_today(self)
        nhan_viens = self.env['nhan_vien'].search([('telegram_chat_id', '!=', False)])
        for nv in nhan_viens:
            existing = self.search([
                ('nhan_vien_id', '=', nv.id),
                ('ngay_cham_cong', '=', today),
                ('gio_vao', '!=', False)
            ], limit=1)
            if not existing:
                msg = (
                    f"⏰ <b>NHẮC NHỞ CHECK-IN</b>\n"
                    f"Xin chào <b>{nv.ho_va_ten}</b>,\n"
                    f"Đã đến giờ làm việc nhưng hệ thống chưa ghi nhận Check-in của bạn hôm nay ({today.strftime('%d/%m/%Y')}).\n"
                    f"Vui lòng đăng nhập Odoo và thực hiện Check-in ngay nhé!"
                )
                nv.send_telegram_notification(msg)

    @api.model
    def cron_remind_check_out(self):
        """Gui tin nhan Telegram nhac nho check-out cho nhan vien chua check-out hom nay."""
        today = fields.Date.context_today(self)
        nhan_viens = self.env['nhan_vien'].search([('telegram_chat_id', '!=', False)])
        for nv in nhan_viens:
            existing = self.search([
                ('nhan_vien_id', '=', nv.id),
                ('ngay_cham_cong', '=', today),
                ('gio_vao', '!=', False),
                ('gio_ra', '=', False)
            ], limit=1)
            if existing:
                msg = (
                    f"⏰ <b>NHẮC NHỞ CHECK-OUT</b>\n"
                    f"Xin chào <b>{nv.ho_va_ten}</b>,\n"
                    f"Đã đến giờ tan làm, vui lòng thực hiện Check-out trên Odoo để ghi nhận giờ công làm việc đầy đủ ngày hôm nay."
                )
                nv.send_telegram_notification(msg)
