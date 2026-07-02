# -*- coding: utf-8 -*-
from odoo import models, fields

class VanBanDi(models.Model):
    _name = 'van_ban_di'
    _description = 'Bảng chứa thông tin văn bản đi'
    _rec_name = 'ten_van_ban'

    so_van_ban_di = fields.Char("Số đi", required=True)
    so_hieu_van_ban = fields.Char("Số/Ký hiệu phát hành", required=True)
    ten_van_ban = fields.Char("Tên văn bản", required=True)
    
    don_vi_soan_thao_id = fields.Many2one('don_vi', string="Đơn vị soạn thảo")
    nguoi_ky_id = fields.Many2one('nhan_vien', string="Người ký")
    noi_nhan = fields.Char("Nơi nhận (Ngoài hệ thống)")
    loai_van_ban_id = fields.Many2one('loai_van_ban', string="Loại văn bản")