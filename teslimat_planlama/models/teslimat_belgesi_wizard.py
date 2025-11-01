# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class TeslimatBelgesiWizard(models.TransientModel):
    _name = 'teslimat.belgesi.wizard'
    _description = 'Teslimat Belgesi Oluşturma Sihirbazı'

    # Temel bilgiler (context ile otomatik dolu gelir)
    # Not: Bu alanlar wizard açılırken context'ten veya default_get'ten doldurulur
    # Ancak stock.picking'den açıldığında arac ve ilçe seçilmeli, bu yüzden readonly=False
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', required=True, readonly=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=False)

    # Transfer No (stock.picking)
    transfer_id = fields.Many2one(
        'stock.picking',
        string='Transfer No',
        domain="[('state','in',['waiting','confirmed','assigned','done'])]",
        help='Transfer numarasına göre arayın (name). İptal ve taslak durumundaki transferler görünmez.'
    )

    # Müşteri ve Adres (otomatik dolar)
    musteri_id = fields.Many2one('res.partner', string='Müşteri', readonly=True)
    adres = fields.Char(string='Adres', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = dict(self.env.context or {})

        # Context'ten tarih/araç/ilçe al
        tarih_ctx = ctx.get('default_teslimat_tarihi')
        arac_ctx = ctx.get('default_arac_id')
        ilce_ctx = ctx.get('default_ilce_id')

        # Tarih bilgisini işle (string ise date'e çevir)
        if tarih_ctx and 'teslimat_tarihi' in (fields_list or []):
            if isinstance(tarih_ctx, str):
                # String formatından date objesine çevir
                from datetime import datetime
                try:
                    tarih_obj = datetime.strptime(tarih_ctx, '%Y-%m-%d').date()
                    res['teslimat_tarihi'] = tarih_obj
                except (ValueError, TypeError):
                    # Hata durumunda string olarak kullan
                    res['teslimat_tarihi'] = tarih_ctx
            else:
                res['teslimat_tarihi'] = tarih_ctx
        
        if arac_ctx and 'arac_id' in (fields_list or []):
            res['arac_id'] = arac_ctx
        if ilce_ctx and 'ilce_id' in (fields_list or []):
            res['ilce_id'] = ilce_ctx

        # Eğer context boş ise aktif kaynaktan doldur (parent form)
        if (not res.get('arac_id') or not res.get('teslimat_tarihi')) and ctx.get('active_model') == 'teslimat.ana.sayfa':
            parent = self.env['teslimat.ana.sayfa'].browse(ctx.get('active_id'))
            if parent:
                if not res.get('arac_id') and parent.arac_id:
                    res['arac_id'] = parent.arac_id.id
                if not res.get('ilce_id') and parent.ilce_id:
                    res['ilce_id'] = parent.ilce_id.id
                # Tarih context ile gelmediyse boş bırakılır, kullanıcı satır butonundan açınca gelir

        # Stock picking'den geldiyse transfer bilgilerini doldur
        if ctx.get('default_transfer_id') and 'transfer_id' in (fields_list or []):
            picking_id = ctx.get('default_transfer_id')
            picking = self.env['stock.picking'].browse(picking_id)
            if picking.exists():
                res['transfer_id'] = picking_id
                # Tarih varsayılan olarak bugün
                if 'teslimat_tarihi' in (fields_list or []) and not res.get('teslimat_tarihi'):
                    res['teslimat_tarihi'] = fields.Date.today()
                # Müşteri bilgisini context'ten al
                if ctx.get('default_musteri_id') and 'musteri_id' in (fields_list or []):
                    res['musteri_id'] = ctx.get('default_musteri_id')

        return res

    @api.onchange('transfer_id')
    def _onchange_transfer_id(self):
        """Transfer seçildiğinde müşteri bilgilerini otomatik doldur"""
        picking = self.transfer_id
        if picking:
            # 1. Transfer durumu kontrolü (iptal ve taslak durumları için uyarı)
            if picking.state in ['cancel', 'draft']:
                return {
                    'warning': {
                        'title': 'Transfer Durumu Uyarısı',
                        'message': f'Transfer {picking.name} durumu "{picking.state}" olduğu için teslimat oluşturulamaz!\n\n'
                                 f'Lütfen onaylanmış veya tamamlanmış bir transfer seçin.'
                    }
                }
            
            # 2. Mükerrer teslimat kontrolü
            existing = self.env['teslimat.belgesi'].search([
                ('stock_picking_id', '=', picking.id)
            ], limit=1)
            if existing:
                return {
                    'warning': {
                        'title': 'Mükerrer Teslimat Uyarısı',
                        'message': f'Transfer {picking.name} için zaten bir teslimat belgesi mevcut!\n\n'
                                 f'Teslimat No: {existing.name}\n'
                                 f'Durum: {existing.durum}\n\n'
                                 f'Lütfen farklı bir transfer seçin.'
                    }
                }
            
            # 3. Müşteri ve adres bilgilerini doldur
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

        # 1. Transfer durumu kontrolü (iptal ve taslak durumları için hata)
        if self.transfer_id:
            if self.transfer_id.state in ['cancel', 'draft']:
                raise UserError(_(f"Transfer {self.transfer_id.name} durumu '{self.transfer_id.state}' olduğu için teslimat oluşturulamaz!\n\nLütfen onaylanmış veya tamamlanmış bir transfer seçin."))
            
            # 2. Mükerrer teslimat kontrolü
            existing = self.env['teslimat.belgesi'].search([
                ('stock_picking_id', '=', self.transfer_id.id)
            ], limit=1)
            if existing:
                raise UserError(_(f"Transfer {self.transfer_id.name} için zaten bir teslimat belgesi mevcut!\n\nTeslimat No: {existing.name}\nDurum: {existing.durum}\n\nLütfen farklı bir transfer seçin."))

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
