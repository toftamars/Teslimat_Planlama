{
    'name': 'Teslimat Planlama',
    'version': '15.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Teslimat planlaması ve rota optimizasyonu',
    'description': """
        Bu modül teslimat planlaması için geliştirilmiştir.
        Özellikler:
        - Kontakt bilgileri yönetimi
        - Transfer işlemleri
        - Stok bilgileri entegrasyonu
        - Teslimat planı oluşturma
        
        NOT: SMS özellikleri şu anda deaktif, gelecekte eklenebilir
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'contacts',
        'stock',
        'delivery',
        'sale',
    ],
               'data': [
               'security/security.xml',
               'security/ir.model.access.csv',
               'data/ir_sequence_data.xml',
               'data/demo_data.xml',
               'views/teslimat_planlama_views.xml',
               'views/teslimat_ana_sayfa_views.xml',

               'views/teslimat_belgesi_wizard_views.xml',
               'views/menu_views.xml',
           ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
