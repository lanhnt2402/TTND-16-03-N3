# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError


class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Bảng chứa thông tin nhân viên'
    _rec_name = 'ho_va_ten'
    _order = 'ten ASC, tuoi DESC'

    # Thông tin cơ bản
    ma_dinh_danh = fields.Char(string="Mã định danh", required=True, copy=False)

    ho_ten_dem = fields.Char(string="Họ tên đệm", required=True)
    ten = fields.Char(string="Tên", required=True)
    ho_va_ten = fields.Char(
        string="Họ và tên",
        compute="_compute_ho_va_ten",
        store=True
    )

    ngay_sinh = fields.Date(string="Ngày sinh")
    tuoi = fields.Integer(string="Tuổi", compute="_compute_tuoi", store=True)
    so_nguoi_bang_tuoi = fields.Integer(
        string="Số người bằng tuổi",
        compute="_compute_so_nguoi_bang_tuoi",
        store=True
    )

    que_quan = fields.Char(string="Quê quán")
    email = fields.Char(string="Email")
    so_dien_thoai = fields.Char(string="Số điện thoại")
    so_bhxh = fields.Char(string="Số BHXH")
    dia_chi = fields.Text(string="Địa chỉ")
    luong = fields.Float(string="Lương", digits=(16, 0))
    anh = fields.Binary(string="Ảnh")

    # Quan hệ với các model khác
    lich_su_cong_tac_ids = fields.One2many(
        "lich_su_cong_tac",
        "nhan_vien_id",
        string="Danh sách lịch sử công tác"
    )

    danh_sach_chung_chi_bang_cap_ids = fields.One2many(
        "danh_sach_chung_chi_bang_cap",
        "nhan_vien_id",
        string="Danh sách chứng chỉ bằng cấp"
    )

    # Quan hệ Many2many với phòng ban (nhân viên có thể thuộc nhiều phòng ban)
    phong_ban_ids = fields.Many2many(
        'phong_ban',
        'phong_ban_nhan_vien_rel',
        'nhan_vien_id',
        'phong_ban_id',
        string="Phòng ban"
    )

    # ===== COMPUTED FIELDS =====
    @api.depends("ho_ten_dem", "ten")
    def _compute_ho_va_ten(self):
        for record in self:
            parts = [part for part in [record.ho_ten_dem, record.ten] if part]
            record.ho_va_ten = ' '.join(parts) if parts else ''

    @api.depends("ngay_sinh")
    def _compute_tuoi(self):
        today = date.today()
        for record in self:
            if record.ngay_sinh:
                age = today.year - record.ngay_sinh.year
                if (today.month, today.day) < (record.ngay_sinh.month, record.ngay_sinh.day):
                    age -= 1
                record.tuoi = age
            else:
                record.tuoi = 0

    @api.depends("tuoi")
    def _compute_so_nguoi_bang_tuoi(self):
        for record in self:
            if record.tuoi:
                record.so_nguoi_bang_tuoi = self.search_count([('tuoi', '=', record.tuoi)])
            else:
                record.so_nguoi_bang_tuoi = 0

    # ===== ONCHANGE & VALIDATION =====
    @api.onchange("ho_ten_dem", "ten")
    def _onchange_ma_dinh_danh(self):
        if self.ho_ten_dem and self.ten:
            # Lấy chữ cái đầu của họ tên đệm (ví dụ: Nguyễn Văn → NV)
            initials = ''.join([word[0].upper() for word in self.ho_ten_dem.split() if word])
            self.ma_dinh_danh = (self.ten + initials).upper()

    @api.constrains('tuoi')
    def _check_tuoi(self):
        for record in self:
            if record.tuoi and record.tuoi < 18:
                raise ValidationError("Tuổi không được bé hơn 18")

    # ===== SQL CONSTRAINTS =====
    _sql_constraints = [
        ('ma_dinh_danh_unique', 'unique(ma_dinh_danh)', 'Mã định danh phải là duy nhất')
    ]