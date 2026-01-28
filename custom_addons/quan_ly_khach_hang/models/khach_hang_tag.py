# -*- coding: utf-8 -*-

from odoo import models, fields


class KhachHangTag(models.Model):
    """Tags để phân loại khách hàng"""
    _name = 'khach.hang.tag'
    _description = 'Nhãn khách hàng'
    _order = 'name'

    name = fields.Char(
        string='Tên nhãn',
        required=True,
        translate=True
    )
    
    color = fields.Integer(
        string='Màu sắc',
        default=0,
        help='Màu hiển thị trên giao diện'
    )
    
    active = fields.Boolean(
        string='Hoạt động',
        default=True
    )
    
    description = fields.Text(
        string='Mô tả'
    )
    
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Tên nhãn đã tồn tại!')
    ]
