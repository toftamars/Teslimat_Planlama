from odoo import models, fields, api
from datetime import datetime, timedelta


class TeslimatAnaSayfa(models.Model):
    _name = 'teslimat.ana.sayfa'
    _description = 'Teslimat Ana Sayfa - Kapasite Sorgulama'

    # Sorgulama Alanları
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=False, 
                              domain="[('aktif', '=', True), ('gecici_kapatma', '=', False)]")
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=False)
    
    # Sonuç Alanları (Hesaplanan)
    tarih_listesi = fields.One2many('teslimat.ana.sayfa.tarih', 'ana_sayfa_id', string='Uygun Tarihler', compute='_compute_tarih_listesi')
    uygun_arac_ids = fields.Many2many('teslimat.arac', string='Uygun Araçlar', compute='_compute_uygun_araclar')
    
    # İlçe Bazlı Kapasite
    toplam_kapasite = fields.Integer(string='Toplam Kapasite', compute='_compute_kapasite_bilgileri')
    kullanilan_kapasite = fields.Integer(string='Kullanılan Kapasite', compute='_compute_kapasite_bilgileri')
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kapasite_bilgileri')
    teslimat_sayisi = fields.Integer(string='Teslimat Sayısı', compute='_compute_kapasite_bilgileri')
    
    # Sorgu kontrolü: sadece buton ile sonuç üret
    sorgulandi = fields.Boolean(string='Sorgulandı mı?', default=False)

    @api.onchange('arac_id', 'ilce_id')
    def _onchange_reset_sorgu(self):
        for record in self:
            record.sorgulandi = False


    
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

    @api.depends('ilce_id', 'arac_id', 'sorgulandi')
    def _compute_tarih_listesi(self):
        """Seçilen ilçe ve araç için uygun tarihleri hesapla"""
        for record in self:
            if record.sorgulandi and record.ilce_id and record.arac_id and record.ilce_uygun_mu:
                # Sonraki 30 günü kontrol et
                bugun = fields.Date.today()
                tarihler = []
                
                for i in range(30):
                    tarih = bugun + timedelta(days=i)
                    gun_adi = tarih.strftime('%A')  # İngilizce gün adı
                    
                    # Türkçe gün adlarını eşleştir
                    gun_eslesmesi = {
                        'Monday': 'Pazartesi',
                        'Tuesday': 'Salı', 
                        'Wednesday': 'Çarşamba',
                        'Thursday': 'Perşembe',
                        'Friday': 'Cuma',
                        'Saturday': 'Cumartesi',
                        'Sunday': 'Pazar'
                    }
                    
                    gun_adi_tr = gun_eslesmesi.get(gun_adi, gun_adi)
                    
                    # İlçe-gün uygunluğunu kontrol et
                    ilce_uygun_mu = self._check_ilce_gun_uygunlugu(record.ilce_id, tarih)
                    
                    # Sadece uygun ve kapasitesi olan günleri ekle
                    if ilce_uygun_mu:
                        # Bu tarih için teslimat sayısını hesapla
                        teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                            ('teslimat_tarihi', '=', tarih),
                            ('arac_id', '=', record.arac_id.id),
                            ('durum', 'in', ['hazir', 'yolda', 'teslim_edildi'])
                        ])
                        
                        # Kapasite hesaplama
                        toplam_kapasite = record.arac_id.gunluk_teslimat_limiti
                        kalan_kapasite = toplam_kapasite - teslimat_sayisi
                        doluluk_orani = (teslimat_sayisi / toplam_kapasite * 100) if toplam_kapasite > 0 else 0
                        # Kapasitesi dolu günleri listelemeyelim
                        if kalan_kapasite <= 0:
                            continue
                        
                        # Durum belirleme
                        if kalan_kapasite <= 0:
                            durum = 'dolu'
                            durum_icon = '🔴'
                            durum_text = 'DOLU'
                        elif doluluk_orani >= 80:
                            durum = 'dolu_yakin'
                            durum_icon = '🟡'
                            durum_text = 'DOLU YAKIN'
                        else:
                            durum = 'musait'
                            durum_icon = '🟢'
                            durum_text = 'MUSAİT'
                        
                        tarihler.append({
                            'tarih': tarih,
                            'gun_adi': gun_adi_tr,
                            'teslimat_sayisi': teslimat_sayisi,
                            'toplam_kapasite': toplam_kapasite,
                            'kalan_kapasite': kalan_kapasite,
                            'doluluk_orani': doluluk_orani,
                            'durum': durum,
                            'durum_icon': durum_icon,
                            'durum_text': durum_text
                        })
                
                # Mevcut kayıtları temizle ve tüm satırları tek seferde ekle
                record.tarih_listesi = [(5, 0, 0)] + [(0, 0, t) for t in tarihler]
            else:
                record.tarih_listesi = [(5, 0, 0)]
    
    def _check_ilce_gun_uygunlugu(self, ilce, tarih):
        """İlçe ve tarih uygunluğunu kontrol et"""
        gun_adi = tarih.strftime('%A')
        
        # İlçe yaka tipine göre uygun günleri belirle
        if ilce.yaka_tipi == 'anadolu':
            # Anadolu Yakası ilçeleri için uygun günler
            uygun_gunler = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']  # Pazartesi-Cuma
        elif ilce.yaka_tipi == 'avrupa':
            # Avrupa Yakası ilçeleri için uygun günler
            uygun_gunler = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']  # Pazartesi-Cuma
        else:
            # Bilinmeyen yaka tipi için tüm günler
            uygun_gunler = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return gun_adi in uygun_gunler

    @api.depends('ilce_id', 'arac_id', 'sorgulandi')
    def _compute_uygun_araclar(self):
        """Seçilen ilçe ve araç için uygunluk kontrolü"""
        for record in self:
            if record.sorgulandi and record.ilce_uygun_mu and record.arac_id:
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

    @api.depends('ilce_id', 'arac_id', 'uygun_arac_ids', 'sorgulandi')
    def _compute_kapasite_bilgileri(self):
        """Kapasite bilgilerini hesapla"""
        for record in self:
            if record.sorgulandi and record.ilce_uygun_mu and record.arac_id:
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



    def action_sorgula(self):
        """Sorgula butonuna basıldığında çalışacak method"""
        self.ensure_one()
        
        if not self.arac_id or not self.ilce_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Uyarı',
                    'message': 'Lütfen önce araç ve ilçe seçin.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

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
        
        # Sadece buton ile sorgulama yap: bayrağı aç
        self.sorgulandi = True

        # Uygun tarihleri hesapla ve O2M'ye tek seferde yaz
        bugun = fields.Date.today()
        tarihler = []
        if self.ilce_uygun_mu:
            for i in range(30):
                tarih = bugun + timedelta(days=i)
                if not self._check_ilce_gun_uygunlugu(self.ilce_id, tarih):
                    continue

                # Bu tarih için mevcut teslimat sayısı
                teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                    ('teslimat_tarihi', '=', tarih),
                    ('arac_id', '=', self.arac_id.id),
                    ('durum', 'in', ['hazir', 'yolda', 'teslim_edildi'])
                ])

                toplam_kapasite = self.arac_id.gunluk_teslimat_limiti
                kalan_kapasite = max((toplam_kapasite - teslimat_sayisi), 0)
                doluluk_orani = (teslimat_sayisi / toplam_kapasite * 100) if toplam_kapasite > 0 else 0

                gun_eslesmesi = {
                    'Monday': 'Pazartesi', 'Tuesday': 'Salı', 'Wednesday': 'Çarşamba',
                    'Thursday': 'Perşembe', 'Friday': 'Cuma', 'Saturday': 'Cumartesi', 'Sunday': 'Pazar'
                }
                gun_adi_tr = gun_eslesmesi.get(tarih.strftime('%A'), tarih.strftime('%A'))

                # Kapasitesi dolu günleri listelemeyelim
                if kalan_kapasite <= 0:
                    continue
                elif doluluk_orani >= 80:
                    durum_icon, durum_text = '🟡', 'DOLU YAKIN'
                else:
                    durum_icon, durum_text = '🟢', 'MUSAİT'

                tarihler.append({
                    'tarih': tarih,
                    'gun_adi': gun_adi_tr,
                    'teslimat_sayisi': teslimat_sayisi,
                    'toplam_kapasite': toplam_kapasite,
                    'kalan_kapasite': kalan_kapasite,
                    'doluluk_orani': doluluk_orani,
                    'durum': 'musait' if durum_text == 'MUSAİT' else ('dolu' if durum_text == 'DOLU' else 'dolu_yakin'),
                    'durum_icon': durum_icon,
                    'durum_text': durum_text,
                })

        # Mevcutları temizle ve yeni kayıtları ekle
        self.tarih_listesi = [(5, 0, 0)] + [(0, 0, t) for t in tarihler]
        
        # Görünümü yenileyerek O2M listeyi anında göster
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    

