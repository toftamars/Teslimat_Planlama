{
    'name': 'Teslimat Planlama',
    'version': '15.0.2.3.9',
    'category': 'Inventory',
    'summary': 'Teslimat planlaması ve rota optimizasyonu',
    'description': """
        Teslimat Planlama Modülü
        
        Bu modül teslimat planlaması ve yönetimi için geliştirilmiştir.
        
        Özellikler:
        - Araç ve kapasite yönetimi
        - İlçe-gün eşleştirmeleri (dinamik yapılandırma)
        - Teslimat belgesi oluşturma ve takibi
        - Transfer belgeleri entegrasyonu
        - Kapasite sorgulama ve raporlama
        - 3 farklı rol: Kullanıcı, Sürücü, Yönetici
        
        Kurallar:
        - User grubu günlük max 7 teslimat oluşturabilir
        - Manager grubu sınırsız teslimat oluşturabilir
        - Tüm yapılandırmalar modül içinden yapılabilir (dinamik)
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'contacts',
        'stock',
        'mail',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/teslimat_program_kurulum_data.xml',
        'data/istanbul_ilceleri_data.xml',
        
        # Core Views
        # 'views/teslimat_sehir_views.xml',  # Deprecated - using res.country.state
        'views/teslimat_ilce_views.xml',
        'views/teslimat_gun_views.xml',
        'views/teslimat_arac_views.xml',

        # Action'ları içeren Views (ONCE yukle - menu bunları referans ediyor)
        'views/teslimat_ana_sayfa_views.xml',  # action_teslimat_ana_sayfa
        'views/teslimat_belgesi_views.xml',     # action_teslimat_belgesi, action_teslimat_belgesi_surucu
        'views/teslimat_arac_kapatma_views.xml',  # action_teslimat_arac_kapatma

        # Menu (Tüm action'lar yuklendikten sonra)
        'views/menu_views.xml',
        
        # Business Logic Views
        'views/teslimat_planlama_views.xml',
        'views/teslimat_transfer_views.xml',
        
        # Wizard Views
        'views/teslimat_belgesi_wizard_views.xml',
        'views/teslimat_gun_kapatma_wizard_views.xml',
        'views/teslimat_konum_wizard_views.xml',
        'views/teslimat_tamamlama_wizard_views.xml',
        'views/teslimat_arac_kapatma_wizard_views.xml',
        
        # Inherit Views
        'views/stock_picking_views.xml',
        'views/res_partner_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_backend': [
            'teslimat_planlama/static/src/js/uygun_gunler_click.js',
            'teslimat_planlama/static/src/js/fotograf_zoom.js',
        ],
    },
}
