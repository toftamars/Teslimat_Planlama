from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TeslimatKapasiteOnay(models.Model):
    _name = 'teslimat.kapasite.onay'
    _description = 'Teslimat Kapasite Aşımı Onay Sistemi'
    _order = 'create_date desc'

    name = fields.Char(string='Onay No', required=True, copy=False, readonly=True, 
                      default=lambda self: _('Yeni'))
    
    # Teslimat Bilgileri
    teslimat_belgesi_id = fields.Many2one('teslimat.belgesi', string='Teslimat Belgesi', required=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç', related='teslimat_belgesi_id.arac_id', readonly=True)
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', related='teslimat_belgesi_id.teslimat_tarihi', readonly=True)
    
    # Kapasite Bilgileri
    mevcut_teslimat_sayisi = fields.Integer(string='Mevcut Teslimat Sayısı', readonly=True)
    gunluk_limit = fields.Integer(string='Günlük Limit', related='arac_id.gunluk_teslimat_limiti', readonly=True)
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kalan_kapasite', store=True)
    
    # Onay Bilgileri
    onay_durumu = fields.Selection([
        ('bekliyor', 'Onay Bekliyor'),
        ('onaylandi', 'Onaylandı'),
        ('reddedildi', 'Reddedildi'),
        ('iptal', 'İptal')
    ], string='Onay Durumu', default='bekliyor', required=True)
    
    onaylayan_id = fields.Many2one('res.users', string='Onaylayan', readonly=True)
    onay_tarihi = fields.Datetime(string='Onay Tarihi', readonly=True)
    onay_notu = fields.Text(string='Onay Notu')
    
    red_notu = fields.Text(string='Red Notu')
    red_tarihi = fields.Datetime(string='Red Tarihi', readonly=True)
    red_eden_id = fields.Many2one('res.users', string='Red Eden', readonly=True)
    
    # Sistem Bilgileri
    olusturan_id = fields.Many2one('res.users', string='Oluşturan', default=lambda self: self.env.user, readonly=True)
    olusturma_tarihi = fields.Datetime(string='Oluşturma Tarihi', default=fields.Datetime.now, readonly=True)
    
    @api.depends('mevcut_teslimat_sayisi', 'gunluk_limit')
    def _compute_kalan_kapasite(self):
        for record in self:
            record.kalan_kapasite = record.gunluk_limit - record.mevcut_teslimat_sayisi
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Yeni')) == _('Yeni'):
            vals['name'] = self.env['ir.sequence'].next_by_code('teslimat.kapasite.onay') or _('Yeni')
        
        # Mevcut teslimat sayısını hesapla
        if vals.get('teslimat_belgesi_id'):
            teslimat = self.env['teslimat.belgesi'].browse(vals['teslimat_belgesi_id'])
            if teslimat.arac_id and teslimat.teslimat_tarihi:
                mevcut_teslimat = self.env['teslimat.belgesi'].search_count([
                    ('arac_id', '=', teslimat.arac_id.id),
                    ('teslimat_tarihi', '=', teslimat.teslimat_tarihi),
                    ('durum', 'in', ['hazir', 'yolda']),
                    ('id', '!=', teslimat.id)
                ])
                vals['mevcut_teslimat_sayisi'] = mevcut_teslimat
        
        return super(TeslimatKapasiteOnay, self).create(vals)
    
    def action_onayla(self):
        """Kapasite aşımını onayla"""
        self.ensure_one()
        
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise ValidationError(_('Sadece teslimat yöneticileri onay verebilir!'))
        
        self.write({
            'onay_durumu': 'onaylandi',
            'onaylayan_id': self.env.user.id,
            'onay_tarihi': fields.Datetime.now()
        })
        
        # Teslimat belgesini aktif et
        if self.teslimat_belgesi_id:
            self.teslimat_belgesi_id.write({'durum': 'hazir'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Onaylandı'),
                'message': _('Kapasite aşımı onaylandı. Teslimat oluşturuldu.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reddet(self):
        """Kapasite aşımını reddet"""
        self.ensure_one()
        
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise ValidationError(_('Sadece teslimat yöneticileri reddedebilir!'))
        
        if not self.red_notu:
            raise ValidationError(_('Red notu zorunludur!'))
        
        self.write({
            'onay_durumu': 'reddedildi',
            'red_eden_id': self.env.user.id,
            'red_tarihi': fields.Datetime.now()
        })
        
        # Teslimat belgesini iptal et
        if self.teslimat_belgesi_id:
            self.teslimat_belgesi_id.write({'durum': 'iptal'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reddedildi'),
                'message': _('Kapasite aşımı reddedildi. Teslimat iptal edildi.'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_iptal(self):
        """Onay talebini iptal et"""
        self.ensure_one()
        
        if self.onay_durumu != 'bekliyor':
            raise ValidationError(_('Sadece bekleyen onaylar iptal edilebilir!'))
        
        self.write({'onay_durumu': 'iptal'})
        
        # Teslimat belgesini iptal et
        if self.teslimat_belgesi_id:
            self.teslimat_belgesi_id.write({'durum': 'iptal'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('İptal Edildi'),
                'message': _('Onay talebi iptal edildi.'),
                'type': 'info',
                'sticky': False,
            }
        }
    
    @api.model
    def create_kapasite_onay_talebi(self, teslimat_belgesi):
        """Kapasite aşımı için otomatik onay talebi oluştur"""
        # Mevcut onay talebi var mı kontrol et
        mevcut_onay = self.search([
            ('teslimat_belgesi_id', '=', teslimat_belgesi.id),
            ('onay_durumu', '=', 'bekliyor')
        ], limit=1)
        
        if mevcut_onay:
            return mevcut_onay
        
        # Yeni onay talebi oluştur
        onay_talebi = self.create({
            'teslimat_belgesi_id': teslimat_belgesi.id
        })
        
        return onay_talebi
    
    @api.model
    def get_bekleyen_onaylar(self):
        """Bekleyen onay taleplerini getir"""
        return self.search([
            ('onay_durumu', '=', 'bekliyor')
        ], order='create_date asc')
    
    @api.model
    def get_onay_istatistikleri(self):
        """Onay istatistiklerini getir"""
        return {
            'bekleyen': self.search_count([('onay_durumu', '=', 'bekliyor')]),
            'onaylanan': self.search_count([('onay_durumu', '=', 'onaylandi')]),
            'reddedilen': self.search_count([('onay_durumu', '=', 'reddedildi')]),
            'iptal_edilen': self.search_count([('onay_durumu', '=', 'iptal')])
        }
