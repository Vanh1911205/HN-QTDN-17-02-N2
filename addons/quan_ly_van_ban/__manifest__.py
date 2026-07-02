# -*- coding: utf-8 -*-
{
    'name': "quan_ly_van_ban",
    'summary': """Module quản lý văn bản đi và văn bản đến liên kết nhân sự""",
    'description': """
        Thiết lập mối quan hệ giữa hai module nhan_su và quan_ly_van_ban.
    """,
    'author': "FIT-DNU",
    'website': "https://ttdn1501.aiotlabdnu.xyz/web",
    'category': 'Document Management',
    'version': '1.0',
    'depends': ['base', 'nhan_su', 'quan_ly_cham_cong_luong'],
    'data': [
        'security/ir.model.access.csv',
        'views/loai_van_ban.xml',
        'views/van_ban_den.xml',
        'views/van_ban_di.xml',
        'views/menu.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
}