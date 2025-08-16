from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Teslimat planlama alanları
    teslimat_planlama_id = fields.Many2one('teslimat.planlama', string='Teslimat Planlaması')
    teslimat_transfer_id = fields.Many2one('teslimat.transfer', string='Teslimat Transfer')
    
    # Rota bilgileri
    rota_sira_no = fields.Integer(string='Rota Sıra No')
    tahmini_varis_saati = fields.Datetime(string='Tahmini Varış Saati')
    gercek_varis_saati = fields.Datetime(string='Gerçek Varış Saati')
    
    # Teslimat durumu
    teslimat_durumu = fields.Selection([
        ('planlandi', 'Planlandı'),
        ('yolda', 'Yolda'),
        ('teslim_edildi', 'Teslim Edildi'),
        ('gecikti', 'Gecikti'),
        ('iptal', 'İptal')
    ], string='Teslimat Durumu', default='planlandi')
    
    # Mesafe ve süre bilgileri
    mesafe_km = fields.Float(string='Mesafe (KM)')
    tahmini_sure_dakika = fields.Integer(string='Tahmini Süre (Dakika)')
    gercek_sure_dakika = fields.Integer(string='Gerçek Süre (Dakika)')
    
    # Notlar
    teslimat_notlari = fields.Text(string='Teslimat Notları')
    
    @api.onchange('teslimat_transfer_id')
    def _onchange_teslimat_transfer(self):
        if self.teslimat_transfer_id:
            self.teslimat_planlama_id = self.teslimat_transfer_id.planlama_id
            self.tahmini_varis_saati = self.teslimat_transfer_id.planlanan_tarih
    
    def action_teslimat_baslat(self):
        """Teslimatı başlat"""
        self.write({
            'teslimat_durumu': 'yolda',
            'state': 'in_transit'
        })
        if self.teslimat_transfer_id:
            self.teslimat_transfer_id.write({'durum': 'yolda'})
    
    def action_teslimat_tamamla(self):
        """Teslimatı tamamla"""
        self.write({
            'teslimat_durumu': 'teslim_edildi',
            'gercek_varis_saati': fields.Datetime.now()
        })
        if self.teslimat_transfer_id:
            self.teslimat_transfer_id.write({
                'durum': 'tamamlandi',
                'gerceklesen_tarih': fields.Datetime.now()
            })
    
    def action_teslimat_gecikti(self):
        """Teslimat gecikti olarak işaretle"""
        self.write({'teslimat_durumu': 'gecikti'})
