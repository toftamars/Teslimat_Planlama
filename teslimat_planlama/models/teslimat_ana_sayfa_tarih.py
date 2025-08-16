from odoo import models, fields, api

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
    
    # Hesaplanan Alanlar
    doluluk_bar = fields.Html(string='Doluluk Barı', compute='_compute_doluluk_bar')
    
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
