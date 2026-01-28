# -*- coding: utf-8 -*-
{
    'name': 'Quản Lý Công Việc',
    'version': '15.0.1.1.0',
    'category': 'Project',
    'summary': 'Quản lý công việc tích hợp AI đánh giá chất lượng',
    'description': """
        Quản Lý Công Việc Tùy Chỉnh
        ===========================
        
        Tính năng chính:
        ----------------
        * Quản lý công việc chi tiết với workflow
        * Phân công công việc cho nhân viên
        * Liên kết công việc với khách hàng
        * Đánh giá chất lượng công việc bằng AI (Gemini)
        * So sánh yêu cầu vs kết quả thực tế
        * Theo dõi tiến độ và deadline
        * Thống kê hiệu suất làm việc
        * Tích hợp với module Nhân sự và Khách hàng
        
        AI Features:
        ------------
        * 🤖 Đánh giá báo cáo: So sánh yêu cầu vs kết quả (API 1 - QUAN TRỌNG NHẤT)
        * 🎯 Gợi ý phân công thông minh: AI chọn nhân viên phù hợp (API 2)
        * 🔮 Dự đoán thời gian: AI ước lượng thời gian hoàn thành (API 3)
        * ⚠️ Phát hiện rủi ro: Cảnh báo sớm công việc có vấn đề (API 4)
        * 📝 Tạo tiêu chí nghiệm thu tự động (API 5)
        * Phân tích chi tiết: Đã làm gì / Chưa làm gì / Làm vượt mức
        * Quality scoring tự động với xếp loại A+/A/B/C/D/F
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
        'quan_ly_nhan_su',
        'quan_ly_khach_hang',  # Required: cong.viec uses interaction_id field
    ],
    'data': [
        # Security
        'security/cong_viec_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/cong_viec_data.xml',
        'data/cong_viec_cron.xml',
        'data/cong_viec_mail_template.xml',
        'data/gemini_api_config.xml',
        
        # Views
        'views/cong_viec_views.xml',
        'views/cong_viec_tag_views.xml',
        'views/menu_views.xml',
        
        # Reports
        'report/cong_viec_report.xml',
        
        # Wizards
        'wizards/task_assignment_wizard_views.xml',
        'wizards/task_report_evaluation_wizard_views.xml',
        'wizards/task_workflow_wizard_views.xml',
    ],
    'demo': [
        'data/cong_viec_demo.xml',
    ],

    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['google-genai', 'PyPDF2', 'python-docx'],
    },
}
