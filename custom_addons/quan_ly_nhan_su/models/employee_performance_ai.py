# -*- coding: utf-8 -*-
"""
AI Service nâng cao cho đánh giá hiệu suất nhân viên
Bổ sung phân tích chi tiết và biểu đồ thống kê
"""

import logging
from odoo import api, models, fields, _
from odoo.exceptions import UserError
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class EmployeePerformanceAI(models.Model):
    """Model để lưu kết quả đánh giá AI chi tiết"""
    _name = 'employee.performance.ai'
    _description = 'AI Performance Evaluation Results'
    _order = 'evaluation_date desc'

    employee_id = fields.Many2one(
        'nhan.su',
        string='Nhân viên',
        required=True,
        ondelete='cascade',
        index=True
    )

    evaluation_date = fields.Datetime(
        string='Ngày đánh giá',
        required=True,
        default=fields.Datetime.now
    )

    overall_score = fields.Float(
        string='Điểm tổng thể',
        digits=(5, 2)
    )

    performance_level = fields.Selection([
        ('poor', 'Kém (0-40)'),
        ('below_average', 'Dưới trung bình (40-60)'),
        ('average', 'Trung bình (60-75)'),
        ('good', 'Tốt (75-85)'),
        ('excellent', 'Xuất sắc (85-95)'),
        ('outstanding', 'Nổi bật (95-100)')
    ], string='Mức hiệu suất')

    # Chi tiết điểm số
    completion_score = fields.Float(string='Điểm hoàn thành', digits=(5, 2))
    quality_score = fields.Float(string='Điểm chất lượng', digits=(5, 2))
    deadline_score = fields.Float(string='Điểm đúng hạn', digits=(5, 2))
    efficiency_score = fields.Float(string='Điểm hiệu quả', digits=(5, 2))
    growth_score = fields.Float(string='Điểm phát triển', digits=(5, 2))

    # Phân tích
    strengths = fields.Text(string='Điểm mạnh')
    improvements = fields.Text(string='Cần cải thiện')
    recommendations = fields.Text(string='Khuyến nghị')
    detailed_analysis = fields.Text(string='Phân tích chi tiết')

    # Thống kê công việc
    total_tasks = fields.Integer(string='Tổng công việc')
    completed_tasks = fields.Integer(string='Đã hoàn thành')
    overdue_tasks = fields.Integer(string='Quá hạn')
    completion_rate = fields.Float(string='Tỷ lệ hoàn thành', digits=(5, 2))
    average_quality = fields.Float(string='Chất lượng TB', digits=(5, 2))

    # JSON data để lưu chi tiết
    raw_data = fields.Text(string='Dữ liệu gốc (JSON)')


class NhanSuPerformanceAI(models.Model):
    """Extend NhanSu với AI đánh giá nâng cao"""
    _inherit = 'nhan.su'

    # Thêm các field cho biểu đồ
    performance_trend_ids = fields.One2many(
        'employee.performance.ai',
        'employee_id',
        string='Lịch sử đánh giá AI'
    )

    last_6_months_performance = fields.Text(
        string='Hiệu suất 6 tháng gần đây',
        compute='_compute_performance_trend',
        store=False
    )

    performance_chart_data = fields.Text(
        string='Dữ liệu biểu đồ',
        compute='_compute_performance_chart_data',
        store=False
    )

    @api.depends('performance_trend_ids')
    def _compute_performance_trend(self):
        """Tính xu hướng hiệu suất 6 tháng gần đây"""
        for record in self:
            six_months_ago = fields.Datetime.now() - relativedelta(months=6)
            recent_evaluations = record.performance_trend_ids.filtered(
                lambda e: e.evaluation_date >= six_months_ago
            ).sorted('evaluation_date')
            
            if recent_evaluations:
                trend_text = "📊 Xu hướng 6 tháng gần đây:\n\n"
                for eval in recent_evaluations:
                    trend_text += f"• {eval.evaluation_date.strftime('%d/%m/%Y')}: {eval.overall_score:.1f}/100 ({eval.performance_level})\n"
                record.last_6_months_performance = trend_text
            else:
                record.last_6_months_performance = "Chưa có dữ liệu đánh giá trong 6 tháng gần đây."

    @api.depends('performance_trend_ids')
    def _compute_performance_chart_data(self):
        """Tạo dữ liệu JSON cho biểu đồ"""
        for record in self:
            six_months_ago = fields.Datetime.now() - relativedelta(months=6)
            recent_evaluations = record.performance_trend_ids.filtered(
                lambda e: e.evaluation_date >= six_months_ago
            ).sorted('evaluation_date')
            
            chart_data = {
                'labels': [],
                'overall_scores': [],
                'completion_scores': [],
                'quality_scores': [],
                'deadline_scores': []
            }
            
            for eval in recent_evaluations:
                chart_data['labels'].append(eval.evaluation_date.strftime('%d/%m/%Y'))
                chart_data['overall_scores'].append(eval.overall_score)
                chart_data['completion_scores'].append(eval.completion_score)
                chart_data['quality_scores'].append(eval.quality_score)
                chart_data['deadline_scores'].append(eval.deadline_score)
            
            record.performance_chart_data = json.dumps(chart_data)

    def action_ai_evaluate_detailed(self):
        """Đánh giá hiệu suất chi tiết bằng AI"""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        
        # Chuẩn bị dữ liệu chi tiết
        employee_data = {
            'name': self.name,
            'job_position': dict(self._fields['job_position'].selection).get(self.job_position, ''),
            'department': self.department_id.name if self.department_id else '',
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'overdue_tasks': self.overdue_tasks,
            'task_completion_rate': self.task_completion_rate,
            'average_task_score': self.average_task_score,
            'join_date': str(self.join_date) if self.join_date else '',
            'working_years': self.working_years if hasattr(self, 'working_years') else 0,
        }
        
        try:
            # Gọi AI phân tích chi tiết
            ai_result = ai_service.analyze_employee_performance_detailed(employee_data)
            
            # Lưu kết quả vào performance_trend_ids
            performance_vals = {
                'employee_id': self.id,
                'evaluation_date': fields.Datetime.now(),
                'overall_score': ai_result.get('overall_score', 0),
                'performance_level': ai_result.get('performance_level', 'average'),
                'completion_score': ai_result.get('completion_score', 0),
                'quality_score': ai_result.get('quality_score', 0),
                'deadline_score': ai_result.get('deadline_score', 0),
                'efficiency_score': ai_result.get('efficiency_score', 0),
                'growth_score': ai_result.get('growth_score', 0),
                'strengths': ai_result.get('strengths', ''),
                'improvements': ai_result.get('improvements', ''),
                'recommendations': ai_result.get('recommendations', ''),
                'detailed_analysis': ai_result.get('analysis', ''),
                'total_tasks': self.total_tasks,
                'completed_tasks': self.completed_tasks,
                'overdue_tasks': self.overdue_tasks,
                'completion_rate': self.task_completion_rate,
                'average_quality': self.average_task_score,
                'raw_data': json.dumps(ai_result)
            }
            
            self.env['employee.performance.ai'].create(performance_vals)
            
            # Cập nhật field chính
            self._compute_ai_performance()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Đánh giá AI hoàn tất',
                    'message': f'Điểm hiệu suất: {ai_result.get("overall_score", 0):.1f}/100\nMức: {ai_result.get("performance_level", "average")}',
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            _logger.error(f"Lỗi đánh giá AI chi tiết: {str(e)}")
            raise UserError(f'Lỗi đánh giá AI: {str(e)[:200]}')

