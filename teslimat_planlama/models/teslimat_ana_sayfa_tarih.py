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
    doluluk_bar = fields.Html(string='Doluluk Barı', compute='_compute_doluluk_bar')
    
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
        
            # Basit buton HTML
            record.doluluk_bar = f"""
                <div style="text-align: center; padding: 10px;">
                    <div style="font-size: 18px; margin-bottom: 5px;">{icon}</div>
                    <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">
                        {record.durum_text}
                    </div>
                    <div style="background: #f8f9fa; border-radius: 10px; height: 20px; margin: 5px 0;">
                        <div style="background: {color}; height: 100%; border-radius: 10px; width: {min(record.doluluk_orani, 100)}%;"></div>
                    </div>
                    <div style="font-size: 12px; color: #6c757d; margin-bottom: 10px;">
                        {record.doluluk_orani:.1f}% Dolu
                    </div>
                    <button type="button" 
                            class="btn btn-primary" 
                            style="padding: 8px 15px; font-size: 14px; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 4px; font-weight: bold;"
                            onclick="
                                var action = {{
                                    'type': 'ir.actions.act_window',
                                    'name': 'Teslimat Belgesi Oluştur',
                                    'res_model': 'teslimat.belgesi',
                                    'view_mode': 'form',
                                    'target': 'current',
                                    'context': {{
                                        'default_teslimat_tarihi': '{record.tarih}',
                                        'default_arac_id': {record.ana_sayfa_id.arac_id.id if record.ana_sayfa_id and record.ana_sayfa_id.arac_id else 'false'},
                                        'default_ilce_id': {record.ana_sayfa_id.ilce_id.id if record.ana_sayfa_id and record.ana_sayfa_id.ilce_id else 'false'},
                                        'form_view_initial_mode': 'edit'
                                    }}
                                }};
                                odoo.define('teslimat_action', function (require) {{
                                    var ActionManager = require('web.ActionManager');
                                    ActionManager.do_action(action);
                                }});
                            ">
                        📋 Teslimat Oluştur
                    </button>
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


