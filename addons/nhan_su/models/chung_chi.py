# -*- coding: utf-8 -*-
from odoo import models, fields


class ChungChi(models.Model):
    _name = 'chung_chi'
    _description = 'Chứng chỉ'
    _rec_name = 'ten_chung_chi'

    ten_chung_chi = fields.Char("Tên chứng chỉ", required=True)
    don_vi_cap = fields.Char("Đơn vị cấp")
    ngay_cap = fields.Date("Ngày cấp")
    ngay_het_han = fields.Date("Ngày hết hạn")
    mo_ta = fields.Text("Mô tả")

    # Quan hệ với nhân viên (không bắt buộc để có thể tạo danh mục chung)
    nhan_vien_id = fields.Many2one('nhan_vien', string="Nhân viên", ondelete='cascade')
    
    # Quan hệ ngược với danh sách chứng chỉ bằng cấp
    danh_sach_chung_chi_bang_cap_ids = fields.One2many(
        'danh_sach_chung_chi_bang_cap',
        'chung_chi_bang_cap_id',
        string="Danh sách nhân viên có chứng chỉ này"
    )