# -*- coding: utf-8 -*-
from odoo import models, fields


class ChucVu(models.Model):
    _name = 'chuc_vu'
    _description = 'Chức vụ'
    _rec_name = 'ten_chuc_vu'

    ma_chuc_vu = fields.Char("Mã chức vụ", required=True)
    ten_chuc_vu = fields.Char("Tên chức vụ", required=True)