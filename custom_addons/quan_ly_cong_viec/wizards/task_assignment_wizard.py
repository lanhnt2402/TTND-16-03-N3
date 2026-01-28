# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class TaskAssignmentWizard(models.TransientModel):
    """Wizard phân công công việc hàng loạt"""
    _name = 'task.assignment.wizard'
    _description = 'Wizard phân công công việc'

    # Chọn nhân viên
    employee_ids = fields.Many2many(
        'nhan.su',
        string='Nhân viên',
        required=True,
        domain="[('working_status', '=', 'working')]",
        help='Chọn nhân viên để phân công công việc'
    )
    
    # Chọn khách hàng (optional)
    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        help='Công việc liên quan đến khách hàng (tùy chọn)'
    )
    
    # Thông tin công việc
    task_name = fields.Char(
        string='Tên công việc',
        required=True
    )
    
    requirement = fields.Html(
        string='Yêu cầu công việc',
        required=True
    )
    
    acceptance_criteria = fields.Text(
        string='Tiêu chí nghiệm thu'
    )
    
    deliverable = fields.Char(
        string='Sản phẩm bàn giao'
    )
    
    # Thời gian
    deadline = fields.Datetime(
        string='Deadline',
        required=True,
        default=fields.Datetime.now
    )
    
    estimated_hours = fields.Float(
        string='Thời gian ước lượng (giờ)',
        default=8.0
    )
    
    # Ưu tiên
    priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Bình thường'),
        ('2', 'Cao'),
        ('3', 'Rất cao')
    ], string='Ưu tiên', default='1')
    
    # Người giám sát
    supervisor_id = fields.Many2one(
        'nhan.su',
        string='Người giám sát',
        domain="[('working_status', '=', 'working')]"
    )
    
    # Tags
    tag_ids = fields.Many2many(
        'cong.viec.tag',
        string='Tags'
    )
    
    # Gửi email thông báo (Đã tắt - chỉ hiện thông báo trong Odoo)
    send_email = fields.Boolean(
        string='Gửi email thông báo',
        default=False,
        help='Tính năng đã tắt. Chỉ hiện thông báo trong Odoo.'
    )
    
    # AI Suggestions
    use_ai_suggestion = fields.Boolean(
        string='Sử dụng gợi ý AI',
        default=False,
        help='AI sẽ gợi ý nhân viên phù hợp nhất'
    )
    
    ai_suggested_employee_id = fields.Many2one(
        'nhan.su',
        string='Nhân viên được AI gợi ý',
        readonly=True
    )
    
    ai_suggestion_confidence = fields.Float(
        string='Độ tin cậy gợi ý (%)',
        readonly=True
    )
    
    ai_suggestion_reasoning = fields.Text(
        string='Lý do gợi ý',
        readonly=True
    )
    
    ai_predicted_hours = fields.Float(
        string='Thời gian dự đoán (giờ)',
        readonly=True,
        help='AI dự đoán thời gian hoàn thành'
    )
    
    def action_get_ai_suggestions(self):
        """
        Gọi AI để gợi ý nhân viên phù hợp nhất
        """
        self.ensure_one()
        
        if not self.task_name or not self.requirement:
            raise UserError('Vui lòng nhập tên công việc và yêu cầu trước khi lấy gợi ý AI!')
        
        ai_task_service = self.env['ai.task.service']
        
        try:
            # Chuẩn bị thông tin task
            import re
            task_info = {
                'name': self.task_name,
                'requirement': re.sub(r'<[^>]+>', '', self.requirement or ''),
                'estimated_hours': self.estimated_hours,
                'priority': dict(self._fields['priority'].selection).get(self.priority, 'Bình thường'),
                'deadline': self.deadline,
                'required_skills': []  # TODO: Extract from requirement
            }
            
            # Lấy danh sách nhân viên khả dụng
            employees = self.env['nhan.su'].search([
                ('working_status', '=', 'working')
            ])
            
            available_employees = []
            for emp in employees:
                # Đếm số task hiện tại
                current_tasks = self.env['cong.viec'].search_count([
                    ('assigned_employee_id', '=', emp.id),
                    ('state', 'not in', ['done', 'cancelled'])
                ])
                
                # Tính workload
                workload_tasks = self.env['cong.viec'].search([
                    ('assigned_employee_id', '=', emp.id),
                    ('state', 'not in', ['done', 'cancelled'])
                ])
                workload_hours = sum(workload_tasks.mapped('estimated_hours'))
                
                # Tính completion rate
                total_tasks = self.env['cong.viec'].search_count([
                    ('assigned_employee_id', '=', emp.id)
                ])
                completed_tasks = self.env['cong.viec'].search_count([
                    ('assigned_employee_id', '=', emp.id),
                    ('state', '=', 'done')
                ])
                completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                
                # Tính avg quality score
                done_tasks = self.env['cong.viec'].search([
                    ('assigned_employee_id', '=', emp.id),
                    ('state', '=', 'done'),
                    ('ai_quality_score', '>', 0)
                ])
                avg_quality = sum(done_tasks.mapped('ai_quality_score')) / len(done_tasks) if done_tasks else 70
                
                available_employees.append({
                    'id': emp.id,
                    'name': emp.name,
                    'job_position': emp.job_position or 'N/A',
                    'skills': emp.notes or '',
                    'current_tasks_count': current_tasks,
                    'avg_completion_rate': completion_rate,
                    'avg_quality_score': avg_quality,
                    'workload_hours': workload_hours
                })
            
            # Gọi AI
            result = ai_task_service.suggest_task_assignment(task_info, available_employees)
            
            # Cập nhật gợi ý
            self.write({
                'ai_suggested_employee_id': result.get('recommended_employee_id'),
                'ai_suggestion_confidence': result.get('confidence_score', 0),
                'ai_suggestion_reasoning': result.get('reasoning', ''),
                'use_ai_suggestion': True
            })
            
            # Dự đoán thời gian
            if result.get('recommended_employee_id'):
                predicted = ai_task_service.predict_task_duration(
                    f"{self.task_name}\n\n{re.sub(r'<[^>]+>', '', self.requirement or '')}",
                    result.get('recommended_employee_id')
                )
                self.ai_predicted_hours = predicted.get('predicted_hours', self.estimated_hours)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🤖 AI Gợi ý nhân viên',
                    'message': f'Độ tin cậy: {result.get("confidence_score", 0):.0f}% - {result.get("reasoning", "")}',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(f'Lỗi gọi AI:\n{str(e)[:500]}')
    
    def action_apply_ai_suggestion(self):
        """
        Áp dụng gợi ý của AI vào employee_ids
        """
        self.ensure_one()
        
        if not self.ai_suggested_employee_id:
            raise UserError('Chưa có gợi ý AI! Vui lòng nhấn "Lấy gợi ý AI" trước.')
        
        self.employee_ids = [(6, 0, [self.ai_suggested_employee_id.id])]
        
        if self.ai_predicted_hours > 0:
            self.estimated_hours = self.ai_predicted_hours
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Đã áp dụng',
                'message': f'Chọn: {self.ai_suggested_employee_id.name} ({self.ai_predicted_hours:.1f}h)',
                'type': 'success',
            }
        }
    
    def action_assign_tasks(self):
        """Tạo và phân công công việc cho các nhân viên đã chọn"""
        self.ensure_one()
        
        if not self.employee_ids:
            raise UserError(_('Vui lòng chọn ít nhất một nhân viên!'))
        
        # Tạo công việc cho từng nhân viên
        tasks_created = self.env['cong.viec']
        
        for employee in self.employee_ids:
            # Tạo task
            task_vals = {
                'name': f"{self.task_name} - {employee.name}",
                'requirement': self.requirement,
                'acceptance_criteria': self.acceptance_criteria,
                'deliverable': self.deliverable,
                'assigned_employee_id': employee.id,
                'customer_id': self.customer_id.id if self.customer_id else False,
                'supervisor_id': self.supervisor_id.id if self.supervisor_id else False,
                'deadline': self.deadline,
                'estimated_hours': self.estimated_hours,
                'priority': self.priority,
                'tag_ids': [(6, 0, self.tag_ids.ids)],
                'state': 'todo',
            }
            
            task = self.env['cong.viec'].create(task_vals)
            tasks_created |= task
            
            # CHỈ HIỆN THÔNG BÁO - KHÔNG GỬI EMAIL
            # Thông báo đã được tự động tạo trong create() method của cong.viec
            # (message_post và activity_schedule)
        
        # Thông báo thành công
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thành công!'),
                'message': _('Đã tạo %d công việc cho %d nhân viên.') % (len(tasks_created), len(self.employee_ids)),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'cong.viec',
                    'view_mode': 'tree,form',
                    'domain': [('id', 'in', tasks_created.ids)],
                    'name': _('Công việc vừa tạo'),
                },
            }
        }


