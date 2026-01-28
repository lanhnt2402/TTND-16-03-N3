# -*- coding: utf-8 -*-
{
    'name': 'Quản Lý Khách Hàng',
    'version': '15.0.1.1.0',
    'category': 'Sales/CRM',
    'summary': 'Quản lý khách hàng tích hợp AI phân tích tiềm năng',
    'description': """
        Quản Lý Khách Hàng Tùy Chỉnh
        ============================
        
        Tính năng chính:
        ----------------
        * Quản lý thông tin khách hàng chi tiết
        * Theo dõi vòng đời khách hàng (Lead → Active → Completed)
        * Phân tích tiềm năng khách hàng bằng AI (Gemini)
        * Cảnh báo nguy cơ mất khách (Churn Risk)
        * Quản lý công việc liên quan đến khách hàng
        * Thống kê và báo cáo chi tiết
        * Tích hợp với module Nhân sự và Công việc
        
        AI Features:
        ------------
        * Customer Scoring tự động
        * Phân tích hành vi khách hàng
        * Khuyến nghị hành động tiếp theo
        * Dự đoán nguy cơ mất khách
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
        'quan_ly_nhan_su',  # Dependency on HR module
    ],
    'data': [
        # Security
        'security/khach_hang_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/khach_hang_data.xml',
        'data/khach_hang_cron.xml',
        'data/khach_hang_mail_template.xml',
        
        # Views
        'views/khach_hang_views.xml',
        'views/khach_hang_interaction_views.xml',
        'views/khach_hang_tag_views.xml',
        'views/menu_views.xml',
        
        # Wizards
        'wizards/customer_workflow_wizard_views.xml',
        
        # Reports
        'report/khach_hang_report.xml',
    ],
    'demo': [
        'data/khach_hang_demo.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
