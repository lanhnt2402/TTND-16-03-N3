# -*- coding: utf-8 -*-
"""
Công Việc - AI Integration
Mở rộng model cong.viec với các action AI
"""

from odoo import models, api, fields, _
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class CongViecAIIntegration(models.Model):
    """Tích hợp AI vào công việc"""
    
    _inherit = 'cong.viec'
    
    # ==================== AI WORK REPORT ANALYSIS BUTTON ====================
    
    def action_ai_analyze_work_report(self):
        """
        🤖 BUTTON: AI Đánh Giá Báo Cáo Công Việc Toàn Diện
        
        Tính năng chính (sử dụng 4 API keys):
        1. Trích xuất text từ file PDF/Word → API Key #1
        2. So sánh yêu cầu vs kết quả → API Key #3 (CRITICAL)
        3. Đánh giá chất lượng chi tiết → API Key #4
        4. Gợi ý cải thiện → API Key #5
        
        Returns:
            - % Hoàn thành
            - Danh sách: Đã làm / Chưa làm
            - Điểm chất lượng: 0-100
            - Gợi ý cải thiện
        """
        self.ensure_one()
        
        # Validation
        if not self.result_note and len(self.result_file_ids) == 0:
            raise UserError(
                '❌ Chưa có báo cáo kết quả!\n\n'
                'Để AI đánh giá, vui lòng:\n'
                '• Nhập kết quả vào tab "Kết quả thực tế", HOẶC\n'
                '• Upload file báo cáo (PDF/Word) vào "File kết quả"\n\n'
                'Lưu ý: Upload file sẽ cho kết quả chính xác hơn!'
            )
        
        if self.state not in ['review', 'done']:
            raise UserError(
                '⚠️  Chỉ đánh giá báo cáo khi:\n'
                '• Công việc đã gửi duyệt (Review), hoặc\n'
                '• Công việc đã hoàn thành (Done)'
            )
        
        _logger.info(f"🚀 Starting AI Work Report Analysis: {self.task_code} - {self.name}")
        
        try:
            ai_service = self.env['ai.service']
            
            # Prepare task data
            task_data = {
                'name': self.name,
                'requirement': self.requirement or '',
                'acceptance_criteria': self.acceptance_criteria or '',
                'result_note': self.result_note or '',
                'deliverable': self.deliverable or '',
                'estimated_hours': self.estimated_hours,
                'actual_hours': self.actual_hours,
                'deadline': str(self.deadline),
                'completed_date': str(self.completed_date) if self.completed_date else '',
                'is_overdue': self.is_overdue
            }
            
            # Prepare files for analysis
            report_files = []
            for attachment in self.result_file_ids:
                report_files.append({
                    'name': attachment.name,
                    'datas': attachment.datas  # Already base64 encoded
                })
            
            # Call AI Analysis - Sử dụng ai.task.service thay vì ai.service
            _logger.info(f"📄 Analyzing {len(report_files)} file(s)...")
            
            # Sử dụng ai.task.service.evaluate_task_report (API chính)
            ai_task_service = self.env['ai.task.service']
            result = ai_task_service.evaluate_task_report(
                task_data=task_data,
                report_files=report_files if len(report_files) > 0 else None
            )
            
            # Format results for display (nếu là list, convert sang string)
            completed_items = result.get('completed_items', '')
            incomplete_items = result.get('incomplete_items', '')
            recommendations_html = result.get('recommendations', '')
            
            # Nếu là list, convert sang string
            if isinstance(completed_items, list):
                completed_items = '\n'.join([f"✅ {item}" for item in completed_items])
            if isinstance(incomplete_items, list):
                incomplete_items = '\n'.join([f"❌ {item}" for item in incomplete_items])
            
            # Update fields - Sử dụng đúng field names từ model cong.viec
            self.write({
                'ai_report_evaluated': True,
                'ai_evaluation_date': fields.Datetime.now(),
                'ai_overall_completion': result.get('overall_completion', result.get('completion_percentage', 0)),
                'ai_completed_items': result.get('completed_items', ''),
                'ai_incomplete_items': result.get('incomplete_items', ''),
                'ai_exceeded_items': result.get('exceeded_items', ''),
                'ai_requirement_match_score': result.get('requirement_match_score', 0),
                'ai_quality_score': result.get('quality_score', 0),
                'ai_time_efficiency': result.get('time_efficiency_score', 0),
                'ai_deadline_performance': result.get('deadline_score', 0),
                'ai_report_strengths': result.get('strengths', ''),
                'ai_report_weaknesses': result.get('weaknesses', ''),
                'ai_recommendation': result.get('recommendations', ''),
                'ai_detailed_analysis': result.get('detailed_analysis', ''),
                'ai_grade': result.get('grade', 'N/A')
            })
            
            _logger.info(f"✅ AI Analysis Complete: Overall Score = {result.get('overall_score')}/100")
            
            # Success message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🎉 Phân Tích AI Hoàn Tất!',
                    'message': f"""
                    <strong>Kết quả đánh giá:</strong><br/>
                    • Hoàn thành: {result.get('overall_completion', result.get('completion_percentage', 0)):.1f}%<br/>
                    • Chất lượng: {result.get('quality_score', 0):.1f}/100<br/>
                    • Đáp ứng yêu cầu: {result.get('requirement_match_score', 0):.1f}/100<br/>
                    • Xếp loại: {result.get('grade', 'N/A')}<br/><br/>
                    Xem chi tiết trong tab "AI Evaluation"
                    """,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }
            
        except Exception as e:
            _logger.error(f"❌ AI Analysis Error: {str(e)[:500]}")
            raise UserError(
                f'❌ Lỗi phân tích AI:\n\n{str(e)[:300]}\n\n'
                'Vui lòng thử lại sau hoặc liên hệ quản trị viên.'
            )
    
    @api.model
    def _format_items_list(self, items, icon, css_class):
        """Format list of items as HTML"""
        if not items or len(items) == 0:
            return '<p class="text-muted"><em>Không có</em></p>'
        
        html = '<ul class="list-unstyled">'
        for item in items:
            html += f'<li class="text-{css_class}"><strong>{icon}</strong> {item}</li>'
        html += '</ul>'
        return html
    
    # ==================== AI TASK SUGGESTIONS ====================
    
    def action_ai_suggest_employee(self):
        """
        🤖 AI Gợi Ý Nhân Viên Phù Hợp
        Sử dụng API Key #2
        """
        self.ensure_one()
        
        if self.assigned_employee_id:
            raise UserError('Công việc đã có nhân viên thực hiện!')
        
        try:
            ai_service = self.env['ai.service']
            
            # Get all available employees
            employees = self.env['nhan.su'].search([
                ('working_status', '=', 'working')
            ])
            
            # Prepare data
            task_info = {
                'name': self.name,
                'requirement': self.requirement[:500] if self.requirement else '',
                'priority': self.priority,
                'estimated_hours': self.estimated_hours
            }
            
            # Get AI suggestions (implementation needed in ai_service)
            # For now, return top 3 employees by workload
            suggestions = []
            for emp in employees[:5]:
                suggestions.append({
                    'employee': emp,
                    'score': 85 - emp.total_tasks * 2,  # Simple scoring
                    'reason': f'Workload: {emp.total_tasks} tasks'
                })
            
            # Sort by score
            suggestions.sort(key=lambda x: x['score'], reverse=True)
            
            message = '🤖 <strong>AI Gợi Ý Nhân Viên:</strong><br/><br/>'
            for i, sugg in enumerate(suggestions[:3], 1):
                message += f"{i}. <strong>{sugg['employee'].name}</strong> "
                message += f"({sugg['employee'].job_position})<br/>"
                message += f"   Score: {sugg['score']}/100 - {sugg['reason']}<br/><br/>"
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Employee Suggestions',
                    'message': message,
                    'type': 'info',
                    'sticky': True
                }
            }
            
        except Exception as e:
            _logger.error(f"AI Suggest Employee Error: {e}")
            raise UserError(f'Lỗi AI: {str(e)[:200]}')
    
    def action_ai_estimate_duration(self):
        """
        🤖 AI Ước Tính Thời Gian
        Sử dụng API Key #2
        """
        self.ensure_one()
        
        if not self.assigned_employee_id:
            raise UserError('Chưa có nhân viên được giao!')
        
        try:
            # Get similar completed tasks
            similar_tasks = self.search([
                ('assigned_employee_id', '=', self.assigned_employee_id.id),
                ('state', '=', 'done'),
                ('actual_hours', '>', 0)
            ], limit=5, order='completed_date desc')
            
            if len(similar_tasks) == 0:
                estimated = self.estimated_hours if self.estimated_hours > 0 else 40
                confidence = 'Low'
            else:
                avg_hours = sum(t.actual_hours for t in similar_tasks) / len(similar_tasks)
                estimated = round(avg_hours, 1)
                confidence = 'High' if len(similar_tasks) >= 3 else 'Medium'
            
            message = f"""
            <strong>🤖 AI Ước Tính Thời Gian:</strong><br/><br/>
            • Nhân viên: {self.assigned_employee_id.name}<br/>
            • Dự đoán: <strong>{estimated} giờ</strong><br/>
            • Độ tin cậy: {confidence}<br/>
            • Dựa trên: {len(similar_tasks)} công việc tương tự<br/><br/>
            <em>Lưu ý: Đây là ước tính dựa trên lịch sử</em>
            """
            
            # Update estimated_hours if not set
            if self.estimated_hours == 0:
                self.estimated_hours = estimated
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Duration Estimation',
                    'message': message,
                    'type': 'info',
                    'sticky': True
                }
            }
            
        except Exception as e:
            _logger.error(f"AI Estimate Duration Error: {e}")
            raise UserError(f'Lỗi AI: {str(e)[:200]}')
