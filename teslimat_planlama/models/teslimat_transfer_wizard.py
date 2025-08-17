from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TeslimatTransferWizard(models.TransientModel):
    _name = 'teslimat.transfer.wizard'
    _description = 'Teslimat Belgesi Oluşturma - Transfer Entegrasyonu'

    # Bağlamdan gelen temel bilgiler (readonly)
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', required=True, readonly=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=True, readonly=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=True, readonly=True)

    # Transfer seçimi
    transfer_no = fields.Char(string='Transfer No', help=_('Stock Picking referansı (name)'))
    transfer_id = fields.Many2one('stock.picking', string='Transfer', domain="[('state','in',['waiting','confirmed','assigned','done'])]")

    # Müşteri bilgisi
    musteri_id = fields.Many2one('res.partner', string='Müşteri')

    # Bilgi alanı
    transfer_bilgileri = fields.Html(string='Transfer Bilgileri', readonly=True)

    @api.onchange('transfer_no')
    def _onchange_transfer_no(self):
        if self.transfer_no and len(self.transfer_no) >= 3:
            picking = self.env['stock.picking'].search([('name', '=', self.transfer_no)], limit=1)
            self.transfer_id = picking.id if picking else False
            self._update_transfer_info()

    @api.onchange('transfer_id')
    def _onchange_transfer_id(self):
        self.transfer_no = self.transfer_id.name if self.transfer_id else False
        self._update_transfer_info()

    def _update_transfer_info(self):
        if not self.transfer_id:
            self.musteri_id = False
            self.transfer_bilgileri = False
            return
        picking = self.transfer_id
        self.musteri_id = picking.partner_id.id if picking.partner_id else False
        lines = []
        if picking.move_ids_without_package:
            for mv in picking.move_ids_without_package[:5]:
                lines.append(f"<li>{mv.product_id.display_name} - {mv.product_uom_qty} {mv.product_uom.name}</li>")
        line_html = '<ul>%s</ul>' % ''.join(lines) if lines else '<em>Ürün satırı bulunamadı.</em>'
        self.transfer_bilgileri = (
            f"<p><strong>Transfer:</strong> {picking.name}</p>"
            f"<p><strong>Müşteri:</strong> {picking.partner_id.display_name if picking.partner_id else '-'}" 
            f"</p>"
            f"<p><strong>Planlanan Tarih:</strong> {self.teslimat_tarihi or ''}</p>"
            f"<p><strong>Ürünler:</strong> {line_html}</p>"
        )

    def action_create_delivery(self):
        self.ensure_one()
        if not self.transfer_id:
            raise UserError(_('Lütfen geçerli bir transfer seçin.'))
        # Aynı transfer için mükerrer kontrol
        existing = self.env['teslimat.belgesi'].search([('stock_picking_id', '=', self.transfer_id.id)], limit=1)
        if existing:
            raise UserError(_(f"Bu transfer için zaten bir teslimat belgesi var: {existing.name}"))
        vals = {
            'teslimat_tarihi': self.teslimat_tarihi,
            'arac_id': self.arac_id.id,
            'ilce_id': self.ilce_id.id,
            'musteri_id': self.musteri_id.id if self.musteri_id else False,
            'stock_picking_id': self.transfer_id.id,
            'transfer_no': self.transfer_no,
            'durum': 'hazir',
        }
        rec = self.env['teslimat.belgesi'].create(vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('Teslimat Belgesi')
        }


