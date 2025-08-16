from odoo import models, fields, api
from odoo.exceptions import ValidationError

class TeslimatOlusturWizard(models.TransientModel):
    _name = 'teslimat.olustur.wizard'
    _description = 'Teslimat Belgesi Oluşturma Wizard'

    # Seçim Alanı
    olusturma_tipi = fields.Selection([
        ('transfer_no', 'Transfer No ile'),
        ('manuel', 'Manuel Teslimat')
    ], string='Oluşturma Tipi', required=True, default='transfer_no')
    
    # Transfer No Alanı
    transfer_no = fields.Char(string='Transfer No', 
                             help='Örnek: AKS/POS/72133, AKSY/OUT/19574')
    
    # Manuel Teslimat Alanları
    musteri_adi = fields.Char(string='Müşteri Adı')
    adres = fields.Text(string='Adres')
    telefon = fields.Char(string='Telefon')
    urun_aciklamasi = fields.Text(string='Ürün Açıklaması')
    teslimat_notu = fields.Text(string='Teslimat Notu')
    
    # Otomatik Doldurulan Alanlar
    bulunan_transfer = fields.Many2one('stock.picking', string='Bulunan Transfer', readonly=True)
    transfer_bilgileri = fields.Text(string='Transfer Bilgileri', readonly=True)
    
    @api.onchange('transfer_no')
    def _onchange_transfer_no(self):
        """Transfer no girildiğinde transfer bilgilerini ara"""
        if self.transfer_no and len(self.transfer_no) > 5:
            # Transfer no'yu ara
            transfer = self.env['stock.picking'].search([
                ('name', '=', self.transfer_no)
            ], limit=1)
            
            if transfer:
                self.bulunan_transfer = transfer.id
                self.transfer_bilgileri = f"""
                    ✅ Transfer Bulundu!
                    
                    📦 Transfer No: {transfer.name}
                    👤 Müşteri: {transfer.partner_id.name if transfer.partner_id else 'Belirtilmemiş'}
                    📍 Adres: {transfer.partner_id.street if transfer.partner_id and transfer.partner_id.street else 'Belirtilmemiş'}
                    📞 Telefon: {transfer.partner_id.phone if transfer.partner_id and transfer.partner_id.phone else 'Belirtilmemiş'}
                    📋 Ürünler: {len(transfer.move_ids_without_package)} adet ürün
                    📅 Tarih: {transfer.scheduled_date.strftime('%d.%m.%Y') if transfer.scheduled_date else 'Belirtilmemiş'}
                """
            else:
                self.bulunan_transfer = False
                self.transfer_bilgileri = f"""
                    ❌ Transfer Bulunamadı!
                    
                    🔍 Aranan: {self.transfer_no}
                    💡 Örnek formatlar:
                    • AKS/POS/72133
                    • AKSY/OUT/19574
                    • POS/IN/12345
                """
    
    def action_teslimat_olustur(self):
        """Teslimat belgesi oluştur"""
        self.ensure_one()
        
        # Ana sayfa bilgilerini al
        ana_sayfa_id = self.env.context.get('ana_sayfa_id')
        if not ana_sayfa_id:
            raise ValidationError("Ana sayfa bilgisi bulunamadı!")
        
        ana_sayfa = self.env['teslimat.ana.sayfa'].browse(ana_sayfa_id)
        
        if self.olusturma_tipi == 'transfer_no':
            # Transfer no ile oluştur
            if not self.bulunan_transfer:
                raise ValidationError("Lütfen geçerli bir transfer no girin!")
            
            teslimat_belgesi = self.env['teslimat.belgesi'].create({
                'arac_id': ana_sayfa.arac_id.id,
                'ilce_id': ana_sayfa.ilce_id.id,
                'teslimat_tarihi': self.env.context.get('teslimat_tarihi'),
                'durum': 'hazir',
                'transfer_no': self.transfer_no,
                'stock_picking_id': self.bulunan_transfer.id,
                'musteri_id': self.bulunan_transfer.partner_id.id if self.bulunan_transfer.partner_id else False,
                'aciklama': f"Transfer No: {self.transfer_no} - {ana_sayfa.ilce_id.name} ilçesi için oluşturuldu"
            })
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'teslimat.belgesi',
                'res_id': teslimat_belgesi.id,
                'view_mode': 'form',
                'target': 'current',
                'name': f'Teslimat Belgesi - {self.transfer_no}'
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
