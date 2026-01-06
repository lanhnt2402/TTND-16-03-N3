# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PhongBan(models.Model):
    _name = 'phong_ban'
    _description = 'Bảng chứa thông tin phòng ban'
    _rec_name = 'ten_phong_ban'
    _order = 'ten_phong_ban ASC'

    ma_dinh_danh = fields.Char("Mã định danh", required=True)
    ten_phong_ban = fields.Char("Tên phòng ban", required=True)

    # Quan hệ Many2many với nhân viên - SỬA ĐÚNG CÁCH (không chỉ định column1, column2)
    nhan_vien_ids = fields.Many2many(
        'nhan_vien',
        'phong_ban_nhan_vien_rel',  # tên bảng trung gian
        string="Danh sách nhân viên"
    )

    # Quan hệ phân cấp phòng ban
    phong_ban_id = fields.Many2one(
        'phong_ban',
        string="Phòng ban cha",
        ondelete='cascade'
    )
    phong_ban_con_ids = fields.One2many(
        'phong_ban',
        'phong_ban_id',
        string="Phòng ban con"
    )

    # Số lượng nhân viên (computed)
    so_luong_nhan_vien = fields.Integer(
        "Số lượng nhân viên",
        compute="_compute_so_luong_nhan_vien",
        store=True
    )

    # Mô tả
    mo_ta = fields.Text("Mô tả")

    # Trạng thái hoạt động
    trang_thai = fields.Selection(
        [
            ('dang_hoat_dong', 'Đang hoạt động'),
            ('tam_dung', 'Tạm dừng'),
            ('ngung_hoat_dong', 'Ngừng hoạt động')
        ],
        string="Trạng thái",
        default='dang_hoat_dong'
    )

    # Ngày thành lập
    ngay_thanh_lap = fields.Date("Ngày thành lập")

    # Trưởng phòng
    truong_phong_id = fields.Many2one(
        'nhan_vien',
        string="Trưởng phòng"
    )

    # Thông tin liên hệ
    dia_chi = fields.Char("Địa chỉ")
    so_dien_thoai = fields.Char("Số điện thoại")
    email = fields.Char("Email")

    # ===== COMPUTED =====
    @api.depends('nhan_vien_ids')
    def _compute_so_luong_nhan_vien(self):
        for record in self:
            record.so_luong_nhan_vien = len(record.nhan_vien_ids)

    # ===== CONSTRAINTS =====
    @api.constrains('phong_ban_id')
    def _check_phong_ban_id(self):
        for record in self:
            if record.phong_ban_id and record.phong_ban_id.id == record.id:
                raise ValidationError("Phòng ban không thể là phòng ban cha của chính nó")

    @api.constrains('truong_phong_id', 'nhan_vien_ids')
    def _check_truong_phong(self):
        for record in self:
            if record.truong_phong_id and record.truong_phong_id not in record.nhan_vien_ids:
                raise ValidationError("Trưởng phòng phải thuộc danh sách nhân viên của phòng ban")

    _sql_constraints = [
        ('ma_dinh_danh_unique', 'unique(ma_dinh_danh)', 'Mã định danh phải là duy nhất')
    ]

    # Hiển thị tên kèm mã
    @api.model
    def name_get(self):
        result = []
        for record in self:
            name = record.ten_phong_ban
            if record.ma_dinh_danh:
                name = f"[{record.ma_dinh_danh}] {name}"
            result.append((record.id, name))
        return result