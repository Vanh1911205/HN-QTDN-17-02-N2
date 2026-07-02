# -*- coding: utf-8 -*-
from odoo import models, fields

class LoaiVanBan(models.Model):
    _name = 'loai_van_ban'
    _description = 'Danh mục Loại văn bản'
    _rec_name = 'ten_loai'

    ten_loai = fields.Char(string="Tên loại văn bản", required=True)
    ma_loai = fields.Char(string="Mã loại văn bản")