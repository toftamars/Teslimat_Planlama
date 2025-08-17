from odoo import models, fields, api
from odoo.exceptions import ValidationError

class TeslimatOlusturWizard(models.TransientModel):
    _name = 'teslimat.olustur.wizard'
    _description = 'Teslimat Belgesi Oluşturma Wizard'

    # Ana Sayfa Bilgileri (Otomatik doldurulan)
    ana_sayfa_id = fields.Many2one('teslimat.ana.sayfa', string='Ana Sayfa', readonly=True)
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', readonly=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç', readonly=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', readonly=True)
    
    # Seçim Alanı
    olusturma_tipi = fields.Selection([
        ('transfer_no', '🔄 Transfer Belgesi Entegrasyonu'),
        ('manuel', '✍️ Manuel Teslimat')
    ], string='Oluşturma Tipi', required=True, default='transfer_no')
    
    # Transfer No Alanı
    transfer_no = fields.Char(string='Transfer No', 
                             help='Örnek: AKS/POS/72133, AKSY/OUT/19574')
    
    # Transfer Seçimi Alanı
    transfer_id = fields.Many2one('stock.picking', string='Transfer Belgesi Seç',
                                  domain="[('state', 'in', ['confirmed', 'assigned', 'waiting'])]",
                                  help='Mevcut transfer belgelerinden seçim yapın')
    
    # Manuel Teslimat Alanları
    musteri_adi = fields.Char(string='Müşteri Adı')
    adres = fields.Text(string='Adres')
    telefon = fields.Char(string='Telefon')
    urun_aciklamasi = fields.Text(string='Ürün Açıklaması')
    teslimat_notu = fields.Text(string='Teslimat Notu')
    
    # Otomatik Doldurulan Alanlar
    bulunan_transfer = fields.Many2one('stock.picking', string='Bulunan Transfer', readonly=True)
    transfer_bilgileri = fields.Html(string='Transfer Bilgileri', readonly=True)
    
    @api.onchange('transfer_no')
    def _onchange_transfer_no(self):
        """Transfer no girildiğinde transfer bilgilerini ara"""
        if self.transfer_no and len(self.transfer_no) > 5:
            # Transfer no'yu ara
            transfer = self.env['stock.picking'].search([
                ('name', '=', self.transfer_no)
            ], limit=1)
            
            if transfer:
                self.transfer_id = transfer.id
                self.bulunan_transfer = transfer.id
                self._update_transfer_bilgileri(transfer)
            else:
                self.transfer_id = False
                self.bulunan_transfer = False
                self._update_transfer_bilgileri(False)
    
    @api.onchange('transfer_id')
    def _onchange_transfer_id(self):
        """Transfer seçildiğinde otomatik olarak transfer no ve bilgilerini güncelle"""
        if self.transfer_id:
            self.transfer_no = self.transfer_id.name
            self.bulunan_transfer = self.transfer_id.id
            self._update_transfer_bilgileri(self.transfer_id)
        else:
            self.transfer_no = False
            self.bulunan_transfer = False
            self._update_transfer_bilgileri(False)
    
    def _update_transfer_bilgileri(self, transfer):
        """Transfer bilgilerini güncelle"""
        if transfer:
            self.transfer_bilgileri = f"""
                <div style="background: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; padding: 15px; margin: 10px 0;">
                    <h4 style="color: #155724; margin: 0 0 10px 0;">✅ Transfer Belgesi Bulundu!</h4>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div><strong>📦 Transfer No:</strong> {transfer.name}</div>
                        <div><strong>👤 Müşteri:</strong> {transfer.partner_id.name if transfer.partner_id else 'Belirtilmemiş'}</div>
                        <div><strong>📍 Adres:</strong> {transfer.partner_id.street if transfer.partner_id and transfer.partner_id.street else 'Belirtilmemiş'}</div>
                        <div><strong>📞 Telefon:</strong> {transfer.partner_id.phone if transfer.partner_id and transfer.partner_id.phone else 'Belirtilmemiş'}</div>
                        <div><strong>📋 Ürün Sayısı:</strong> {len(transfer.move_ids_without_package)} adet ürün</div>
                        <div><strong>📅 Tarih:</strong> {transfer.scheduled_date.strftime('%d.%m.%Y') if transfer.scheduled_date else 'Belirtilmemiş'}</div>
                    </div>
                    
                    <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 3px;">
                        <strong>💡 Bilgi:</strong> Bu transfer belgesi seçilen tarih ve araç için teslimat belgesine dönüştürülecek.
                    </div>
                </div>
            """
        else:
            self.transfer_bilgileri = f"""
                <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; padding: 15px; margin: 10px 0;">
                    <h4 style="color: #721c24; margin: 0 0 10px 0;">❌ Transfer Belgesi Bulunamadı!</h4>
                    
                    <div style="margin-bottom: 15px;">
                        <strong>🔍 Aranan Transfer No:</strong> {self.transfer_no or 'Belirtilmemiş'}
                    </div>
                    
                    <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 3px; padding: 10px;">
                        <strong>💡 Örnek Transfer No Formatları:</strong><br/>
                        • AKS/POS/72133<br/>
                        • AKSY/OUT/19574<br/>
                        • POS/IN/12345<br/>
                        • AKS/OUT/98765
                    </div>
                    
                    <div style="margin-top: 15px; padding: 10px; background: #d1ecf1; border: 1px solid #bee5eb; border-radius: 3px;">
                        <strong>🔧 Kontrol Edilecekler:</strong><br/>
                        • Transfer no doğru yazıldı mı?<br/>
                        • Transfer belgesi sistemde mevcut mu?<br/>
                        • Transfer durumu uygun mu?
                    </div>
                </div>
            """
    
    def action_teslimat_olustur(self):
        """Transfer Belgesi Entegrasyonu ile teslimat belgesi oluştur"""
        self.ensure_one()
        
        # Ana sayfa bilgilerini al
        if self.ana_sayfa_id:
            ana_sayfa = self.ana_sayfa_id
        else:
            ana_sayfa_id = self.env.context.get('ana_sayfa_id')
            if not ana_sayfa_id:
                raise ValidationError("Ana sayfa bilgisi bulunamadı!")
            ana_sayfa = self.env['teslimat.ana.sayfa'].browse(ana_sayfa_id)
        
        if self.olusturma_tipi == 'transfer_no':
            # Transfer no ile oluştur
            if not self.bulunan_transfer:
                raise ValidationError("Lütfen geçerli bir transfer no girin!")
            
            # Transferden ürün/miktar bilgisini çek
            move = False
            if self.bulunan_transfer.move_ids_without_package:
                move = self.bulunan_transfer.move_ids_without_package[0]
            if not move:
                raise ValidationError("Seçilen transfer belgesinde ürün hareketi bulunamadı!")
            
            teslimat_belgesi = self.env['teslimat.belgesi'].create({
                'arac_id': ana_sayfa.arac_id.id,
                'ilce_id': ana_sayfa.ilce_id.id,
                'teslimat_tarihi': self.teslimat_tarihi or self.env.context.get('teslimat_tarihi'),
                'durum': 'hazir',
                'transfer_no': self.transfer_no,
                'stock_picking_id': self.bulunan_transfer.id,
                'musteri_id': self.bulunan_transfer.partner_id.id if self.bulunan_transfer.partner_id else False,
                'urun_id': move.product_id.id,
                'miktar': move.product_uom_qty,
                'aciklama': f"Transfer No: {self.transfer_no} - {ana_sayfa.ilce_id.name} ilçesi için oluşturuldu"
            })
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'teslimat.belgesi',
                'res_id': teslimat_belgesi.id,
                'view_mode': 'form',
                'target': 'current',
                'name': f'Transfer Entegrasyonu - {self.transfer_no}'
            }
            
        else:
            # Manuel teslimat oluştur
            if not self.musteri_adi:
                raise ValidationError("Müşteri adı zorunludur!")
            
            teslimat_belgesi = self.env['teslimat.belgesi'].create({
                'arac_id': ana_sayfa.arac_id.id,
                'ilce_id': ana_sayfa.ilce_id.id,
                'teslimat_tarihi': self.env.context.get('teslimat_tarihi'),
                'durum': 'hazir',
                'aciklama': f"""
                    Manuel Teslimat:
                    Müşteri: {self.musteri_adi}
                    Adres: {self.adres or 'Belirtilmemiş'}
                    Telefon: {self.telefon or 'Belirtilmemiş'}
                    Ürün: {self.urun_aciklamasi or 'Belirtilmemiş'}
                    Not: {self.teslimat_notu or 'Belirtilmemiş'}
                    
                    {ana_sayfa.ilce_id.name} ilçesi için oluşturuldu
                """
            })
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'teslimat.belgesi',
                'res_id': teslimat_belgesi.id,
                'view_mode': 'form',
                'target': 'current',
                'name': f'Manuel Teslimat - {self.musteri_adi}'
            }
