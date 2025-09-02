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

    @api.depends('doluluk_orani', 'durum', 'tarih')
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
        
            is_manager = self.env.user.has_group('stock.group_stock_manager')
            
            # Teslimat Belgesi Oluştur butonu HTML
            create_button_html = f"""
                <div style="margin-top: 10px;">
                    <button type="button" 
                            class="btn btn-primary" 
                            style="padding: 5px 10px; font-size: 12px; cursor: pointer;"
                            onclick="
                                var self = this;
                                var action = {{
                                    'type': 'ir.actions.act_window',
                                    'name': 'Teslimat Belgesi Oluştur',
                                    'res_model': 'teslimat.belgesi',
                                    'view_mode': 'form',
                                    'view_type': 'form',
                                    'target': 'current',
                                    'context': {{
                                        'default_teslimat_tarihi': '{record.tarih}',
                                        'default_arac_id': {record.ana_sayfa_id.arac_id.id if record.ana_sayfa_id and record.ana_sayfa_id.arac_id else 'false'},
                                        'default_ilce_id': {record.ana_sayfa_id.ilce_id.id if record.ana_sayfa_id and record.ana_sayfa_id.ilce_id else 'false'},
                                        'form_view_initial_mode': 'edit'
                                    }}
                                }};
                                self.dispatchEvent(new CustomEvent('odoo-action', {{
                                    bubbles: true,
                                    detail: {{ action: action }}
                                }}));
                            ">
                        📋 Teslimat Oluştur
                    </button>
                </div>
            """
            
            if is_manager:
                # Yönetici için tıklanabilir ikon ve buton
                record.doluluk_bar = f"""
                    <div style="text-align: center;">
                        <div style="font-size: 18px; margin-bottom: 5px; cursor: pointer;" 
                             title="Tıklayarak teslimat belgesi oluştur">{icon}</div>
                        <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">
                            {record.durum_text}
                        </div>
                        <div style="background: #f8f9fa; border-radius: 10px; height: 20px; margin: 5px 0;">
                            <div style="background: {color}; height: 100%; border-radius: 10px; width: {min(record.doluluk_orani, 100)}%;"></div>
                        </div>
                        <div style="font-size: 12px; color: #6c757d;">
                            {record.doluluk_orani:.1f}% Dolu
                        </div>
                        {create_button_html}
                    </div>
                """
            else:
                # Normal kullanıcı için tıklanamaz ikon
                record.doluluk_bar = f"""
                    <div style="text-align: center;">
                        <div style="font-size: 18px; margin-bottom: 5px; cursor: not-allowed; opacity: 0.7; pointer-events: none; user-select: none;" 
                             title="Bu işlem için yönetici yetkisi gereklidir">{icon}</div>
                        <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">
                            {record.durum_text}
                        </div>
                        <div style="background: #f8f9fa; border-radius: 10px; height: 20px; margin: 5px 0;">
                            <div style="background: {color}; height: 100%; border-radius: 10px; width: {min(record.doluluk_orani, 100)}%;"></div>
                        </div>
                        <div style="font-size: 12px; color: #6c757d;">
                            {record.doluluk_orani:.1f}% Dolu
                        </div>
                        <div style="font-size: 10px; color: #6c757d; margin-top: 5px;">
                            🔒 Sadece Görüntüleme
                        </div>
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

    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        # Satıra tıklanınca direkt teslimat belgesi create formunu aç
        ctx = {
            'default_teslimat_tarihi': self.tarih,
            'default_arac_id': self.ana_sayfa_id.arac_id.id if self.ana_sayfa_id and self.ana_sayfa_id.arac_id else False,
            'form_view_initial_mode': 'edit',
        }
        if self.ana_sayfa_id and self.ana_sayfa_id.ilce_id:
            ctx['default_ilce_id'] = self.ana_sayfa_id.ilce_id.id
        
        # Direkt teslimat belgesi create formunu aç
        return {
            'type': 'ir.actions.act_window',
            'name': 'Yeni Teslimat Belgesi',
            'res_model': 'teslimat.belgesi',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }
