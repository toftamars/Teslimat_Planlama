# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class TeslimatBelgesiWizard(models.TransientModel):
    _name = 'teslimat.belgesi.wizard'
    _description = 'Teslimat Belgesi Oluşturma Sihirbazı'

    # Temel bilgiler (context ile otomatik dolu gelir)
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', required=True, readonly=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=True, readonly=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=False, readonly=True)

    # Transfer No (stock.picking)
    transfer_id = fields.Many2one(
        'stock.picking',
        string='Transfer No',
        domain="[('state','in',['waiting','confirmed','assigned','done'])]",
        help='Transfer numarasına göre arayın (name)'
    )

    # Müşteri ve Adres (otomatik dolar)
    musteri_id = fields.Many2one('res.partner', string='Müşteri', readonly=True)
    adres = fields.Char(string='Adres', readonly=True)

    @api.onchange('transfer_id')
    def _onchange_transfer_id(self):
        picking = self.transfer_id
        if picking:
            if picking.partner_id:
                self.musteri_id = picking.partner_id.id
                # Adres metni
                try:
                    self.adres = picking.partner_id._display_address()
                except Exception:
                    parts = [picking.partner_id.street or '', picking.partner_id.city or '', picking.partner_id.zip or '']
                    self.adres = ', '.join([p for p in parts if p])

    def action_teslimat_olustur(self):
        self.ensure_one()

        # Mükerrer transfer kontrolü
        if self.transfer_id:
            existing = self.env['teslimat.belgesi'].search([
                ('stock_picking_id', '=', self.transfer_id.id)
            ], limit=1)
            if existing:
                raise UserError(_(f"Bu transfer için zaten bir teslimat belgesi mevcut: {existing.name}"))

        vals = {
            'teslimat_tarihi': self.teslimat_tarihi,
            'arac_id': self.arac_id.id,
            'ilce_id': self.ilce_id.id,
            'musteri_id': self.musteri_id.id,
            'durum': 'hazir',
        }
        if self.transfer_id:
            vals.update({
                'stock_picking_id': self.transfer_id.id,
                'transfer_no': self.transfer_id.name,
            })

        teslimat = self.env['teslimat.belgesi'].create(vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('Teslimat Belgesi')
        }
