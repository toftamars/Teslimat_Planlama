# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class TeslimatBelgesiWizard(models.TransientModel):
    _name = 'teslimat.belgesi.wizard'
    _description = 'Teslimat Belgesi Oluşturma Sihirbazı'

    # Tarih ve Araç Bilgileri
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', required=True, readonly=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=True, readonly=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=True, readonly=True)
    
    # Kapasite Bilgileri
    gunluk_limit = fields.Integer(string='Günlük Limit', related='arac_id.gunluk_teslimat_limiti', readonly=True)
    mevcut_teslimat = fields.Integer(string='Mevcut Teslimat Sayısı', compute='_compute_mevcut_teslimat')
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', compute='_compute_kalan_kapasite')
    
    # Transfer Bilgileri
    transfer_id = fields.Many2one('stock.picking', string='Transfer Belgesi', 
                                domain="[('state','in',['waiting','confirmed','assigned','done'])]")
    transfer_no = fields.Char(string='Transfer No', help='Örnek: AKS/OUT/12345')
    
    # Müşteri ve Ürün Bilgileri
    musteri_id = fields.Many2one('res.partner', string='Müşteri', required=True)
    urun_id = fields.Many2one('product.product', string='Ürün', required=True)
    miktar = fields.Float(string='Miktar', default=1.0, required=True)
    birim = fields.Many2one('uom.uom', string='Birim', related='urun_id.uom_id', readonly=True)
    
    # Notlar
    notlar = fields.Text(string='Notlar')
    
    @api.depends('arac_id', 'teslimat_tarihi')
    def _compute_mevcut_teslimat(self):
        for wizard in self:
            if wizard.arac_id and wizard.teslimat_tarihi:
                teslimat_sayisi = self.env['teslimat.belgesi'].search_count([
                    ('arac_id', '=', wizard.arac_id.id),
                    ('teslimat_tarihi', '=', wizard.teslimat_tarihi),
                    ('durum', 'in', ['hazir', 'yolda'])
                ])
                wizard.mevcut_teslimat = teslimat_sayisi
            else:
                wizard.mevcut_teslimat = 0
    
    @api.depends('gunluk_limit', 'mevcut_teslimat')
    def _compute_kalan_kapasite(self):
        for wizard in self:
            wizard.kalan_kapasite = wizard.gunluk_limit - wizard.mevcut_teslimat
    
    @api.onchange('transfer_id')
    def _onchange_transfer_id(self):
        if self.transfer_id:
            self.transfer_no = self.transfer_id.name
            if self.transfer_id.partner_id:
                self.musteri_id = self.transfer_id.partner_id.id
            
            # İlk ürün hareketini al
            if self.transfer_id.move_ids_without_package:
                move = self.transfer_id.move_ids_without_package[0]
                self.urun_id = move.product_id.id
                self.miktar = move.product_uom_qty
    
    @api.onchange('transfer_no')
    def _onchange_transfer_no(self):
        if self.transfer_no and len(self.transfer_no) > 5:
            transfer = self.env['stock.picking'].search([
                ('name', '=', self.transfer_no),
                ('state', 'in', ['waiting', 'confirmed', 'assigned', 'done'])
            ], limit=1)
            
            if transfer:
                self.transfer_id = transfer.id
                self._onchange_transfer_id()
    
    def action_teslimat_olustur(self):
        self.ensure_one()
        
        # Kapasite kontrolü
        if self.kalan_kapasite <= 0:
            is_manager = self.env.user.has_group('stock.group_stock_manager')
            if not is_manager:
                raise UserError(_(f"Araç günlük kapasitesi dolu! (Limit: {self.gunluk_limit})"))
        
        # Mükerrer transfer kontrolü
        if self.transfer_id:
            existing = self.env['teslimat.belgesi'].search([
                ('stock_picking_id', '=', self.transfer_id.id)
            ], limit=1)
            if existing:
                raise UserError(_(f"Bu transfer için zaten bir teslimat belgesi mevcut: {existing.name}"))
        
        # Teslimat belgesi oluştur
        vals = {
            'teslimat_tarihi': self.teslimat_tarihi,
            'arac_id': self.arac_id.id,
            'ilce_id': self.ilce_id.id,
            'musteri_id': self.musteri_id.id,
            'urun_id': self.urun_id.id,
            'miktar': self.miktar,
            'durum': 'hazir',
            'notlar': self.notlar,
        }
        
        if self.transfer_id:
            vals.update({
                'stock_picking_id': self.transfer_id.id,
                'transfer_no': self.transfer_no,
            })
        
        teslimat = self.env['teslimat.belgesi'].create(vals)
        
        # Oluşturulan teslimat belgesini aç
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('Teslimat Belgesi')
        }
