from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Teslimat planlama alanları
    teslimat_bolgesi = fields.Char(string='Teslimat Bölgesi')
    teslimat_suresi = fields.Integer(string='Teslimat Süresi (Gün)', default=1)
    teslimat_notlari = fields.Text(string='Teslimat Notları')
    
    # Konum bilgileri
    enlem = fields.Float(string='Enlem')
    boylam = fields.Float(string='Boylam')
    
    # Teslimat tercihleri
    tercih_edilen_teslimat_gunu = fields.Selection([
        ('pazartesi', 'Pazartesi'),
        ('sali', 'Salı'),
        ('carsamba', 'Çarşamba'),
        ('persembe', 'Perşembe'),
        ('cuma', 'Cuma'),
        ('cumartesi', 'Cumartesi'),
        ('pazar', 'Pazar')
    ], string='Tercih Edilen Teslimat Günü')
    
    tercih_edilen_teslimat_saati = fields.Selection([
        ('09:00', '09:00'),
        ('10:00', '10:00'),
        ('11:00', '11:00'),
        ('12:00', '12:00'),
        ('13:00', '13:00'),
        ('14:00', '14:00'),
        ('15:00', '15:00'),
        ('16:00', '16:00'),
        ('17:00', '17:00')
    ], string='Tercih Edilen Teslimat Saati')
    
    # Teslimat geçmişi
    teslimat_planlama_ids = fields.One2many('teslimat.planlama', 'musteri_ids', string='Teslimat Planlamaları')
    
    @api.depends('enlem', 'boylam')
    def _compute_konum_bilgisi(self):
        for partner in self:
            if partner.enlem and partner.boylam:
                partner.konum_bilgisi = f"{partner.enlem}, {partner.boylam}"
            else:
                partner.konum_bilgisi = "Konum bilgisi yok"
    
    konum_bilgisi = fields.Char(string='Konum Bilgisi', compute='_compute_konum_bilgisi', store=True)