class BulkTaskUpdateWizard(models.TransientModel):
    """Wizard cập nhật hàng loạt công việc"""
    _name = 'bulk.task.update.wizard'
    _description = 'Wizard cập nhật hàng loạt'

    task_ids = fields.Many2many(
        'cong.viec',
        string='Công việc',
        required=True
    )
    
    # Fields có thể cập nhật
    update_state = fields.Boolean('Cập nhật trạng thái')
    new_state = fields.Selection([
        ('draft', 'Nháp'),
        ('todo', 'Cần làm'),
        ('in_progress', 'Đang thực hiện'),
        ('review', 'Đang review'),
        ('done', 'Hoàn thành'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái mới')
    
    update_priority = fields.Boolean('Cập nhật ưu tiên')
    new_priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Bình thường'),
        ('2', 'Cao'),
        ('3', 'Rất cao')
    ], string='Ưu tiên mới')
    
    update_deadline = fields.Boolean('Cập nhật deadline')
    new_deadline = fields.Datetime('Deadline mới')
    
    update_supervisor = fields.Boolean('Cập nhật người giám sát')
    new_supervisor_id = fields.Many2one('nhan.su', string='Người giám sát mới')
    
    update_tags = fields.Boolean('Cập nhật tags')
    new_tag_ids = fields.Many2many('cong.viec.tag', string='Tags mới')
    
    @api.model
    def default_get(self, fields_list):
        """Lấy tasks đã chọn từ context"""
        res = super().default_get(fields_list)
        
        # Lấy active_ids từ context
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['task_ids'] = [(6, 0, active_ids)]
        
        return res
    
    def action_update_tasks(self):
        """Cập nhật hàng loạt các công việc"""
        self.ensure_one()
        
        if not self.task_ids:
            raise UserError(_('Không có công việc nào được chọn!'))
        
        # Chuẩn bị values để update
        vals = {}
        
        if self.update_state and self.new_state:
            vals['state'] = self.new_state
        
        if self.update_priority and self.new_priority:
            vals['priority'] = self.new_priority
        
        if self.update_deadline and self.new_deadline:
            vals['deadline'] = self.new_deadline
        
        if self.update_supervisor:
            vals['supervisor_id'] = self.new_supervisor_id.id if self.new_supervisor_id else False
        
        if self.update_tags:
            vals['tag_ids'] = [(6, 0, self.new_tag_ids.ids)]
        
        if not vals:
            raise UserError(_('Vui lòng chọn ít nhất một trường để cập nhật!'))
        
        # Cập nhật
        self.task_ids.write(vals)
        
        # Thông báo thành công
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thành công!'),
                'message': _('Đã cập nhật %d công việc.') % len(self.task_ids),
                'type': 'success',
                'sticky': False,
            }
        }
