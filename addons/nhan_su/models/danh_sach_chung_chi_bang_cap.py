# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DanhSachChungChiBangCap(models.Model):
    _name = 'danh_sach_chung_chi_bang_cap'
    _description = 'Danh sách chứng chỉ, bằng cấp của nhân viên'
    _rec_name = 'chung_chi_bang_cap_id'

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string="Nhân viên",
        required=True,
        ondelete='cascade'
    )
    chung_chi_bang_cap_id = fields.Many2one(
        'chung_chi',
        string="Chứng chỉ / Bằng cấp",
        required=True
    )
    ghi_chu = fields.Char(string="Ghi chú")

    # Các field related để hiển thị thông tin nhân viên nhanh
    ma_dinh_danh = fields.Char(
        string="Mã nhân viên",
        related='nhan_vien_id.ma_dinh_danh',
        readonly=True
    )
    ho_va_ten = fields.Char(
        string="Họ và tên",
        related='nhan_vien_id.ho_va_ten',
        readonly=True
    )
    tuoi = fields.Integer(
        string="Tuổi",
        related='nhan_vien_id.tuoi',
        readonly=True
    )