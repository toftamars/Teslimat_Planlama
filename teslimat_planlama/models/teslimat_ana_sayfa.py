from odoo import models, fields, api
from datetime import datetime, timedelta


class TeslimatAnaSayfa(models.Model):
    _name = 'teslimat.ana.sayfa'
    _description = 'Teslimat Ana Sayfa - Kapasite Sorgulama'

    # Sorgulama Alanları
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=True, 
                              domain="[('aktif', '=', True), ('gecici_kapatma', '=', False)]")
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
    
    @api.depends('arac_id')
    def _compute_gun(self):
        """Seçilen araç için uygun günleri belirle"""
        for record in self:
            if record.arac_id:
                # Araç tipine göre uygun günleri bul
                arac_tipi = record.arac_id.arac_tipi
                
                if arac_tipi in ['anadolu_yakasi', 'avrupa_yakasi']:
                    # Yaka bazlı araçlar için tüm günler uygun
                    gun = self.env['teslimat.gun'].search([('aktif', '=', True)], limit=1)
                    record.gun_id = gun.id if gun else False
                else:
                    # Küçük araçlar ve ek araç için tüm günler uygun
                    gun = self.env['teslimat.gun'].search([('aktif', '=', True)], limit=1)
                    record.gun_id = gun.id if gun else False
            else:
                record.gun_id = False

    @api.depends('ilce_id', 'arac_id')
    def _compute_ilce_uygunluk(self):
        """İlçe-arac uygunluğunu kontrol et"""
        for record in self:
            if record.ilce_id and record.arac_id:
                # Araç tipine göre ilçe uygunluğunu kontrol et
                arac_tipi = record.arac_id.arac_tipi
                ilce_yaka = record.ilce_id.yaka_tipi
                
                # Yaka bazlı araçlar için kısıtlama
                if arac_tipi == 'anadolu_yakasi':
                    if ilce_yaka == 'anadolu':
                        record.ilce_uygun_mu = True
                        record.uygunluk_mesaji = f"✅ {record.ilce_id.name} ilçesine {record.arac_id.name} ile teslimat yapılabilir (Anadolu Yakası)"
                    else:
                        record.ilce_uygun_mu = False
                        record.uygunluk_mesaji = f"❌ {record.ilce_id.name} ilçesine {record.arac_id.name} ile teslimat yapılamaz (Anadolu Yakası araç sadece Anadolu Yakası ilçelerine gidebilir)"
                
                elif arac_tipi == 'avrupa_yakasi':
                    if ilce_yaka == 'avrupa':
                        record.ilce_uygun_mu = True
                        record.uygunluk_mesaji = f"✅ {record.ilce_id.name} ilçesine {record.arac_id.name} ile teslimat yapılabilir (Avrupa Yakası)"
                    else:
                        record.ilce_uygun_mu = False
                        record.uygunluk_mesaji = f"❌ {record.ilce_id.name} ilçesine {record.arac_id.name} ile teslimat yapılamaz (Avrupa Yakası araç sadece Avrupa Yakası ilçelerine gidebilir)"
                
                # Küçük araçlar ve ek araç için kısıtlama yok
                elif arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']:
                    record.ilce_uygun_mu = True
                    record.uygunluk_mesaji = f"✅ {record.ilce_id.name} ilçesine {record.arac_id.name} ile teslimat yapılabilir (Her iki yakaya da gidebilir)"
                
                else:
                    record.ilce_uygun_mu = False
                    record.uygunluk_mesaji = f"❌ Bilinmeyen araç tipi: {arac_tipi}"
            else:
                record.ilce_uygun_mu = False
                record.uygunluk_mesaji = "Lütfen araç ve ilçe seçin"

    @api.depends('ilce_id', 'arac_id')
    def _compute_uygun_araclar(self):
        """Seçilen ilçe ve araç için uygunluk kontrolü"""
        for record in self:
            if record.ilce_uygun_mu and record.arac_id:
                # Seçilen araç uygun mu kontrol et
                ilce_yaka = record.ilce_id.yaka_tipi
                arac_tipi = record.arac_id.arac_tipi
                
                # Yaka uygunluğu kontrol et
                if ilce_yaka == 'anadolu' and arac_tipi == 'anadolu_yakasi':
                    record.uygun_arac_ids = [record.arac_id.id]
                elif ilce_yaka == 'avrupa' and arac_tipi == 'avrupa_yakasi':
                    record.uygun_arac_ids = [record.arac_id.id]
                elif arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']:
                    # Küçük araçlar her iki yakaya da gidebilir
                    record.uygun_arac_ids = [record.arac_id.id]
                else:
                    record.uygun_arac_ids = []
            else:
                record.uygun_arac_ids = []

    @api.depends('ilce_id', 'arac_id', 'uygun_arac_ids')
    def _compute_kapasite_bilgileri(self):
        """Kapasite bilgilerini hesapla"""
        for record in self:
            if record.ilce_uygun_mu and record.arac_id:
                # Seçilen aracın kapasitesi
                record.toplam_kapasite = record.arac_id.gunluk_teslimat_limiti
                
                # Bugün için mevcut teslimat sayısı
                bugun = fields.Date.today()
                teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                    ('teslimat_tarihi', '=', bugun),
                    ('arac_id', '=', record.arac_id.id),
                    ('durum', 'in', ['hazir', 'yolda', 'teslim_edildi'])
                ])
                
                record.kullanilan_kapasite = teslimat_sayisi
                record.kalan_kapasite = record.toplam_kapasite - teslimat_sayisi
                record.teslimat_sayisi = teslimat_sayisi
            else:
                record.toplam_kapasite = 0
                record.kullanilan_kapasite = 0
                record.kalan_kapasite = 0
                record.teslimat_sayisi = 0

    @api.depends('arac_id')
    def _compute_gunluk_kapasite(self):
        """Seçilen araç için günlük kapasite bilgilerini hesapla"""
        for record in self:
            if record.arac_id:
                # Bugün için tüm aktif araçların kapasitesi
                aktif_araclar = self.env['teslimat.arac'].search([
                    ('aktif', '=', True),
                    ('gecici_kapatma', '=', False)
                ])
                
                # Toplam günlük kapasite
                record.gunluk_toplam_kapasite = sum(arac.gunluk_teslimat_limiti for arac in aktif_araclar)
                
                # Bugün için toplam teslimat sayısı
                bugun = fields.Date.today()
                record.gunluk_teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                    ('teslimat_tarihi', '=', bugun),
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
                    📊 {self.ilce_id.name} İlçesi - {self.arac_id.name}
                    
                    🚗 Seçilen Araç: {self.arac_id.name}
                    🚗 Araç Tipi: {self.arac_id.arac_tipi.replace('_', ' ').title()}
                    📦 Araç Kapasitesi: {self.toplam_kapasite}
                    ✅ Bugün Kullanılan: {self.kullanilan_kapasite}
                    🔄 Bugün Kalan: {self.kalan_kapasite}
                    
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
