# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class KhachHangInteraction(models.Model):
    _name = 'khach.hang.interaction'
    _description = 'Tương tác với khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'interaction_date desc, id desc'

    # ==================== THÔNG TIN CƠ BẢN ====================
    
    name = fields.Char(
        string='Tên tương tác',
        required=True,
        tracking=True,
        help='Tên mô tả tương tác (VD: Gọi điện, Gửi báo giá, Hẹn gặp)'
    )
    
    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        required=True,
        tracking=True,
        ondelete='cascade',
        index=True
    )
    
    interaction_type = fields.Selection([
        ('call', 'Gọi điện'),
        ('email', 'Gửi email'),
        ('meeting', 'Hẹn gặp'),
        ('quote', 'Gửi báo giá'),
        ('presentation', 'Thuyết trình'),
        ('demo', 'Demo sản phẩm'),
        ('visit', 'Thăm khách hàng'),
        ('other', 'Khác')
    ], string='Loại tương tác', required=True, default='call', tracking=True)
    
    interaction_date = fields.Datetime(
        string='Thời gian tương tác',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    employee_id = fields.Many2one(
        'nhan.su',
        string='Nhân viên thực hiện',
        required=False,  # Cho phép để trống để tester hoặc user chưa mapping employee vẫn ghi nhận được tương tác
        tracking=True,
        domain="[('working_status', '=', 'working')]",
        default=lambda self: self._default_employee()
    )
    
    duration = fields.Float(
        string='Thời lượng (phút)',
        help='Thời gian tương tác (VD: 15 phút cho cuộc gọi)'
    )
    
    # ==================== NỘI DUNG ====================
    
    description = fields.Html(
        string='Nội dung tương tác',
        required=True,
        tracking=True,
        help='Mô tả chi tiết về cuộc tương tác'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'khach_hang_interaction_attachment_rel',
        'interaction_id',
        'attachment_id',
        string='File đính kèm',
        help='Các file bằng chứng liên quan đến tương tác này (email, ghi âm, hình ảnh, tài liệu, ...)'
    )
    
    outcome = fields.Selection([
        ('positive', 'Tích cực'),
        ('neutral', 'Trung tính'),
        ('negative', 'Tiêu cực'),
        ('pending', 'Đang chờ phản hồi')
    ], string='Kết quả', default='pending', tracking=True)
    
    next_action = fields.Text(
        string='Hành động tiếp theo',
        help='Các bước tiếp theo cần thực hiện'
    )
    
    next_action_date = fields.Date(
        string='Ngày thực hiện tiếp theo',
        help='Ngày dự kiến thực hiện hành động tiếp theo'
    )
    
    # ==================== PHÁT SINH CÔNG VIỆC ====================
    
    # Tạm thời comment để tránh lỗi khi cài module mới
    # Uncomment sau khi đã cài xong cả quan_ly_cong_viec và upgrade
    # task_ids = fields.One2many(
    #     'cong.viec',
    #     'interaction_id',
    #     string='Công việc phát sinh',
    #     help='Các công việc được tạo từ tương tác này'
    # )
    
    task_count = fields.Integer(
        string='Số công việc',
        compute='_compute_task_count',
        store=False
    )
    
    # ==================== METADATA ====================
    
    active = fields.Boolean(
        string='Hoạt động',
        default=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company
    )
    
    # ==================== COMPUTE METHODS ====================
    
    @api.depends('customer_id')
    def _compute_task_count(self):
        """Đếm số công việc phát sinh từ tương tác"""
        for record in self:
            # Tạm thời return 0 vì task_ids đang comment
            # Sau khi uncomment task_ids, đổi depends thành 'task_ids'
            record.task_count = 0
            # Code sau khi uncomment task_ids:
            # if 'cong.viec' in self.env:
            #     try:
            #         record.task_count = self.env['cong.viec'].search_count([
            #             ('interaction_id', '=', record.id)
            #         ])
            #     except Exception:
            #         record.task_count = 0
            # else:
            #     record.task_count = 0
    
    # ==================== HELPER METHODS ====================
    
    def _default_employee(self):
        """Lấy nhân viên mặc định từ khách hàng"""
        # Có thể override trong context
        try:
            if self._context.get('default_customer_id'):
                customer = self.env['khach.hang'].browse(self._context['default_customer_id'])
                if customer.exists() and customer.primary_employee_id:
                    return customer.primary_employee_id.id
        except Exception:
            pass
        return False
    
    # ==================== ACTION METHODS ====================
    
    def action_create_task(self):
        """Tạo công việc từ tương tác này"""
        self.ensure_one()
        
        return {
            'name': f'Tạo công việc - {self.customer_id.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'view_mode': 'form',
            'context': {
                'default_customer_id': self.customer_id.id,
                'default_assigned_employee_id': self.employee_id.id,
                # 'default_interaction_id': self.id,  # Tạm thời comment để tránh lỗi database
                'default_name': f'{self.name} - {self.customer_id.display_name}',
                'default_requirement': f'<p><strong>Từ tương tác:</strong> {self.name}</p><p>{self.description or ""}</p>',
                'default_priority': '2' if self.outcome == 'negative' else '1',
            },
            'target': 'new',
        }
    
    def action_view_tasks(self):
        """Xem danh sách công việc phát sinh"""
        self.ensure_one()
        return {
            'name': f'Công việc - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'view_mode': 'kanban,tree,form,calendar',
            # Tạm thời filter theo customer_id thay vì interaction_id
            'domain': [('customer_id', '=', self.customer_id.id)],
            'context': {
                # 'default_interaction_id': self.id,  # Tạm thời comment để tránh lỗi database
                'default_customer_id': self.customer_id.id,
            }
        }
    
    # ==================== CRUD METHODS ====================
    
    @api.model
    def create(self, vals):
        """Override create"""
        record = super().create(vals)
        
        # Notify assigned employee
        if record.employee_id and record.employee_id.user_id:
            record.message_subscribe(partner_ids=record.employee_id.user_id.partner_id.ids)
        
        # Update customer last contact date
        if record.customer_id:
            record.customer_id.write({
                'last_contact_date': record.interaction_date
            })
            
            # Auto-update customer status nếu cần (chỉ khi có tương tác thực tế)
            # Không tự động chuyển, để user tự chuyển bằng action_set_contacted (có validation)
            # if record.customer_id.status == 'lead' and record.interaction_type in ['call', 'meeting', 'visit']:
            #     record.customer_id.status = 'contacted'
        
        return record
    
    def write(self, vals):
        """Override write"""
        result = super().write(vals)
        
        # Update customer last contact date
        if 'interaction_date' in vals or 'customer_id' in vals:
            for record in self:
                if record.customer_id:
                    record.customer_id.write({
                        'last_contact_date': record.interaction_date
                    })
        
        return result

