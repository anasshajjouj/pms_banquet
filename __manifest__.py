{
    'name': 'PMS Banquet Administration',
    'version': '1.0',
    'sequence': 1,
    'category': 'Property Management',
    'description': """
Management of banquets in a hospitality environment""",
    'depends': ['event'],
    'summary': 'Management of banquets in a hospitality environment',
    'website': 'https://www.agilorg.com',
    'data': [
        'security/ir.model.access.csv',
        'views/banquet_account_view.xml',
        'views/banquet_event_view.xml',
        'views/banquet_view.xml',
        'views/menus_action.xml',
        'views/rooms_views.xml',
        'views/sale_order_view.xml',

    ],
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
# -*- coding: utf-8 -*-






