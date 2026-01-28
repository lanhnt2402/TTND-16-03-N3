# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PhongBan(models.Model):
    _name = 'phong.ban'
    _description = 'Phòng ban'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True

    # ==================== THÔNG TIN CƠ BẢN ====================
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
        help='Thứ tự hiển thị'
    )
    
    code = fields.Char(
        string='Mã phòng ban',
        required=True,
        copy=False,
        index=True,
        tracking=True,
        help='Ví dụ: IT, HR, SALES'
    )
    
    name = fields.Char(
        string='Tên phòng ban',
        required=True,
        translate=True,
        tracking=True,
        index=True
    )
    
    complete_name = fields.Char(
        string='Tên đầy đủ',
        compute='_compute_complete_name',
        store=True,
        recursive=True,
        help='Hiển thị cấu trúc phòng ban cha > con'
    )
    
    # ==================== CẤU TRÚC PHÒNG BAN ====================
    
    parent_id = fields.Many2one(
        'phong.ban',
        string='Phòng ban cấp trên',
        ondelete='restrict',
        tracking=True,
        index=True
    )
    
    parent_path = fields.Char(index=True)
    
    child_ids = fields.One2many(
        'phong.ban',
        'parent_id',
        string='Phòng ban cấp dưới'
    )
    
    child_count = fields.Integer(
        string='Số phòng ban con',
        compute='_compute_child_count'
    )
    
    # ==================== QUẢN LÝ ====================
    
    manager_id = fields.Many2one(
        'nhan.su',
        string='Trưởng phòng',
        tracking=True,
        domain="[('working_status', '=', 'working')]",
        help='Người quản lý phòng ban'
    )
    
    manager_email = fields.Char(
        string='Email trưởng phòng',
        related='manager_id.work_email',
        readonly=True
    )
    
    manager_phone = fields.Char(
        string='SĐT trưởng phòng',
        related='manager_id.phone',
        readonly=True
    )
    
    # ==================== NHÂN VIÊN ====================
    
    employee_ids = fields.One2many(
        'nhan.su',
        'department_id',
        string='Nhân viên'
    )
    
    employee_count = fields.Integer(
        string='Số lượng nhân viên',
        compute='_compute_employee_count',
        store=True
    )
    
    working_employee_count = fields.Integer(
        string='Nhân viên đang làm việc',
        compute='_compute_employee_count',
        store=True
    )
    
    # ==================== THÔNG TIN BỔ SUNG ====================
    
    description = fields.Html(
        string='Mô tả',
        help='Mô tả chức năng, nhiệm vụ của phòng ban'
    )
    
    color = fields.Integer(
        string='Màu sắc',
        default=0,
        help='Màu hiển thị trên Kanban'
    )
    
    active = fields.Boolean(
        string='Hoạt động',
        default=True,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True
    )
    
    note = fields.Text(
        string='Ghi chú nội bộ'
    )
    
    # ==================== SQL CONSTRAINTS ====================
    
    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code, company_id)', 
         'Mã phòng ban đã tồn tại trong công ty này!'),
    ]
    
    # ==================== COMPUTE METHODS ====================
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        """Compute complete name recursively"""
        """Tính tên đầy đủ theo cấu trúc cha > con"""
        for record in self:
            if record.parent_id:
                record.complete_name = f"{record.parent_id.complete_name} / {record.name}"
            else:
                record.complete_name = record.name
    
    @api.depends('child_ids')
    def _compute_child_count(self):
        """Đếm số phòng ban con"""
        for record in self:
            record.child_count = len(record.child_ids)
    
    @api.depends('employee_ids', 'employee_ids.working_status')
    def _compute_employee_count(self):
        """Đếm số nhân viên"""
        for record in self:
            employees = record.employee_ids
            record.employee_count = len(employees)
            record.working_employee_count = len(
                employees.filtered(lambda e: e.working_status == 'working')
            )
    
    # ==================== CONSTRAINTS ====================
    
    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        """Kiểm tra vòng lặp trong cấu trúc phòng ban"""
        if not self._check_recursion():
            raise ValidationError(
                'Lỗi: Không thể tạo cấu trúc phòng ban đệ quy!\n'
                'Phòng ban không thể là phòng ban cha của chính nó.'
            )
    
    @api.constrains('manager_id')
    def _check_manager_department(self):
        """Manager phải thuộc phòng ban này hoặc phòng ban cha"""
        for record in self:
            if record.manager_id:
                if record.manager_id.department_id != record:
                    # Cho phép manager từ phòng ban cha
                    if record.parent_id and record.manager_id.department_id != record.parent_id:
                        raise ValidationError(
                            f'Trưởng phòng {record.manager_id.name} phải thuộc '
                            f'phòng ban {record.name} hoặc phòng ban cấp trên!'
                        )
    
    # ==================== CRUD METHODS ====================
    
    @api.model
    def create(self, vals):
        """Override create"""
        record = super().create(vals)
        
        # Log creation
        record.message_post(
            body=f"Phòng ban mới được tạo: {record.name}",
            subject="Tạo phòng ban"
        )
        
        return record
    
    def write(self, vals):
        """Override write"""
        # Track manager change
        if 'manager_id' in vals:
            for record in self:
                old_manager = record.manager_id
                new_manager = self.env['nhan.su'].browse(vals['manager_id']) if vals['manager_id'] else False
                
                if old_manager != new_manager:
                    record.message_post(
                        body=f"Trưởng phòng thay đổi: {old_manager.name if old_manager else 'Không có'} → {new_manager.name if new_manager else 'Không có'}",
                        subject="Thay đổi trưởng phòng"
                    )
        
        return super().write(vals)
    
    def unlink(self):
        """Không cho xóa phòng ban có nhân viên hoặc phòng ban con"""
        for record in self:
            if record.employee_count > 0:
                raise ValidationError(
                    f'Không thể xóa phòng ban {record.name}!\n'
                    f'Phòng ban còn {record.employee_count} nhân viên.\n'
                    f'Vui lòng chuyển nhân viên sang phòng ban khác trước.'
                )
            
            if record.child_count > 0:
                raise ValidationError(
                    f'Không thể xóa phòng ban {record.name}!\n'
                    f'Phòng ban còn {record.child_count} phòng ban con.\n'
                    f'Vui lòng xóa hoặc chuyển các phòng ban con trước.'
                )
        
        return super().unlink()
    
    # ==================== ACTION METHODS ====================
    
    def action_view_employees(self):
        """Xem danh sách nhân viên trong phòng ban"""
        self.ensure_one()
        return {
            'name': f'Nhân viên - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'nhan.su',
            'view_mode': 'tree,form,kanban',
            'domain': [('department_id', '=', self.id)],
            'context': {
                'default_department_id': self.id,
                'search_default_working': 1,
            }
        }
    
    def action_view_child_departments(self):
        """Xem phòng ban con"""
        self.ensure_one()
        return {
            'name': f'Phòng ban cấp dưới - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'phong.ban',
            'view_mode': 'tree,form,kanban',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id}
        }
    
    # ==================== NAME & DISPLAY ====================
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Search by code or name"""
        args = args or []
        if name:
            records = self._search([
                '|',
                ('code', operator, name),
                ('name', operator, name)
            ] + args, limit=limit, access_rights_uid=name_get_uid)
        else:
            records = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return records
