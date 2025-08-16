from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
        """Belirli ilçe için uygun günleri getir"""
        domain = [
            ('aktif', '=', True),
            ('gecici_kapatma', '=', False),
            ('ilce_ids.ilce_id', '=', ilce_id)
        ]
        
        if tarih:
            domain += [
                '|',
                ('kapatma_bitis', '=', False),
                ('kapatma_bitis', '<', tarih)
            ]
        
        return self.search(domain, order='sequence')


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
