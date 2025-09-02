from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class TeslimatGun(models.Model):
    _name = 'teslimat.gun'
    _description = 'Teslimat Gün Yönetimi'
    _order = 'sequence'

    name = fields.Char(string='Gün Adı', required=True)
    sequence = fields.Integer(string='Sıra', default=10)
    gun_kodu = fields.Selection([
        ('pazartesi', 'Pazartesi'),
        ('sali', 'Salı'),
        ('carsamba', 'Çarşamba'),
        ('persembe', 'Perşembe'),
        ('cuma', 'Cuma'),
        ('cumartesi', 'Cumartesi'),
        ('pazar', 'Pazar')
    ], string='Gün Kodu', required=True)
    
    # Durum Bilgileri
    aktif = fields.Boolean(string='Aktif', default=True)
    gecici_kapatma = fields.Boolean(string='Geçici Kapatma')
    kapatma_sebebi = fields.Text(string='Kapatma Sebebi')
    kapatma_baslangic = fields.Date(string='Kapatma Başlangıç')
    kapatma_bitis = fields.Date(string='Kapatma Bitiş')
    
    # Kapasite Bilgileri
    gunluk_maksimum_teslimat = fields.Integer(string='Günlük Maksimum Teslimat', default=50)
    mevcut_teslimat_sayisi = fields.Integer(string='Mevcut Teslimat Sayısı', compute='_compute_mevcut_teslimat', store=True)
    kalan_teslimat_kapasitesi = fields.Integer(string='Kalan Teslimat Kapasitesi', compute='_compute_kalan_kapasite', store=True)
    
    # İlçe Eşleşmeleri
    ilce_ids = fields.One2many('teslimat.gun.ilce', 'gun_id', string='İlçe Eşleşmeleri')
    
    # Yaka Bazlı Gruplandırma
    yaka_tipi = fields.Selection([
        ('anadolu', 'Anadolu Yakası'),
        ('avrupa', 'Avrupa Yakası'),
        ('her_ikisi', 'Her İkisi')
    ], string='Yaka Tipi', default='her_ikisi')
    
    @api.depends('ilce_ids', 'ilce_ids.teslimat_sayisi')
    def _compute_mevcut_teslimat(self):
        for record in self:
            bugun = fields.Date.today()
            bugun_teslimatlar = record.ilce_ids.filtered(
                lambda i: i.tarih == bugun
            )
            record.mevcut_teslimat_sayisi = sum(bugun_teslimatlar.mapped('teslimat_sayisi'))
    
    @api.depends('gunluk_maksimum_teslimat', 'mevcut_teslimat_sayisi')
    def _compute_kalan_kapasite(self):
        for record in self:
            record.kalan_teslimat_kapasitesi = record.gunluk_maksimum_teslimat - record.mevcut_teslimat_sayisi
    
    def action_gecici_kapat(self):
        """Günü geçici olarak kapat"""
        self.ensure_one()
        return {
            'name': _('Gün Kapatma'),
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.gun.kapatma.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_gun_id': self.id}
        }
    
    def action_aktif_et(self):
        """Günü aktif et"""
        self.ensure_one()
        self.write({
            'gecici_kapatma': False,
            'kapatma_sebebi': False,
            'kapatma_baslangic': False,
            'kapatma_bitis': False
        })
    
    @api.model
    def get_uygun_gunler(self, ilce_id, tarih=None):
        """Belirli ilçe için uygun günleri getir - Kod ile çalışır"""
        # İlçe adını al
        ilce = self.env['teslimat.ilce'].browse(ilce_id)
        if not ilce:
            return self.env['teslimat.gun']
        
        ilce_adi = ilce.name
        
        # Kod ile ilçe-gün eşleşmelerini tanımla
        ilce_gun_eslesmeleri = {
            # ANADOLU YAKASI
            'Maltepe': ['pazartesi', 'perşembe'],
            'Kartal': ['pazartesi', 'perşembe'],
            'Pendik': ['pazartesi', 'perşembe'],
            'Tuzla': ['pazartesi', 'perşembe'],
            'Üsküdar': ['sali', 'carsamba', 'cuma'],
            'Kadıköy': ['sali', 'carsamba', 'cuma'],
            'Ümraniye': ['sali', 'carsamba', 'cuma'],
            'Ataşehir': ['sali', 'carsamba', 'cuma'],
            'Beykoz': ['cumartesi'],
            'Çekmeköy': ['cumartesi'],
            'Sancaktepe': ['cumartesi'],
            'Sultanbeyli': ['cumartesi'],
            'Şile': ['cumartesi'],
            
            # AVRUPA YAKASI
            'Şişli': ['pazartesi', 'cuma'],
            'Beşiktaş': ['pazartesi', 'cuma'],
            'Beyoğlu': ['pazartesi', 'cuma'],
            'Kağıthane': ['pazartesi', 'cuma'],
            'Sarıyer': ['sali'],
            'Eyüpsultan': ['sali'],
            'Sultangazi': ['sali'],
            'Gaziosmanpaşa': ['sali'],
            'Bağcılar': ['carsamba'],
            'Bahçelievler': ['carsamba'],
            'Bakırköy': ['carsamba', 'perşembe', 'cumartesi'],
            'Güngören': ['carsamba'],
            'Esenler': ['carsamba'],
            'Zeytinburnu': ['carsamba'],
            'Bayrampaşa': ['carsamba'],
            'Fatih': ['carsamba'],
            'Büyükçekmece': ['perşembe', 'cumartesi'],
            'Silivri': ['perşembe', 'cumartesi'],
            'Çatalca': ['perşembe', 'cumartesi'],
            'Arnavutköy': ['perşembe', 'cumartesi']
        }
        
        # İlçe için uygun günleri bul
        uygun_gun_kodlari = ilce_gun_eslesmeleri.get(ilce_adi, [])
        
        if not uygun_gun_kodlari:
            return self.env['teslimat.gun']
        
        # Günleri getir
        domain = [
            ('gun_kodu', 'in', uygun_gun_kodlari),
            ('aktif', '=', True),
            ('gecici_kapatma', '=', False)
        ]
        
        if tarih:
            domain += [
                '|',
                ('kapatma_bitis', '=', False),
                ('kapatma_bitis', '<', tarih)
            ]
        
        return self.search(domain, order='sequence')
    
    @api.model
    def check_availability(self, date, district_id=None):
        """Belirli bir tarih için teslimat günü müsaitlik kontrolü"""
        if not date:
            return {'available': False, 'reason': 'Tarih belirtilmedi'}
        
        # Haftanın gününü belirle (0=Pazartesi, 1=Salı, vs.)
        day_mapping = {
            0: 'pazartesi',
            1: 'sali', 
            2: 'carsamba',
            3: 'persembe',
            4: 'cuma',
            5: 'cumartesi',
            6: 'pazar'
        }
        
        day_of_week = day_mapping.get(date.weekday())
        if not day_of_week:
            return {'available': False, 'reason': 'Geçersiz gün'}
        
        # Günü bul
        day = self.search([('gun_kodu', '=', day_of_week)], limit=1)
        if not day:
            return {'available': False, 'reason': f'{day_of_week.capitalize()} günü bulunamadı'}
        
        # 1. Gün aktif mi?
        if not day.aktif:
            return {'available': False, 'reason': f'{day.name} günü aktif değil'}
        
        # 2. Geçici kapatılmış mı?
        if day.gecici_kapatma:
            return {'available': False, 'reason': f'{day.name} günü geçici olarak kapatılmış'}
        
        # 3. Kapatma tarihleri geçerli mi?
        if day.kapatma_baslangic and day.kapatma_bitis:
            if day.kapatma_baslangic <= date <= day.kapatma_bitis:
                return {'available': False, 'reason': f'{day.name} günü {day.kapatma_baslangic.strftime("%d/%m/%Y")} - {day.kapatma_bitis.strftime("%d/%m/%Y")} tarihleri arasında kapatılmış'}
        
        # 4. İlçe o gün için tanımlı mı? (Kod ile kontrol)
        if district_id:
            # İlçe adını al
            ilce = self.env['teslimat.ilce'].browse(district_id)
            if not ilce:
                return {'available': False, 'reason': 'İlçe bulunamadı'}
            
            ilce_adi = ilce.name
            
            # Kod ile ilçe-gün eşleşmelerini tanımla
            ilce_gun_eslesmeleri = {
                # ANADOLU YAKASI
                'Maltepe': ['pazartesi', 'perşembe'],
                'Kartal': ['pazartesi', 'perşembe'],
                'Pendik': ['pazartesi', 'perşembe'],
                'Tuzla': ['pazartesi', 'perşembe'],
                'Üsküdar': ['sali', 'carsamba', 'cuma'],
                'Kadıköy': ['sali', 'carsamba', 'cuma'],
                'Ümraniye': ['sali', 'carsamba', 'cuma'],
                'Ataşehir': ['sali', 'carsamba', 'cuma'],
                'Beykoz': ['cumartesi'],
                'Çekmeköy': ['cumartesi'],
                'Sancaktepe': ['cumartesi'],
                'Sultanbeyli': ['cumartesi'],
                'Şile': ['cumartesi'],
                
                # AVRUPA YAKASI
                'Şişli': ['pazartesi', 'cuma'],
                'Beşiktaş': ['pazartesi', 'cuma'],
                'Beyoğlu': ['pazartesi', 'cuma'],
                'Kağıthane': ['pazartesi', 'cuma'],
                'Sarıyer': ['sali'],
                'Eyüpsultan': ['sali'],
                'Sultangazi': ['sali'],
                'Gaziosmanpaşa': ['sali'],
                'Bağcılar': ['carsamba'],
                'Bahçelievler': ['carsamba'],
                'Bakırköy': ['carsamba', 'perşembe', 'cumartesi'],
                'Güngören': ['carsamba'],
                'Esenler': ['carsamba'],
                'Zeytinburnu': ['carsamba'],
                'Bayrampaşa': ['carsamba'],
                'Fatih': ['carsamba'],
                'Büyükçekmece': ['perşembe', 'cumartesi'],
                'Silivri': ['perşembe', 'cumartesi'],
                'Çatalca': ['perşembe', 'cumartesi'],
                'Arnavutköy': ['perşembe', 'cumartesi']
            }
            
            # İlçe için uygun günleri kontrol et
            uygun_gun_kodlari = ilce_gun_eslesmeleri.get(ilce_adi, [])
            
            if day_of_week not in uygun_gun_kodlari:
                return {'available': False, 'reason': f'Seçilen ilçeye {day.name} günü teslimat yapılamaz'}
        
        # 5. Genel kapasite kontrolü
        if day.mevcut_teslimat_sayisi >= day.gunluk_maksimum_teslimat:
            return {'available': False, 'reason': f'Günlük genel kapasite dolu ({day.mevcut_teslimat_sayisi}/{day.gunluk_maksimum_teslimat})'}
        
        # Tüm kontroller geçildi - müsait
        return {
            'available': True, 
            'reason': 'Müsait',
            'day_id': day.id,
            'day_name': day.name,
            'remaining_capacity': day.kalan_teslimat_kapasitesi,
            'district_capacity': ilce_gun_eslesmesi.kalan_kapasite if district_id and 'ilce_gun_eslesmesi' in locals() else None
        }
    
    @api.model
    def get_available_dates(self, start_date, end_date, district_id=None, max_days=7):
        """Belirli tarih aralığında müsait günleri getir"""
        if not start_date or not end_date:
            return []
        
        available_dates = []
        current_date = start_date
        
        while current_date <= end_date and len(available_dates) < max_days:
            availability = self.check_availability(current_date, district_id)
            
            if availability['available']:
                available_dates.append({
                    'date': current_date,
                    'day_name': availability['day_name'],
                    'remaining_capacity': availability['remaining_capacity'],
                    'district_capacity': availability['district_capacity']
                })
            
            current_date += timedelta(days=1)
        
        return available_dates
    
    @api.model
    def get_next_available_date(self, district_id=None, start_date=None):
        """Bir sonraki müsait teslimat tarihini getir"""
        if not start_date:
            start_date = fields.Date.today()
        
        # 30 gün ileriye kadar kontrol et
        end_date = start_date + timedelta(days=30)
        available_dates = self.get_available_dates(start_date, end_date, district_id, max_days=1)
        
        if available_dates:
            return available_dates[0]
        
        return None


