from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class TeslimatPlanlamaAkilli(models.Model):
    _name = 'teslimat.planlama.akilli'
    _description = 'Akıllı Teslimat Planlama ve Kontrol Sistemi'
    _order = 'create_date desc'

    name = fields.Char(string='Planlama Adı', required=True)
    planlama_tarihi = fields.Date(string='Planlama Tarihi', required=True, default=fields.Date.today)
    
    # Planlama Durumu
    durum = fields.Selection([
        ('taslak', 'Taslak'),
        ('hazirlaniyor', 'Hazırlanıyor'),
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal')
    ], string='Durum', default='taslak', required=True)
    
    # Otomatik Kontrol Sonuçları
    ilce_gun_uygunluk_kontrol = fields.Boolean(string='İlçe-Gün Uygunluk Kontrolü', default=False)
    arac_kapasite_kontrol = fields.Boolean(string='Araç Kapasite Kontrolü', default=False)
    cakisma_kontrol = fields.Boolean(string='Çakışma Kontrolü', default=False)
    
    # Planlama Detayları
    toplam_teslimat = fields.Integer(string='Toplam Teslimat', compute='_compute_toplamlar', store=True)
    basarili_teslimat = fields.Integer(string='Başarılı Teslimat', compute='_compute_toplamlar', store=True)
    hatali_teslimat = fields.Integer(string='Hatalı Teslimat', compute='_compute_toplamlar', store=True)
    
    # İlişkiler
    teslimat_ids = fields.One2many('teslimat.belgesi', 'planlama_akilli_id', string='Teslimatlar')
    
    # Notlar
    notlar = fields.Text(string='Planlama Notları')
    
    @api.depends('teslimat_ids', 'teslimat_ids.durum')
    def _compute_toplamlar(self):
        for record in self:
            record.toplam_teslimat = len(record.teslimat_ids)
            record.basarili_teslimat = len(record.teslimat_ids.filtered(lambda t: t.durum in ['hazir', 'yolda', 'teslim_edildi']))
            record.hatali_teslimat = len(record.teslimat_ids.filtered(lambda t: t.durum == 'iptal'))
    
    def action_otomatik_kontrol(self):
        """Tüm teslimatlar için otomatik kontrol yap"""
        self.ensure_one()
        
        teslimatlar = self.env['teslimat.belgesi'].search([
            ('teslimat_tarihi', '=', self.planlama_tarihi)
        ])
        
        kontrol_sonuclari = {
            'ilce_gun_uygunluk': 0,
            'arac_kapasite': 0,
            'cakisma': 0,
            'hatalar': []
        }
        
        for teslimat in teslimatlar:
            # 1. İlçe-gün uygunluğu kontrolü
            if teslimat.ilce_id and teslimat.teslimat_tarihi:
                availability = self.env['teslimat.gun'].check_availability(
                    teslimat.teslimat_tarihi, 
                    teslimat.ilce_id.id
                )
                
                if not availability['available']:
                    kontrol_sonuclari['ilce_gun_uygunluk'] += 1
                    kontrol_sonuclari['hatalar'].append(f"Teslimat {teslimat.name}: {availability['reason']}")
            
            # 2. Araç kapasitesi kontrolü
            if teslimat.arac_id and teslimat.teslimat_tarihi:
                gunluk_teslimat = self.env['teslimat.belgesi'].search_count([
                    ('arac_id', '=', teslimat.arac_id.id),
                    ('teslimat_tarihi', '=', teslimat.teslimat_tarihi),
                    ('durum', 'in', ['hazir', 'yolda']),
                    ('id', '!=', teslimat.id)
                ])
                
                if gunluk_teslimat >= teslimat.arac_id.gunluk_teslimat_limiti:
                    kontrol_sonuclari['arac_kapasite'] += 1
                    kontrol_sonuclari['hatalar'].append(f"Teslimat {teslimat.name}: Araç kapasitesi dolu")
            
            # 3. Çakışma kontrolü
            cakisan_teslimat = self.env['teslimat.belgesi'].search([
                ('arac_id', '=', teslimat.arac_id.id),
                ('teslimat_tarihi', '=', teslimat.teslimat_tarihi),
                ('id', '!=', teslimat.id),
                ('durum', 'in', ['hazir', 'yolda'])
            ])
            
            if cakisan_teslimat:
                kontrol_sonuclari['cakisma'] += 1
                kontrol_sonuclari['hatalar'].append(f"Teslimat {teslimat.name}: Araç çakışması")
        
        # Kontrol sonuçlarını güncelle
        self.write({
            'ilce_gun_uygunluk_kontrol': kontrol_sonuclari['ilce_gun_uygunluk'] > 0,
            'arac_kapasite_kontrol': kontrol_sonuclari['arac_kapasite'] > 0,
            'cakisma_kontrol': kontrol_sonuclari['cakisma'] > 0
        })
        
        # Sonuçları göster
        if kontrol_sonuclari['hatalar']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Kontrol Tamamlandı'),
                    'message': f"Kontrol tamamlandı!\n\nHatalar:\n" + "\n".join(kontrol_sonuclari['hatalar'][:5]),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Kontrol Tamamlandı'),
                    'message': 'Tüm kontroller başarılı! Hiç hata bulunamadı.',
                    'type': 'success',
                    'sticky': False,
                }
            }
    
    def action_yaka_bazli_optimizasyon(self):
        """Yaka bazlı rota optimizasyonu yap"""
        self.ensure_one()
        
        # Anadolu ve Avrupa yakası için ayrı planlama
        anadolu_teslimatlar = self.env['teslimat.belgesi'].search([
            ('teslimat_tarihi', '=', self.planlama_tarihi),
            ('ilce_id.yaka_tipi', '=', 'anadolu')
        ])
        
        avrupa_teslimatlar = self.env['teslimat.belgesi'].search([
            ('teslimat_tarihi', '=', self.planlama_tarihi),
            ('ilce_id.yaka_tipi', '=', 'avrupa')
        ])
        
        # Yaka bazlı araç ataması
        anadolu_araclar = self.env['teslimat.arac'].search([
            ('arac_tipi', 'in', ['anadolu_yakasi', 'kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']),
            ('aktif', '=', True),
            ('gecici_kapatma', '=', False)
        ])
        
        avrupa_araclar = self.env['teslimat.arac'].search([
            ('arac_tipi', 'in', ['avrupa_yakasi', 'kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']),
            ('aktif', '=', True),
            ('gecici_kapatma', '=', False)
        ])
        
        # Optimizasyon sonuçlarını kaydet
        self.notlar = f"""
        Yaka Bazlı Optimizasyon Sonuçları:
        
        Anadolu Yakası:
        - Teslimat Sayısı: {len(anadolu_teslimatlar)}
        - Uygun Araç Sayısı: {len(anadolu_araclar)}
        
        Avrupa Yakası:
        - Teslimat Sayısı: {len(avrupa_teslimatlar)}
        - Uygun Araç Sayısı: {len(avrupa_araclar)}
        
        Optimizasyon Tarihi: {fields.Datetime.now()}
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Optimizasyon Tamamlandı'),
                'message': f'Yaka bazlı optimizasyon tamamlandı!\nAnadolu: {len(anadolu_teslimatlar)} teslimat\nAvrupa: {len(avrupa_teslimatlar)} teslimat',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_kapasite_bazli_dagitim(self):
        """Kapasite bazlı teslimat dağıtımı yap"""
        self.ensure_one()
        
        teslimatlar = self.env['teslimat.belgesi'].search([
            ('teslimat_tarihi', '=', self.planlama_tarihi),
            ('durum', '=', 'taslak')
        ])
        
        araclar = self.env['teslimat.arac'].search([
            ('aktif', '=', True),
            ('gecici_kapatma', '=', False)
        ])
        
        # Kapasite bazlı dağıtım
        dagitim_sonuclari = []
        
        for teslimat in teslimatlar:
            en_uygun_arac = None
            en_yuksek_kapasite = 0
            
            for arac in araclar:
                # Araç-İlçe uyumluluğu kontrolü
                if arac.arac_tipi in ['anadolu_yakasi', 'avrupa_yakasi']:
                    if arac.arac_tipi == 'anadolu_yakasi' and teslimat.ilce_id.yaka_tipi == 'avrupa':
                        continue
                    if arac.arac_tipi == 'avrupa_yakasi' and teslimat.ilce_id.yaka_tipi == 'anadolu':
                        continue
                
                # Kapasite kontrolü
                gunluk_teslimat = self.env['teslimat.belgesi'].search_count([
                    ('arac_id', '=', arac.id),
                    ('teslimat_tarihi', '=', teslimat.teslimat_tarihi),
                    ('durum', 'in', ['hazir', 'yolda'])
                ])
                
                kalan_kapasite = arac.gunluk_teslimat_limiti - gunluk_teslimat
                
                if kalan_kapasite > 0 and kalan_kapasite > en_yuksek_kapasite:
                    en_yuksek_kapasite = kalan_kapasite
                    en_uygun_arac = arac
            
            if en_uygun_arac:
                teslimat.write({'arac_id': en_uygun_arac.id})
                dagitim_sonuclari.append(f"Teslimat {teslimat.name} → {en_uygun_arac.name}")
            else:
                dagitim_sonuclari.append(f"Teslimat {teslimat.name} → Uygun araç bulunamadı!")
        
        # Sonuçları kaydet
        self.notlar += f"\n\nKapasite Bazlı Dağıtım Sonuçları:\n" + "\n".join(dagitim_sonuclari)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dağıtım Tamamlandı'),
                'message': f'Kapasite bazlı dağıtım tamamlandı!\n{len(dagitim_sonuclari)} teslimat dağıtıldı.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_oncelik_sistemi(self):
        """Öncelik sistemi uygula"""
        self.ensure_one()
        
        teslimatlar = self.env['teslimat.belgesi'].search([
            ('teslimat_tarihi', '=', self.planlama_tarihi)
        ])
        
        # Öncelik belirleme (müşteri büyüklüğü, teslimat süresi, vb.)
        for teslimat in teslimatlar:
            oncelik_puani = 0
            
            # Müşteri büyüklüğü (customer_rank)
            if teslimat.musteri_id.customer_rank:
                oncelik_puani += teslimat.musteri_id.customer_rank * 10
            
            # Teslimat süresi (kısa süre = yüksek öncelik)
            if teslimat.ilce_id.teslimat_suresi:
                oncelik_puani += (10 - teslimat.ilce_id.teslimat_suresi) * 5
            
            # Özel durumlar
            if teslimat.ilce_id.ozel_durum == 'yogun':
                oncelik_puani += 20
            elif teslimat.ilce_id.ozel_durum == 'ozel':
                oncelik_puani += 30
            
            teslimat.write({'oncelik_puani': oncelik_puani})
        
        # Önceliğe göre sırala
        sirali_teslimatlar = teslimatlar.sorted('oncelik_puani', reverse=True)
        
        # Sıra numaralarını güncelle
        for index, teslimat in enumerate(sirali_teslimatlar, 1):
            teslimat.write({'sira_no': index})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Öncelik Sistemi'),
                'message': f'Öncelik sistemi uygulandı!\n{len(teslimatlar)} teslimat önceliğe göre sıralandı.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def get_gunluk_rapor(self, tarih=None):
        """Günlük teslimat raporu oluştur"""
        if not tarih:
            tarih = fields.Date.today()
        
        teslimatlar = self.env['teslimat.belgesi'].search([
            ('teslimat_tarihi', '=', tarih)
        ])
        
        # İlçe bazlı performans
        ilce_performans = {}
        for teslimat in teslimatlar:
            ilce_adi = teslimat.ilce_id.name
            if ilce_adi not in ilce_performans:
                ilce_performans[ilce_adi] = {
                    'toplam': 0,
                    'basarili': 0,
                    'iptal': 0,
                    'yaka_tipi': teslimat.ilce_id.yaka_tipi
                }
            
            ilce_performans[ilce_adi]['toplam'] += 1
            if teslimat.durum in ['hazir', 'yolda', 'teslim_edildi']:
                ilce_performans[ilce_adi]['basarili'] += 1
            elif teslimat.durum == 'iptal':
                ilce_performans[ilce_adi]['iptal'] += 1
        
        # Araç kullanım istatistikleri
        arac_istatistik = {}
        for teslimat in teslimatlar:
            arac_adi = teslimat.arac_id.name
            if arac_adi not in arac_istatistik:
                arac_istatistik[arac_adi] = {
                    'toplam': 0,
                    'kapasite': teslimat.arac_id.gunluk_teslimat_limiti,
                    'kullanım_orani': 0
                }
            
            arac_istatistik[arac_adi]['toplam'] += 1
        
        # Kullanım oranlarını hesapla
        for arac in arac_istatistik.values():
            if arac['kapasite'] > 0:
                arac['kullanım_orani'] = (arac['toplam'] / arac['kapasite']) * 100
        
        return {
            'tarih': tarih,
            'toplam_teslimat': len(teslimatlar),
            'basarili_teslimat': len(teslimatlar.filtered(lambda t: t.durum in ['hazir', 'yolda', 'teslim_edildi'])),
            'iptal_teslimat': len(teslimatlar.filtered(lambda t: t.durum == 'iptal')),
            'ilce_performans': ilce_performans,
            'arac_istatistik': arac_istatistik
        }
