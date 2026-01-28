# -*- coding: utf-8 -*-
"""
Wizard đánh giá báo cáo công việc bằng AI
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64


class TaskReportEvaluationWizard(models.TransientModel):
    """Wizard upload báo cáo và đánh giá bằng AI"""
    
    _name = 'task.report.evaluation.wizard'
    _description = 'Wizard đánh giá báo cáo AI'
    
    task_id = fields.Many2one(
        'cong.viec',
        string='Công việc',
        required=True,
        readonly=True
    )
    
    task_name = fields.Char(
        related='task_id.name',
        string='Tên công việc',
        readonly=True
    )
    
    task_requirement = fields.Html(
        related='task_id.requirement',
        string='Yêu cầu',
        readonly=True
    )
    
    # Kết quả công việc
    result_note = fields.Html(
        string='Báo cáo kết quả',
        help='Mô tả chi tiết công việc đã làm'
    )
    
    result_file_ids = fields.Many2many(
        'ir.attachment',
        'task_report_wizard_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='File báo cáo',
        help='Upload file báo cáo: PDF, DOCX, TXT'
    )
    
    actual_hours = fields.Float(
        string='Số giờ thực tế',
        help='Số giờ đã làm thực tế'
    )
    
    # Kết quả đánh giá
    evaluation_done = fields.Boolean(
        string='Đã đánh giá',
        default=False,
        readonly=True
    )
    
    ai_overall_completion = fields.Float(
        string='% Hoàn thành',
        readonly=True
    )
    
    ai_grade = fields.Char(
        string='Xếp loại',
        readonly=True
    )
    
    ai_completed_items = fields.Text(
        string='✅ Đã hoàn thành',
        readonly=True
    )
    
    ai_incomplete_items = fields.Text(
        string='❌ Chưa hoàn thành',
        readonly=True
    )
    
    ai_exceeded_items = fields.Text(
        string='⭐ Làm vượt mức',
        readonly=True
    )
    
    ai_detailed_analysis = fields.Text(
        string='Phân tích chi tiết',
        readonly=True
    )
    
    ai_recommendations = fields.Text(
        string='Khuyến nghị',
        readonly=True
    )
    
    @api.model
    def default_get(self, fields_list):
        """Load dữ liệu từ task"""
        res = super().default_get(fields_list)
        
        task_id = self.env.context.get('active_id')
        if task_id:
            task = self.env['cong.viec'].browse(task_id)
            res.update({
                'task_id': task.id,
                'result_note': task.result_note or '',
                'actual_hours': task.actual_hours or 0.0,
                'result_file_ids': [(6, 0, task.result_file_ids.ids)]
            })
        
        return res
    
    def action_evaluate_with_ai(self):
        """
        Đánh giá báo cáo bằng AI
        """
        self.ensure_one()
        
        if not self.result_note and not self.result_file_ids:
            raise UserError('Vui lòng nhập báo cáo kết quả hoặc upload file báo cáo!')
        
        ai_task_service = self.env['ai.task.service']
        
        try:
            # Chuẩn bị dữ liệu
            task_data = {
                'task_code': self.task_id.task_code,
                'name': self.task_id.name,
                'requirement': self.task_id.requirement or '',
                'acceptance_criteria': self.task_id.acceptance_criteria or '',
                'deliverable': self.task_id.deliverable or '',
                'result_note': self.result_note or self.task_id.result_note or '',
                'estimated_hours': self.task_id.estimated_hours,
                'actual_hours': self.actual_hours or self.task_id.actual_hours,
                'deadline': self.task_id.deadline,
                'completed_date': self.task_id.completed_date or fields.Datetime.now(),
                'is_overdue': self.task_id.is_overdue,
                'has_result_files': len(self.result_file_ids) > 0
            }
            
            # Chuẩn bị files
            report_files = []
            for attachment in self.result_file_ids:
                try:
                    file_data = base64.b64decode(attachment.datas)
                    report_files.append({
                        'filename': attachment.name,
                        'file_data': file_data
                    })
                except Exception as e:
                    # Bỏ qua file lỗi
                    pass
            
            # Gọi AI đánh giá
            result = ai_task_service.evaluate_task_report(task_data, report_files)
            
            # Lưu kết quả vào wizard
            self.write({
                'evaluation_done': True,
                'ai_overall_completion': result.get('overall_completion', 0),
                'ai_grade': result.get('grade', 'B'),
                'ai_completed_items': result.get('completed_items', ''),
                'ai_incomplete_items': result.get('incomplete_items', ''),
                'ai_exceeded_items': result.get('exceeded_items', ''),
                'ai_detailed_analysis': result.get('detailed_analysis', ''),
                'ai_recommendations': result.get('recommendations', '')
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🤖 Đánh giá hoàn tất',
                    'message': f'Hoàn thành: {result.get("overall_completion", 0):.0f}% - Xếp loại: {result.get("grade", "B")}',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(f'Lỗi đánh giá AI:\n{str(e)[:500]}')
    
    def action_save_and_apply(self):
        """
        Lưu kết quả vào task và áp dụng đánh giá AI
        """
        self.ensure_one()
        
        if not self.evaluation_done:
            raise UserError('Vui lòng đánh giá bằng AI trước khi lưu!')
        
        # Cập nhật task
        vals = {
            'result_note': self.result_note,
            'actual_hours': self.actual_hours,
            'result_file_ids': [(6, 0, self.result_file_ids.ids)],
            'ai_report_evaluated': True,
            'ai_overall_completion': self.ai_overall_completion,
            'ai_requirement_match_score': self.ai_overall_completion,  # Simplified
            'ai_quality_score': self.ai_overall_completion,
            'ai_completed_items': self.ai_completed_items,
            'ai_incomplete_items': self.ai_incomplete_items,
            'ai_exceeded_items': self.ai_exceeded_items,
            'ai_detailed_analysis': self.ai_detailed_analysis,
            'ai_recommendation': self.ai_recommendations,
            'ai_grade': self.ai_grade,
            'ai_evaluation_date': fields.Datetime.now()
        }
        
        self.task_id.write(vals)
        
        # Post message
        self.task_id.message_post(
            body=f"""
            <h3>📝 Báo cáo công việc đã được đánh giá bằng AI</h3>
            <h4>📊 Kết quả:</h4>
            <ul>
                <li><strong>Hoàn thành:</strong> {self.ai_overall_completion:.1f}%</li>
                <li><strong>Xếp loại:</strong> {self.ai_grade}</li>
            </ul>
            <h4>✅ Đã làm:</h4>
            <pre>{self.ai_completed_items[:300]}</pre>
            <h4>❌ Chưa làm:</h4>
            <pre>{self.ai_incomplete_items[:300]}</pre>
            <h4>💡 Khuyến nghị:</h4>
            <pre>{self.ai_recommendations[:300]}</pre>
            """,
            subject="🤖 AI Evaluation Report"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Đã lưu thành công',
                'message': f'Kết quả đánh giá đã được lưu vào công việc',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }


class TaskSubmitReportWizard(models.TransientModel):
    """Wizard nộp báo cáo (cho nhân viên)"""
    
    _name = 'task.submit.report.wizard'
    _description = 'Wizard nộp báo cáo'
    
    task_id = fields.Many2one(
        'cong.viec',
        string='Công việc',
        required=True,
        readonly=True
    )
    
    result_note = fields.Html(
        string='Báo cáo kết quả',
        required=True,
        help='Mô tả chi tiết những gì bạn đã làm'
    )
    
    result_file_ids = fields.Many2many(
        'ir.attachment',
        'task_submit_wizard_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='File kết quả',
        help='Upload file: Word, PDF, Excel, ZIP, v.v.'
    )
    
    actual_hours = fields.Float(
        string='Số giờ đã làm',
        required=True,
        help='Tổng số giờ thực tế bạn đã làm'
    )
    
    submit_for_review = fields.Boolean(
        string='Gửi duyệt ngay',
        default=True,
        help='Chuyển sang trạng thái "Chờ duyệt" sau khi nộp'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Load dữ liệu từ task"""
        res = super().default_get(fields_list)
        
        task_id = self.env.context.get('active_id')
        if task_id:
            task = self.env['cong.viec'].browse(task_id)
            res.update({
                'task_id': task.id,
                'result_note': task.result_note or '',
                'actual_hours': task.actual_hours or task.estimated_hours,
                'result_file_ids': [(6, 0, task.result_file_ids.ids)]
            })
        
        return res
    
    def action_submit_report(self):
        """
        Nộp báo cáo công việc
        """
        self.ensure_one()
        
        # Validate
        if not self.result_note:
            raise UserError('Vui lòng nhập báo cáo kết quả!')
        
        if self.actual_hours <= 0:
            raise UserError('Vui lòng nhập số giờ đã làm!')
        
        # Cập nhật task
        vals = {
            'result_note': self.result_note,
            'actual_hours': self.actual_hours,
            'result_file_ids': [(6, 0, self.result_file_ids.ids)],
            'progress': 100
        }
        
        if self.submit_for_review:
            vals['state'] = 'review'
        
        self.task_id.write(vals)
        
        # Post message
        self.task_id.message_post(
            body=f"""
            <h3>📝 Nhân viên đã nộp báo cáo</h3>
            <ul>
                <li><strong>Số giờ làm:</strong> {self.actual_hours:.1f}h (Ước lượng: {self.task_id.estimated_hours:.1f}h)</li>
                <li><strong>Số file đính kèm:</strong> {len(self.result_file_ids)}</li>
                <li><strong>Trạng thái:</strong> {'Chờ duyệt' if self.submit_for_review else 'Đang thực hiện'}</li>
            </ul>
            <p><em>Báo cáo đã được nộp. Người giám sát có thể sử dụng AI để đánh giá.</em></p>
            """,
            subject="📤 Báo cáo công việc"
        )
        
        # Notify supervisor
        if self.submit_for_review and self.task_id.supervisor_id and self.task_id.supervisor_id.user_id:
            self.task_id.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.task_id.supervisor_id.user_id.id,
                summary=f'Duyệt báo cáo: {self.task_id.name}',
                note=f'Nhân viên {self.task_id.assigned_employee_id.name} đã nộp báo cáo.\n'
                     f'Số giờ: {self.actual_hours:.1f}h\n'
                     f'File: {len(self.result_file_ids)}\n\n'
                     f'💡 Sử dụng nút "Đánh giá AI" để phân tích tự động.'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Đã nộp báo cáo',
                'message': 'Báo cáo của bạn đã được gửi' + (' để duyệt' if self.submit_for_review else ''),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }
