# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LichSuDanhGia(models.Model):
    """Lưu lịch sử đánh giá hiệu suất nhân viên"""
    _name = 'lich.su.danh.gia'
    _description = 'Lịch sử đánh giá hiệu suất'
    _order = 'evaluation_date desc, id desc'
    _rec_name = 'display_name'

    # ==================== THÔNG TIN CƠ BẢN ====================
    
    employee_id = fields.Many2one(
        'nhan.su',
        string='Nhân viên',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    employee_code = fields.Char(
        string='Mã nhân viên',
        related='employee_id.employee_code',
        store=True,
        readonly=True
    )
    
    department_id = fields.Many2one(
        'phong.ban',
        string='Phòng ban',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )
    
    display_name = fields.Char(
        string='Tên hiển thị',
        compute='_compute_display_name',
        store=True
    )
    
    # ==================== THÔNG TIN ĐÁNH GIÁ ====================
    
    evaluation_date = fields.Datetime(
        string='Ngày đánh giá',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    
    evaluation_type = fields.Selection([
        ('monthly', 'Hàng tháng'),
        ('quarterly', 'Hàng quý'),
        ('annual', 'Hàng năm'),
        ('probation', 'Kết thúc thử việc'),
        ('project', 'Kết thúc dự án'),
        ('ai_auto', 'AI tự động')
    ], string='Loại đánh giá', required=True, default='ai_auto')
    
    evaluator_id = fields.Many2one(
        'res.users',
        string='Người đánh giá',
        default=lambda self: self.env.user,
        help='Người thực hiện đánh giá (Manager/HR)'
    )
    
    # ==================== ĐIỂM SỐ ====================
    
    overall_score = fields.Float(
        string='Điểm tổng hợp',
        digits=(5, 2),
        required=True,
        help='Điểm tổng hợp từ 0-100'
    )
    
    performance_level = fields.Selection([
        ('poor', 'Kém (0-40)'),
        ('below_average', 'Dưới trung bình (40-60)'),
        ('average', 'Trung bình (60-75)'),
        ('good', 'Tốt (75-85)'),
        ('excellent', 'Xuất sắc (85-95)'),
        ('outstanding', 'Nổi bật (95-100)')
    ], string='Mức hiệu suất', compute='_compute_performance_level', store=True)
    
    task_completion_rate = fields.Float(
        string='Tỷ lệ hoàn thành công việc (%)',
        digits=(5, 2),
        help='% công việc hoàn thành'
    )
    
    quality_score = fields.Float(
        string='Điểm chất lượng',
        digits=(5, 2),
        help='Điểm chất lượng công việc'
    )
    
    deadline_compliance = fields.Float(
        string='Tuân thủ deadline (%)',
        digits=(5, 2),
        help='% công việc hoàn thành đúng hạn'
    )
    
    # ==================== PHÂN TÍCH AI ====================
    
    ai_analysis = fields.Text(
        string='Phân tích AI',
        help='Phân tích tổng quan từ AI'
    )
    
    strengths = fields.Text(
        string='Điểm mạnh',
        help='Những điểm mạnh của nhân viên'
    )
    
    improvements = fields.Text(
        string='Điểm cần cải thiện',
        help='Những điểm cần cải thiện'
    )
    
    recommendations = fields.Text(
        string='Khuyến nghị',
        help='Khuyến nghị phát triển từ AI'
    )
    
    # ==================== THỐNG KÊ CÔNG VIỆC ====================
    
    total_tasks = fields.Integer(
        string='Tổng số công việc',
        default=0
    )
    
    completed_tasks = fields.Integer(
        string='Công việc hoàn thành',
        default=0
    )
    
    overdue_tasks = fields.Integer(
        string='Công việc quá hạn',
        default=0
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
    
    note = fields.Html(
        string='Ghi chú',
        help='Ghi chú bổ sung từ người đánh giá'
    )
    
    # ==================== COMPUTE METHODS ====================
    
    @api.depends('employee_id.name', 'evaluation_date', 'evaluation_type')
    def _compute_display_name(self):
        """Tạo tên hiển thị"""
        for record in self:
            if record.employee_id and record.evaluation_date:
                eval_type = dict(record._fields['evaluation_type'].selection).get(record.evaluation_type, '')
                date_str = fields.Datetime.to_string(record.evaluation_date)[:10]
                record.display_name = f"{record.employee_id.name} - {eval_type} - {date_str}"
            else:
                record.display_name = 'Đánh giá mới'
    
    @api.depends('overall_score')
    def _compute_performance_level(self):
        """Tính mức hiệu suất dựa trên điểm"""
        for record in self:
            score = record.overall_score
            if score >= 95:
                record.performance_level = 'outstanding'
            elif score >= 85:
                record.performance_level = 'excellent'
            elif score >= 75:
                record.performance_level = 'good'
            elif score >= 60:
                record.performance_level = 'average'
            elif score >= 40:
                record.performance_level = 'below_average'
            else:
                record.performance_level = 'poor'
    
    # ==================== CONSTRAINTS ====================
    
    @api.constrains('overall_score')
    def _check_overall_score(self):
        """Kiểm tra điểm hợp lệ"""
        for record in self:
            if not (0 <= record.overall_score <= 100):
                raise ValidationError(
                    f'Điểm tổng hợp phải trong khoảng 0-100!\n'
                    f'Giá trị hiện tại: {record.overall_score}'
                )
    
    @api.constrains('task_completion_rate', 'deadline_compliance')
    def _check_percentage_fields(self):
        """Kiểm tra các trường % hợp lệ"""
        for record in self:
            if record.task_completion_rate and not (0 <= record.task_completion_rate <= 100):
                raise ValidationError('Tỷ lệ hoàn thành phải trong khoảng 0-100%')
            
            if record.deadline_compliance and not (0 <= record.deadline_compliance <= 100):
                raise ValidationError('Tuân thủ deadline phải trong khoảng 0-100%')
    
    # ==================== CRUD METHODS ====================
    
    @api.model
    def create(self, vals):
        """Override create"""
        record = super().create(vals)
        
        # Gửi thông báo cho nhân viên
        if record.employee_id and record.employee_id.user_id:
            record.employee_id.message_post(
                body=f"""
                    <h3>📊 Đánh giá hiệu suất mới</h3>
                    <ul>
                        <li><strong>Loại:</strong> {dict(record._fields['evaluation_type'].selection).get(record.evaluation_type)}</li>
                        <li><strong>Điểm:</strong> {record.overall_score}/100</li>
                        <li><strong>Mức:</strong> {dict(record._fields['performance_level'].selection).get(record.performance_level)}</li>
                        <li><strong>Ngày:</strong> {record.evaluation_date}</li>
                    </ul>
                """,
                subject="Đánh giá hiệu suất",
                partner_ids=record.employee_id.user_id.partner_id.ids
            )
        
        return record
    
    # ==================== ACTION METHODS ====================
    
    def action_view_employee(self):
        """Xem thông tin nhân viên"""
        self.ensure_one()
        return {
            'name': f'Nhân viên: {self.employee_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'nhan.su',
            'res_id': self.employee_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_compare_with_previous(self):
        """So sánh với đánh giá trước đó"""
        self.ensure_one()
        
        previous = self.search([
            ('employee_id', '=', self.employee_id.id),
            ('id', '<', self.id)
        ], limit=1, order='evaluation_date desc')
        
        if not previous:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thông báo',
                    'message': 'Không tìm thấy đánh giá trước đó để so sánh',
                    'type': 'warning',
                }
            }
        
        # Tính sự thay đổi
        score_change = self.overall_score - previous.overall_score
        change_icon = '📈' if score_change > 0 else '📉' if score_change < 0 else '➡️'
        
        message = f"""
            <h3>So sánh với đánh giá trước</h3>
            <table class="table table-sm">
                <tr>
                    <th>Chỉ tiêu</th>
                    <th>Lần trước</th>
                    <th>Lần này</th>
                    <th>Thay đổi</th>
                </tr>
                <tr>
                    <td>Điểm tổng hợp</td>
                    <td>{previous.overall_score:.1f}</td>
                    <td>{self.overall_score:.1f}</td>
                    <td>{change_icon} {score_change:+.1f}</td>
                </tr>
                <tr>
                    <td>Tỷ lệ hoàn thành</td>
                    <td>{previous.task_completion_rate:.1f}%</td>
                    <td>{self.task_completion_rate:.1f}%</td>
                    <td>{self.task_completion_rate - previous.task_completion_rate:+.1f}%</td>
                </tr>
                <tr>
                    <td>Chất lượng</td>
                    <td>{previous.quality_score:.1f}</td>
                    <td>{self.quality_score:.1f}</td>
                    <td>{self.quality_score - previous.quality_score:+.1f}</td>
                </tr>
            </table>
        """
        
        self.message_post(body=message, subject="So sánh đánh giá")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'So sánh hoàn tất',
                'message': f'Điểm thay đổi: {change_icon} {score_change:+.1f}',
                'type': 'success' if score_change >= 0 else 'warning',
                'sticky': False,
            }
        }
