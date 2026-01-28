# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unidecode import unidecode
import re
import logging

_logger = logging.getLogger(__name__)


class NhanSu(models.Model):
    _name = 'nhan.su'
    _description = 'Quản lý nhân sự'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_code desc, id desc'
    _rec_name = 'name'

    # ==================== THÔNG TIN ĐỊNH DANH ====================
    
    employee_code = fields.Char(
        string='Mã nhân viên',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default='/',
        tracking=True,
        help='Mã duy nhất: Chữ cái đầu họ tên + Ngày sinh (VD: DNN-02062004)'
    )
    
    name = fields.Char(
        string='Họ và tên',
        required=True,
        index=True,
        tracking=True,
        help='Họ tên đầy đủ theo CCCD'
    )
    
    avatar = fields.Image(
        string='Ảnh đại diện',
        max_width=256,
        max_height=256
    )
    
    gender = fields.Selection([
        ('male', 'Nam'),
        ('female', 'Nữ'),
        ('other', 'Khác')
    ], string='Giới tính', tracking=True)
    
    date_of_birth = fields.Date(
        string='Ngày sinh',
        required=True,
        tracking=True
    )
    
    age = fields.Integer(
        string='Tuổi',
        compute='_compute_age',
        store=True,
        help='Tính tự động từ ngày sinh'
    )
    
    place_of_birth = fields.Char(
        string='Nơi sinh',
        help='Tỉnh/Thành phố nơi sinh'
    )
    
    nationality = fields.Many2one(
        'res.country',
        string='Quốc tịch',
        default=lambda self: self.env.ref('base.vn', raise_if_not_found=False)
    )
    
    marital_status = fields.Selection([
        ('single', 'Độc thân'),
        ('married', 'Đã kết hôn'),
        ('divorced', 'Đã ly hôn'),
        ('widowed', 'Góa')
    ], string='Tình trạng hôn nhân')
    
    # CCCD/CMND
    identification_type = fields.Selection([
        ('cccd', 'Căn cước công dân (CCCD)'),
        ('cmnd', 'Chứng minh nhân dân (CMND)'),
        ('passport', 'Hộ chiếu')
    ], string='Loại giấy tờ', default='cccd')
    
    identification_number = fields.Char(
        string='Số CCCD/CMND',
        required=True,
        copy=False,
        tracking=True,
        help='12 số (CCCD) hoặc 9 số (CMND cũ)'
    )
    
    identification_issue_date = fields.Date(string='Ngày cấp')
    identification_issue_place = fields.Char(string='Nơi cấp')
    identification_expiry_date = fields.Date(string='Ngày hết hạn')
    
    # ==================== THÔNG TIN LIÊN HỆ ====================
    
    phone = fields.Char(
        string='Số điện thoại',
        required=True,
        tracking=True,
        help='Số điện thoại di động chính'
    )
    
    work_email = fields.Char(
        string='Email công ty',
        required=False,
        readonly=True,
        tracking=True,
        help='Email công ty chính thức (VD: nghiadn2004@dnu.edu.vn) - Tự động tạo từ họ tên và năm sinh'
    )
    
    personal_email = fields.Char(
        string='Email cá nhân',
        tracking=True,
        help='Email cá nhân (Gmail, Yahoo, ...)'
    )
    
    # Người liên hệ khẩn cấp
    emergency_contact_name = fields.Char(string='Người liên hệ khẩn cấp')
    emergency_contact_relationship = fields.Selection([
        ('parent', 'Cha/Mẹ'),
        ('spouse', 'Vợ/Chồng'),
        ('sibling', 'Anh/Chị/Em'),
        ('child', 'Con'),
        ('other', 'Khác')
    ], string='Quan hệ')
    emergency_contact_phone = fields.Char(string='SĐT khẩn cấp')
    
    # Địa chỉ
    permanent_address = fields.Text(string='Địa chỉ thường trú')
    permanent_city = fields.Many2one(
        'res.country.state',
        string='Tỉnh/TP thường trú',
        domain="[('country_id.code', '=', 'VN')]"
    )
    
    temporary_address = fields.Text(string='Địa chỉ tạm trú')
    temporary_city = fields.Many2one(
        'res.country.state',
        string='Tỉnh/TP tạm trú',
        domain="[('country_id.code', '=', 'VN')]"
    )
    
    current_address = fields.Text(
        string='Địa chỉ hiện tại',
        compute='_compute_current_address',
        help='Ưu tiên tạm trú, không có thì lấy thường trú'
    )
    
    # ==================== THÔNG TIN CÔNG VIỆC ====================
    
    department_id = fields.Many2one(
        'phong.ban',
        string='Phòng ban',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True
    )
    
    job_position = fields.Selection([
        # Development
        ('backend_dev', 'Backend Developer'),
        ('frontend_dev', 'Frontend Developer'),
        ('fullstack_dev', 'Fullstack Developer'),
        ('mobile_dev', 'Mobile Developer'),
        ('devops', 'DevOps Engineer'),
        ('qa_engineer', 'QA Engineer'),
        ('ba', 'Business Analyst'),
        
        # Management
        ('tech_lead', 'Tech Lead'),
        ('project_manager', 'Project Manager'),
        ('product_manager', 'Product Manager'),
        ('scrum_master', 'Scrum Master'),
        
        # Design
        ('ui_designer', 'UI Designer'),
        ('ux_designer', 'UX Designer'),
        ('graphic_designer', 'Graphic Designer'),
        
        # Sales & Marketing
        ('sales', 'Sales Executive'),
        ('account_manager', 'Account Manager'),
        ('marketing', 'Marketing Specialist'),
        ('content_writer', 'Content Writer'),
        
        # HR & Admin
        ('hr_manager', 'HR Manager'),
        ('hr_staff', 'HR Staff'),
        ('accountant', 'Accountant'),
        ('admin', 'Admin Staff'),
        
        # Other
        ('ceo', 'CEO'),
        ('cto', 'CTO'),
        ('cfo', 'CFO'),
        ('director', 'Director'),
    ], string='Vị trí công việc', required=True, tracking=True)
    
    job_level = fields.Selection([
        ('intern', 'Thực tập sinh'),
        ('fresher', 'Nhân viên mới (Fresher)'),
        ('junior', 'Nhân viên (Junior)'),
        ('middle', 'Nhân viên chính (Middle)'),
        ('senior', 'Nhân viên cao cấp (Senior)'),
        ('expert', 'Chuyên gia (Expert)'),
        ('team_lead', 'Trưởng nhóm (Team Lead)'),
        ('manager', 'Quản lý (Manager)'),
        ('director', 'Giám đốc (Director)')
    ], string='Cấp bậc', required=True, tracking=True)
    
    manager_id = fields.Many2one(
        'nhan.su',
        string='Quản lý trực tiếp',
        tracking=True,
        domain="[('id', '!=', id), ('working_status', '=', 'working')]"
    )
    
    work_location = fields.Char(
        string='Địa điểm làm việc',
        default='Hà Nội'
    )
    
    employment_type = fields.Selection([
        ('fulltime', 'Toàn thời gian'),
        ('parttime', 'Bán thời gian'),
        ('contract', 'Hợp đồng dịch vụ'),
        ('intern', 'Thực tập')
    ], string='Hình thức', required=True, default='fulltime')
    
    working_type = fields.Selection([
        ('office', 'Tại văn phòng'),
        ('remote', 'Từ xa (Remote)'),
        ('hybrid', 'Kết hợp (Hybrid)')
    ], string='Phương thức làm việc', default='office')
    
    # Ngày tháng
    join_date = fields.Date(
        string='Ngày vào làm',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    probation_start_date = fields.Date(
        string='Ngày bắt đầu thử việc',
        compute='_compute_probation_dates',
        store=True
    )
    
    probation_end_date = fields.Date(
        string='Ngày kết thúc thử việc',
        tracking=True
    )
    
    probation_duration = fields.Integer(
        string='Thời gian thử việc (ngày)',
        compute='_compute_probation_duration',
        help='Tính từ join_date'
    )
    
    # Hợp đồng
    contract_type = fields.Selection([
        ('probation', 'Hợp đồng thử việc'),
        ('definite', 'Hợp đồng xác định thời hạn'),
        ('indefinite', 'Hợp đồng không xác định thời hạn'),
        ('seasonal', 'Hợp đồng theo mùa vụ'),
        ('project', 'Hợp đồng theo dự án')
    ], string='Loại hợp đồng', tracking=True)
    
    contract_start_date = fields.Date(string='Ngày bắt đầu HĐ chính thức', tracking=True)
    contract_end_date = fields.Date(string='Ngày kết thúc HĐ', tracking=True)
    contract_number = fields.Char(string='Số hợp đồng', copy=False)
    
    # Trạng thái
    working_status = fields.Selection([
        ('draft', 'Nháp'),
        ('probation', 'Đang thử việc'),
        ('working', 'Đang làm việc'),
        ('on_leave', 'Đang nghỉ phép'),
        ('maternity_leave', 'Nghỉ thai sản'),
        ('sick_leave', 'Nghỉ ốm'),
        ('resigned', 'Đã nghỉ việc'),
        ('retired', 'Đã nghỉ hưu'),
        ('terminated', 'Bị sa thải')
    ], string='Trạng thái', default='draft', required=True, tracking=True)
    
    resignation_date = fields.Date(string='Ngày nghỉ việc', tracking=True)
    resignation_reason = fields.Text(string='Lý do nghỉ việc')
    
    retirement_age_check = fields.Boolean(
        string='Đủ tuổi nghỉ hưu',
        compute='_compute_retirement_age_check',
        store=True
    )
    
    # ==================== LƯƠNG & PHÚC LỢI ====================
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.ref('base.VND', raise_if_not_found=False)
    )
    
    base_salary = fields.Monetary(
        string='Lương cơ bản',
        currency_field='currency_id',
        required=True,
        default=0.0,
        tracking=True
    )
    
    # Phụ cấp
    position_allowance = fields.Monetary(string='Phụ cấp chức vụ', currency_field='currency_id', default=0.0)
    housing_allowance = fields.Monetary(string='Phụ cấp nhà ở', currency_field='currency_id', default=0.0)
    transportation_allowance = fields.Monetary(string='Phụ cấp đi lại', currency_field='currency_id', default=0.0)
    phone_allowance = fields.Monetary(string='Phụ cấp điện thoại', currency_field='currency_id', default=0.0)
    meal_allowance = fields.Monetary(string='Phụ cấp ăn trưa', currency_field='currency_id', default=0.0)
    other_allowance = fields.Monetary(string='Phụ cấp khác', currency_field='currency_id', default=0.0)
    
    total_allowance = fields.Monetary(
        string='Tổng phụ cấp',
        compute='_compute_total_allowance',
        store=True,
        currency_field='currency_id'
    )
    
    gross_salary = fields.Monetary(
        string='Tổng lương (Gross)',
        compute='_compute_gross_salary',
        store=True,
        currency_field='currency_id'
    )
    
    # Bảo hiểm
    insurance_salary = fields.Monetary(
        string='Lương đóng BHXH',
        compute='_compute_insurance_salary',
        store=True,
        currency_field='currency_id'
    )
    
    social_insurance = fields.Boolean(string='BHXH', default=True)
    health_insurance = fields.Boolean(string='BHYT', default=True)
    unemployment_insurance = fields.Boolean(string='BHTN', default=True)
    insurance_number = fields.Char(string='Số sổ BHXH', copy=False)
    
    # Thuế
    tax_code = fields.Char(string='Mã số thuế', copy=False)
    number_of_dependents = fields.Integer(string='Số người phụ thuộc', default=0)
    
    # Ngân hàng
    bank_name = fields.Char(string='Ngân hàng')
    bank_account_number = fields.Char(string='Số tài khoản', copy=False)
    bank_branch = fields.Char(string='Chi nhánh')
    
    # ==================== HIỆU SUẤT & AI ====================
    
    # Task statistics (computed dynamically to avoid circular dependency)
    total_tasks = fields.Integer(
        string='Tổng số công việc',
        compute='_compute_task_statistics',
        store=True
    )
    
    completed_tasks = fields.Integer(
        string='Công việc hoàn thành',
        compute='_compute_task_statistics',
        store=True
    )
    
    overdue_tasks = fields.Integer(
        string='Công việc quá hạn',
        compute='_compute_task_statistics',
        store=True
    )
    
    task_completion_rate = fields.Float(
        string='Tỷ lệ hoàn thành (%)',
        compute='_compute_task_statistics',
        store=True,
        digits=(5, 2)
    )
    
    average_task_score = fields.Float(
        string='Điểm TB công việc',
        compute='_compute_task_statistics',
        store=True,
        digits=(5, 2)
    )
    
    # AI Performance
    ai_performance_score = fields.Float(
        string='Điểm hiệu suất AI',
        compute='_compute_ai_performance',
        store=True,
        digits=(5, 2)
    )
    
    ai_performance_level = fields.Selection([
        ('poor', 'Kém (0-40)'),
        ('below_average', 'Dưới trung bình (40-60)'),
        ('average', 'Trung bình (60-75)'),
        ('good', 'Tốt (75-85)'),
        ('excellent', 'Xuất sắc (85-95)'),
        ('outstanding', 'Nổi bật (95-100)')
    ], string='Mức hiệu suất', compute='_compute_ai_performance', store=True)
    
    ai_evaluation_date = fields.Datetime(
        string='Lần đánh giá cuối',
        compute='_compute_ai_performance',
        store=True
    )
    
    ai_strengths = fields.Text(
        string='Điểm mạnh (AI)',
        compute='_compute_ai_performance',
        store=True
    )
    
    ai_improvement_areas = fields.Text(
        string='Cần cải thiện (AI)',
        compute='_compute_ai_performance',
        store=True
    )
    
    ai_recommendations = fields.Text(
        string='Khuyến nghị phát triển (AI)',
        compute='_compute_ai_performance',
        store=True
    )
    
    # Lịch sử đánh giá
    performance_history_ids = fields.One2many(
        'lich.su.danh.gia',
        'employee_id',
        string='Lịch sử đánh giá'
    )
    
    performance_history_count = fields.Integer(
        string='Số lần đánh giá',
        compute='_compute_performance_history_count'
    )
    
    # ==================== HỆ THỐNG ====================
    
    user_id = fields.Many2one(
        'res.users',
        string='Tài khoản hệ thống',
        ondelete='restrict',
        help='Liên kết với tài khoản đăng nhập Odoo'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True
    )
    
    active = fields.Boolean(
        string='Hoạt động',
        default=True,
        tracking=True
    )
    
    note = fields.Html(string='Ghi chú')
    
    # ==================== SQL CONSTRAINTS ====================
    
    _sql_constraints = [
        ('employee_code_uniq', 'UNIQUE(employee_code)',
         'Mã nhân viên đã tồn tại!'),
        ('identification_number_uniq', 'UNIQUE(identification_number)',
         'Số CCCD/CMND đã tồn tại!'),
        ('user_id_uniq', 'UNIQUE(user_id)',
         'Tài khoản hệ thống đã được gán cho nhân viên khác!'),
        ('base_salary_positive', 'CHECK(base_salary >= 0)',
         'Lương cơ bản phải >= 0'),
    ]
    
    # ==================== COMPUTE METHODS ====================
    
    @api.depends('date_of_birth')
    def _compute_age(self):
        """Tính tuổi từ ngày sinh"""
        for record in self:
            if record.date_of_birth:
                record.age = relativedelta(
                    fields.Date.today(),
                    record.date_of_birth
                ).years
            else:
                record.age = 0
    
    @api.depends('age', 'gender')
    def _compute_retirement_age_check(self):
        """Kiểm tra tuổi nghỉ hưu"""
        for record in self:
            if record.age and record.gender:
                retirement_age = 62 if record.gender == 'male' else 60
                record.retirement_age_check = record.age >= retirement_age
            else:
                record.retirement_age_check = False
    
    @api.depends('temporary_address', 'permanent_address')
    def _compute_current_address(self):
        """Địa chỉ hiện tại ưu tiên tạm trú"""
        for record in self:
            record.current_address = record.temporary_address or record.permanent_address
    
    @api.depends('join_date')
    def _compute_probation_dates(self):
        """Tính ngày bắt đầu thử việc"""
        for record in self:
            record.probation_start_date = record.join_date
    
    @api.depends('join_date', 'probation_end_date')
    def _compute_probation_duration(self):
        """Tính thời gian thử việc"""
        for record in self:
            if record.join_date and record.probation_end_date:
                record.probation_duration = (record.probation_end_date - record.join_date).days
            else:
                record.probation_duration = 0
    
    @api.depends(
        'position_allowance', 'housing_allowance', 'transportation_allowance',
        'phone_allowance', 'meal_allowance', 'other_allowance'
    )
    def _compute_total_allowance(self):
        """Tính tổng phụ cấp"""
        for record in self:
            record.total_allowance = sum([
                record.position_allowance,
                record.housing_allowance,
                record.transportation_allowance,
                record.phone_allowance,
                record.meal_allowance,
                record.other_allowance
            ])
    
    @api.depends('base_salary', 'total_allowance')
    def _compute_gross_salary(self):
        """Tính tổng lương"""
        for record in self:
            record.gross_salary = record.base_salary + record.total_allowance
    
    @api.depends('base_salary')
    def _compute_insurance_salary(self):
        """Tính lương đóng BHXH"""
        BASE_SALARY_2024 = 1800000
        MAX_INSURANCE_SALARY = BASE_SALARY_2024 * 20  # 36.000.000 VNĐ
        
        for record in self:
            if record.base_salary > MAX_INSURANCE_SALARY:
                record.insurance_salary = MAX_INSURANCE_SALARY
            else:
                record.insurance_salary = record.base_salary
    
    def _compute_task_statistics(self):
        """Tính thống kê công việc từ module cong_viec - Tối ưu performance"""
        # Check if cong.viec model exists (module might not be installed)
        if 'cong.viec' not in self.env:
            for record in self:
                record.total_tasks = 0
                record.completed_tasks = 0
                record.overdue_tasks = 0
                record.task_completion_rate = 0.0
                record.average_task_score = 0.0
            return
        
        if not self:
            return
        
        # Tối ưu: dùng read_group thay vì search trong loop
        CongViec = self.env['cong.viec']
        
        # Đếm tổng số task
        total_counts = CongViec.read_group(
            [('assigned_employee_id', 'in', self.ids)],
            ['assigned_employee_id'],
            ['assigned_employee_id']
        )
        total_dict = {item['assigned_employee_id'][0]: item['assigned_employee_id_count'] for item in total_counts}
        
        # Đếm task completed
        completed_counts = CongViec.read_group(
            [('assigned_employee_id', 'in', self.ids), ('state', '=', 'done')],
            ['assigned_employee_id'],
            ['assigned_employee_id']
        )
        completed_dict = {item['assigned_employee_id'][0]: item['assigned_employee_id_count'] for item in completed_counts}
        
        # Đếm task overdue
        overdue_counts = CongViec.read_group(
            [('assigned_employee_id', 'in', self.ids), ('is_overdue', '=', True)],
            ['assigned_employee_id'],
            ['assigned_employee_id']
        )
        overdue_dict = {item['assigned_employee_id'][0]: item['assigned_employee_id_count'] for item in overdue_counts}
        
        # Tính điểm trung bình (cần query riêng vì có điều kiện phức tạp)
        for record in self:
            record.total_tasks = total_dict.get(record.id, 0)
            record.completed_tasks = completed_dict.get(record.id, 0)
            record.overdue_tasks = overdue_dict.get(record.id, 0)
            
            if record.total_tasks > 0:
                record.task_completion_rate = (record.completed_tasks / record.total_tasks) * 100
            else:
                record.task_completion_rate = 0.0
            
            # Điểm trung bình từ AI (query riêng cho accuracy)
            completed_tasks = CongViec.search([
                ('assigned_employee_id', '=', record.id),
                ('state', '=', 'done'),
                ('ai_quality_score', '>', 0)
            ])
            if completed_tasks:
                record.average_task_score = sum(completed_tasks.mapped('ai_quality_score')) / len(completed_tasks)
            else:
                record.average_task_score = 0.0
    
    @api.depends('total_tasks', 'completed_tasks', 'overdue_tasks', 'average_task_score', 'task_completion_rate')
    def _compute_ai_performance(self):
        """Tính điểm hiệu suất AI"""
        ai_service = self.env['ai.service']
        
        for record in self:
            if record.total_tasks == 0:
                record.ai_performance_score = 0.0
                record.ai_performance_level = False
                record.ai_evaluation_date = False
                record.ai_strengths = ''
                record.ai_improvement_areas = ''
                record.ai_recommendations = ''
                continue
            
            try:
                # Chuẩn bị dữ liệu cho AI
                employee_data = {
                    'name': record.name,
                    'job_position': record.job_position,
                    'department': record.department_id.name if record.department_id else '',
                    'total_tasks': record.total_tasks,
                    'completed_tasks': record.completed_tasks,
                    'overdue_tasks': record.overdue_tasks,
                    'task_completion_rate': record.task_completion_rate,
                    'average_task_score': record.average_task_score,
                }
                
                # Gọi AI phân tích
                ai_result = ai_service.analyze_employee_performance(employee_data)
                
                # Cập nhật kết quả
                record.ai_performance_score = ai_result.get('overall_score', 0.0)
                record.ai_performance_level = ai_result.get('performance_level', 'average')
                record.ai_evaluation_date = fields.Datetime.now()
                record.ai_strengths = ai_result.get('strengths', '')
                record.ai_improvement_areas = ai_result.get('improvements', '')
                record.ai_recommendations = ai_result.get('recommendations', '')
                
                # Lưu lịch sử
                record._create_performance_history(ai_result)
                
            except Exception as e:
                _logger.error(f"Lỗi tính AI performance cho {record.name}: {str(e)}")
                # Fallback: tính điểm đơn giản
                record._compute_simple_performance()
    
    def _compute_simple_performance(self):
        """Tính điểm đơn giản khi AI lỗi"""
        self.ensure_one()
        
        completion_score = (self.task_completion_rate / 100) * 40
        quality_score = (self.average_task_score / 100) * 30
        deadline_score = ((self.total_tasks - self.overdue_tasks) / self.total_tasks) * 20 if self.total_tasks > 0 else 0
        workload_score = min(10, (self.total_tasks / 20) * 10)
        
        total_score = completion_score + quality_score + deadline_score + workload_score
        self.ai_performance_score = round(total_score, 2)
        
        if total_score >= 85:
            self.ai_performance_level = 'excellent'
        elif total_score >= 75:
            self.ai_performance_level = 'good'
        elif total_score >= 60:
            self.ai_performance_level = 'average'
        else:
            self.ai_performance_level = 'below_average'
        
        self.ai_evaluation_date = fields.Datetime.now()
    
    @api.depends('performance_history_ids')
    def _compute_performance_history_count(self):
        """Đếm số lần đánh giá"""
        for record in self:
            record.performance_history_count = len(record.performance_history_ids)
    
    # ==================== HELPER METHODS ====================
    
    @api.model
    def _generate_work_email(self, name, date_of_birth):
        """
        Tạo email công ty tự động theo format: <tên><họ><năm_sinh>@dnu.edu.vn
        Ví dụ: Đỗ Ngọc Nghĩa (02/06/2004) → nghiadn2004@dnu.edu.vn
        
        Args:
            name (str): Họ tên đầy đủ
            date_of_birth (date): Ngày sinh
            
        Returns:
            str: Email công ty
        """
        if not name or not date_of_birth:
            return ''
        
        # Xử lý tên
        words = name.strip().split()
        if len(words) == 0:
            return ''
        
        # Lấy tên (từ cuối cùng) và họ (chữ cái đầu các từ còn lại)
        ten = unidecode(words[-1]).lower()  # Nghĩa
        ho_dem = ''.join([unidecode(w[0]).lower() for w in words[:-1]])  # DN (Đỗ Ngọc)
        
        # Lấy năm sinh
        if isinstance(date_of_birth, str):
            date_of_birth = fields.Date.from_string(date_of_birth)
        year = date_of_birth.strftime('%Y')
        
        # Tạo email: nghiadn2004@dnu.edu.vn
        email = f"{ten}{ho_dem}{year}@dnu.edu.vn"
        
        # Kiểm tra trùng
        counter = 1
        base_email = email
        while True:
            existing = self.search([('work_email', '=', email)], limit=1)
            if not existing:
                break
            email = f"{ten}{ho_dem}{year}{counter}@dnu.edu.vn"
            counter += 1
            if counter > 99:
                break
        
        return email
    
    @api.model
    def _generate_employee_code(self, name=None, date_of_birth=None):
        """
        Tạo mã nhân viên tự động theo format: XXX-DDMMYYYY hoặc XXX-DDMMYYYY-N
        Ví dụ: DNN-02062004 hoặc DNN-02062004-1
        """
        if not name or not date_of_birth:
            raise ValidationError('Cần có Họ tên và Ngày sinh để tạo mã nhân viên.')

        words = [w for w in unidecode(name).strip().split() if w]
        if not words:
            raise ValidationError('Họ tên không hợp lệ để tạo mã nhân viên.')

        initials = ''.join(w[0].upper() for w in words)

        if isinstance(date_of_birth, str):
            date_of_birth = fields.Date.from_string(date_of_birth)
        date_str = date_of_birth.strftime('%d%m%Y')

        base = f'{initials}-{date_str}'
        code = base
        counter = 1
        while self.search_count([('employee_code', '=', code)]) > 0:
            code = f'{base}-{counter}'
            counter += 1
        return code
    
    def _create_performance_history(self, ai_result=None):
        """Tạo bản ghi lịch sử đánh giá"""
        self.ensure_one()
        if self.total_tasks > 0:
            vals = {
                'employee_id': self.id,
                'evaluation_type': 'ai_auto',
                'overall_score': self.ai_performance_score,
                'task_completion_rate': self.task_completion_rate,
                'quality_score': self.average_task_score,
                'deadline_compliance': ((self.total_tasks - self.overdue_tasks) / self.total_tasks) * 100 if self.total_tasks > 0 else 0,
                'total_tasks': self.total_tasks,
                'completed_tasks': self.completed_tasks,
                'overdue_tasks': self.overdue_tasks,
            }
            
            if ai_result:
                vals.update({
                    'ai_analysis': ai_result.get('analysis', ''),
                    'strengths': ai_result.get('strengths', ''),
                    'improvements': ai_result.get('improvements', ''),
                    'recommendations': ai_result.get('recommendations', ''),
                })
            
            self.env['lich.su.danh.gia'].create(vals)
    
    # ==================== CONSTRAINTS ====================
    
    @api.constrains('employee_code')
    def _check_employee_code_format(self):
        """
        Kiểm tra format mã nhân viên: XXX-DDMMYYYY hoặc XXX-DDMMYYYY-N
        Ví dụ: DNN-02062004 hoặc DNN-02062004-1
        """
        # Pattern: 2-5 chữ cái + dấu gạch ngang + 8 số (ngày sinh) + (tùy chọn: -số thứ tự)
        pattern = r'^[A-Z]{2,5}-\d{8}(-\d+)?$'
        for record in self:
            # Bỏ qua check khi tạo mới (employee_code = '/' hoặc False)
            if record.employee_code and record.employee_code != '/' and not re.match(pattern, record.employee_code):
                raise ValidationError(
                    'Mã nhân viên phải theo format: XXX-DDMMYYYY\n'
                    'Ví dụ: DNN-02062004 (Đỗ Ngọc Nghĩa, sinh 02/06/2004)\n'
                    'Nếu trùng: DNN-02062004-1, DNN-02062004-2,...'
                )
    
    @api.constrains('date_of_birth')
    def _check_minimum_age(self):
        """Kiểm tra tuổi tối thiểu"""
        for record in self:
            if record.date_of_birth:
                age = relativedelta(fields.Date.today(), record.date_of_birth).years
                if age < 15:
                    raise ValidationError(
                        'Người lao động phải đủ 15 tuổi trở lên '
                        '(Điều 145, Bộ luật Lao động 2019)'
                    )
    
    @api.constrains('identification_number')
    def _check_identification_unique(self):
        """CCCD/CMND không được trùng"""
        for record in self:
            if record.identification_number:
                duplicate = self.search([
                    ('id', '!=', record.id),
                    ('identification_number', '=', record.identification_number)
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        f'Số CCCD/CMND {record.identification_number} '
                        f'đã tồn tại cho nhân viên: {duplicate.name}'
                    )
    
    @api.constrains('work_email', 'personal_email')
    def _check_email_format(self):
        """Kiểm tra format email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for record in self:
            if record.work_email and not re.match(pattern, record.work_email):
                raise ValidationError(f'Email công ty không hợp lệ: {record.work_email}')
            if record.personal_email and not re.match(pattern, record.personal_email):
                raise ValidationError(f'Email cá nhân không hợp lệ: {record.personal_email}')
    
    @api.constrains('phone')
    def _check_phone_format(self):
        """Kiểm tra format số điện thoại Việt Nam"""
        for record in self:
            if record.phone:
                # Loại bỏ khoảng trắng và dấu gạch ngang
                phone_clean = re.sub(r'[\s\-\(\)]', '', record.phone)
                # Kiểm tra format: 10 số (bắt đầu bằng 0) hoặc 11 số (bắt đầu bằng +84 hoặc 84)
                if not re.match(r'^(0\d{9}|84\d{9}|\+84\d{9})$', phone_clean):
                    raise ValidationError(
                        f'Số điện thoại không hợp lệ: {record.phone}\n'
                        'Định dạng đúng: 0987654321 hoặc +84987654321 hoặc 84987654321'
                    )
    
    @api.constrains('probation_end_date')
    def _check_probation_period(self):
        """Kiểm tra thời gian thử việc"""
        for record in self:
            if record.join_date and record.probation_end_date:
                days = (record.probation_end_date - record.join_date).days
                max_days = 180 if record.job_level in ['expert', 'manager', 'director'] else 60
                if days > max_days:
                    raise ValidationError(
                        f'Thời gian thử việc vượt quá quy định: {days} ngày\n'
                        f'Tối đa: {max_days} ngày cho cấp bậc {dict(record._fields["job_level"].selection).get(record.job_level)}'
                    )
    
    @api.constrains('manager_id')
    def _check_manager_hierarchy(self):
        """Manager không được trỏ về chính mình"""
        for record in self:
            if record.manager_id:
                if record.manager_id == record:
                    raise ValidationError('Nhân viên không thể là quản lý của chính mình')
                
                # Kiểm tra vòng lặp
                current = record.manager_id
                visited = set()
                while current:
                    if current.id in visited:
                        raise ValidationError('Phát hiện vòng lặp trong cấu trúc quản lý')
                    visited.add(current.id)
                    current = current.manager_id
    
    @api.constrains('base_salary')
    def _check_minimum_wage(self):
        """Kiểm tra lương tối thiểu vùng"""
        MINIMUM_WAGE = {
            'region_1': 4680000,
            'region_2': 4160000,
            'region_3': 3640000,
            'region_4': 3250000
        }
        
        for record in self:
            if record.base_salary > 0 and record.employment_type == 'fulltime':
                min_wage = MINIMUM_WAGE.get('region_1', 0)
                if record.base_salary < min_wage:
                    raise ValidationError(
                        f'Lương cơ bản ({record.base_salary:,.0f} VNĐ) '
                        f'thấp hơn lương tối thiểu vùng ({min_wage:,.0f} VNĐ)'
                    )
    
    # ==================== CRUD METHODS ====================
    
    @api.model
    def create(self, vals):
        """Override create"""
        # Tạo mã nhân viên tự động theo họ tên + ngày sinh
        if not vals.get('employee_code') or vals.get('employee_code') == '/':
            vals['employee_code'] = self._generate_employee_code(
                name=vals.get('name'),
                date_of_birth=vals.get('date_of_birth')
            )
        
        # Tạo email công ty tự động nếu chưa có
        if not vals.get('work_email'):
            vals['work_email'] = self._generate_work_email(
                name=vals.get('name'),
                date_of_birth=vals.get('date_of_birth')
            )
        
        record = super().create(vals)
        
        # ==================== TỰ ĐỘNG TẠO TÀI KHOẢN USER ====================
        if record.employee_code and not record.user_id:
            try:
                # Kiểm tra xem đã có user với login này chưa
                existing_user = self.env['res.users'].search([
                    ('login', '=', record.employee_code)
                ], limit=1)
                
                if not existing_user:
                    # Tạo user mới với password random
                    import secrets
                    import string
                    # Tạo password random 8 ký tự: chữ hoa + chữ thường + số
                    alphabet = string.ascii_letters + string.digits
                    default_password = ''.join(secrets.choice(alphabet) for i in range(8))
                    
                    user_vals = {
                        'name': record.name,
                        'login': record.employee_code,  # Tên đăng nhập = mã nhân viên
                        'password': default_password,  # Mật khẩu random an toàn
                        'email': record.work_email or record.personal_email or f"{record.employee_code}@company.com",
                        'groups_id': [(6, 0, [self.env.ref('quan_ly_nhan_su.group_nhan_su_employee').id])],
                        'active': True,
                    }
                    
                    user = self.env['res.users'].create(user_vals)
                    
                    # Gán user vào nhân viên
                    record.user_id = user.id
                    
                    _logger.info(f"✅ Đã tạo tài khoản user cho nhân viên {record.name} (Mã: {record.employee_code})")
                else:
                    # Nếu đã có user, gán vào nhân viên
                    record.user_id = existing_user.id
                    _logger.info(f"⚠️ Đã tìm thấy user với login {record.employee_code}, đã gán vào nhân viên")
                    
            except Exception as e:
                _logger.error(f"❌ Lỗi khi tạo user cho nhân viên {record.name}: {str(e)}")
                # Không raise error để không chặn việc tạo nhân viên
                record.message_post(
                    body=f"⚠️ <strong>Cảnh báo:</strong> Không thể tạo tài khoản đăng nhập tự động. Lỗi: {str(e)[:200]}",
                    subject="Cảnh báo tạo tài khoản"
                )
        
        # Gửi email chào mừng
        if record.work_email:
            login_info = ""
            if record.user_id:
                # Lưu password tạm thời vào note để HR có thể cung cấp cho nhân viên
                # (Trong thực tế nên gửi qua email riêng tư)
                login_info = f"""
                    <li><strong>Tên đăng nhập:</strong> {record.employee_code}</li>
                    <li><strong>Mật khẩu:</strong> Đã được tạo tự động (vui lòng liên hệ HR để nhận mật khẩu)</li>
                    <li><em>Vui lòng đổi mật khẩu sau lần đăng nhập đầu tiên!</em></li>
                """
            
            record.message_post(
                body=f"""
                    <h3>Chào mừng {record.name} gia nhập công ty!</h3>
                    <ul>
                        <li><strong>Mã nhân viên:</strong> {record.employee_code}</li>
                        <li><strong>Email công ty:</strong> {record.work_email}</li>
                        <li><strong>Phòng ban:</strong> {record.department_id.name if record.department_id else 'N/A'}</li>
                        <li><strong>Vị trí:</strong> {dict(record._fields['job_position'].selection).get(record.job_position) if record.job_position else 'N/A'}</li>
                        <li><strong>Ngày vào làm:</strong> {record.join_date if record.join_date else 'N/A'}</li>
                        {login_info}
                    </ul>
                """,
                subject="Chào mừng nhân viên mới"
            )
        
        return record
    
    def write(self, vals):
        """Override write"""
        # Track status change
        if 'working_status' in vals:
            for record in self:
                old_status = record.working_status
                new_status = vals['working_status']
                if old_status != new_status:
                    record.message_post(
                        body=f"Trạng thái thay đổi: {dict(record._fields['working_status'].selection).get(old_status)} → {dict(record._fields['working_status'].selection).get(new_status)}",
                        subject="Cập nhật trạng thái"
                    )
        
        return super().write(vals)
    
    # ==================== ACTION METHODS ====================
    
    def action_set_working(self):
        """Chuyển sang trạng thái đang làm việc"""
        for record in self:
            if record.age < 15:
                raise UserError('Không thể chuyển trạng thái: Chưa đủ tuổi lao động (15 tuổi)')
            
            record.working_status = 'working'
            record.message_post(
                body=f"Nhân viên chuyển sang trạng thái: Đang làm việc",
                subject="Cập nhật trạng thái"
            )
    
    def action_resign(self):
        """Xử lý nghỉ việc"""
        for record in self:
            record.write({
                'working_status': 'resigned',
                'resignation_date': fields.Date.today(),
                'active': False
            })
            
            if record.user_id:
                record.user_id.active = False
            
            record.message_post(
                body=f"Nhân viên đã nghỉ việc. Lý do: {record.resignation_reason or 'Không nêu'}",
                subject="Nghỉ việc"
            )
    
    def action_view_tasks(self):
        """Xem danh sách công việc được giao"""
        self.ensure_one()
        return {
            'name': f'Công việc - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'view_mode': 'kanban,tree,form,calendar',
            'domain': [('assigned_employee_id', '=', self.id)],
            'context': {
                'default_assigned_employee_id': self.id,
                'search_default_my_tasks': 1,
                'search_default_group_by_state': 1,
            }
        }
    
    def action_view_performance_history(self):
        """Xem lịch sử đánh giá"""
        self.ensure_one()
        return {
            'name': f'Lịch sử đánh giá - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lich.su.danh.gia',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }
    
    def action_evaluate_performance(self):
        """Đánh giá hiệu suất thủ công"""
        self.ensure_one()
        self._compute_ai_performance()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đánh giá hoàn tất',
                'message': f'Điểm hiệu suất: {self.ai_performance_score:.1f}/100',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_performance_ai(self):
        """Xem lịch sử đánh giá AI và biểu đồ"""
        self.ensure_one()
        return {
            'name': f'Biểu đồ hiệu suất - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.performance.ai',
            'view_mode': 'graph,tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'search_default_employee_id': self.id,
            }
        }
    
    # ==================== SCHEDULED ACTIONS ====================
    
    @api.model
    def cron_check_retirement_age(self):
        """Tự động chuyển trạng thái nghỉ hưu"""
        employees = self.search([
            ('working_status', '=', 'working'),
            ('retirement_age_check', '=', True)
        ])
        
        for emp in employees:
            emp.write({
                'working_status': 'retired',
                'active': False
            })
            emp.message_post(
                body=f"Tự động chuyển trạng thái nghỉ hưu (Tuổi: {emp.age})",
                subject="Nghỉ hưu"
            )
    
    # ==================== NAME & DISPLAY ====================
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = f"[{record.employee_code}] {record.name}"
            if record.job_position:
                name += f" - {record.job_position}"
            result.append((record.id, name))
        return result
