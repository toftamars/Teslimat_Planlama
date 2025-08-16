from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TeslimatArac(models.Model):
    _name = 'teslimat.arac'
    _description = 'Teslimat Araç Yönetimi'
    _order = 'name'

    name = fields.Char(string='Araç Adı', required=True)
    arac_tipi = fields.Selection([
        ('anadolu_yakasi', 'Anadolu Yakası'),
        ('avrupa_yakasi', 'Avrupa Yakası'),
        ('kucuk_arac_1', 'Küçük Araç 1'),
        ('kucuk_arac_2', 'Küçük Araç 2'),
        ('ek_arac', 'Ek Araç')
    ], string='Araç Tipi', required=True)
    
    # Kapasite Bilgileri
    gunluk_teslimat_limiti = fields.Integer(string='Günlük Teslimat Limiti', default=7)
    mevcut_kapasite = fields.Integer(string='Mevcut Kapasite', compute='_compute_mevcut_kapasite', store=True)
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kalan_kapasite', store=True)
    
    # Durum Bilgileri
    aktif = fields.Boolean(string='Aktif', default=True)
    gecici_kapatma = fields.Boolean(string='Geçici Kapatma')
    kapatma_sebebi = fields.Text(string='Kapatma Sebebi')
    kapatma_baslangic = fields.Datetime(string='Kapatma Başlangıç')
    kapatma_bitis = fields.Datetime(string='Kapatma Bitiş')
    
    # İlçe Uyumluluğu
    uygun_ilceler = fields.Many2many('teslimat.ilce', string='Uygun İlçeler')
    
    # Teslimat Geçmişi
    teslimat_ids = fields.One2many('teslimat.belgesi', 'arac_id', string='Teslimatlar')
    
    @api.depends('teslimat_ids', 'teslimat_ids.durum')
    def _compute_mevcut_kapasite(self):
        for record in self:
            bugun = fields.Date.today()
            bugun_teslimatlar = record.teslimat_ids.filtered(
                lambda t: t.teslimat_tarihi == bugun and t.durum in ['hazir', 'yolda']
            )
            record.mevcut_kapasite = len(bugun_teslimatlar)
    
    @api.depends('gunluk_teslimat_limiti', 'mevcut_kapasite')
    def _compute_kalan_kapasite(self):
        for record in self:
            record.kalan_kapasite = record.gunluk_teslimat_limiti - record.mevcut_kapasite
    
    @api.constrains('gunluk_teslimat_limiti')
    def _check_gunluk_limit(self):
        for record in self:
            if record.gunluk_teslimat_limiti <= 0:
                raise ValidationError(_('Günlük teslimat limiti 0\'dan büyük olmalıdır.'))
    
    def action_gecici_kapat(self):
        """Aracı geçici olarak kapat"""
        self.ensure_one()
        return {
            'name': _('Geçici Kapatma'),
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.arac.kapatma.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_arac_id': self.id}
        }
    
    def action_aktif_et(self):
        """Aracı aktif et"""
        self.ensure_one()
        self.write({
            'gecici_kapatma': False,
            'kapatma_sebebi': False,
            'kapatma_baslangic': False,
            'kapatma_bitis': False
        })
    
    def action_kapasite_ayarla(self):
        """Araç kapasitesini ayarla"""
        self.ensure_one()
        return {
            'name': _('Kapasite Ayarla'),
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.arac.kapasite.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_arac_id': self.id}
        }
    
    @api.model
    def get_uygun_araclar(self, ilce_id, tarih, teslimat_sayisi=1):
        """Belirli ilçe ve tarih için uygun araçları getir"""
        domain = [
            ('aktif', '=', True),
            ('gecici_kapatma', '=', False),
            ('uygun_ilceler', 'in', [ilce_id]),
            ('kalan_kapasite', '>=', teslimat_sayisi)
        ]
        
        # Kapatma tarihi kontrolü
        if tarih:
            domain += [
                '|',
                ('kapatma_bitis', '=', False),
                ('kapatma_bitis', '<', tarih)
            ]
        
        return self.search(domain, order='kalan_kapasite desc')
