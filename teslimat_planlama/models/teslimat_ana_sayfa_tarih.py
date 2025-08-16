from odoo import models, fields, api
from odoo.exceptions import AccessError

class TeslimatAnaSayfaTarih(models.Model):
    _name = 'teslimat.ana.sayfa.tarih'
    _description = 'Ana Sayfa Tarih Listesi'
    _order = 'tarih'

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
        """Durum gösterimi için ikon + metin"""
        for record in self:
            record.durum_gosterim = f"{record.durum_icon} {record.durum_text}"

    @api.depends('doluluk_orani', 'durum')
    def _compute_doluluk_bar(self):
        """Doluluk oranı için görsel bar oluştur"""
        for record in self:
            if record.durum == 'dolu':
                color = '#dc3545'  # Kırmızı
                icon = '🔴'
            elif record.durum == 'dolu_yakin':
                color = '#ffc107'  # Sarı
                icon = '🟡'
            else:
                color = '#28a745'  # Yeşil
                icon = '🟢'
            
            record.doluluk_bar = f"""
                <div style="text-align: center;">
                    <div style="font-size: 18px; margin-bottom: 5px;">{icon}</div>
                    <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">
                        {record.durum_text}
                    </div>
                    <div style="background: #f8f9fa; border-radius: 10px; height: 20px; margin: 5px 0;">
                        <div style="background: {color}; height: 100%; border-radius: 10px; width: {min(record.doluluk_orani, 100)}%;"></div>
                    </div>
                    <div style="font-size: 12px; color: #6c757d;">
                        {record.doluluk_orani:.1f}% Dolu
                    </div>
                </div>
            """
    
    def write(self, vals):
        """Sadece yönetici düzenleyebilir"""
        # Yönetici kontrolü
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError("Bu kayıtları düzenlemek için yönetici yetkisi gereklidir!")
        
        return super().write(vals)
    
    def unlink(self):
        """Sadece yönetici silebilir"""
        # Yönetici kontrolü
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError("Bu kayıtları silmek için yönetici yetkisi gereklidir!")
        
        return super().unlink()
    
    def action_teslimat_olustur(self):
        """Seçilen tarih için teslimat belgesi oluştur"""
        self.ensure_one()
        
        # Ana sayfa bilgilerini al
        ana_sayfa = self.ana_sayfa_id
        if not ana_sayfa or not ana_sayfa.arac_id or not ana_sayfa.ilce_id:
            raise AccessError("Gerekli bilgiler eksik!")
        
        # Teslimat belgesi oluştur
        teslimat_belgesi = self.env['teslimat.belgesi'].create({
            'arac_id': ana_sayfa.arac_id.id,
            'ilce_id': ana_sayfa.ilce_id.id,
            'teslimat_tarihi': self.tarih,
            'durum': 'hazir',
            'aciklama': f"{self.gun_adi} - {ana_sayfa.ilce_id.name} ilçesi için otomatik oluşturuldu"
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat_belgesi.id,
            'view_mode': 'form',
            'target': 'current',
            'name': f'Teslimat Belgesi - {self.tarih}'
        }
