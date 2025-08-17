from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TeslimatProgramKurulum(models.Model):
    _name = 'teslimat.program.kurulum'
    _description = 'Teslimat Programı Kurulum Sistemi'

    name = fields.Char(string='Kurulum Adı', default='Teslimat Programı Kurulumu')
    durum = fields.Selection([
        ('kurulmadi', 'Kurulmadı'),
        ('kuruluyor', 'Kuruluyor'),
        ('tamamlandi', 'Tamamlandı'),
        ('hata', 'Hata')
    ], string='Durum', default='kurulmadi')
    
    kurulum_tarihi = fields.Datetime(string='Kurulum Tarihi')
    hata_mesaji = fields.Text(string='Hata Mesajı')
    
    def action_teslimat_programini_kur(self):
        """Teslimat programını otomatik kur"""
        self.ensure_one()
        self.write({'durum': 'kuruluyor'})
        
        try:
            # 1. Günleri oluştur
            self._gunleri_olustur()
            
            # 2. İlçeleri oluştur
            self._ilceleri_olustur()
            
            # 3. Teslimat programını oluştur
            self._teslimat_programini_olustur()
            
            # 4. Araçları oluştur
            self._araclari_olustur()
            
            self.write({
                'durum': 'tamamlandi',
                'kurulum_tarihi': fields.Datetime.now()
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Başarılı'),
                    'message': _('Teslimat programı başarıyla kuruldu!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            self.write({
                'durum': 'hata',
                'hata_mesaji': str(e)
            })
            raise ValidationError(_(f'Kurulum sırasında hata oluştu: {str(e)}'))
    
    def _gunleri_olustur(self):
        """Haftanın 7 gününü oluştur"""
        gunler = [
            {'name': 'Pazartesi', 'gun_kodu': 'pazartesi', 'sequence': 1, 'yaka_tipi': 'her_ikisi'},
            {'name': 'Salı', 'gun_kodu': 'sali', 'sequence': 2, 'yaka_tipi': 'her_ikisi'},
            {'name': 'Çarşamba', 'gun_kodu': 'carsamba', 'sequence': 3, 'yaka_tipi': 'her_ikisi'},
            {'name': 'Perşembe', 'gun_kodu': 'persembe', 'sequence': 4, 'yaka_tipi': 'her_ikisi'},
            {'name': 'Cuma', 'gun_kodu': 'cuma', 'sequence': 5, 'yaka_tipi': 'her_ikisi'},
            {'name': 'Cumartesi', 'gun_kodu': 'cumartesi', 'sequence': 6, 'yaka_tipi': 'her_ikisi'},
            {'name': 'Pazar', 'gun_kodu': 'pazar', 'sequence': 7, 'yaka_tipi': 'her_ikisi'}
        ]
        
        for gun_data in gunler:
            if not self.env['teslimat.gun'].search([('gun_kodu', '=', gun_data['gun_kodu'])]):
                self.env['teslimat.gun'].create(gun_data)
    
    def _ilceleri_olustur(self):
        """İstanbul ilçelerini oluştur"""
        self.env['teslimat.ilce'].create_istanbul_ilceleri()
    
    def _teslimat_programini_olustur(self):
        """Teslimat programını oluştur"""
        # Pazartesi (8 ilçe)
        self._gun_ilce_eslesmesi_olustur('pazartesi', [
            # Anadolu Yakası
            {'ilce': 'Maltepe', 'maksimum_teslimat': 15},
            {'ilce': 'Kartal', 'maksimum_teslimat': 20},
            {'ilce': 'Pendik', 'maksimum_teslimat': 18},
            {'ilce': 'Tuzla', 'maksimum_teslimat': 12},
            # Avrupa Yakası
            {'ilce': 'Beyoğlu', 'maksimum_teslimat': 25},
            {'ilce': 'Şişli', 'maksimum_teslimat': 20},
            {'ilce': 'Beşiktaş', 'maksimum_teslimat': 22},
            {'ilce': 'Kağıthane', 'maksimum_teslimat': 18}
        ])
        
        # Salı (10 ilçe)
        self._gun_ilce_eslesmesi_olustur('sali', [
            # Anadolu Yakası
            {'ilce': 'Üsküdar', 'maksimum_teslimat': 25},
            {'ilce': 'Kadıköy', 'maksimum_teslimat': 30},
            {'ilce': 'Ataşehir', 'maksimum_teslimat': 22},
            {'ilce': 'Ümraniye', 'maksimum_teslimat': 28},
            # Avrupa Yakası
            {'ilce': 'Sarıyer', 'maksimum_teslimat': 20},
            {'ilce': 'Bakırköy', 'maksimum_teslimat': 25},
            {'ilce': 'Bahçelievler', 'maksimum_teslimat': 22},
            {'ilce': 'Güngören', 'maksimum_teslimat': 18},
            {'ilce': 'Esenler', 'maksimum_teslimat': 20},
            {'ilce': 'Bağcılar', 'maksimum_teslimat': 25}
        ])
        
        # Çarşamba (8 ilçe)
        self._gun_ilce_eslesmesi_olustur('carsamba', [
            # Anadolu Yakası
            {'ilce': 'Üsküdar', 'maksimum_teslimat': 25},
            {'ilce': 'Kadıköy', 'maksimum_teslimat': 30},
            {'ilce': 'Ataşehir', 'maksimum_teslimat': 22},
            {'ilce': 'Ümraniye', 'maksimum_teslimat': 28},
            # Avrupa Yakası
            {'ilce': 'Beyoğlu', 'maksimum_teslimat': 25},
            {'ilce': 'Şişli', 'maksimum_teslimat': 20},
            {'ilce': 'Beşiktaş', 'maksimum_teslimat': 22},
            {'ilce': 'Kağıthane', 'maksimum_teslimat': 18}
        ])
        
        # Perşembe (11 ilçe)
        self._gun_ilce_eslesmesi_olustur('persembe', [
            # Anadolu Yakası
            {'ilce': 'Üsküdar', 'maksimum_teslimat': 25},
            {'ilce': 'Kadıköy', 'maksimum_teslimat': 30},
            {'ilce': 'Ataşehir', 'maksimum_teslimat': 22},
            {'ilce': 'Ümraniye', 'maksimum_teslimat': 28},
            # Avrupa Yakası
            {'ilce': 'Eyüpsultan', 'maksimum_teslimat': 20},
            {'ilce': 'Gaziosmanpaşa', 'maksimum_teslimat': 22},
            {'ilce': 'Küçükçekmece', 'maksimum_teslimat': 25},
            {'ilce': 'Avcılar', 'maksimum_teslimat': 18},
            {'ilce': 'Başakşehir', 'maksimum_teslimat': 20},
            {'ilce': 'Sultangazi', 'maksimum_teslimat': 18},
            {'ilce': 'Arnavutköy', 'maksimum_teslimat': 15}
        ])
        
        # Cuma (6 ilçe)
        self._gun_ilce_eslesmesi_olustur('cuma', [
            # Anadolu Yakası
            {'ilce': 'Maltepe', 'maksimum_teslimat': 15},
            {'ilce': 'Kartal', 'maksimum_teslimat': 20},
            {'ilce': 'Pendik', 'maksimum_teslimat': 18},
            # Avrupa Yakası
            {'ilce': 'Fatih', 'maksimum_teslimat': 30},
            {'ilce': 'Zeytinburnu', 'maksimum_teslimat': 20},
            {'ilce': 'Bayrampaşa', 'maksimum_teslimat': 18}
        ])
        
        # Cumartesi (9 ilçe)
        self._gun_ilce_eslesmesi_olustur('cumartesi', [
            # Anadolu Yakası
            {'ilce': 'Sancaktepe', 'maksimum_teslimat': 15},
            {'ilce': 'Çekmeköy', 'maksimum_teslimat': 18},
            {'ilce': 'Beykoz', 'maksimum_teslimat': 12},
            {'ilce': 'Şile', 'maksimum_teslimat': 8},
            {'ilce': 'Sultanbeyli', 'maksimum_teslimat': 15},
            # Avrupa Yakası
            {'ilce': 'Esenyurt', 'maksimum_teslimat': 25},
            {'ilce': 'Beylikdüzü', 'maksimum_teslimat': 20},
            {'ilce': 'Silivri', 'maksimum_teslimat': 15},
            {'ilce': 'Çatalca', 'maksimum_teslimat': 10}
        ])
        
        # Pazar: Teslimat yapılmaz (otomatik olarak oluşturulmaz)
    
    def _gun_ilce_eslesmesi_olustur(self, gun_kodu, ilce_listesi):
        """Belirli gün için ilçe eşleşmelerini oluştur"""
        gun = self.env['teslimat.gun'].search([('gun_kodu', '=', gun_kodu)], limit=1)
        if not gun:
            return
        
        for ilce_data in ilce_listesi:
            ilce = self.env['teslimat.ilce'].search([('name', '=', ilce_data['ilce'])], limit=1)
            if ilce:
                # Mevcut eşleşme var mı kontrol et
                mevcut = self.env['teslimat.gun.ilce'].search([
                    ('gun_id', '=', gun.id),
                    ('ilce_id', '=', ilce.id)
                ])
                
                if not mevcut:
                    self.env['teslimat.gun.ilce'].create({
                        'gun_id': gun.id,
                        'ilce_id': ilce.id,
                        'maksimum_teslimat': ilce_data['maksimum_teslimat'],
                        'ozel_durum': 'normal'
                    })
    
    def _araclari_olustur(self):
        """Varsayılan araçları oluştur"""
        araclar = [
            {
                'name': 'Anadolu Yakası Araç 1',
                'arac_tipi': 'anadolu_yakasi',
                'gunluk_teslimat_limiti': 7
            },
            {
                'name': 'Anadolu Yakası Araç 2',
                'arac_tipi': 'anadolu_yakasi',
                'gunluk_teslimat_limiti': 7
            },
            {
                'name': 'Avrupa Yakası Araç 1',
                'arac_tipi': 'avrupa_yakasi',
                'gunluk_teslimat_limiti': 7
            },
            {
                'name': 'Avrupa Yakası Araç 2',
                'arac_tipi': 'avrupa_yakasi',
                'gunluk_teslimat_limiti': 7
            },
            {
                'name': 'Küçük Araç 1',
                'arac_tipi': 'kucuk_arac_1',
                'gunluk_teslimat_limiti': 7
            },
            {
                'name': 'Küçük Araç 2',
                'arac_tipi': 'kucuk_arac_2',
                'gunluk_teslimat_limiti': 7
            },
            {
                'name': 'Ek Araç',
                'arac_tipi': 'ek_arac',
                'gunluk_teslimat_limiti': 7
            }
        ]
        
        for arac_data in araclar:
            if not self.env['teslimat.arac'].search([('name', '=', arac_data['name'])]):
                arac = self.env['teslimat.arac'].create(arac_data)
                
                # Araç tipine göre uygun ilçeleri ata
                if 'anadolu' in arac_data['arac_tipi']:
                    anadolu_ilceleri = self.env['teslimat.ilce'].search([('yaka_tipi', '=', 'anadolu')])
                    arac.uygun_ilceler = [(6, 0, anadolu_ilceleri.ids)]
                elif 'avrupa' in arac_data['arac_tipi']:
                    avrupa_ilceleri = self.env['teslimat.ilce'].search([('yaka_tipi', '=', 'avrupa')])
                    arac.uygun_ilceler = [(6, 0, avrupa_ilceleri.ids)]
                else:
                    # Küçük araçlar ve ek araç tüm ilçelere gidebilir
                    tum_ilceler = self.env['teslimat.ilce'].search([])
                    arac.uygun_ilceler = [(6, 0, tum_ilceler.ids)]
