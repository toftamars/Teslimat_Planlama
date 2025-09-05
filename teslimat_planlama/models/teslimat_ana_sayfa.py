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
    tarih_listesi = fields.One2many(
        'teslimat.ana.sayfa.tarih',
        'ana_sayfa_id',
        string=' ',
        compute='_compute_tarih_listesi',
        store=True,
        compute_sudo=True
    )
    uygun_arac_ids = fields.Many2many('teslimat.arac', string='Uygun Araçlar', compute='_compute_uygun_araclar')
    arac_kucuk_mu = fields.Boolean(string='Küçük Araç mı?', compute='_compute_arac_kucuk_mu')
    
    # İlçe Bazlı Kapasite
    toplam_kapasite = fields.Integer(string='Toplam Kapasite', compute='_compute_kapasite_bilgileri')
    kullanilan_kapasite = fields.Integer(string='Kullanılan Kapasite', compute='_compute_kapasite_bilgileri')
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kapasite_bilgileri')
    teslimat_sayisi = fields.Integer(string='Teslimat Sayısı', compute='_compute_kapasite_bilgileri')
    

    
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

    @api.depends('arac_id')
    def _compute_arac_kucuk_mu(self):
        for record in self:
            record.arac_kucuk_mu = bool(record.arac_id and record.arac_id.arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac'])

    @api.depends('ilce_id', 'arac_id')
    def _compute_ilce_uygunluk(self):
        """İlçe-arac uygunluğunu kontrol et"""
        for record in self:
            if record.arac_id and record.arac_id.arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']:
                record.ilce_uygun_mu = True
                record.uygunluk_mesaji = "✅ Küçük araç ile tüm ilçelere gün kısıtı olmadan teslimat yapılabilir"
            elif record.ilce_id and record.arac_id:
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

    @api.depends('ilce_id', 'arac_id', 'ilce_uygun_mu')
    def _compute_tarih_listesi(self):
        """Seçilen ilçe ve araç için uygun tarihleri hesapla"""
        for record in self:
            small_vehicle = bool(record.arac_id and record.arac_id.arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac'])
            if record.arac_id and (small_vehicle or (record.ilce_id and record.ilce_uygun_mu)):
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
                    
                    # İlçe-gün uygunluğunu kontrol et (küçük araçlar için kısıt yok)
                    ilce_uygun_mu = True if small_vehicle else self._check_ilce_gun_uygunlugu(record.ilce_id, tarih)
                    
                    # Sadece uygun günleri ekle
                    if ilce_uygun_mu:
                        # Bu tarih için teslimat sayısını hesapla
                        teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                            ('teslimat_tarihi', '=', tarih),
                            ('arac_id', '=', record.arac_id.id),
                            ('durum', 'in', ['hazir', 'yolda', 'teslim_edildi'])
                        ])
                        
                        # Debug: Teslimat sayısını kontrol et
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.info(f"TESLIMAT SAYISI DEBUG - Tarih: {tarih}, Araç: {record.arac_id.name}, Sayı: {teslimat_sayisi}")
                        
                        # Kapasite hesaplama
                        toplam_kapasite = record.arac_id.gunluk_teslimat_limiti
                        kalan_kapasite = toplam_kapasite - teslimat_sayisi
                        
                        # Doluluk oranı hesaplama - çok güvenli hesaplama
                        try:
                            # Güvenli değer dönüşümü
                            teslimat_float = float(teslimat_sayisi or 0)
                            kapasite_float = float(toplam_kapasite or 0)
                            
                            if kapasite_float > 0:
                                doluluk_orani = round((teslimat_float / kapasite_float) * 100, 2)
                                
                                # Maksimum %100 sınırı
                                if doluluk_orani > 100:
                                    doluluk_orani = 100.0
                            else:
                                doluluk_orani = 0.0
                        except (TypeError, ValueError, ZeroDivisionError) as e:
                            import logging
                            _logger = logging.getLogger(__name__)
                            _logger.error(f"DOLULUK ORANI HESAPLAMA HATASI: {str(e)}")
                            _logger.error(f"  teslimat_sayisi: {teslimat_sayisi} (type: {type(teslimat_sayisi)})")
                            _logger.error(f"  toplam_kapasite: {toplam_kapasite} (type: {type(toplam_kapasite)})")
                            doluluk_orani = 0.0
                        
                        # Debug log
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.info(f"KAPASITE HESAPLAMA - Araç: {record.arac_id.name}")
                        _logger.info(f"  Teslimat Sayısı: {teslimat_sayisi} (type: {type(teslimat_sayisi)})")
                        _logger.info(f"  Toplam Kapasite: {toplam_kapasite} (type: {type(toplam_kapasite)})")
                        _logger.info(f"  Float Teslimat: {teslimat_float}")
                        _logger.info(f"  Float Kapasite: {kapasite_float}")
                        _logger.info(f"  Hesaplama: ({teslimat_float} / {kapasite_float}) * 100 = {doluluk_orani}%")
                        
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
                
                commands = [(5, 0, 0)]
                for tarih_bilgi in tarihler:
                    commands.append((0, 0, tarih_bilgi))
                record.tarih_listesi = commands
            else:
                record.tarih_listesi = [(5, 0, 0)]
    
    def _check_ilce_gun_uygunlugu(self, ilce, tarih):
        """İlçe ve tarih uygunluğunu kontrol et.
        Öncelik: 1) Statik ilçe-gün haritası 2) Model eşleşmeleri 3) Varsayılan hafta içi
        """
        if not ilce or not tarih:
            return False
        # 0=Mon ... 6=Sun -> day_code
        day_mapping = {0: 'pazartesi', 1: 'sali', 2: 'carsamba', 3: 'persembe', 4: 'cuma', 5: 'cumartesi', 6: 'pazar'}
        day_code = day_mapping.get(tarih.weekday())

        # 1) Statik harita (kullanıcının verdiği liste)
        static_map = {
            # Anadolu
            'maltepe': {'pazartesi', 'cuma'},
            'kartal': {'pazartesi', 'cuma'},
            'pendik': {'pazartesi', 'cuma'},
            'tuzla': {'pazartesi'},
            'uskudar': {'sali', 'carsamba', 'persembe'}, 'üsküdar': {'sali', 'carsamba', 'persembe'},
            'kadikoy': {'sali', 'carsamba', 'persembe'}, 'kadıköy': {'sali', 'carsamba', 'persembe'},
            'atasehir': {'sali', 'carsamba', 'persembe'}, 'ataşehir': {'sali', 'carsamba', 'persembe'},
            'umraniye': {'sali', 'carsamba', 'persembe'}, 'ümraniye': {'sali', 'carsamba', 'persembe'},
            'sancaktepe': {'cumartesi'}, 'cekmekoy': {'cumartesi'}, 'çekmeköy': {'cumartesi'},
            'beykoz': {'cumartesi'}, 'sile': {'cumartesi'}, 'şile': {'cumartesi'}, 'sultanbeyli': {'cumartesi'},
            # Avrupa
            'beyoglu': {'pazartesi', 'carsamba'}, 'beyoğlu': {'pazartesi', 'carsamba'},
            'sisli': {'pazartesi', 'carsamba'}, 'şişli': {'pazartesi', 'carsamba'},
            'besiktas': {'pazartesi', 'carsamba'}, 'beşiktaş': {'pazartesi', 'carsamba'},
            'kagithane': {'pazartesi', 'carsamba'}, 'kağıthane': {'pazartesi', 'carsamba'},
            'sariyer': {'sali'}, 'sarıyer': {'sali'},
            'bakirkoy': {'sali'}, 'bakırköy': {'sali'},
            'bahcelievler': {'sali'}, 'bahçelievler': {'sali'},
            'gungoren': {'sali'}, 'güngören': {'sali'},
            'esenler': {'sali'},
            'bagcilar': {'sali'}, 'bağcılar': {'sali'},
            'eyupsultan': {'persembe'}, 'eyüpsultan': {'persembe'},
            'gaziosmanpasa': {'persembe'}, 'gaziosmanpaşa': {'persembe'},
            'kucukcekmece': {'persembe'}, 'küçükçekmece': {'persembe'},
            'avcilar': {'persembe'}, 'avcılar': {'persembe'},
            'basaksehir': {'persembe'}, 'başakşehir': {'persembe'},
            'sultangazi': {'persembe'}, 'arnavutkoy': {'persembe'}, 'arnavutköy': {'persembe'},
            'fatih': {'cuma'}, 'zeytinburnu': {'cuma'}, 'bayrampasa': {'cuma'}, 'bayrampaşa': {'cuma'},
            'esenyurt': {'cumartesi'}, 'beylikduzu': {'cumartesi'}, 'beylikdüzü': {'cumartesi'},
            'silivri': {'cumartesi'}, 'catalca': {'cumartesi'}, 'çatalca': {'cumartesi'},
        }
        key = (ilce.name or '').strip().lower()
        if key in static_map:
            return day_code in static_map[key]

        # 2) Model eşleşmeleri (varsa)
        Gun = self.env['teslimat.gun']
        IlceGun = self.env['teslimat.gun.ilce']
        day = Gun.search([('gun_kodu', '=', day_code), ('aktif', '=', True), ('gecici_kapatma', '=', False)], limit=1)
        if not day:
            return False
        has_any_mapping_for_ilce = bool(IlceGun.search_count([('ilce_id', '=', ilce.id)]))
        has_mapping_for_day = bool(IlceGun.search_count([('ilce_id', '=', ilce.id), ('gun_id', '=', day.id)]))
        if has_any_mapping_for_ilce:
            return has_mapping_for_day

        # 3) Varsayılan olarak hafta içi
        if ilce.yaka_tipi in ('anadolu', 'avrupa'):
            return day_code in {'pazartesi', 'sali', 'carsamba', 'persembe', 'cuma'}
        return False

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

    @api.depends('ilce_id', 'arac_id', 'uygun_arac_ids', 'ilce_uygun_mu')
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



    def action_sorgula(self):
        """Sorgula butonuna basıldığında çalışacak method"""
        self.ensure_one()

        # Kayıt henüz persist edilmemişse, önce kalıcı bir kayıt oluştur ve ona yönlendir
        if not self.id:
            new_rec = self.create({
                'arac_id': self.arac_id.id if self.arac_id else False,
                'ilce_id': self.ilce_id.id if self.ilce_id else False,
            })

            # Yeni kayıtta hesaplamaları çalıştır
            new_rec._compute_tarih_listesi()
            new_rec._compute_kapasite_bilgileri()

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'teslimat.ana.sayfa',
                'res_id': new_rec.id,
                'view_mode': 'form',
                'target': 'current',
                'name': 'Ana Sayfa',
            }

        # Geçerlilik kontrolleri
        if not self.arac_id or not (self.ilce_uygun_mu or self.arac_kucuk_mu):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Uyarı',
                    'message': self.uygunluk_mesaji or 'Lütfen önce araç ve ilçe seçin.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Mevcut kalıcı kayıtta hesaplamaları güncelle ve formu yeniden aç
        self._compute_tarih_listesi()
        self._compute_kapasite_bilgileri()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.ana.sayfa',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'name': 'Ana Sayfa',
        }
    
    def action_teslimat_olustur_from_tarih(self):
        """Tarih satırından teslimat oluştur"""
        # Context'ten active_id al (hangi tarih satırı tıklandı)
        active_id = self.env.context.get('active_id')
        if not active_id:
            return
            
        # Tarih kaydını bul
        tarih_record = self.env['teslimat.ana.sayfa.tarih'].browse(active_id)
        if not tarih_record.exists():
            return
            
        # Teslimat belgesi oluştur
        vals = {
            'teslimat_tarihi': tarih_record.tarih,
            'durum': 'taslak'
        }
        
        # Ana sayfa bilgilerini al
        if tarih_record.ana_sayfa_id:
            if tarih_record.ana_sayfa_id.arac_id:
                vals['arac_id'] = tarih_record.ana_sayfa_id.arac_id.id
            if tarih_record.ana_sayfa_id.ilce_id:
                vals['ilce_id'] = tarih_record.ana_sayfa_id.ilce_id.id
        
        # Debug log
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"TESLIMAT OLUŞTUR - Vals: {vals}")
        
        # Belgeyi oluştur
        teslimat_belgesi = self.env['teslimat.belgesi'].create(vals)
        
        # Form'u aç
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teslimat Belgesi',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat_belgesi.id,
            'view_mode': 'form',
            'target': 'current',
        }

