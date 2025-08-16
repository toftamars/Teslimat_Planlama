from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TeslimatPlanlama(models.Model):
    _name = 'teslimat.planlama'
    _description = 'Teslimat Planlama'
    _order = 'tarih desc'

    name = fields.Char(string='Plan Adı', required=True, copy=False, readonly=True, 
                      default=lambda self: _('Yeni'))
    tarih = fields.Date(string='Plan Tarihi', required=True, default=fields.Date.today)
    durum = fields.Selection([
        ('taslak', 'Taslak'),
        ('onaylandi', 'Onaylandı'),
        ('calisiyor', 'Çalışıyor'),
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal')
    ], string='Durum', default='taslak', required=True)
    
    # Kontakt bilgileri
    musteri_ids = fields.Many2many('res.partner', string='Müşteriler', 
                                  domain=[('customer_rank', '>', 0)])
    
    # Transfer bilgileri
    transfer_ids = fields.One2many('teslimat.transfer', 'planlama_id', string='Transferler')
    
    # Stok bilgileri
    urun_ids = fields.Many2many('product.product', string='Ürünler')
    
    # Planlama detayları
    baslangic_tarihi = fields.Datetime(string='Başlangıç Tarihi')
    bitis_tarihi = fields.Datetime(string='Bitiş Tarihi')
    notlar = fields.Text(string='Notlar')
    
    # Hesaplanan alanlar
    toplam_transfer = fields.Integer(string='Toplam Transfer', compute='_compute_toplamlar')
    toplam_urun = fields.Integer(string='Toplam Ürün', compute='_compute_toplamlar')
    
    @api.depends('transfer_ids', 'urun_ids')
    def _compute_toplamlar(self):
        for record in self:
            record.toplam_transfer = len(record.transfer_ids)
            record.toplam_urun = len(record.urun_ids)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Yeni')) == _('Yeni'):
            vals['name'] = self.env['ir.sequence'].next_by_code('teslimat.planlama') or _('Yeni')
        return super(TeslimatPlanlama, self).create(vals)
    
    def action_onayla(self):
        self.write({'durum': 'onaylandi'})
    
    def action_baslat(self):
        self.write({'durum': 'calisiyor'})
    
    def action_tamamla(self):
        self.write({'durum': 'tamamlandi'})
    
    def action_iptal(self):
        self.write({'durum': 'iptal'})


class TeslimatTransfer(models.Model):
    _name = 'teslimat.transfer'
    _description = 'Teslimat Transfer'
    _order = 'sira_no'

    name = fields.Char(string='Transfer Adı', required=True)
    planlama_id = fields.Many2one('teslimat.planlama', string='Planlama', required=True)
    sira_no = fields.Integer(string='Sıra No', default=1)
    
    # Araç Bilgisi
    arac_id = fields.Many2one('teslimat.arac', string='Araç')
    
    # Transfer belgesi entegrasyonu
    transfer_no = fields.Char(string='Transfer No', help='Transfer belgesi numarası')
    stock_picking_id = fields.Many2one('stock.picking', string='Transfer Belgesi', 
                                      domain=[('picking_type_id.code', '=', 'internal')])
    
    # Transfer detayları (otomatik doldurulacak)
    kaynak_konum = fields.Many2one('stock.location', string='Kaynak Konum', required=True)
    hedef_konum = fields.Many2one('stock.location', string='Hedef Konum', required=True)
    urun_id = fields.Many2one('product.product', string='Ürün', required=True)
    miktar = fields.Float(string='Miktar', required=True)
    birim = fields.Many2one('uom.uom', string='Birim', related='urun_id.uom_id', readonly=True)
    
    # Müşteri bilgileri (otomatik doldurulacak)
    musteri_id = fields.Many2one('res.partner', string='Müşteri', 
                                domain=[('customer_rank', '>', 0)])
    
    # Zaman bilgileri
    planlanan_tarih = fields.Datetime(string='Planlanan Tarih')
    gerceklesen_tarih = fields.Datetime(string='Gerçekleşen Tarih')
    
    # Durum
    durum = fields.Selection([
        ('bekliyor', 'Bekliyor'),
        ('hazirlaniyor', 'Hazırlanıyor'),
        ('yolda', 'Yolda'),
        ('tamamlandi', 'Tamamlandı'),
        ('iptal', 'İptal')
    ], string='Durum', default='bekliyor')
    
    notlar = fields.Text(string='Notlar')
    
    @api.onchange('transfer_no')
    def _onchange_transfer_no(self):
        """Transfer no girildiğinde bilgileri otomatik doldur"""
        if self.transfer_no:
            # Transfer belgesini bul
            picking = self.env['stock.picking'].search([
                ('name', '=', self.transfer_no),
                ('picking_type_id.code', '=', 'internal')
            ], limit=1)
            
            if picking:
                self.stock_picking_id = picking.id
                self._onchange_stock_picking()
    
    @api.onchange('stock_picking_id')
    def _onchange_stock_picking(self):
        """Transfer belgesi seçildiğinde bilgileri otomatik doldur"""
        if self.stock_picking_id:
            picking = self.stock_picking_id
            
            # Konum bilgileri
            if picking.location_id:
                self.kaynak_konum = picking.location_id.id
            if picking.location_dest_id:
                self.hedef_konum = picking.location_dest_id.id
            
            # Ürün ve miktar bilgileri (ilk satırdan)
            if picking.move_ids_without_package:
                move = picking.move_ids_without_package[0]
                self.urun_id = move.product_id.id
                self.miktar = move.product_uom_qty
            
            # Müşteri bilgisi (eğer varsa)
            if picking.partner_id and picking.partner_id.customer_rank > 0:
                self.musteri_id = picking.partner_id.id
            
            # Transfer adı
            if not self.name:
                self.name = f"Transfer: {picking.name}"
    
    def action_transfer_belgesi_olustur(self):
        """Transfer belgesinden teslimat belgesi oluştur"""
        for record in self:
            if record.stock_picking_id:
                # Teslimat belgesi oluştur
                delivery_picking = self.env['stock.picking'].create({
                    'picking_type_id': self.env.ref('stock.picking_type_out').id,
                    'location_id': record.kaynak_konum.id,
                    'location_dest_id': record.hedef_konum.id,
                    'partner_id': record.musteri_id.id if record.musteri_id else False,
                    'origin': record.name,
                    'scheduled_date': record.planlanan_tarih or fields.Datetime.now(),
                    'note': f"Teslimat Transfer: {record.name}",
                    'teslimat_transfer_id': record.id,
                    'teslimat_planlama_id': record.planlama_id.id,
                })
                
                # Ürün satırı ekle
                if record.urun_id and record.miktar:
                    self.env['stock.move'].create({
                        'name': record.urun_id.name,
                        'product_id': record.urun_id.id,
                        'product_uom_qty': record.miktar,
                        'product_uom': record.birim.id,
                        'picking_id': delivery_picking.id,
                        'location_id': record.kaynak_konum.id,
                        'location_dest_id': record.hedef_konum.id,
                    })
                
                record.write({'durum': 'hazirlaniyor'})
                
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking',
                    'res_id': delivery_picking.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
