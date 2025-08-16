from odoo import models, fields, api, _


class TeslimatSehir(models.Model):
    _name = 'teslimat.sehir'
    _description = 'Teslimat Şehir Yönetimi'
    _order = 'name'

    name = fields.Char(string='Şehir Adı', required=True)
    ulke_id = fields.Many2one('res.country', string='Ülke', default=lambda self: self.env.ref('base.tr'))
    aktif = fields.Boolean(string='Aktif', default=True)
    
    # İlçe İlişkisi
    ilce_ids = fields.One2many('teslimat.ilce', 'sehir_id', string='İlçeler')
    
    # Teslimat Bilgileri
    teslimat_aktif = fields.Boolean(string='Teslimat Aktif', default=True)
    varsayilan_teslimat_suresi = fields.Integer(string='Varsayılan Teslimat Süresi (Gün)', default=1)
    
    @api.model
    def get_istanbul(self):
        """İstanbul şehrini getir veya oluştur"""
        istanbul = self.search([('name', 'ilike', 'İstanbul')], limit=1)
        if not istanbul:
            istanbul = self.create({
                'name': 'İstanbul',
                'ulke_id': self.env.ref('base.tr').id,
                'teslimat_aktif': True,
                'varsayilan_teslimat_suresi': 1
            })
        return istanbul


