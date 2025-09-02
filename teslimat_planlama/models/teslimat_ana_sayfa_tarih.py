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
            
            # Yönetici kontrolü
            is_manager = self.env.user.has_group('stock.group_stock_manager')
            
            if is_manager:
                # Yönetici için tıklanabilir ikon
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
        """Seçilen tarih için doğrudan Teslimat Belgesi formunu (create) aç."""
        self.ensure_one()
        
        # Ana sayfa bilgilerini al
        ana_sayfa = self.ana_sayfa_id
        if not ana_sayfa or not ana_sayfa.arac_id:
            raise AccessError("Gerekli bilgiler eksik!")

        # Küçük araçlar için ilçe zorunlu değildir
        arac_tipi = ana_sayfa.arac_id.arac_tipi or ''
        is_small = arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']
        if not is_small and not ana_sayfa.ilce_id:
            raise AccessError("İlçe seçimi zorunludur!")
        
        # Teslimat Belgesi formunu create modda aç
        form_view = self.env.ref('teslimat_planlama.view_teslimat_belgesi_form')
        ctx = {
            'default_teslimat_tarihi': self.tarih,
            'default_arac_id': ana_sayfa.arac_id.id,
            'form_view_initial_mode': 'edit',
        }
        if ana_sayfa.ilce_id:
            ctx['default_ilce_id'] = ana_sayfa.ilce_id.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'view_mode': 'form',
            'views': [(form_view.id, 'form')],
            'view_id': form_view.id,
            'target': 'current',
            'context': ctx,
            'name': f'Teslimat Belgesi Oluştur - {self.tarih} ({self.gun_adi})',
        }

    def get_formview_action(self, access_uid=None):
        """Satıra tıklamayı tamamen engelle: Eski wizard açılmasın."""
        # Boş bir action döndürerek açılmayı engelle
        return {
            'type': 'ir.actions.act_window_close'
        }
