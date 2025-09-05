from odoo import models, fields, api
from odoo.exceptions import AccessError

class TeslimatAnaSayfaTarih(models.Model):
    _name = 'teslimat.ana.sayfa.tarih'
    _description = 'Ana Sayfa Tarih Listesi'
    _order = 'tarih'
    _rec_name = 'tarih'

    ana_sayfa_id = fields.Many2one('teslimat.ana.sayfa', string='Ana Sayfa')
    
    # Tarih Bilgileri
    tarih = fields.Date(string='Tarih', required=True)
    gun_adi = fields.Char(string='Gün', required=True)
    
    # Kapasite Bilgileri
    teslimat_sayisi = fields.Integer(string='Teslimat Sayısı', default=0)
    toplam_kapasite = fields.Integer(string='Toplam Kapasite', default=0)
    kalan_kapasite = fields.Integer(string='Kalan Kapasite', default=0)
    doluluk_orani = fields.Float(string='Doluluk Oranı (%)', default=0.0)
    
    # Durum Bilgileri
    durum = fields.Selection([
        ('musait', 'Müsait'),
        ('dolu_yakin', 'Dolu Yakın'),
        ('dolu', 'Dolu')
    ], string='Durum', default='musait')
    
    durum_icon = fields.Char(string='Durum İkonu', default='🟢')
    durum_text = fields.Char(string='Durum Metni', default='MUSAİT')
    durum_gosterim = fields.Char(string='Durum Gösterimi', compute='_compute_durum_gosterim')
    
    # Hesaplanan Alanlar
    doluluk_bar = fields.Html(string='Doluluk Barı', compute='_compute_doluluk_bar', store=True)
    
    @api.depends('durum_icon', 'durum_text')
    def _compute_durum_gosterim(self):
        for record in self:
            record.durum_gosterim = f"{record.durum_icon} {record.durum_text}"

    @api.depends('doluluk_orani', 'durum', 'tarih', 'ana_sayfa_id')
    def _compute_doluluk_bar(self):
        for record in self:
            if record.durum == 'dolu':
                color = '#dc3545'
                icon = '🔴'
            elif record.durum == 'dolu_yakin':
                color = '#ffc107'
                icon = '🟡'
            else:
                color = '#28a745'
                icon = '🟢'
        
            # Random ID ile cache sorunu çözülecek
            import random
            random_id = random.randint(100000, 999999)
            
            # DEBUG: URL parametrelerini logla
            import logging
            _logger = logging.getLogger(__name__)
            
            tarih_param = record.tarih
            arac_id_param = record.ana_sayfa_id.arac_id.id if record.ana_sayfa_id and record.ana_sayfa_id.arac_id else ''
            ilce_id_param = record.ana_sayfa_id.ilce_id.id if record.ana_sayfa_id and record.ana_sayfa_id.ilce_id else ''
            
            _logger.info(f"URL PARAMETRELERİ - Tarih: {tarih_param}, Araç ID: {arac_id_param}, İlçe ID: {ilce_id_param}")
            _logger.info(f"Ana Sayfa: {record.ana_sayfa_id}, Araç: {record.ana_sayfa_id.arac_id if record.ana_sayfa_id else 'YOK'}, İlçe: {record.ana_sayfa_id.ilce_id if record.ana_sayfa_id else 'YOK'}")
            
            # Basit HTML buton - sadece görsel
            record.doluluk_bar = f"""
                <div style="text-align: center; padding: 10px;">
                    <span style="display: inline-block; padding: 8px 16px; font-size: 14px; background-color: #007bff; color: white; border-radius: 5px;">
                        📋 Teslimat Oluştur ({tarih_param})
                    </span>
                </div>
            """

    def write(self, vals):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError("Bu kayıtları düzenlemek için yönetici yetkisi gereklidir!")
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError("Bu kayıtları silmek için yönetici yetkisi gereklidir!")
        return super().unlink()

    def action_teslimat_olustur(self):
        """Direkt Teslimat Belgesi oluştur ve aç - ZORLA TARİH GEÇİŞİ"""
        self.ensure_one()
        
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"=== ACTION_TESLIMAT_OLUSTUR ÇAĞRILDI ===")
        _logger.info(f"Tarih: {self.tarih}")
        _logger.info(f"Ana Sayfa Araç: {self.ana_sayfa_id.arac_id.name if self.ana_sayfa_id and self.ana_sayfa_id.arac_id else 'YOK'}")
        _logger.info(f"Ana Sayfa İlçe: {self.ana_sayfa_id.ilce_id.name if self.ana_sayfa_id and self.ana_sayfa_id.ilce_id else 'YOK'}")
        
        # Teslimat belgesi oluştur - ZORLA
        vals = {
            'teslimat_tarihi': self.tarih,
            'durum': 'taslak'
        }
        
        # Ana sayfa bilgilerini al
        if self.ana_sayfa_id:
            if self.ana_sayfa_id.arac_id:
                vals['arac_id'] = self.ana_sayfa_id.arac_id.id
                _logger.info(f"Araç ID eklendi: {self.ana_sayfa_id.arac_id.id}")
            if self.ana_sayfa_id.ilce_id:
                vals['ilce_id'] = self.ana_sayfa_id.ilce_id.id
                _logger.info(f"İlçe ID eklendi: {self.ana_sayfa_id.ilce_id.id}")
        
        _logger.info(f"Teslimat belgesi vals: {vals}")
        
        # Belgeyi oluştur
        teslimat_belgesi = self.env['teslimat.belgesi'].create(vals)
        _logger.info(f"Teslimat belgesi oluşturuldu: {teslimat_belgesi.name}")
        _logger.info(f"Oluşturulan belge tarihi: {teslimat_belgesi.teslimat_tarihi}")
        
        # Oluşturulan belgenin formunu aç
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teslimat Belgesi',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat_belgesi.id,
            'view_mode': 'form',
            'target': 'current',
        }


