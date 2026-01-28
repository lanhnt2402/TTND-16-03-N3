# -*- coding: utf-8 -*-
{
    'name': 'Quản Lý Nhân Sự',
    'version': '15.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Quản lý nhân sự tích hợp AI đánh giá hiệu suất',
    'description': """
        Quản Lý Nhân Sự Tùy Chỉnh
        ==========================
        
        Tính năng chính:
        ----------------
        * Quản lý thông tin nhân viên chi tiết
        * Quản lý phòng ban và cơ cấu tổ chức
        * Quản lý hợp đồng lao động (tuân thủ luật VN)
        * Quản lý lương, phụ cấp, bảo hiểm
        * Đánh giá hiệu suất nhân viên bằng AI (Gemini)
        * Lịch sử đánh giá và phát triển
        * Tích hợp với module Công việc và Khách hàng
        
        Tuân thủ:
        ---------
        * Bộ luật Lao động Việt Nam 2019
        * Luật Bảo hiểm xã hội 2014
        * Nghị định 06/2022/NĐ-CP về CCCD
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        # Security
        'security/nhan_su_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/nhan_su_data.xml',
        'data/nhan_su_cron.xml',
        'data/nhan_su_mail_template.xml',
        
        # Views
        'views/nhan_su_views.xml',
        'views/phong_ban_views.xml',
        'views/lich_su_danh_gia_views.xml',
        'views/employee_performance_ai_views.xml',
        'views/menu_views.xml',
        'views/data_cleanup_wizard_views.xml',
        
        # Reports
        'report/nhan_su_report.xml',
    ],
   
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['google-genai', 'unidecode'],
    },
}
