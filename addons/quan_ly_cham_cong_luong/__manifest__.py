# -*- coding: utf-8 -*-
{
    'name': 'Quản lý Chấm công & Tính lương',
    'version': '2.0',
    'category': 'Human Resources',
    'summary': 'Chấm công AI, Phiếu lương, Hợp đồng AI, HR Chatbot Telegram',
    'author': 'FIT-DNU',
    'depends': ['base', 'nhan_su', 'web'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/hr_luong_co_ban_views.xml',
        'views/hr_cham_cong_views.xml',
        'views/hr_khen_thuong_ky_luat_views.xml',
        'views/hr_phieu_luong_views.xml',
        'views/hr_hop_dong_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'quan_ly_cham_cong_luong/static/src/css/backend_theme.css',
        ],
    },
    'controllers': ['controllers'],
    'installable': True,
    'application': True,
}
