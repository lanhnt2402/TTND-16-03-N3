# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DonVi(models.Model):
    _name = 'don_vi'
    _description = 'Đơn vị'
    _rec_name = 'ten_don_vi'

    ma_don_vi = fields.Char(string="Mã đơn vị", required=True)
    ten_don_vi = fields.Char(string="Tên đơn vị", required=True)

    _sql_constraints = [
        ('ma_don_vi_unique', 'unique(ma_don_vi)', 'Mã đơn vị đã tồn tại, vui lòng nhập mã khác!')
    ]

    @api.model
    def name_get(self):
        result = []
        for record in self:
            name = record.ten_don_vi
            if record.ma_don_vi:
                name = f"[{record.ma_don_vi}] {name}"
            result.append((record.id, name))
        return result