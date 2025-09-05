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
            
            # HTML buton ile context parametreleri
            context_params = f"'default_teslimat_tarihi': '{tarih_param}'"
            if arac_id_param:
                context_params += f", 'default_arac_id': {arac_id_param}"
            if ilce_id_param:
                context_params += f", 'default_ilce_id': {ilce_id_param}"
            
            # Tarih bilgisini debug için logla
            _logger.info(f"BUTON İÇİN TARİH: {tarih_param} (Type: {type(tarih_param)})")
            _logger.info(f"CONTEXT PARAMS: {context_params}")
            
            record.doluluk_bar = f"""
                <div style="text-align: center; padding: 10px;">
                    <a href="/web#action=teslimat_planlama.action_teslimat_belgesi_olustur&context={{{context_params}}}&r={random_id}" 
                       style="display: inline-block; padding: 8px 16px; font-size: 14px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;"
                       target="_self">
                        📋 Teslimat Oluştur
                    </a>
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
        """Direkt Teslimat Belgesi create formunu aç (kısa yol)"""
        self.ensure_one()
        
        # Context ile varsayılan değerleri hazırla
        ctx = {
            'default_teslimat_tarihi': self.tarih,
            'form_view_initial_mode': 'edit',
        }
        
        # Ana sayfa bilgilerini al
        ana_sayfa = self.ana_sayfa_id
        if ana_sayfa and ana_sayfa.arac_id:
            ctx['default_arac_id'] = ana_sayfa.arac_id.id
            if ana_sayfa.ilce_id:
                ctx['default_ilce_id'] = ana_sayfa.ilce_id.id
        
        # Direkt form create modunda aç
        return {
            'type': 'ir.actions.act_window',
            'name': 'Yeni Teslimat Belgesi',
            'res_model': 'teslimat.belgesi',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }


