# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ChamCong(models.Model):
    _name = 'cham_cong'
    _description = 'Chấm công'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    ngay_cham_cong = fields.Date(string="Ngày chấm công", required=True)
    gio_vao = fields.Float(string="Giờ vào")
    gio_ra = fields.Float(string="Giờ ra")
    ghi_chu = fields.Text(string="Ghi chú")

    so_gio_lam = fields.Float(
        string="Số giờ làm",
        compute='_compute_so_gio_lam',
        store=True
    )

    @api.depends('gio_vao', 'gio_ra')
    def _compute_so_gio_lam(self):
        for rec in self:
            if rec.gio_vao and rec.gio_ra:
                rec.so_gio_lam = max(rec.gio_ra - rec.gio_vao, 0)
            else:
                rec.so_gio_lam = 0