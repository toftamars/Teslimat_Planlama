from odoo import models, fields, api
from datetime import datetime, timedelta


class TeslimatAnaSayfa(models.Model):
    _name = 'teslimat.ana.sayfa'
    _description = 'Teslimat Ana Sayfa - Kapasite Sorgulama'

    # Sorgulama Alanları
    sorgu_tarihi = fields.Date(string='Tarih', required=True, default=fields.Date.today)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=True)
    
    # Sonuç Alanları (Hesaplanan)
    gun_id = fields.Many2one('teslimat.gun', string='Teslimat Günü', compute='_compute_gun', store=True)
    uygun_arac_ids = fields.Many2many('teslimat.arac', string='Uygun Araçlar', compute='_compute_uygun_araclar')
    
    # İlçe Bazlı Kapasite
    toplam_kapasite = fields.Integer(string='Toplam Kapasite', compute='_compute_kapasite_bilgileri')
    kullanilan_kapasite = fields.Integer(string='Kullanılan Kapasite', compute='_compute_kapasite_bilgileri')
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kapasite_bilgileri')
    teslimat_sayisi = fields.Integer(string='Teslimat Sayısı', compute='_compute_kapasite_bilgileri')
    
    # Günlük Genel Kapasite
    gunluk_toplam_kapasite = fields.Integer(string='Günlük Toplam Kapasite', compute='_compute_gunluk_kapasite')
    gunluk_kullanilan_kapasite = fields.Integer(string='Günlük Kullanılan Kapasite', compute='_compute_gunluk_kapasite')
    gunluk_kalan_kapasite = fields.Integer(string='Günlük Kalan Kapasite', compute='_compute_gunluk_kapasite')
    gunluk_teslimat_sayisi = fields.Integer(string='Günlük Teslimat Sayısı', compute='_compute_gunluk_kapasite')
    
    # Yaka Bazlı Kapasite
    anadolu_yaka_kapasite = fields.Integer(string='Anadolu Yakası Kapasite', compute='_compute_gunluk_kapasite')
    avrupa_yaka_kapasite = fields.Integer(string='Avrupa Yakası Kapasite', compute='_compute_gunluk_kapasite')
    
    # İlçe-Gün Uygunluk Kontrolü
    ilce_uygun_mu = fields.Boolean(string='İlçe Uygun mu?', compute='_compute_ilce_uygunluk', store=True)
    uygunluk_mesaji = fields.Text(string='Uygunluk Mesajı', compute='_compute_ilce_uygunluk')
    
    @api.depends('sorgu_tarihi')
    def _compute_gun(self):
        """Seçilen tarihe göre teslimat gününü belirle"""
        for record in self:
            if record.sorgu_tarihi:
                # Haftanın gününü bul (0=Pazartesi, 1=Salı, vs.)
                gun_kodu = record.sorgu_tarihi.strftime('%A').lower()
                gun_map = {
                    'monday': 'pazartesi',
                    'tuesday': 'sali',
                    'wednesday': 'carsamba',
                    'thursday': 'persembe',
                    'friday': 'cuma',
                    'saturday': 'cumartesi',
                    'sunday': 'pazar'
                }
                gun_kodu_tr = gun_map.get(gun_kodu, 'pazartesi')
                
                # İlgili günü bul
                gun = self.env['teslimat.gun'].search([('gun_kodu', '=', gun_kodu_tr)], limit=1)
                record.gun_id = gun.id if gun else False
            else:
                record.gun_id = False

    @api.depends('ilce_id', 'gun_id')
    def _compute_ilce_uygunluk(self):
        """İlçe-gün uygunluğunu kontrol et"""
        for record in self:
            if record.ilce_id and record.gun_id:
                # İlçe o gün için tanımlı mı?
                ilce_gun_eslesme = self.env['teslimat.gun.ilce'].search([
                    ('gun_id', '=', record.gun_id.id),
                    ('ilce_id', '=', record.ilce_id.id)
                ], limit=1)
                
                if ilce_gun_eslesme:
                    record.ilce_uygun_mu = True
                    record.uygunluk_mesaji = f"✅ {record.ilce_id.name} ilçesine {record.gun_id.name} günü teslimat yapılabilir"
                else:
                    record.ilce_uygun_mu = False
                    record.uygunluk_mesaji = f"❌ {record.ilce_id.name} ilçesine {record.gun_id.name} günü teslimat yapılamaz"
            else:
                record.ilce_uygun_mu = False
                record.uygunluk_mesaji = "Lütfen tarih ve ilçe seçin"

    @api.depends('ilce_id', 'gun_id', 'sorgu_tarihi')
    def _compute_uygun_araclar(self):
        """Seçilen ilçe ve gün için uygun araçları bul"""
        for record in self:
            if record.ilce_uygun_mu and record.gun_id:
                # İlçe tipine göre uygun araçları bul
                ilce_yaka = record.ilce_id.yaka_tipi
                
                if ilce_yaka in ['anadolu', 'avrupa']:
                    # Yaka bazlı araç seçimi
                    arac_tipi_map = {
                        'anadolu': 'anadolu_yakasi',
                        'avrupa': 'avrupa_yakasi'
                    }
                    arac_tipi = arac_tipi_map.get(ilce_yaka)
                    
                    araclar = self.env['teslimat.arac'].search([
                        ('arac_tipi', '=', arac_tipi),
                        ('aktif', '=', True),
                        ('gecici_kapatma', '=', False)
                    ])
                else:
                    # Her iki yaka için de uygun araçlar
                    araclar = self.env['teslimat.arac'].search([
                        ('aktif', '=', True),
                        ('gecici_kapatma', '=', False)
                    ])
                
                record.uygun_arac_ids = araclar.ids
            else:
                record.uygun_arac_ids = []

    @api.depends('ilce_id', 'gun_id', 'sorgu_tarihi', 'uygun_arac_ids')
    def _compute_kapasite_bilgileri(self):
        """Kapasite bilgilerini hesapla"""
        for record in self:
            if record.ilce_uygun_mu and record.uygun_araclar:
                # Toplam kapasite
                toplam_kapasite = sum(arac.gunluk_teslimat_limiti for arac in record.uygun_araclar)
                
                # O gün için mevcut teslimat sayısı
                teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                    ('teslimat_tarihi', '=', record.sorgu_tarihi),
                    ('ilce_id', '=', record.ilce_id.id),
                    ('arac_id', 'in', record.uygun_araclar.ids),
                    ('durum', 'in', ['hazir', 'yolda', 'teslim_edildi'])
                ])
                
                record.toplam_kapasite = toplam_kapasite
                record.kullanilan_kapasite = teslimat_sayisi
                record.kalan_kapasite = toplam_kapasite - teslimat_sayisi
                record.teslimat_sayisi = teslimat_sayisi
            else:
                record.toplam_kapasite = 0
                record.kullanilan_kapasite = 0
                record.kalan_kapasite = 0
                record.teslimat_sayisi = 0

    @api.depends('sorgu_tarihi')
    def _compute_gunluk_kapasite(self):
        """Seçilen gün için genel kapasite bilgilerini hesapla"""
        for record in self:
            if record.sorgu_tarihi and record.gun_id:
                # O gün için tüm aktif araçların kapasitesi
                aktif_araclar = self.env['teslimat.arac'].search([
                    ('aktif', '=', True),
                    ('gecici_kapatma', '=', False)
                ])
                
                # Toplam günlük kapasite
                record.gunluk_toplam_kapasite = sum(arac.gunluk_teslimat_limiti for arac in aktif_araclar)
                
                # O gün için toplam teslimat sayısı
                record.gunluk_teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                    ('teslimat_tarihi', '=', record.sorgu_tarihi),
                    ('durum', 'in', ['hazir', 'yolda', 'teslim_edildi'])
                ])
                
                record.gunluk_kullanilan_kapasite = record.gunluk_teslimat_sayisi
                record.gunluk_kalan_kapasite = record.gunluk_toplam_kapasite - record.gunluk_teslimat_sayisi
                
                # Yaka bazlı kapasite hesaplama
                anadolu_araclar = aktif_araclar.filtered(lambda a: a.arac_tipi == 'anadolu_yakasi')
                avrupa_araclar = aktif_araclar.filtered(lambda a: a.arac_tipi == 'avrupa_yakasi')
                
                record.anadolu_yaka_kapasite = sum(arac.gunluk_teslimat_limiti for arac in anadolu_araclar)
                record.avrupa_yaka_kapasite = sum(arac.gunluk_teslimat_limiti for arac in avrupa_araclar)
                
            else:
                record.gunluk_toplam_kapasite = 0
                record.gunluk_kullanilan_kapasite = 0
                record.gunluk_kalan_kapasite = 0
                record.gunluk_teslimat_sayisi = 0
                record.anadolu_yaka_kapasite = 0
                record.avrupa_yaka_kapasite = 0

    def action_sorgula(self):
        """Sorgula butonuna basıldığında çalışacak method"""
        self.ensure_one()
        
        if not self.ilce_uygun_mu:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Uyarı',
                    'message': self.uygunluk_mesaji,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Kapasite bilgilerini yeniden hesapla
        self._compute_kapasite_bilgileri()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Kapasite Bilgileri',
                'message': f"""
                    📊 {self.ilce_id.name} İlçesi - {self.gun_id.name}
                    
                    🚗 Uygun Araç Sayısı: {len(self.uygun_arac_ids)}
                    📦 İlçe Toplam Kapasite: {self.toplam_kapasite}
                    ✅ İlçe Kullanılan: {self.kullanilan_kapasite}
                    🔄 İlçe Kalan: {self.kalan_kapasite}
                    
                    🌟 GÜNLÜK GENEL KAPASİTE:
                    📦 Günlük Toplam: {self.gunluk_toplam_kapasite}
                    ✅ Günlük Kullanılan: {self.gunluk_kullanilan_kapasite}
                    🔄 Günlük Kalan: {self.gunluk_kalan_kapasite}
                    
                    🗺️ YAKA BAZLI KAPASİTE:
                    🇹🇷 Anadolu Yakası: {self.anadolu_yaka_kapasite}
                    🇪🇺 Avrupa Yakası: {self.avrupa_yaka_kapasite}
                    
                    {self.uygunluk_mesaji}
                """,
                'type': 'success',
                'sticky': True,
            }
        }