class TeslimatGunIlce(models.Model):
    _name = 'teslimat.gun.ilce'
    _description = 'Teslimat Gün-İlçe Eşleşmesi'
    _unique = ('gun_id', 'ilce_id', 'tarih')

    gun_id = fields.Many2one('teslimat.gun', string='Gün', required=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=True)
    tarih = fields.Date(string='Tarih', required=True, default=fields.Date.today)
    
    # Kapasite Bilgileri
    maksimum_teslimat = fields.Integer(string='Maksimum Teslimat', default=10)
    teslimat_sayisi = fields.Integer(string='Teslimat Sayısı', default=0)
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kalan_kapasite', store=True)
    
    # Özel Durumlar
    ozel_durum = fields.Selection([
        ('normal', 'Normal'),
        ('yogun', 'Yoğun'),
        ('kapali', 'Kapalı'),
        ('ozel', 'Özel')
    ], string='Özel Durum', default='normal')
    
    notlar = fields.Text(string='Notlar')
    
    @api.depends('maksimum_teslimat', 'teslimat_sayisi')
    def _compute_kalan_kapasite(self):
        for record in self:
            record.kalan_kapasite = record.maksimum_teslimat - record.teslimat_sayisi
    
    @api.constrains('teslimat_sayisi', 'maksimum_teslimat')
    def _check_teslimat_kapasitesi(self):
        for record in self:
            if record.teslimat_sayisi > record.maksimum_teslimat:
                raise ValidationError(_('Teslimat sayısı maksimum kapasiteyi aşamaz.'))
