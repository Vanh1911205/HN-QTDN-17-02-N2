# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HRKhenThuongKyLuat(models.Model):
    _name = 'hr_khen_thuong_ky_luat'
    _description = 'Quyết định khen thưởng và kỷ luật'
    _rec_name = 'nhan_vien_id'

    nhan_vien_id = fields.Many2one('nhan_vien', string="Nhân viên", required=True)
    loai_quyet_dinh = fields.Selection([
        ('khen_thuong', 'Khen thưởng (Cộng tiền)'),
        ('ky_luat', 'Kỷ luật (Trừ tiền)')
    ], string="Loại quyết định", required=True, default='khen_thuong')
    so_tien = fields.Float("Số tiền (VND)", required=True, default=0.0)
    ngay_ap_dung = fields.Date("Ngày áp dụng", required=True, default=fields.Date.context_today)
    ly_do = fields.Char("Lý do quyết định")