class TeslimatIlce(models.Model):
    _name = 'teslimat.ilce'
    _description = 'Teslimat İlçe Yönetimi'
    _order = 'sehir_id, name'

    name = fields.Char(string='İlçe Adı', required=True)
    sehir_id = fields.Many2one('teslimat.sehir', string='Şehir', required=True)
    aktif = fields.Boolean(string='Aktif', default=True)
    
    # Yaka Belirleme
    yaka_tipi = fields.Selection([
        ('anadolu', 'Anadolu Yakası'),
        ('avrupa', 'Avrupa Yakası'),
        ('belirsiz', 'Belirsiz')
    ], string='Yaka Tipi', compute='_compute_yaka_tipi', store=True)
    
    # Konum Bilgileri
    enlem = fields.Float(string='Enlem')
    boylam = fields.Float(string='Boylam')
    posta_kodu = fields.Char(string='Posta Kodu')
    
    # Teslimat Bilgileri
    teslimat_aktif = fields.Boolean(string='Teslimat Aktif', default=True)
    teslimat_suresi = fields.Integer(string='Teslimat Süresi (Gün)', default=1)
    teslimat_notlari = fields.Text(string='Teslimat Notları')
    
    # Özel Durumlar
    ozel_durum = fields.Selection([
        ('normal', 'Normal'),
        ('yogun', 'Yoğun'),
        ('kapali', 'Kapalı'),
        ('ozel', 'Özel')
    ], string='Özel Durum', default='normal')
    
    # İlişkiler
    gun_ids = fields.Many2many('teslimat.gun', through='teslimat.gun.ilce', string='Teslimat Günleri')
    arac_ids = fields.Many2many('teslimat.arac', string='Uygun Araçlar')
    
    @api.depends('name')
    def _compute_yaka_tipi(self):
        """İlçe adına göre yaka tipini otomatik belirle"""
        anadolu_ilceleri = [
            'Kadıköy', 'Üsküdar', 'Ataşehir', 'Ümraniye', 'Maltepe', 'Kartal', 
            'Pendik', 'Tuzla', 'Çekmeköy', 'Sancaktepe', 'Sultanbeyli', 'Şile',
            'Beykoz', 'Çatalca', 'Silivri', 'Büyükçekmece', 'Küçükçekmece',
            'Avcılar', 'Esenyurt', 'Başakşehir', 'Sultangazi', 'Eyüpsultan',
            'Kağıthane', 'Şişli', 'Beşiktaş', 'Beyoğlu', 'Fatih', 'Üsküdar'
        ]
        
        avrupa_ilceleri = [
            'Bakırköy', 'Bahçelievler', 'Güngören', 'Esenler', 'Bağcılar',
            'Sultangazi', 'Gaziosmanpaşa', 'Küçükçekmece', 'Avcılar', 'Esenyurt',
            'Başakşehir', 'Arnavutköy', 'Sarıyer', 'Beşiktaş', 'Şişli',
            'Kağıthane', 'Eyüpsultan', 'Fatih', 'Beyoğlu', 'Üsküdar'
        ]
        
        for record in self:
            if record.name:
                if any(ilce.lower() in record.name.lower() for ilce in anadolu_ilceleri):
                    record.yaka_tipi = 'anadolu'
                elif any(ilce.lower() in record.name.lower() for ilce in avrupa_ilceleri):
                    record.yaka_tipi = 'avrupa'
                else:
                    record.yaka_tipi = 'belirsiz'
            else:
                record.yaka_tipi = 'belirsiz'
    
    @api.model
    def create_istanbul_ilceleri(self):
        """İstanbul ilçelerini otomatik oluştur"""
        istanbul = self.env['teslimat.sehir'].get_istanbul()
        
        ilce_listesi = [
            # Anadolu Yakası
            {'name': 'Kadıköy', 'yaka_tipi': 'anadolu'},
            {'name': 'Üsküdar', 'yaka_tipi': 'anadolu'},
            {'name': 'Ataşehir', 'yaka_tipi': 'anadolu'},
            {'name': 'Ümraniye', 'yaka_tipi': 'anadolu'},
            {'name': 'Maltepe', 'yaka_tipi': 'anadolu'},
            {'name': 'Kartal', 'yaka_tipi': 'anadolu'},
            {'name': 'Pendik', 'yaka_tipi': 'anadolu'},
            {'name': 'Tuzla', 'yaka_tipi': 'anadolu'},
            {'name': 'Çekmeköy', 'yaka_tipi': 'anadolu'},
            {'name': 'Sancaktepe', 'yaka_tipi': 'anadolu'},
            {'name': 'Sultanbeyli', 'yaka_tipi': 'anadolu'},
            {'name': 'Şile', 'yaka_tipi': 'anadolu'},
            {'name': 'Beykoz', 'yaka_tipi': 'anadolu'},
            
            # Avrupa Yakası
            {'name': 'Bakırköy', 'yaka_tipi': 'avrupa'},
            {'name': 'Bahçelievler', 'yaka_tipi': 'avrupa'},
            {'name': 'Güngören', 'yaka_tipi': 'avrupa'},
            {'name': 'Esenler', 'yaka_tipi': 'avrupa'},
            {'name': 'Bağcılar', 'yaka_tipi': 'avrupa'},
            {'name': 'Sultangazi', 'yaka_tipi': 'avrupa'},
            {'name': 'Gaziosmanpaşa', 'yaka_tipi': 'avrupa'},
            {'name': 'Küçükçekmece', 'yaka_tipi': 'avrupa'},
            {'name': 'Avcılar', 'yaka_tipi': 'avrupa'},
            {'name': 'Esenyurt', 'yaka_tipi': 'avrupa'},
            {'name': 'Başakşehir', 'yaka_tipi': 'avrupa'},
            {'name': 'Arnavutköy', 'yaka_tipi': 'avrupa'},
            {'name': 'Sarıyer', 'yaka_tipi': 'avrupa'},
            {'name': 'Beşiktaş', 'yaka_tipi': 'avrupa'},
            {'name': 'Şişli', 'yaka_tipi': 'avrupa'},
            {'name': 'Kağıthane', 'yaka_tipi': 'avrupa'},
            {'name': 'Eyüpsultan', 'yaka_tipi': 'avrupa'},
            {'name': 'Fatih', 'yaka_tipi': 'avrupa'},
            {'name': 'Beyoğlu', 'yaka_tipi': 'avrupa'},
            
            # Çatalca ve Silivri
            {'name': 'Çatalca', 'yaka_tipi': 'avrupa'},
            {'name': 'Silivri', 'yaka_tipi': 'avrupa'},
            {'name': 'Büyükçekmece', 'yaka_tipi': 'avrupa'},
        ]
        
        for ilce_data in ilce_listesi:
            if not self.search([('name', '=', ilce_data['name']), ('sehir_id', '=', istanbul.id)]):
                self.create({
                    'name': ilce_data['name'],
                    'sehir_id': istanbul.id,
                    'yaka_tipi': ilce_data['yaka_tipi'],
                    'teslimat_aktif': True,
                    'teslimat_suresi': 1
                })
        
        return True
