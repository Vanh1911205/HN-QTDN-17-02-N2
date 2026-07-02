from odoo import models, fields, api


class ChucVu(models.Model):
    _name = 'chuc_vu'
    _description = 'Bang chua thong tin chuc vu'
    _rec_name = 'ten_chuc_vu'

    ma_chuc_vu = fields.Char("Ma chuc vu", required=True)
    ten_chuc_vu = fields.Char("Ten chuc vu", required=True)
    phu_cap_trach_nhiem = fields.Float(
        "Phu cap trach nhiem (VND)",
        default=0.0,
        help="Muc phu cap trach nhiem mac dinh cho chuc vu nay"
    )
    mo_ta = fields.Text("Mo ta chuc vu")
