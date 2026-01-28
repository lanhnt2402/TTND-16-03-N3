# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import re
import logging

_logger = logging.getLogger(__name__)


class KhachHang(models.Model):
    _name = 'khach.hang'
    _description = 'Quản lý khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'display_name'

    # ==================== THÔNG TIN CƠ BẢN ====================
    
    customer_code = fields.Char(
        string='Mã khách hàng',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default='/',
        tracking=True,
        help='Mã tự động: KH-YYYY-XXXX (VD: KH-2026-0001)'
    )
    
    name = fields.Char(
        string='Tên liên hệ',
        required=True,
        tracking=True,
        index=True,
        help='Tên người liên hệ chính (cá nhân) hoặc tên công ty'
    )
    
    display_name = fields.Char(
        string='Tên hiển thị',
        compute='_compute_display_name',
        store=True,
        index=True
    )
    
    customer_type = fields.Selection([
        ('individual', 'Cá nhân'),
        ('company', 'Doanh nghiệp'),
        ('government', 'Cơ quan nhà nước'),
        ('ngo', 'Tổ chức phi chính phủ')
    ], string='Loại khách hàng', required=True, default='individual', tracking=True)
    
    company_name = fields.Char(
        string='Tên công ty',
        tracking=True,
        help='Bắt buộc nếu loại khách hàng là Doanh nghiệp'
    )
    
    tax_code = fields.Char(
        string='Mã số thuế',
        copy=False,
        tracking=True,
        help='Mã số thuế doanh nghiệp (10 hoặc 13 số)'
    )
    
    registration_number = fields.Char(
        string='Số đăng ký kinh doanh',
        copy=False,
        help='Số ĐKKD/Giấy phép hoạt động'
    )
    
    website = fields.Char(
        string='Website',
        help='URL website công ty'
    )
    
    logo = fields.Binary(
        string='Logo công ty',
        attachment=True
    )
    
    # ==================== THÔNG TIN LIÊN HỆ ====================
    
    job_title = fields.Char(
        string='Chức vụ người liên hệ',
        help='Chức vụ của người liên hệ chính (VD: Giám đốc, Trưởng phòng IT)'
    )
    
    phone = fields.Char(
        string='Số điện thoại',
        required=True,
        tracking=True,
        help='Số điện thoại di động chính'
    )
    
    email = fields.Char(
        string='Email',
        required=True,
        tracking=True,
        help='Email liên hệ'
    )
    
    
    # Địa chỉ
    address = fields.Text(
        string='Địa chỉ',
        help='Địa chỉ văn phòng/nhà riêng'
    )
    
    street = fields.Char(string='Đường')
    street2 = fields.Char(string='Đường 2')
    
    city = fields.Char(
        string='Quận/Huyện'
    )
    
    state_id = fields.Many2one(
        'res.country.state',
        string='Tỉnh/Thành phố',
        domain="[('country_id.code', '=', 'VN')]"
    )
    
    country_id = fields.Many2one(
        'res.country',
        string='Quốc gia',
        default=lambda self: self.env.ref('base.vn', raise_if_not_found=False)
    )
    
    zip_code = fields.Char(string='Mã bưu chính')
    
    # ==================== PHÂN LOẠI & KINH DOANH ====================
    
    industry = fields.Selection([
        ('it_software', 'Công nghệ thông tin'),
        ('manufacturing', 'Sản xuất'),
        ('retail', 'Bán lẻ'),
        ('finance', 'Tài chính - Ngân hàng'),
        ('healthcare', 'Y tế - Chăm sóc sức khỏe'),
        ('education', 'Giáo dục'),
        ('real_estate', 'Bất động sản'),
        ('construction', 'Xây dựng'),
        ('agriculture', 'Nông nghiệp'),
        ('logistics', 'Vận tải - Logistics'),
        ('hospitality', 'Khách sạn - Nhà hàng'),
        ('media', 'Truyền thông'),
        ('telecom', 'Viễn thông'),
        ('energy', 'Năng lượng'),
        ('other', 'Khác')
    ], string='Ngành nghề', tracking=True)
    
    company_size = fields.Selection([
        ('1-10', '1-10 nhân viên'),
        ('11-50', '11-50 nhân viên'),
        ('51-200', '51-200 nhân viên'),
        ('201-500', '201-500 nhân viên'),
        ('501-1000', '501-1000 nhân viên'),
        ('1000+', '1000+ nhân viên')
    ], string='Quy mô công ty')
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.ref('base.VND', raise_if_not_found=False)
    )
    
    annual_revenue = fields.Monetary(
        string='Doanh thu năm',
        currency_field='currency_id',
        help='Doanh thu ước tính hàng năm'
    )
    
    # Nguồn khách hàng
    source = fields.Selection([
        ('website', 'Website'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('zalo', 'Zalo'),
        ('google_ads', 'Google Ads'),
        ('email_campaign', 'Email Marketing'),
        ('referral', 'Giới thiệu'),
        ('event', 'Sự kiện'),
        ('cold_call', 'Gọi điện trực tiếp'),
        ('partner', 'Đối tác'),
        ('other', 'Khác')
    ], string='Nguồn khách hàng', required=True, default='website', tracking=True)
    
    source_detail = fields.Char(
        string='Chi tiết nguồn',
        help='Ví dụ: Tên người giới thiệu, tên chiến dịch'
    )
    
    # Mức độ ưu tiên
    level = fields.Selection([
        ('cold', 'Lạnh'),
        ('warm', 'Ấm'),
        ('hot', 'Nóng'),
        ('vip', 'VIP')
    ], string='Mức độ tiềm năng', default='warm', tracking=True,
        help='Đánh giá mức độ tiềm năng chốt đơn')
    
    priority = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Trung bình'),
        ('2', 'Cao'),
        ('3', 'Cấp bách')
    ], string='Độ ưu tiên', default='1')
    
    # Trạng thái
    status = fields.Selection([
        ('lead', 'Lead mới'),
        ('contacted', 'Đã liên hệ'),
        ('qualified', 'Đủ điều kiện'),
        ('proposal', 'Đã gửi đề xuất'),
        ('negotiation', 'Đàm phán'),
        ('active', 'Đang hoạt động'),
        ('inactive', 'Tạm ngưng'),
        ('completed', 'Hoàn thành'),
        ('lost', 'Mất khách')
    ], string='Trạng thái', default='lead', required=True, tracking=True)
    
    status_reason = fields.Text(
        string='Lý do trạng thái',
        help='Ghi chú lý do chuyển trạng thái (đặc biệt với lost/inactive)'
    )
    
    # ==================== PHÂN CÔNG & QUẢN LÝ ====================
    
    assigned_employee_ids = fields.Many2many(
        'nhan.su',
        'customer_employee_rel',
        'customer_id',
        'employee_id',
        string='Nhân viên phụ trách',
        domain="[('working_status', '=', 'working')]",
        tracking=True,
        help='Có thể phân công nhiều nhân viên cùng chăm sóc'
    )
    
    primary_employee_id = fields.Many2one(
        'nhan.su',
        string='Nhân viên chính',
        compute='_compute_primary_employee',
        store=True,
        help='Nhân viên được gán đầu tiên'
    )
    
    # ==================== THỐNG KÊ & LỊCH SỬ ====================
    
    # Task statistics (computed dynamically to avoid circular dependency)
    task_count = fields.Integer(
        string='Số công việc',
        compute='_compute_task_count',
        store=True
    )
    
    # Tương tác với khách hàng
    interaction_ids = fields.One2many(
        'khach.hang.interaction',
        'customer_id',
        string='Tương tác',
        help='Lịch sử tương tác với khách hàng'
    )
    
    interaction_count = fields.Integer(
        string='Số lần tương tác',
        compute='_compute_interaction_count',
        store=False
    )
    
    # Thời gian
    first_contact_date = fields.Datetime(
        string='Lần liên hệ đầu',
        default=fields.Datetime.now,
        tracking=True
    )
    
    last_contact_date = fields.Datetime(
        string='Lần liên hệ cuối',
        compute='_compute_last_contact',
        store=True
    )
    
    days_since_last_contact = fields.Integer(
        string='Số ngày chưa liên hệ',
        compute='_compute_days_since_contact',
        store=True,
        help='Cảnh báo nếu quá lâu không chăm sóc'
    )
    
    expected_revenue = fields.Monetary(
        string='Doanh thu kỳ vọng',
        currency_field='currency_id',
        tracking=True
    )
    
    probability = fields.Float(
        string='Xác suất chốt đơn (%)',
        digits=(5, 2),
        default=50.0,
        help='Ước tính xác suất chuyển đổi thành khách hàng'
    )
    
    # ==================== AI SCORING & ANALYTICS ====================
    
    ai_score = fields.Float(
        string='AI Customer Score',
        compute='_compute_ai_customer_score',
        store=True,
        digits=(5, 2),
        help='Điểm đánh giá tiềm năng khách hàng bằng AI (0-100)'
    )
    
    ai_score_level = fields.Selection([
        ('very_low', 'Rất thấp (0-20)'),
        ('low', 'Thấp (20-40)'),
        ('medium', 'Trung bình (40-60)'),
        ('high', 'Cao (60-80)'),
        ('very_high', 'Rất cao (80-100)')
    ], string='Mức độ tiềm năng AI', compute='_compute_ai_customer_score', store=True)
    
    ai_recommendation = fields.Text(
        string='Khuyến nghị AI',
        compute='_compute_ai_customer_score',
        store=True,
        help='AI gợi ý hành động tiếp theo'
    )
    
    churn_risk = fields.Float(
        string='Nguy cơ mất khách (%)',
        compute='_compute_churn_risk',
        store=True,
        digits=(5, 2),
        help='AI dự đoán nguy cơ khách hàng rời bỏ'
    )
    
    # ==================== METADATA ====================
    
    active = fields.Boolean(
        string='Hoạt động',
        default=True,
        tracking=True
    )
    
    note = fields.Html(
        string='Ghi chú nội bộ'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company
    )
    
    tag_ids = fields.Many2many(
        'khach.hang.tag',
        string='Nhãn',
        help='Phân loại khách hàng theo tag'
    )
    
    # ==================== SQL CONSTRAINTS ====================
    
    _sql_constraints = [
        ('customer_code_uniq', 'UNIQUE(customer_code)', 
         'Mã khách hàng đã tồn tại!'),
        ('probability_check', 'CHECK(probability >= 0 AND probability <= 100)', 
         'Xác suất phải trong khoảng 0-100%'),
    ]
    
    # ==================== CONSTRAINTS ====================
    
    @api.constrains('customer_type', 'company_name', 'tax_code')
    def _check_company_info(self):
        """Nếu là doanh nghiệp thì bắt buộc có tên công ty và mã số thuế"""
        for record in self:
            if record.customer_type in ['company', 'government']:
                if not record.company_name:
                    raise ValidationError(
                        'Khách hàng doanh nghiệp/cơ quan phải có tên công ty!'
                    )
                if not record.tax_code:
                    raise ValidationError(
                        'Khách hàng doanh nghiệp/cơ quan phải có mã số thuế!'
                    )
    
    @api.constrains('tax_code')
    def _check_tax_code_format(self):
        """Kiểm tra mã số thuế Việt Nam (10 hoặc 13 số)"""
        for record in self:
            if record.tax_code:
                if not re.match(r'^\d{10}(-\d{3})?$', record.tax_code):
                    raise ValidationError(
                        'Mã số thuế phải có 10 số hoặc 10 số + 3 số chi nhánh (10-123)\n'
                        f'Giá trị nhập: {record.tax_code}'
                    )
    
    @api.constrains('customer_code')
    def _check_customer_code_format(self):
        """Kiểm tra format mã khách hàng: KH-YYYY-XXXX"""
        pattern = r'^KH-\d{4}-\d{4}$'
        for record in self:
            # Bỏ qua check khi tạo mới (customer_code = '/' hoặc False)
            if record.customer_code and record.customer_code != '/' and not re.match(pattern, record.customer_code):
                raise ValidationError(
                    'Mã khách hàng phải theo format: KH-YYYY-XXXX\n'
                    'Ví dụ: KH-2026-0001'
                    )
    
    @api.constrains('email')
    def _check_email_format(self):
        """Kiểm tra format email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for record in self:
            if record.email and not re.match(pattern, record.email):
                raise ValidationError(f'Email không hợp lệ: {record.email}')
    
    @api.constrains('phone')
    def _check_phone_format(self):
        """Kiểm tra format số điện thoại Việt Nam - Cho phép cả mobile và cố định"""
        for record in self:
            if record.phone:
                # Loại bỏ khoảng trắng và dấu gạch ngang
                phone_clean = re.sub(r'[\s\-\(\)]', '', record.phone)
                # Cho phép:
                # - Mobile: 09xxxxxxxx, 08xxxxxxxx, 07xxxxxxxx, 03xxxxxxxx (10 số, bắt đầu 0[3-9])
                # - Cố định: 028xxxxxxx, 024xxxxxxx (11 số, bắt đầu 02)
                # - Quốc tế: +84xxxxxxxxx, 84xxxxxxxxx
                mobile_pattern = r'^(0[3-9]\d{8}|84[3-9]\d{8}|\+84[3-9]\d{8})$'
                landline_pattern = r'^(02\d{9})$'
                
                if not (re.match(mobile_pattern, phone_clean) or re.match(landline_pattern, phone_clean)):
                    raise ValidationError(
                        f'Số điện thoại không hợp lệ: {record.phone}\n'
                        'Định dạng đúng:\n'
                        '• Mobile: 0987654321 hoặc +84987654321\n'
                        '• Cố định: 02812345678 (HCM) hoặc 02412345678 (HN)'
                    )
    
    # ==================== COMPUTE METHODS ====================
    
    @api.depends('name', 'company_name', 'customer_type')
    def _compute_display_name(self):
        """Tên hiển thị: Công ty (Người liên hệ) hoặc Tên cá nhân"""
        for record in self:
            if record.customer_type in ['company', 'government'] and record.company_name:
                if record.name and record.name != record.company_name:
                    record.display_name = f"{record.company_name} ({record.name})"
                else:
                    record.display_name = record.company_name
            else:
                record.display_name = record.name or 'Khách hàng mới'
    
    @api.depends('assigned_employee_ids')
    def _compute_primary_employee(self):
        """Lấy nhân viên được gán đầu tiên làm nhân viên chính"""
        for record in self:
            if record.assigned_employee_ids:
                record.primary_employee_id = record.assigned_employee_ids[0]
            else:
                record.primary_employee_id = False
    
    @api.depends('write_date')
    def _compute_last_contact(self):
        """Lấy thời gian cập nhật gần nhất"""
        for record in self:
            record.last_contact_date = record.write_date or record.create_date
    
    @api.depends('write_date')
    def _compute_task_count(self):
        """Đếm số công việc liên quan - tối ưu bằng read_group"""
        # Check if cong.viec model exists (module might not be installed)
        if 'cong.viec' not in self.env:
            for record in self:
                record.task_count = 0
            return
        
        # Tối ưu: dùng read_group thay vì search trong loop
        if self:
            task_counts = self.env['cong.viec'].read_group(
                [('customer_id', 'in', self.ids)],
                ['customer_id'],
                ['customer_id']
            )
            count_dict = {item['customer_id'][0]: item['customer_id_count'] for item in task_counts}
        for record in self:
                record.task_count = count_dict.get(record.id, 0)
    
    @api.depends('interaction_ids')
    def _compute_interaction_count(self):
        """Đếm số lần tương tác"""
        for record in self:
            record.interaction_count = len(record.interaction_ids)
    
    @api.depends('last_contact_date')
    def _compute_days_since_contact(self):
        """Tính số ngày kể từ lần liên hệ cuối"""
        for record in self:
            if record.last_contact_date:
                delta = fields.Datetime.now() - record.last_contact_date
                record.days_since_last_contact = delta.days
            else:
                record.days_since_last_contact = 0
    
    @api.depends(
        'status', 'level', 'days_since_last_contact',
        'probability', 'annual_revenue'
    )
    def _compute_ai_customer_score(self):
        """AI Customer Scoring Algorithm"""
        STATUS_SCORES = {
            'lead': 10, 'contacted': 20, 'qualified': 40,
            'proposal': 60, 'negotiation': 75, 'active': 90,
            'completed': 100, 'inactive': 30, 'lost': 0
        }
        
        LEVEL_SCORES = {
            'cold': 20, 'warm': 50, 'hot': 80, 'vip': 100
        }
        
        ai_service = self.env['ai.service']
        
        for record in self:
            try:
                # Tính điểm cơ bản
                status_score = STATUS_SCORES.get(record.status, 0) * 0.30
                level_score = LEVEL_SCORES.get(record.level, 0) * 0.20
                
                # Engagement frequency (15%)
                if record.days_since_last_contact == 0:
                    engagement_score = 15
                elif record.days_since_last_contact <= 7:
                    engagement_score = 12
                elif record.days_since_last_contact <= 30:
                    engagement_score = 8
                elif record.days_since_last_contact <= 60:
                    engagement_score = 4
                else:
                    engagement_score = 0
                
                # Revenue potential (15%)
                if record.annual_revenue >= 1000000000:  # >= 1 tỷ
                    revenue_score = 15
                elif record.annual_revenue >= 500000000:  # >= 500tr
                    revenue_score = 12
                elif record.annual_revenue >= 100000000:  # >= 100tr
                    revenue_score = 8
                else:
                    revenue_score = 5
                
                # Probability (20%)
                probability_score = (record.probability / 100) * 20
                
                # Tổng điểm
                total = status_score + level_score + engagement_score + revenue_score + probability_score
                record.ai_score = round(total, 2)
                
                # Phân loại
                if total >= 80:
                    record.ai_score_level = 'very_high'
                elif total >= 60:
                    record.ai_score_level = 'high'
                elif total >= 40:
                    record.ai_score_level = 'medium'
                elif total >= 20:
                    record.ai_score_level = 'low'
                else:
                    record.ai_score_level = 'very_low'
                
                # Gọi AI để phân tích sâu hơn
                if record.status not in ['lost', 'completed']:
                    customer_data = {
                        'name': record.display_name,
                        'customer_type': dict(record._fields['customer_type'].selection).get(record.customer_type),
                        'industry': dict(record._fields['industry'].selection).get(record.industry) if record.industry else 'Không rõ',
                        'company_size': record.company_size or 'Không rõ',
                        'status': dict(record._fields['status'].selection).get(record.status),
                        'level': dict(record._fields['level'].selection).get(record.level),
                        'source': dict(record._fields['source'].selection).get(record.source),
                        'total_tasks': 0,  # Sẽ được cập nhật khi tích hợp module công việc
                        'completed_tasks': 0,
                        'last_contact_date': str(record.last_contact_date) if record.last_contact_date else 'Chưa có',
                        'days_since_contact': record.days_since_last_contact,
                        'expected_revenue': record.expected_revenue,
                        'probability': record.probability,
                    }
                    
                    ai_result = ai_service.analyze_customer_potential(customer_data)
                    record.ai_recommendation = ai_result.get('recommendations', '')
                else:
                    record.ai_recommendation = ''
                
            except Exception as e:
                _logger.error(f"Lỗi tính AI score cho {record.display_name}: {str(e)}")
                record.ai_score = total if 'total' in locals() else 50.0
                record.ai_score_level = 'medium'
                record.ai_recommendation = '→ Cần phân tích thêm dữ liệu'
    
    @api.depends('days_since_last_contact', 'status')
    def _compute_churn_risk(self):
        """Tính nguy cơ mất khách (Churn Risk)"""
        for record in self:
            risk = 0.0
            
            # Factor 1: Lâu không liên hệ
            if record.days_since_last_contact > 90:
                risk += 40
            elif record.days_since_last_contact > 60:
                risk += 25
            elif record.days_since_last_contact > 30:
                risk += 10
            
            # Factor 2: Trạng thái
            if record.status == 'inactive':
                risk += 30
            elif record.status == 'lost':
                risk = 100
            
            # Factor 3: Không có nhân viên phụ trách
            if not record.assigned_employee_ids:
                risk += 10
            
            # Factor 4: Mức độ tiềm năng thấp
            if record.level == 'cold':
                risk += 15
            
            record.churn_risk = min(risk, 100)  # Cap at 100%
    
    # ==================== HELPER METHODS ====================
    
    @api.model
    def _generate_customer_code(self):
        """Tạo mã khách hàng tự động: KH-YYYY-XXXX"""
        code = self.env['ir.sequence'].next_by_code('khach.hang')
        if not code:
            year = fields.Date.today().strftime('%Y')
            code = f'KH-{year}-0001'
        code = self._normalize_customer_code(code)
        if re.match(r'^KH-\d{4}-\d{4}$', code):
            year = code[3:7]
            number = int(code[-4:])
            while self.search_count([('customer_code', '=', code)]) > 0:
                number += 1
                code = f'KH-{year}-{number:04d}'
        return code

    @api.model
    def _normalize_customer_code(self, code):
        """Chuẩn hóa mã khách hàng về KH-YYYY-XXXX nếu có thể."""
        code = (code or '').strip()
        if re.match(r'^KH-\d{4}-\d{4}$', code):
            return code
        if re.match(r'^KH\d{4}$', code):
            year = fields.Date.today().strftime('%Y')
            return f'KH-{year}-{code[2:]}'
        if code.startswith('KH'):
            digits = re.findall(r'\d+', code)
            if digits:
                num_str = digits[-1]
                if len(num_str) > 4:
                    num_str = num_str[-4:]
                try:
                    year = fields.Date.today().strftime('%Y')
                    return f'KH-{year}-{int(num_str):04d}'
                except ValueError:
                    pass
        return code
    
    # ==================== CRUD METHODS ====================
    
    @api.model
    def create(self, vals):
        """Override create"""
        if not vals.get('customer_code') or vals.get('customer_code') == '/':
            vals['customer_code'] = self._generate_customer_code()
        
        record = super().create(vals)
        
        # Gửi notification cho nhân viên được phân công
        if record.assigned_employee_ids:
            record._notify_assigned_employees()
        
        return record
    
    def write(self, vals):
        """Override write"""
        # QUAN TRỌNG: Ngăn thay đổi status trực tiếp từ statusbar widget
        # Chỉ cho phép thay đổi status thông qua các action methods (có validation)
        if 'status' in vals and not self.env.context.get('allow_status_change'):
            for record in self:
                old_status = record.status
                new_status = vals['status']

                if old_status != new_status:
                    raise UserError(
                        '❌ Không thể thay đổi trạng thái trực tiếp!\n\n'
                        'Vui lòng sử dụng các nút workflow ở header:\n'
                        '• "Đã liên hệ" - để chuyển từ Lead → Contacted (yêu cầu file/activity)\n'
                        '• "Đủ điều kiện" - để chuyển từ Contacted → Qualified (yêu cầu đánh giá)\n'
                        '• "Gửi đề xuất" - để chuyển từ Qualified → Proposal (yêu cầu file đề xuất)\n'
                        '• "Đàm phán" - để chuyển từ Proposal → Negotiation\n'
                        '• "Kích hoạt" - để chuyển từ Negotiation → Active (yêu cầu có task)\n\n'
                        'Mỗi bước đều có validation và yêu cầu bằng chứng cụ thể (file, ghi chú, activity).'
                    )

        # Track status change - nhưng skip nếu đang trong context của action method
        if 'status' in vals and not self.env.context.get('skip_status_change_message'):
            for record in self:
                old_status = record.status
                new_status = vals['status']
                if old_status != new_status:
                    record.message_post(
                        body=f"Trạng thái thay đổi: {dict(record._fields['status'].selection).get(old_status)} → {dict(record._fields['status'].selection).get(new_status)}",
                        subject="Cập nhật trạng thái khách hàng"
                    )
        
        # Track assigned employee change
        if 'assigned_employee_ids' in vals:
            for record in self:
                record._notify_assigned_employees()
        
        return super().write(vals)
    
    def unlink(self):
        """
        Xóa khách hàng với điều kiện:
        - Chỉ Admin mới được xóa
        - Không có công việc đang thực hiện (trạng thái không phải done/cancelled)
        - Nếu có công việc, phải archive thay vì xóa
        """
        if self.env.context.get('force_unlink'):
            return super().unlink()
        for record in self:
            # Kiểm tra quyền: Chỉ Admin mới được xóa
            if not self.env.user.has_group('quan_ly_nhan_su.group_nhan_su_admin'):
                raise UserError(
                    'Bạn không có quyền xóa khách hàng!\n'
                    'Chỉ Admin mới được phép xóa khách hàng.\n'
                    'Vui lòng sử dụng chức năng "Archive" thay thế.'
                )
            
            # Kiểm tra công việc đang thực hiện
            active_tasks = self.env['cong.viec'].search([
                ('customer_id', '=', record.id),
                ('state', 'not in', ['done', 'cancelled'])
            ], limit=1)
            
            if active_tasks:
                raise UserError(
                    f'Không thể xóa khách hàng "{record.display_name}"!\n\n'
                    f'Khách hàng này đang có công việc chưa hoàn thành.\n'
                    f'Vui lòng:\n'
                    f'• Hoàn thành hoặc hủy tất cả công việc trước\n'
                    f'• Hoặc sử dụng chức năng "Archive" để ẩn khách hàng'
                )
            
            # Kiểm tra có tương tác không (cảnh báo nhưng không chặn)
            interaction_count = self.env['khach.hang.interaction'].search_count([
                ('customer_id', '=', record.id)
            ])
            
            if interaction_count > 0:
                # Chỉ cảnh báo, không chặn
                _logger.warning(
                    f'Đang xóa khách hàng {record.display_name} có {interaction_count} tương tác'
                )
        
        # Ghi log trước khi xóa
        for record in self:
            _logger.info(f'Admin {self.env.user.name} đã xóa khách hàng: {record.display_name} (Mã: {record.customer_code})')
        
        return super().unlink()
    
    # ==================== ACTION METHODS ====================
    
    def action_set_contacted(self):
        """Mở wizard để nhập thông tin liên hệ"""
        self.ensure_one()
        
        if self.status != 'lead':
            raise UserError(f'Chỉ có thể chuyển từ "Lead mới" sang "Đã liên hệ". Trạng thái hiện tại: {dict(self._fields["status"].selection).get(self.status)}')
        
        return {
            'name': 'Đã liên hệ với khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.contacted.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
            }
        }
    
    def action_set_qualified(self):
        """Mở wizard để nhập đánh giá đủ điều kiện"""
        self.ensure_one()
        
        if self.status != 'contacted':
            raise UserError(f'Chỉ có thể chuyển từ "Đã liên hệ" sang "Đủ điều kiện". Trạng thái hiện tại: {dict(self._fields["status"].selection).get(self.status)}')
        
        return {
            'name': 'Đánh giá khách hàng đủ điều kiện',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.qualified.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
            }
        }
    
    def action_send_proposal(self):
        """Mở wizard để upload file đề xuất"""
        self.ensure_one()
        
        if self.status != 'qualified':
            raise UserError(f'Chỉ có thể chuyển từ "Đủ điều kiện" sang "Đã gửi đề xuất". Trạng thái hiện tại: {dict(self._fields["status"].selection).get(self.status)}')
        
        return {
            'name': 'Gửi đề xuất cho khách hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.proposal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
            }
        }
    
    def action_start_negotiation(self):
        """Mở wizard để nhập thông tin đàm phán"""
        self.ensure_one()
        
        if self.status != 'proposal':
            raise UserError(f'Chỉ có thể chuyển từ "Đã gửi đề xuất" sang "Đàm phán". Trạng thái hiện tại: {dict(self._fields["status"].selection).get(self.status)}')
        
        return {
            'name': 'Bắt đầu đàm phán',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.negotiation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
            }
        }
    
    def action_set_active(self):
        """
        Chuyển trạng thái: Negotiation → Active
        BẮT BUỘC: Phải tạo công việc (Task) để bắt đầu triển khai
        """
        for record in self:
            if record.status != 'negotiation':
                raise UserError(f'Chỉ có thể chuyển từ "Đàm phán" sang "Đang hoạt động". Trạng thái hiện tại: {dict(record._fields["status"].selection).get(record.status)}')
            
            # Kiểm tra đã có công việc chưa
            if 'cong.viec' in self.env:
                tasks = self.env['cong.viec'].search([('customer_id', '=', record.id)])
                if not tasks:
                    raise UserError(
                        '❌ Không thể chuyển sang "Đang hoạt động"!\n\n'
                        'Bạn phải tạo công việc (Task) để bắt đầu triển khai.\n\n'
                        'Vui lòng:\n'
                        '1. Tạo công việc cho khách hàng này\n'
                        '2. Giao cho nhân viên thực hiện\n'
                        '3. Sau đó mới chuyển sang "Đang hoạt động"'
                    )
            
            # Track who activated and when
            now = fields.Datetime.now()
            update_vals = {
                'status': 'active',
            }
            
            # Safely add tracking fields
            try:
                if hasattr(record, 'activated_by_id'):
                    update_vals['activated_by_id'] = self.env.user.id
                if hasattr(record, 'activated_date'):
                    update_vals['activated_date'] = now
            except Exception:
                pass
            
            record.with_context(allow_status_change=True, skip_status_change_message=True).write(update_vals)
            
            record.message_post(
                body=f"""
                <h3>🎉 Khách hàng đã kích hoạt</h3>
                <p>Khách hàng chính thức hợp tác. Đã chuyển sang giai đoạn triển khai.</p>
                <ul>
                    <li><strong>Người kích hoạt:</strong> {self.env.user.name}</li>
                    <li><strong>Thời gian:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
                    <li><strong>Bằng chứng:</strong> Đã có {len(tasks)} công việc được tạo</li>
                </ul>
                <p><strong>CRM chuyển vai trò:</strong> Từ bán hàng → sang triển khai</p>
                """,
                subject="Cập nhật trạng thái: Đang hoạt động"
            )
            
            # Return action để reload form view và cập nhật statusbar
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'khach.hang',
                'res_id': record.id,
                'view_mode': 'form',
                'target': 'current',
            }
    
    def action_view_tasks(self):
        """Xem danh sách công việc liên quan"""
        self.ensure_one()
        return {
            'name': f'Công việc - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'view_mode': 'kanban,tree,form,calendar',
            'domain': [('customer_id', '=', self.id)],
            'context': {
                'default_customer_id': self.id,
                'search_default_group_by_state': 1,
            }
        }
    
    def action_view_assigned_employees(self):
        """Xem danh sách nhân viên phụ trách"""
        self.ensure_one()
        return {
            'name': f'Nhân viên phụ trách - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'nhan.su',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.assigned_employee_ids.ids)],
        }
    
    def action_create_task(self):
        """Tạo công việc mới cho khách hàng"""
        self.ensure_one()
        return {
            'name': f'Tạo công việc - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'view_mode': 'form',
            'context': {
                'default_customer_id': self.id,
                'default_assigned_employee_id': self.primary_employee_id.id if self.primary_employee_id else False,
            },
            'target': 'new',
        }
    
    def _notify_assigned_employees(self):
        """
        Thông báo cho nhân viên được phân công
        GỬI EMAIL - Chỉ khi giao trách nhiệm (theo yêu cầu)
        """
        self.ensure_one()
        for employee in self.assigned_employee_ids:
            if employee.user_id and employee.work_email:
                # Subscribe để nhận thông báo
                self.message_subscribe(partner_ids=employee.user_id.partner_id.ids)
                
                # Tạo activity (thông báo trong Inbox)
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=employee.user_id.id,
                    summary=f'Bạn được phân công phụ trách khách hàng {self.display_name}',
                    note=f'Khách hàng: {self.display_name}\nMã: {self.customer_code}\nTrạng thái: {dict(self._fields["status"].selection).get(self.status)}'
                )
                
                # GỬI EMAIL - Thông báo chính thức
                try:
                    email_template = self.env.ref('quan_ly_khach_hang.email_template_assign_customer')
                    email_template.send_mail(self.id, force_send=True)
                except Exception as e:
                    _logger.error(f"Lỗi gửi email giao khách hàng: {str(e)}")
                    # Fallback: Gửi message post nếu email lỗi
                    self.message_post(
                        body=f"""
                        <h3>📢 Phân công khách hàng</h3>
                        <p><strong>Nhân viên {employee.name}</strong> đã được phân công phụ trách khách hàng này.</p>
                        <ul>
                            <li><strong>Tên khách hàng:</strong> {self.display_name}</li>
                            <li><strong>Mã khách hàng:</strong> {self.customer_code}</li>
                            <li><strong>Trạng thái:</strong> {dict(self._fields["status"].selection).get(self.status)}</li>
                            <li><strong>Mức độ tiềm năng:</strong> {dict(self._fields["level"].selection).get(self.level)}</li>
                        </ul>
                        <p>Vui lòng xem thông tin chi tiết và bắt đầu chăm sóc khách hàng.</p>
                        """,
                        subject=f'Phân công phụ trách khách hàng: {self.display_name}',
                        partner_ids=employee.user_id.partner_id.ids,
                        message_type='notification'
                    )
    
    @api.model
    def cron_check_stale_customers(self):
        """Scheduled action: Cảnh báo khách hàng lâu không chăm sóc"""
        stale_customers = self.search([
            ('status', 'in', ['qualified', 'proposal', 'negotiation', 'active']),
            ('days_since_last_contact', '>', 30)
        ])
        
        for customer in stale_customers:
            if customer.primary_employee_id and customer.primary_employee_id.user_id:
                customer.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=customer.primary_employee_id.user_id.id,
                    summary=f'Cảnh báo: Khách hàng {customer.display_name} đã {customer.days_since_last_contact} ngày chưa liên hệ!'
                )
    
    # ==================== AI METHODS ====================
    
    def compute_ai_customer_scoring(self):
        """AI Customer Scoring - Đánh giá tiềm năng khách hàng"""
        self.ensure_one()
        
        ai_service = self.env['ai.service']
        
        try:
            # Chuẩn bị dữ liệu
            customer_data = {
                'name': self.display_name,
                'customer_type': dict(self._fields['customer_type'].selection).get(self.customer_type),
                'industry': dict(self._fields['industry'].selection).get(self.industry) if self.industry else 'N/A',
                'company_size': dict(self._fields['company_size'].selection).get(self.company_size) if self.company_size else 'N/A',
                'source': dict(self._fields['source'].selection).get(self.source),
                'level': dict(self._fields['level'].selection).get(self.level),
                'status': dict(self._fields['status'].selection).get(self.status),
                'annual_revenue': self.annual_revenue,
                'expected_revenue': self.expected_revenue,
                'probability': self.probability,
                'days_since_last_contact': self.days_since_last_contact,
            }
            
            # Gọi AI
            ai_result = ai_service.analyze_customer_potential(customer_data)
            
            # Cập nhật kết quả
            self.write({
                'ai_score': ai_result.get('ai_score', 50.0),
                'ai_score_level': ai_result.get('score_level', 'medium'),
                'churn_risk': ai_result.get('churn_risk', 0.0),
                'ai_recommendation': ai_result.get('recommendations', ''),
            })
            
            # Log
            self.message_post(
                body=f"""
                    <h3>🤖 AI Customer Scoring</h3>
                    <ul>
                        <li><strong>Score:</strong> {self.ai_score}/100 ({self.ai_score_level})</li>
                        <li><strong>Churn Risk:</strong> {self.churn_risk}%</li>
                    </ul>
                """,
                subject="AI Customer Analysis"
            )
            
            return True
            
        except Exception as e:
            _logger.error(f"Lỗi AI scoring cho khách hàng {self.name}: {str(e)}")
            return False

    def check_completion_status(self):
        """Kiểm tra và cập nhật trạng thái Completed nếu tất cả công việc đã xong"""
        if 'cong.viec' not in self.env:
            return
        
        CongViec = self.env['cong.viec']
        for record in self:
            # Chỉ kiểm tra nếu khách hàng đang active/negotiation/qualified
            if record.status in ['active', 'negotiation', 'proposal', 'qualified']:
                tasks = CongViec.search([('customer_id', '=', record.id), ('state', '!=', 'cancelled')])
                if tasks and all(t.state == 'done' for t in tasks):
                    # Tự động chuyển sang completed - cho phép vì đây là logic tự động
                    record.with_context(allow_status_change=True, skip_status_change_message=True).write({
                        'status': 'completed'
                    })
                    record.message_post(
                        body="✅ <strong>Tự động hoàn thành:</strong> Tất cả công việc đã được xử lý xong. Trạng thái khách hàng đã chuyển sang 'Hoàn thành'. Không thể tạo thêm công việc mới.",
                        subject="Khách hàng hoàn thành"
                    )
    
    @api.constrains('status')
    def _check_create_task_when_completed(self):
        """Ngăn tạo công việc mới khi khách hàng đã completed"""
        # Check này sẽ được gọi khi tạo task từ customer form
        pass
    
    def action_create_interaction(self):
        """Tạo tương tác mới với khách hàng"""
        self.ensure_one()
        return {
            'name': f'Tạo tương tác - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'khach.hang.interaction',
            'view_mode': 'form',
            'context': {
                'default_customer_id': self.id,
                'default_employee_id': self.primary_employee_id.id if self.primary_employee_id else False,
            },
            'target': 'new',
        }
    
    def action_view_interactions(self):
        """Xem danh sách tương tác"""
        self.ensure_one()
        return {
            'name': f'Tương tác - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'khach.hang.interaction',
            'view_mode': 'tree,form,kanban',
            'domain': [('customer_id', '=', self.id)],
            'context': {
                'default_customer_id': self.id,
            }
        }
    
    # ==================== NAME & DISPLAY ====================
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = f"[{record.customer_code}] {record.display_name}"
            result.append((record.id, name))
        return result
