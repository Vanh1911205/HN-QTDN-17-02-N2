# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HRLuongCoBan(models.Model):
    _name = 'hr_luong_co_ban'
    _description = 'Cau hinh luong co ban nhan vien'
    _rec_name = 'nhan_vien_id'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhan vien', required=True)
    ma_dinh_danh = fields.Char("Ma dinh danh", related='nhan_vien_id.ma_dinh_danh', store=True)
    luong_co_ban = fields.Float("Luong co ban", required=True, default=0.0)
    luong_dong_bh = fields.Float("Luong dong bao hiem", required=True, default=0.0)
    phat_di_muon_phut = fields.Float("Phat di muon (VND/phut)", default=2000.0, required=True)
    phat_ve_som_phut = fields.Float("Phat ve som (VND/phut)", default=2000.0, required=True)
    phu_cap_an_trua = fields.Float("Phu cap an trua", default=0.0)
    phu_cap_trach_nhiem = fields.Float("Phu cap trach nhiem", default=0.0)
    ghi_chu = fields.Text("Ghi chu bo sung")

    # Chuc vu hien tai lay tu nhan vien
    chuc_vu_hien_tai_id = fields.Many2one(
        'chuc_vu',
        string="Chuc vu hien tai",
        related='nhan_vien_id.chuc_vu_hien_tai_id',
        store=True,
        readonly=True
    )

    @api.onchange('luong_co_ban')
    def _onchange_luong_co_ban(self):
        for rec in self:
            if rec.luong_co_ban and not rec.luong_dong_bh:
                rec.luong_dong_bh = rec.luong_co_ban

    @api.onchange('nhan_vien_id')
    def _onchange_nhan_vien_id(self):
        """Tu dong lay phu cap trach nhiem tu chuc vu khi chon nhan vien."""
        for rec in self:
            if rec.nhan_vien_id and rec.nhan_vien_id.chuc_vu_hien_tai_id:
                rec.phu_cap_trach_nhiem = rec.nhan_vien_id.chuc_vu_hien_tai_id.phu_cap_trach_nhiem

    def action_dong_bo_phu_cap(self):
        """Dong bo lai phu cap trach nhiem tu chuc vu."""
        for rec in self:
            if rec.nhan_vien_id and rec.nhan_vien_id.chuc_vu_hien_tai_id:
                rec.phu_cap_trach_nhiem = rec.nhan_vien_id.chuc_vu_hien_tai_id.phu_cap_trach_nhiem
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Da dong bo',
                'message': 'Phu cap trach nhiem da duoc cap nhat tu chuc vu!',
                'type': 'success',
                'sticky': False,
            }
        }
