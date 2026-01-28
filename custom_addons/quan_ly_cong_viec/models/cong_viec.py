# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import re
import logging
import base64

_logger = logging.getLogger(__name__)


class CongViec(models.Model):
    _name = 'cong.viec'
    _description = 'Quản lý công việc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, deadline asc, id desc'
    _rec_name = 'name'

    # ==================== THÔNG TIN CƠ BẢN ====================
    
    task_code = fields.Char(
        string='Mã công việc',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default='/',
        tracking=True,
        help='Mã tự động: CV-YYYY-XXXXX (VD: CV-2026-00001)'
    )
    
    name = fields.Char(
        string='Tiêu đề công việc',
        required=True,
        tracking=True,
        index=True
    )
    
    description = fields.Html(
        string='Mô tả chi tiết',
        help='Mô tả yêu cầu, phạm vi công việc'
    )
    
    # ==================== YÊU CẦU & KẾT QUẢ ====================
    
    requirement = fields.Html(
        string='Yêu cầu công việc',
        required=True,
        tracking=True,
        help='Mô tả cụ thể các yêu cầu cần đạt được'
    )
    
    acceptance_criteria = fields.Text(
        string='Tiêu chí nghiệm thu',
        help='Các tiêu chí đánh giá hoàn thành (checklist)'
    )
    
    deliverable = fields.Char(
        string='Sản phẩm bàn giao',
        help='Ví dụ: Báo cáo, Code, Thiết kế, v.v.'
    )
    
    result_note = fields.Html(
        string='Kết quả thực tế',
        tracking=True,
        help='Nhân viên mô tả kết quả đã làm'
    )
    
    result_file_ids = fields.Many2many(
        'ir.attachment',
        'cong_viec_result_attachment_rel',
        'task_id',
        'attachment_id',
        string='File kết quả',
        help='Upload file kết quả công việc'
    )
    
    # ==================== PHÂN CÔNG ====================
    
    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        tracking=True,
        ondelete='restrict',
        help='Công việc liên quan đến khách hàng nào'
    )
    
    interaction_id = fields.Many2one(
        'khach.hang.interaction',
        string='Tương tác phát sinh',
        tracking=True,
        ondelete='set null',
        help='Công việc được tạo từ tương tác nào với khách hàng'
    )
    
    assigned_employee_id = fields.Many2one(
        'nhan.su',
        string='Nhân viên thực hiện',
        required=True,
        tracking=True,
        domain="[('working_status', '=', 'working')]",
        ondelete='restrict'
    )
    
    supervisor_id = fields.Many2one(
        'nhan.su',
        string='Người giám sát',
        tracking=True,
        domain="[('working_status', '=', 'working'), ('id', '!=', assigned_employee_id)]",
        help='Manager hoặc người kiểm tra công việc'
    )
    
    department_id = fields.Many2one(
        'phong.ban',
        string='Phòng ban',
        related='assigned_employee_id.department_id',
        store=True,
        readonly=True
    )
    
    # Email liên hệ (tự động từ khách hàng hoặc nhân viên)
    contact_email = fields.Char(
        string='Email liên hệ',
        compute='_compute_contact_email',
        store=True,
        help='Email tự động: ưu tiên email khách hàng, không có thì lấy email nhân viên'
    )
    
    # ==================== ƯU TIÊN & THỜI GIAN ====================
    
    priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Trung bình'),
        ('2', 'Cao'),
        ('3', 'Khẩn cấp')
    ], string='Độ ưu tiên', default='1', required=True, tracking=True)
    
    start_date = fields.Date(
        string='Ngày bắt đầu',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    
    deadline = fields.Date(
        string='Hạn hoàn thành',
        required=True,
        tracking=True
    )
    
    completed_date = fields.Datetime(
        string='Ngày hoàn thành thực tế',
        readonly=True,
        tracking=True
    )
    
    # Thời gian ước lượng vs thực tế
    estimated_hours = fields.Float(
        string='Giờ ước lượng',
        default=0.0,
        help='Số giờ dự kiến hoàn thành'
    )
    
    actual_hours = fields.Float(
        string='Giờ thực tế',
        default=0.0,
        help='Số giờ thực tế đã làm'
    )
    
    time_variance = fields.Float(
        string='Chênh lệch thời gian (%)',
        compute='_compute_time_variance',
        store=True,
        help='% chênh lệch giữa thực tế và ước lượng'
    )
    
    # ==================== TIẾN ĐỘ & TRẠNG THÁI ====================
    
    progress = fields.Integer(
        string='Tiến độ (%)',
        default=0,
        tracking=True,
        help='Tiến độ hoàn thành từ 0-100%'
    )
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('todo', 'Cần làm'),
        ('in_progress', 'Đang thực hiện'),
        ('review', 'Chờ duyệt'),
        ('done', 'Hoàn thành'),
        ('cancelled', 'Hủy bỏ')
    ], string='Trạng thái', default='draft', required=True, tracking=True)
    
    is_overdue = fields.Boolean(
        string='Quá hạn',
        compute='_compute_is_overdue',
        store=True,
        help='True nếu vượt deadline mà chưa hoàn thành'
    )
    
    days_overdue = fields.Integer(
        string='Số ngày quá hạn',
        compute='_compute_is_overdue',
        store=True
    )
    
    # ==================== AI EVALUATION ====================
    
    ai_quality_score = fields.Float(
        string='Điểm chất lượng AI',
        digits=(5, 2),
        readonly=True,
        help='Điểm AI đánh giá chất lượng công việc (0-100)'
    )
    
    ai_quality_level = fields.Selection([
        ('poor', 'Kém (0-40)'),
        ('below_average', 'Dưới TB (40-60)'),
        ('average', 'Trung bình (60-75)'),
        ('good', 'Tốt (75-85)'),
        ('excellent', 'Xuất sắc (85-95)'),
        ('outstanding', 'Nổi bật (95-100)')
    ], string='Mức chất lượng', readonly=True)
    
    ai_evaluation_date = fields.Datetime(
        string='Ngày đánh giá AI',
        readonly=True
    )
    
    # AI Analysis Components
    ai_requirement_match_score = fields.Float(
        string='Điểm đáp ứng yêu cầu',
        digits=(5, 2),
        readonly=True,
        help='AI so sánh yêu cầu vs kết quả (0-100)'
    )
    
    ai_deadline_performance = fields.Float(
        string='Điểm tuân thủ deadline',
        digits=(5, 2),
        readonly=True,
        help='Điểm dựa trên việc hoàn thành đúng hạn'
    )
    
    ai_time_efficiency = fields.Float(
        string='Điểm hiệu suất thời gian',
        digits=(5, 2),
        readonly=True,
        help='Điểm dựa trên actual vs estimated hours'
    )
    
    ai_analysis = fields.Text(
        string='Phân tích AI',
        readonly=True,
        help='AI phân tích chi tiết về công việc'
    )
    
    ai_strengths = fields.Text(
        string='Điểm mạnh (AI)',
        readonly=True
    )
    
    ai_improvements = fields.Text(
        string='Cần cải thiện (AI)',
        readonly=True
    )
    
    ai_recommendation = fields.Text(
        string='Khuyến nghị (AI)',
        readonly=True
    )
    
    # ==================== AI REPORT EVALUATION (PHÂN TÍCH BÁO CÁO) ====================
    
    ai_report_evaluated = fields.Boolean(
        string='Đã đánh giá báo cáo bằng AI',
        default=False,
        readonly=True,
        help='True nếu AI đã phân tích báo cáo kết quả'
    )
    
    ai_overall_completion = fields.Float(
        string='% Hoàn thành tổng thể',
        digits=(5, 2),
        readonly=True,
        help='AI đánh giá mức độ hoàn thành tổng thể (0-100%)'
    )
    
    ai_completed_items = fields.Text(
        string='✅ Đã hoàn thành',
        readonly=True,
        help='Danh sách công việc đã làm (phân tích từ báo cáo)'
    )
    
    ai_incomplete_items = fields.Text(
        string='❌ Chưa hoàn thành',
        readonly=True,
        help='Danh sách công việc chưa làm (so sánh với yêu cầu)'
    )
    
    ai_exceeded_items = fields.Text(
        string='⭐ Làm vượt mức',
        readonly=True,
        help='Công việc làm vượt ngoài yêu cầu ban đầu'
    )
    
    ai_report_strengths = fields.Text(
        string='💪 Điểm mạnh báo cáo',
        readonly=True
    )
    
    ai_report_weaknesses = fields.Text(
        string='⚠️ Điểm yếu báo cáo',
        readonly=True
    )
    
    ai_detailed_analysis = fields.Text(
        string='Phân tích chi tiết',
        readonly=True,
        help='Phân tích chi tiết từ AI về chất lượng báo cáo'
    )
    
    ai_grade = fields.Char(
        string='Xếp loại',
        readonly=True,
        help='Xếp loại A+/A/B+/B/C+/C/D/F'
    )
    
    # ==================== AI RISK & PREDICTION ====================
    
    ai_risk_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nghiêm trọng')
    ], string='Mức độ rủi ro', readonly=True, help='AI phát hiện rủi ro')
    
    ai_risk_score = fields.Float(
        string='Điểm rủi ro',
        digits=(5, 2),
        readonly=True,
        help='Điểm rủi ro 0-100 (càng cao càng nguy hiểm)'
    )
    
    ai_risk_factors = fields.Text(
        string='Yếu tố rủi ro',
        readonly=True,
        help='Các yếu tố gây rủi ro được AI phát hiện'
    )
    
    ai_early_warning = fields.Boolean(
        string='Cảnh báo sớm',
        default=False,
        readonly=True,
        help='True nếu AI phát hiện cần cảnh báo sớm'
    )
    
    ai_predicted_hours = fields.Float(
        string='Thời gian dự đoán (AI)',
        digits=(5, 2),
        readonly=True,
        help='AI dự đoán thời gian hoàn thành (giờ)'
    )
    
    # ==================== AI ĐÁNH GIÁ TIẾN ĐỘ KHI GỬI DUYỆT ====================
    
    ai_progress_completion_level = fields.Char(
        string='Mức độ hoàn thành (AI)',
        readonly=True,
        help='Đánh giá mức độ hoàn thành: Hoàn thành tốt / Hoàn thành / Chưa hoàn thành / Cần bổ sung'
    )
    
    ai_progress_completion_percentage = fields.Float(
        string='% Hoàn thành thực tế (AI)',
        digits=(5, 2),
        readonly=True,
        help='% hoàn thành thực tế do AI đánh giá (0-100)'
    )
    
    ai_progress_deadline_risk = fields.Char(
        string='Nguy cơ trễ hạn (AI)',
        readonly=True,
        help='Đánh giá nguy cơ trễ hạn: Không có rủi ro / Rủi ro thấp / Rủi ro trung bình / Rủi ro cao / Nguy cơ trễ hạn'
    )
    
    ai_progress_deadline_risk_score = fields.Float(
        string='Điểm rủi ro (AI)',
        digits=(5, 2),
        readonly=True,
        help='Điểm rủi ro trễ hạn (0-100, 0 = không rủi ro, 100 = chắc chắn trễ hạn)'
    )
    
    ai_progress_supervisor_recommendations = fields.Text(
        string='Đề xuất cho giám sát (AI)',
        readonly=True,
        help='Đề xuất hành động cho người giám sát từ AI'
    )
    
    ai_progress_detailed_assessment = fields.Text(
        string='Đánh giá chi tiết (AI)',
        readonly=True,
        help='Đánh giá chi tiết về tình trạng công việc từ AI'
    )
    
    ai_progress_evaluation_date = fields.Datetime(
        string='Ngày đánh giá tiến độ (AI)',
        readonly=True,
        help='Thời điểm AI đánh giá tiến độ'
    )
    
    ai_prediction_confidence = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao')
    ], string='Độ tin cậy dự đoán', readonly=True)
    
    # ==================== FILE ĐÍNH KÈM ====================
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'cong_viec_attachment_rel',
        'task_id',
        'attachment_id',
        string='Tài liệu đính kèm',
        help='Upload tài liệu liên quan'
    )
    
    attachment_count = fields.Integer(
        string='Số file',
        compute='_compute_attachment_count'
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
    
    tag_ids = fields.Many2many(
        'cong.viec.tag',
        string='Nhãn'
    )
    
    color = fields.Integer(
        string='Màu sắc',
        help='Màu hiển thị trên Kanban'
    )
    
    # ==================== SQL CONSTRAINTS ====================
    
    _sql_constraints = [
        ('task_code_uniq', 'UNIQUE(task_code)', 
         'Mã công việc đã tồn tại!'),
        ('progress_check', 'CHECK(progress >= 0 AND progress <= 100)', 
         'Tiến độ phải trong khoảng 0-100%'),
        ('estimated_hours_positive', 'CHECK(estimated_hours >= 0)', 
         'Giờ ước lượng phải >= 0'),
        ('actual_hours_positive', 'CHECK(actual_hours >= 0)', 
         'Giờ thực tế phải >= 0'),
    ]
    
    # ==================== CONSTRAINTS ====================
    
    @api.constrains('start_date', 'deadline')
    def _check_dates(self):
        """Ngày bắt đầu phải <= deadline"""
        for record in self:
            if record.start_date and record.deadline:
                if record.start_date > record.deadline:
                    raise ValidationError(
                        f'Ngày bắt đầu ({record.start_date}) không thể sau deadline ({record.deadline})!'
                    )
    
    @api.constrains('assigned_employee_id')
    def _check_employee_status(self):
        """Không giao việc cho nhân viên đã nghỉ"""
        for record in self:
            if record.assigned_employee_id:
                if record.assigned_employee_id.working_status != 'working':
                    raise ValidationError(
                        f'Không thể giao việc cho nhân viên {record.assigned_employee_id.name} '
                        f'(Trạng thái: {dict(record.assigned_employee_id._fields["working_status"].selection).get(record.assigned_employee_id.working_status)})'
                    )
    
    @api.constrains('task_code')
    def _check_task_code_format(self):
        """Kiểm tra format mã công việc: CV-YYYY-XXXXX"""
        pattern = r'^CV-\d{4}-\d{5}$'
        for record in self:
            # Bỏ qua check khi tạo mới (task_code = '/' hoặc False)
            if record.task_code and record.task_code != '/' and not re.match(pattern, record.task_code):
                raise ValidationError(
                    'Mã công việc phải theo format: CV-YYYY-XXXXX\n'
                    'Ví dụ: CV-2026-00001'
                    )
    
    @api.constrains('supervisor_id', 'assigned_employee_id')
    def _check_supervisor(self):
        """Supervisor không được là chính nhân viên thực hiện"""
        for record in self:
            if record.supervisor_id and record.assigned_employee_id:
                if record.supervisor_id == record.assigned_employee_id:
                    raise ValidationError(
                        'Người giám sát không thể là chính nhân viên thực hiện công việc!'
                    )
    
    # ==================== COMPUTE METHODS ====================
    
    @api.depends('customer_id', 'assigned_employee_id', 'assigned_employee_id.work_email')
    def _compute_contact_email(self):
        """Tự động lấy email từ khách hàng hoặc nhân viên"""
        for record in self:
            # Kiểm tra email từ khách hàng (nếu có)
            if record.customer_id:
                # Sử dụng getattr để tránh lỗi nếu field không tồn tại
                customer_email = getattr(record.customer_id, 'email', False)
                if customer_email:
                    record.contact_email = customer_email
                    continue
            
            # Nếu không có email khách hàng, lấy từ nhân viên
            if record.assigned_employee_id and record.assigned_employee_id.work_email:
                record.contact_email = record.assigned_employee_id.work_email
            else:
                record.contact_email = False
    
    @api.depends('deadline', 'state', 'completed_date')
    def _compute_is_overdue(self):
        """Kiểm tra quá hạn"""
        today = fields.Date.today()
        for record in self:
            if record.state != 'done' and record.deadline:
                if today > record.deadline:
                    record.is_overdue = True
                    record.days_overdue = (today - record.deadline).days
                else:
                    record.is_overdue = False
                    record.days_overdue = 0
            else:
                record.is_overdue = False
                record.days_overdue = 0
    
    @api.depends('estimated_hours', 'actual_hours')
    def _compute_time_variance(self):
        """Tính % chênh lệch thời gian"""
        for record in self:
            if record.estimated_hours > 0:
                variance = ((record.actual_hours - record.estimated_hours) / record.estimated_hours) * 100
                record.time_variance = round(variance, 2)
            else:
                record.time_variance = 0.0
    
    @api.depends('attachment_ids', 'result_file_ids')
    def _compute_attachment_count(self):
        """Đếm tổng số file"""
        for record in self:
            record.attachment_count = len(record.attachment_ids) + len(record.result_file_ids)
    
    # ==================== HELPER METHODS ====================
    
    @api.model
    def _generate_task_code(self):
        """Tạo mã công việc tự động: CV-YYYY-XXXXX"""
        code = self.env['ir.sequence'].next_by_code('cong.viec')
        if not code:
            year = fields.Date.today().strftime('%Y')
            code = f'CV-{year}-00001'
        code = self._normalize_task_code(code)
        if re.match(r'^CV-\d{4}-\d{5}$', code):
            year = code[3:7]
            number = int(code[-5:])
            while self.search_count([('task_code', '=', code)]) > 0:
                number += 1
                code = f'CV-{year}-{number:05d}'
        return code

    @api.model
    def _normalize_task_code(self, code):
        """Chuẩn hóa mã công việc về CV-YYYY-XXXXX nếu có thể."""
        code = (code or '').strip()
        if re.match(r'^CV-\d{4}-\d{5}$', code):
            return code
        if re.match(r'^CV\d{4}$', code):
            year = fields.Date.today().strftime('%Y')
            return f'CV-{year}-{int(code[2:]):05d}'
        if code.startswith('CV'):
            digits = re.findall(r'\d+', code)
            if digits:
                num_str = digits[-1]
                if len(num_str) > 5:
                    num_str = num_str[-5:]
                try:
                    year = fields.Date.today().strftime('%Y')
                    return f'CV-{year}-{int(num_str):05d}'
                except ValueError:
                    pass
        return code
    
    # ==================== AI EVALUATION METHODS ====================
    
    def compute_ai_evaluation(self):
        """AI Evaluation Algorithm - Tính toán điểm chất lượng công việc"""
        self.ensure_one()
        
        if self.state != 'done':
            return False
        
        ai_service = self.env['ai.service']
        
        try:
            # Chuẩn bị dữ liệu đầy đủ cho AI
            task_data = {
                'name': self.name,
                'employee_name': self.assigned_employee_id.name,
                'requirement': re.sub(r'<[^>]+>', '', self.requirement or ''),
                'acceptance_criteria': self.acceptance_criteria or 'Không có tiêu chí cụ thể',
                'deliverable': self.deliverable or 'Không xác định',
                'result_note': re.sub(r'<[^>]+>', '', self.result_note or ''),
                'estimated_hours': self.estimated_hours,
                'actual_hours': self.actual_hours,
                'deadline': str(self.deadline),
                'completed_date': str(self.completed_date) if self.completed_date else 'Chưa hoàn thành',
                'is_overdue': self.is_overdue,
            }
            
            # Gọi AI phân tích
            ai_result = ai_service.analyze_task_quality(task_data)
            
            # Cập nhật kết quả
            self.write({
                'ai_quality_score': ai_result.get('quality_score', 0.0),
                'ai_quality_level': ai_result.get('quality_level', 'average'),
                'ai_requirement_match_score': ai_result.get('requirement_match_score', 0.0),
                'ai_deadline_performance': ai_result.get('deadline_performance', 0.0),
                'ai_time_efficiency': ai_result.get('time_efficiency', 0.0),
                'ai_strengths': ai_result.get('strengths', ''),
                'ai_improvements': ai_result.get('improvements', ''),
                'ai_recommendation': ai_result.get('recommendations', ''),
                'ai_evaluation_date': fields.Datetime.now(),
            })
            
            # Log evaluation
            self.message_post(
                body=f"""
                    <h3>🤖 AI Evaluation Completed</h3>
                    <ul>
                        <li><strong>Overall Score:</strong> {self.ai_quality_score}/100 ({self.ai_quality_level})</li>
                        <li><strong>Requirement Match:</strong> {self.ai_requirement_match_score}/40</li>
                        <li><strong>Deadline Performance:</strong> {self.ai_deadline_performance}/30</li>
                        <li><strong>Time Efficiency:</strong> {self.ai_time_efficiency}/20</li>
                    </ul>
                """,
                subject="AI Quality Evaluation"
            )
            
            # Cập nhật thống kê cho nhân viên
            self.assigned_employee_id._compute_task_statistics()
            self.assigned_employee_id._compute_ai_performance()
            
            return True
            
        except Exception as e:
            _logger.error(f"Lỗi đánh giá AI cho task {self.name}: {str(e)}")
            return False
    
    def action_ai_evaluate_report(self):
        """
        🤖 API #3 - CRITICAL: Đánh giá báo cáo công việc bằng AI (QUAN TRỌNG NHẤT)
        
        Phân tích toàn diện:
        1. Trích xuất text từ file PDF/Word (API #1)
        2. So sánh yêu cầu vs kết quả (API #3 - CRITICAL)
        3. Đánh giá chất lượng (API #4)
        4. Gợi ý cải thiện (API #5)
        
        Button action - Phân tích chi tiết báo cáo so với yêu cầu
        """
        self.ensure_one()
        
        if not self.result_note and not self.result_file_ids:
            raise UserError(
                '❌ Chưa có báo cáo kết quả!\n\n'
                'Vui lòng:\n'
                '• Nhập kết quả vào tab "Kết quả thực tế", HOẶC\n'
                '• Upload file báo cáo (PDF/Word) vào "File kết quả"'
            )
        
        ai_task_service = self.env['ai.task.service']
        
        try:
            # Chuẩn bị dữ liệu task
            task_data = {
                'task_code': self.task_code,
                'name': self.name,
                'requirement': self.requirement or '',
                'acceptance_criteria': self.acceptance_criteria or '',
                'deliverable': self.deliverable or '',
                'result_note': self.result_note or '',
                'estimated_hours': self.estimated_hours,
                'actual_hours': self.actual_hours,
                'deadline': self.deadline,
                'completed_date': self.completed_date,
                'is_overdue': self.is_overdue,
                'has_result_files': len(self.result_file_ids) > 0
            }
            
            # Chuẩn bị file báo cáo
            report_files = []
            for attachment in self.result_file_ids:
                try:
                    file_data = base64.b64decode(attachment.datas)
                    report_files.append({
                        'filename': attachment.name,
                        'file_data': file_data
                    })
                except Exception as e:
                    _logger.warning(f"Không đọc được file {attachment.name}: {str(e)}")
            
            # Gọi AI đánh giá
            result = ai_task_service.evaluate_task_report(task_data, report_files)
            
            # Lưu kết quả
            self.write({
                'ai_report_evaluated': True,
                'ai_overall_completion': result.get('overall_completion', 0),
                'ai_requirement_match_score': result.get('requirement_match_score', 0),
                'ai_quality_score': result.get('quality_score', 0),
                'ai_time_efficiency': result.get('time_efficiency_score', 0),
                'ai_deadline_performance': result.get('deadline_score', 0),
                'ai_completed_items': result.get('completed_items', ''),
                'ai_incomplete_items': result.get('incomplete_items', ''),
                'ai_exceeded_items': result.get('exceeded_items', ''),
                'ai_report_strengths': result.get('strengths', ''),
                'ai_report_weaknesses': result.get('weaknesses', ''),
                'ai_recommendation': result.get('recommendations', ''),
                'ai_detailed_analysis': result.get('detailed_analysis', ''),
                'ai_grade': result.get('grade', 'B'),
                'ai_evaluation_date': fields.Datetime.now()
            })
            
            # Post message
            self.message_post(
                body=f"""
                <h3>🤖 AI Đánh Giá Báo Cáo Hoàn Tất</h3>
                <h4>📊 Kết quả tổng quan:</h4>
                <ul>
                    <li><strong>Mức độ hoàn thành:</strong> {result.get('overall_completion', 0):.1f}%</li>
                    <li><strong>Xếp loại:</strong> {result.get('grade', 'B')}</li>
                    <li><strong>Đáp ứng yêu cầu:</strong> {result.get('requirement_match_score', 0):.1f}/100</li>
                    <li><strong>Chất lượng:</strong> {result.get('quality_score', 0):.1f}/100</li>
                </ul>
                <h4>✅ Đã hoàn thành:</h4>
                <pre>{result.get('completed_items', 'N/A')[:300]}</pre>
                <h4>❌ Chưa hoàn thành:</h4>
                <pre>{result.get('incomplete_items', 'N/A')[:300]}</pre>
                """,
                subject="🎯 Kết quả đánh giá AI"
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Đánh giá thành công!',
                    'message': f'AI đã phân tích báo cáo. Điểm: {result.get("overall_completion", 0):.0f}% - Xếp loại: {result.get("grade", "B")}',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Lỗi đánh giá báo cáo AI: {str(e)}")
            raise UserError(f'Lỗi đánh giá AI:\n{str(e)[:300]}')
    
    def action_ai_detect_risks(self):
        """
        API 4: Phát hiện rủi ro công việc bằng AI
        """
        self.ensure_one()
        
        if self.state in ['done', 'cancelled']:
            raise UserError('Công việc đã hoàn thành hoặc bị hủy, không cần phát hiện rủi ro.')
        
        ai_task_service = self.env['ai.task.service']
        
        try:
            task_data = {
                'name': self.name,
                'progress': self.progress,
                'deadline': self.deadline,
                'start_date': self.start_date,
                'estimated_hours': self.estimated_hours,
                'actual_hours': self.actual_hours,
                'employee_current_tasks': self.env['cong.viec'].search_count([
                    ('assigned_employee_id', '=', self.assigned_employee_id.id),
                    ('state', 'not in', ['done', 'cancelled'])
                ]),
                'employee_overdue_rate': 0,  # TODO: Calculate from employee stats
                'is_complex': self.estimated_hours > 40  # >40h = complex
            }
            
            result = ai_task_service.detect_task_risks(task_data)
            
            # Lưu kết quả
            self.write({
                'ai_risk_level': result.get('risk_level', 'medium'),
                'ai_risk_score': result.get('risk_score', 50),
                'ai_risk_factors': '\n'.join(result.get('risk_factors', [])),
                'ai_early_warning': result.get('early_warning', False)
            })
            
            # Post message
            risk_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'}
            self.message_post(
                body=f"""
                <h3>{risk_emoji.get(result.get('risk_level', 'medium'), '🟡')} Phát hiện rủi ro AI</h3>
                <ul>
                    <li><strong>Mức độ:</strong> {result.get('risk_level', 'medium').upper()} ({result.get('risk_score', 0):.0f}/100)</li>
                    <li><strong>Yếu tố rủi ro:</strong><ul>{''.join(['<li>'+f+'</li>' for f in result.get('risk_factors', [])])}</ul></li>
                </ul>
                <h4>💡 Khuyến nghị:</h4>
                <pre>{result.get('recommendations', 'N/A')}</pre>
                """,
                subject=f"⚠️ Rủi ro: {result.get('risk_level', 'medium').upper()}"
            )
            
            # Create activity nếu rủi ro cao
            if result.get('risk_level') in ['high', 'critical'] and self.supervisor_id and self.supervisor_id.user_id:
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=self.supervisor_id.user_id.id,
                    summary=f'⚠️ Rủi ro {result.get("risk_level").upper()}: {self.name}',
                    note=f'AI phát hiện rủi ro cao ({result.get("risk_score", 0):.0f}/100).\n\n' + 
                         result.get('recommendations', '')
                )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': f'{risk_emoji.get(result.get("risk_level", "medium"), "🟡")} Phát hiện rủi ro',
                    'message': f'Mức độ: {result.get("risk_level", "medium").upper()} - Điểm: {result.get("risk_score", 0):.0f}/100',
                    'type': 'warning' if result.get('risk_level') in ['high', 'critical'] else 'info',
                    'sticky': result.get('risk_level') in ['high', 'critical'],
                }
            }
            
        except Exception as e:
            _logger.error(f"Lỗi phát hiện rủi ro AI: {str(e)}")
            raise UserError(f'Lỗi phát hiện rủi ro:\n{str(e)[:300]}')
    
    def action_ai_predict_duration(self):
        """
        API 3: Dự đoán thời gian hoàn thành
        """
        self.ensure_one()
        
        ai_task_service = self.env['ai.task.service']
        
        try:
            # Lấy lịch sử công việc tương tự
            similar_tasks = self.search([
                ('assigned_employee_id', '=', self.assigned_employee_id.id),
                ('state', '=', 'done'),
                ('estimated_hours', '>', 0),
                ('actual_hours', '>', 0)
            ], limit=5, order='completed_date desc')
            
            historical_tasks = []
            for task in similar_tasks:
                historical_tasks.append({
                    'name': task.name,
                    'estimated_hours': task.estimated_hours,
                    'actual_hours': task.actual_hours,
                    'complexity': 'high' if task.estimated_hours > 40 else 'medium'
                })
            
            task_description = f"{self.name}\n\nYêu cầu:\n{re.sub(r'<[^>]+>', '', self.requirement or '')[:500]}"
            
            result = ai_task_service.predict_task_duration(
                task_description,
                self.assigned_employee_id.id,
                historical_tasks
            )
            
            # Lưu kết quả
            self.write({
                'ai_predicted_hours': result.get('predicted_hours', 8.0),
                'ai_prediction_confidence': result.get('confidence_level', 'medium')
            })
            
            # Gợi ý cập nhật estimated_hours nếu chênh lệch lớn
            if self.estimated_hours > 0:
                diff_percent = abs(result.get('predicted_hours', 0) - self.estimated_hours) / self.estimated_hours * 100
                if diff_percent > 30:
                    message = f"⚠️ AI dự đoán {result.get('predicted_hours', 0):.1f}h (khác {diff_percent:.0f}% so với ước lượng hiện tại)"
                else:
                    message = f"✅ Ước lượng hợp lý (AI dự đoán {result.get('predicted_hours', 0):.1f}h)"
            else:
                message = f"💡 Gợi ý ước lượng: {result.get('predicted_hours', 0):.1f}h"
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🔮 Dự đoán thời gian AI',
                    'message': message,
                    'type': 'info',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Lỗi dự đoán thời gian AI: {str(e)}")
            raise UserError(f'Lỗi dự đoán AI:\n{str(e)[:300]}')
    
    # ==================== CRUD METHODS ====================
    
    @api.model
    def create(self, vals):
        """Override create"""
        if not vals.get('task_code') or vals.get('task_code') == '/':
            vals['task_code'] = self._generate_task_code()
        
        # Kiểm tra khách hàng đã completed - không cho tạo task mới
        if vals.get('customer_id'):
            customer = self.env['khach.hang'].browse(vals['customer_id'])
            if customer.status == 'completed':
                raise UserError(
                    f'Không thể tạo công việc mới cho khách hàng đã hoàn thành!\n\n'
                    f'Khách hàng "{customer.display_name}" đã ở trạng thái "Hoàn thành".\n'
                    f'Tất cả công việc của khách hàng này đã hoàn thành.\n\n'
                    f'Nếu cần tạo công việc mới, vui lòng thay đổi trạng thái khách hàng trước.'
                )
        
        # Auto-suggest nhân viên từ khách hàng (nếu có)
        if vals.get('customer_id') and not vals.get('assigned_employee_id'):
            customer = self.env['khach.hang'].browse(vals['customer_id'])
            if customer.primary_employee_id and customer.primary_employee_id.working_status == 'working':
                vals['assigned_employee_id'] = customer.primary_employee_id.id
        
        # Auto-suggest nhân viên từ tương tác (nếu có)
        if vals.get('interaction_id') and not vals.get('assigned_employee_id'):
            try:
                interaction = self.env['khach.hang.interaction'].browse(vals['interaction_id'])
                if interaction.exists() and interaction.employee_id and interaction.employee_id.working_status == 'working':
                    vals['assigned_employee_id'] = interaction.employee_id.id
            except Exception:
                pass
        
        # Auto-set supervisor = manager của assigned employee
        if vals.get('assigned_employee_id') and not vals.get('supervisor_id'):
            employee = self.env['nhan.su'].browse(vals['assigned_employee_id'])
            if employee.manager_id:
                vals['supervisor_id'] = employee.manager_id.id
        
        # Tự động chuyển từ Draft → Todo khi giao cho nhân viên
        if vals.get('assigned_employee_id') and (not vals.get('state') or vals.get('state') == 'draft'):
            vals['state'] = 'todo'
        
        record = super().create(vals)
        
        # Notify assigned employee
        if record.assigned_employee_id and record.assigned_employee_id.user_id:
            record.message_subscribe(partner_ids=record.assigned_employee_id.user_id.partner_id.ids)
            
            # Activity notification
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=record.assigned_employee_id.user_id.id,
                summary=f'Bạn được giao công việc: {record.name}',
                note=f'Khách hàng: {record.customer_id.display_name if record.customer_id else "N/A"}\nHạn hoàn thành: {record.deadline}'
            )
            
            # Message post notification
            customer_info = f'<li><strong>Khách hàng:</strong> {record.customer_id.display_name if record.customer_id else "N/A"}</li>' if record.customer_id else ''
            record.message_post(
                body=f"""
                <h3>📋 Giao công việc</h3>
                <p><strong>Nhân viên {record.assigned_employee_id.name}</strong> được giao công việc này.</p>
                <ul>
                    <li><strong>Tên công việc:</strong> {record.name}</li>
                    <li><strong>Mã công việc:</strong> {record.task_code}</li>
                    {customer_info}
                    <li><strong>Hạn hoàn thành:</strong> {record.deadline}</li>
                    <li><strong>Độ ưu tiên:</strong> {dict(record._fields["priority"].selection).get(record.priority)}</li>
                </ul>
                <p>Vui lòng bắt đầu thực hiện công việc.</p>
                """,
                subject=f'Giao công việc: {record.name}',
                partner_ids=record.assigned_employee_id.user_id.partner_id.ids,
                message_type='notification'
            )
            
        # Notify supervisor
        if record.supervisor_id and record.supervisor_id.user_id:
            record.message_subscribe(partner_ids=record.supervisor_id.user_id.partner_id.ids)
            
            # Activity notification
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=record.supervisor_id.user_id.id,
                summary=f'Bạn đang giám sát công việc: {record.name}',
                note=f'Nhân viên thực hiện: {record.assigned_employee_id.name if record.assigned_employee_id else "N/A"}\nKhách hàng: {record.customer_id.display_name if record.customer_id else "N/A"}'
            )
            
            # Message post notification
            record.message_post(
                body=f"""
                <h3>👥 Giám sát công việc</h3>
                <p><strong>Bạn ({record.supervisor_id.name})</strong> đang giám sát công việc này.</p>
                <ul>
                    <li><strong>Tên công việc:</strong> {record.name}</li>
                    <li><strong>Nhân viên thực hiện:</strong> {record.assigned_employee_id.name if record.assigned_employee_id else "N/A"}</li>
                    <li><strong>Khách hàng:</strong> {record.customer_id.display_name if record.customer_id else "N/A"}</li>
                    <li><strong>Hạn hoàn thành:</strong> {record.deadline}</li>
                </ul>
                <p>Vui lòng theo dõi tiến độ công việc.</p>
                """,
                subject=f'Giám sát công việc: {record.name}',
                partner_ids=record.supervisor_id.user_id.partner_id.ids,
                message_type='notification'
            )
        
        return record
    
    def write(self, vals):
        """Override write"""
        # QUAN TRỌNG: Ngăn thay đổi state trực tiếp từ statusbar widget
        # Chỉ cho phép thay đổi state thông qua các action methods (có validation)
        if 'state' in vals and not self.env.context.get('allow_state_change'):
            for record in self:
                old_state = record.state
                new_state = vals['state']

                # Cho phép một số trường hợp tự động hợp lệ
                is_auto_draft_to_todo = (old_state == 'draft' and new_state == 'todo' and
                                        self.env.context.get('auto_assign_to_todo'))
                is_auto_progress_to_review = (old_state != 'review' and new_state == 'review' and
                                              self.env.context.get('auto_progress_to_review'))

                if old_state != new_state and not (is_auto_draft_to_todo or is_auto_progress_to_review):
                    raise UserError(
                        '❌ Không thể thay đổi trạng thái trực tiếp!\n\n'
                        'Vui lòng sử dụng các nút workflow ở header:\n'
                        '• "Bắt đầu" - để chuyển từ Cần làm → Đang thực hiện\n'
                        '• "Gửi duyệt" - để chuyển từ Đang thực hiện → Chờ duyệt (yêu cầu file kết quả)\n'
                        '• "Duyệt" - để chuyển từ Chờ duyệt → Hoàn thành (yêu cầu file kết quả)\n'
                        '• "Từ chối" - để chuyển từ Chờ duyệt → Đang thực hiện\n'
                        '• "Hủy bỏ" - để hủy công việc\n'
                        '• "Mở lại" - để mở lại công việc đã hoàn thành/hủy\n\n'
                        'Mỗi bước đều có validation và yêu cầu bằng chứng cụ thể (file, ghi chú).'
                    )

        # Track state change - nhưng skip nếu đang trong context của action method
        if 'state' in vals and not self.env.context.get('skip_state_change_message'):
            for record in self:
                old_state = record.state
                new_state = vals['state']
                if old_state != new_state:
                    record.message_post(
                        body=f"Trạng thái: {dict(record._fields['state'].selection).get(old_state)} → {dict(record._fields['state'].selection).get(new_state)}",
                        subject="Cập nhật trạng thái"
                    )
                    
                    # Tự động đánh giá AI hiệu suất nhân viên khi công việc hoàn thành
                    if new_state == 'done' and record.assigned_employee_id:
                        try:
                            employee = record.assigned_employee_id
                            _logger.info(f"🤖 Tự động đánh giá AI hiệu suất cho nhân viên: {employee.name} (từ công việc {record.name})")
                            
                            # Trigger compute để cập nhật điểm AI dựa trên thống kê mới
                            if hasattr(employee, '_compute_ai_performance'):
                                # Invalidate cache để force recompute
                                employee.invalidate_cache(['total_tasks', 'completed_tasks', 'average_task_score', 'task_completion_rate'])
                                employee._compute_ai_performance()
                                _logger.info(f"✅ Đã cập nhật điểm AI hiệu suất cho {employee.name}: {employee.ai_performance_score}/100")
                            
                        except Exception as emp_error:
                            _logger.error(f"❌ Lỗi tự động đánh giá AI hiệu suất nhân viên: {str(emp_error)[:300]}")
        
        # Auto-update supervisor khi thay đổi nhân viên
        if 'assigned_employee_id' in vals and not vals.get('supervisor_id'):
            for record in self:
                new_employee = self.env['nhan.su'].browse(vals['assigned_employee_id'])
                if new_employee.manager_id:
                    vals['supervisor_id'] = new_employee.manager_id.id
        
        # Tự động chuyển từ Draft → Todo khi giao cho nhân viên
        if 'assigned_employee_id' in vals and vals.get('assigned_employee_id'):
            for record in self:
                if record.state == 'draft' and not vals.get('state'):
                    vals['state'] = 'todo'
                    # Thông báo cho nhân viên
                    if record.assigned_employee_id and record.assigned_employee_id.user_id:
                        record.message_post(
                            body="✅ Công việc đã được giao. Trạng thái: Cần làm",
                            subject="Giao công việc"
                        )
        
        # Kiểm tra khách hàng đã completed - không cho tạo task mới (khi thay đổi customer_id)
        if 'customer_id' in vals and vals.get('customer_id'):
            for record in self:
                customer = self.env['khach.hang'].browse(vals['customer_id'])
                if customer.status == 'completed':
                    raise UserError(
                        f'Không thể gán công việc cho khách hàng đã hoàn thành!\n\n'
                        f'Khách hàng "{customer.display_name}" đã ở trạng thái "Hoàn thành".\n'
                        f'Tất cả công việc của khách hàng này đã hoàn thành.'
                    )
        
        # Auto-suggest nhân viên từ khách hàng (nếu thay đổi khách hàng)
        if 'customer_id' in vals and not vals.get('assigned_employee_id'):
            for record in self:
                if not record.assigned_employee_id:  # Chỉ khi chưa có nhân viên
                    customer = self.env['khach.hang'].browse(vals['customer_id'])
                    if customer.primary_employee_id and customer.primary_employee_id.working_status == 'working':
                        vals['assigned_employee_id'] = customer.primary_employee_id.id
        
        # Auto-complete when progress = 100
        # CHÚ Ý: Chỉ tự động chuyển sang review nếu chưa được set state='done' trong cùng lần write
        if 'progress' in vals and vals['progress'] == 100:
            if 'state' not in vals and self.state not in ['done', 'cancelled']:
                vals['state'] = 'review'
        
        return super().write(vals)
    
    def unlink(self):
        """Không cho xóa task đã hoàn thành"""
        if self.env.context.get('force_unlink'):
            return super().unlink()
        for record in self:
            if record.state == 'done':
                raise UserError(
                    'Không thể xóa công việc đã hoàn thành!\n'
                    'Vui lòng sử dụng Archive thay vì xóa.'
                )
        return super().unlink()
    
    # ==================== ACTION METHODS ====================
    
    def action_start(self):
        """Mở wizard để nhập thông tin bắt đầu"""
        self.ensure_one()
        
        if self.state != 'todo':
            raise UserError(f'Chỉ có thể bắt đầu từ trạng thái "Cần làm". Trạng thái hiện tại: {dict(self._fields["state"].selection).get(self.state)}')
            
        if not self.assigned_employee_id:
                raise UserError('Công việc chưa được giao cho nhân viên nào!')
            
        return {
            'name': 'Bắt đầu công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'task.start.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
            }
        }
    
    def action_submit_review(self):
        """Mở wizard để nhập kết quả và upload file"""
        self.ensure_one()
        
        if self.state != 'in_progress':
            raise UserError(f'Chỉ có thể gửi duyệt từ trạng thái "Đang thực hiện". Trạng thái hiện tại: {dict(self._fields["state"].selection).get(self.state)}')
            
        # Check permission
        if self.assigned_employee_id.user_id and self.env.uid != self.assigned_employee_id.user_id.id and not self.env.user.has_group('base.group_system'):
                raise UserError('Chỉ nhân viên thực hiện mới được phép gửi duyệt!')

        return {
            'name': 'Gửi duyệt công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'task.submit.review.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                'default_result_note': self.result_note or '',
                'default_result_file_ids': [(6, 0, self.result_file_ids.ids)] if self.result_file_ids else False,
                'default_actual_hours': self.actual_hours or 0,
            }
        }
    
    def action_approve(self):
        """Mở wizard để nhập ghi chú duyệt"""
        self.ensure_one()
        
        if self.state != 'review':
            raise UserError(f'Chỉ có thể duyệt từ trạng thái "Chờ duyệt". Trạng thái hiện tại: {dict(self._fields["state"].selection).get(self.state)}')
            
        # Check permission
        if not self.supervisor_id or not self.supervisor_id.user_id:
                raise UserError('Công việc chưa có người giám sát, không thể phê duyệt!')
            
        if self.env.uid != self.supervisor_id.user_id.id and not self.env.user.has_group('base.group_system'):
            raise UserError('Chỉ người giám sát mới được phép phê duyệt!')
        
        if not self.result_file_ids:
            raise UserError('❌ Công việc chưa có file kết quả. Vui lòng yêu cầu nhân viên upload file kết quả trước khi duyệt.')
        
        return {
            'name': 'Duyệt công việc',
            'type': 'ir.actions.act_window',
            'res_model': 'task.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
            }
        }
    
    def action_reject(self):
        """Review → In Progress (Supervisor rejects)"""
        for record in self:
            if record.state == 'review':
                # Check permission: Only supervisor can reject
                if not record.supervisor_id or not record.supervisor_id.user_id:
                    raise UserError('Công việc chưa có người giám sát, không thể từ chối!')
                
                if self.env.uid != record.supervisor_id.user_id.id and not self.env.user.has_group('base.group_system'):
                    raise UserError('Chỉ người giám sát mới được phép từ chối!')

                # Track who rejected and when
                now = fields.Datetime.now()
                update_vals = {
                    'state': 'in_progress',
                }
                
                # Safely add tracking fields
                try:
                    if hasattr(record, 'rejected_by_id'):
                        update_vals['rejected_by_id'] = self.env.user.id
                    if hasattr(record, 'rejected_date'):
                        update_vals['rejected_date'] = now
                except Exception:
                    pass
                
                record.with_context(allow_state_change=True, skip_state_change_message=True).write(update_vals)
                
                # Notify employee - GỬI EMAIL khi từ chối
                if record.assigned_employee_id and record.assigned_employee_id.user_id:
                    # Activity notification
                    record.activity_schedule(
                        'mail.mail_activity_data_warning',
                        user_id=record.assigned_employee_id.user_id.id,
                        summary=f'❌ Công việc {record.name} cần chỉnh sửa',
                        note=f'Người từ chối: {record.supervisor_id.name}\n\nVui lòng xem chi tiết yêu cầu chỉnh sửa trong phần Ghi chú/Chatter.\n\nCông việc sẽ quay lại trạng thái "Đang thực hiện" để bạn tiếp tục chỉnh sửa.'
                    )
                    
                    # GỬI EMAIL - Thông báo chính thức từ chối
                    if record.assigned_employee_id.work_email:
                        try:
                            email_template = self.env.ref('quan_ly_cong_viec.email_template_task_rejected')
                            email_template.send_mail(record.id, force_send=True)
                        except Exception as e:
                            _logger.error(f"Lỗi gửi email từ chối: {str(e)}")
                            # Fallback: Gửi message post nếu email lỗi
                            record.message_post(
                                body=f"""
                                <h3>❌ Công việc cần chỉnh sửa</h3>
                                <p><strong>Công việc "{record.name}"</strong> đã được <strong>{record.supervisor_id.name if record.supervisor_id else "N/A"}</strong> xem xét và yêu cầu chỉnh sửa.</p>
                                <ul>
                                    <li><strong>Người từ chối:</strong> {record.supervisor_id.name if record.supervisor_id else "N/A"}</li>
                                    <li><strong>Thời gian:</strong> {fields.Datetime.now().strftime("%d/%m/%Y %H:%M")}</li>
                                    <li><strong>Trạng thái:</strong> Đã chuyển về "Đang thực hiện"</li>
                        </ul>
                        <p><strong>Vui lòng:</strong></p>
                        <ol>
                            <li>Xem lại yêu cầu và phản hồi từ người giám sát</li>
                            <li>Chỉnh sửa kết quả công việc theo yêu cầu</li>
                            <li>Gửi lại duyệt sau khi hoàn thành chỉnh sửa</li>
                        </ol>
                        <p>Vui lòng kiểm tra phần Ghi chú/Chatter để xem chi tiết yêu cầu chỉnh sửa.</p>
                        """,
                        subject=f'Công việc {record.name} cần chỉnh sửa',
                        partner_ids=record.assigned_employee_id.user_id.partner_id.ids,
                        message_type='notification'
                    )

                # Post general message
                record.message_post(
                    body=f"❌ Công việc bị <strong>{record.supervisor_id.name if record.supervisor_id else 'N/A'}</strong> từ chối, cần làm lại. Trạng thái đã chuyển về 'Đang thực hiện'.",
                    subject="Từ chối công việc"
                )
    
    def action_cancel(self):
        """Cancel task"""
        for record in self:
            record.write({
                'state': 'cancelled',
                'active': False
            })
            record.message_post(body="Công việc đã bị hủy")
    
    def action_reopen(self):
        """Done/Cancelled → In Progress"""
        for record in self:
            if record.state in ['done', 'cancelled']:
                record.write({
                    'state': 'in_progress',
                    'active': True
                })
                record.message_post(body="Mở lại công việc")
    
    # ==================== SCHEDULED ACTIONS ====================
    
    @api.model
    def cron_check_overdue_tasks(self):
        """Scheduled action: Cảnh báo task quá hạn"""
        overdue_tasks = self.search([
            ('state', 'not in', ['done', 'cancelled']),
            ('is_overdue', '=', True)
        ])
        
        for task in overdue_tasks:
            if task.assigned_employee_id and task.assigned_employee_id.user_id:
                task.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=task.assigned_employee_id.user_id.id,
                    summary=f'⚠️ Task quá hạn {task.days_overdue} ngày: {task.name}'
                )
    
    @api.model
    def cron_remind_deadline(self):
        """Scheduled action: Nhắc deadline sắp tới (3 ngày trước)"""
        upcoming_deadline = fields.Date.today() + timedelta(days=3)
        tasks = self.search([
            ('state', 'not in', ['done', 'cancelled']),
            ('deadline', '=', upcoming_deadline)
        ])
        
        for task in tasks:
            if task.assigned_employee_id and task.assigned_employee_id.user_id:
                task.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=task.assigned_employee_id.user_id.id,
                    summary=f'⏰ Deadline sắp tới (3 ngày): {task.name}',
                    date_deadline=task.deadline
                )
    
    # ==================== NAME & DISPLAY ====================
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            try:
                # Kiểm tra field có tồn tại trước khi truy cập (tránh lỗi khi chưa upgrade)
                if hasattr(record, 'task_code') and record.task_code and record.task_code != '/':
                    name = f"[{record.task_code}] {record.name}"
                else:
                    name = record.name if hasattr(record, 'name') else f"Task #{record.id}"
            except Exception as e:
                # Nếu có lỗi, chỉ dùng ID
                _logger.warning(f"Error in name_get for task {record.id}: {str(e)[:100]}")
                name = f"Task #{record.id}"
            result.append((record.id, name))
        return result
    
    # ==================== AI ACTION METHODS ====================
    
    def action_ai_predict_time(self):
        """AI dự đoán thời gian hoàn thành"""
        self.ensure_one()
        ai_service = self.env['ai.task.service']
        
        try:
            result = ai_service.predict_task_duration(
                task_description=f"{self.name}\n\n{self.requirement}",
                employee_id=self.assigned_employee_id.id if self.assigned_employee_id else None,
                historical_tasks=[]
            )
            
            self.write({
                'ai_predicted_hours': result.get('predicted_hours', 0),
                'ai_prediction_confidence': result.get('confidence', 0),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🤖 AI Dự Đoán',
                    'message': f'Thời gian dự đoán: {result.get("predicted_hours", 0)} giờ',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(f'Lỗi AI: {str(e)}')
    
    def action_ai_detect_risk(self):
        """AI phát hiện rủi ro"""
        self.ensure_one()
        ai_service = self.env['ai.task.service']
        
        try:
            task_data = {
                'task_code': self.task_code,
                'name': self.name,
                'requirement': self.requirement,
                'deadline': str(self.deadline),
                'estimated_hours': self.estimated_hours,
                'priority': self.priority,
                'assigned_employee_name': self.assigned_employee_id.name if self.assigned_employee_id else '',
                'progress': self.progress,
            }
            result = ai_service.detect_task_risks(task_data)
            
            self.write({
                'ai_risk_level': result.get('risk_level', 'low'),
                'ai_risk_factors': result.get('risk_factors', ''),
                'ai_risk_recommendations': result.get('recommendations', ''),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ Phát Hiện Rủi Ro',
                    'message': f'Mức độ rủi ro: {result.get("risk_level", "low").upper()}',
                    'type': 'warning' if result.get('risk_level') in ['medium', 'high'] else 'info',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(f'Lỗi AI: {str(e)}')
    
    def action_ai_generate_acceptance_criteria(self):
        """AI tạo tiêu chí nghiệm thu"""
        self.ensure_one()
        ai_service = self.env['ai.task.service']
        
        try:
            result = ai_service.generate_acceptance_criteria(
                task_requirement=f"{self.name}\n\n{self.requirement}"
            )
            
            self.write({
                'ai_acceptance_criteria': result.get('acceptance_criteria', ''),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Tiêu Chí Nghiệm Thu',
                    'message': 'Đã tạo tiêu chí nghiệm thu tự động',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(f'Lỗi AI: {str(e)}')
