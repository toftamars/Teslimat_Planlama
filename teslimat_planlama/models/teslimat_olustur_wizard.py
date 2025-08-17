from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError, UserError


class TeslimatOlusturWizard(models.TransientModel):
    _name = 'teslimat.olustur.wizard'
    _description = 'Teslimat Belgesi Oluşturma Sihirbazı (Geçici - Kaldırılacak)'

    # Geçici alanlar - sadece model tanımı için
    name = fields.Char('Geçici Alan', default='Geçici Model - Kaldırılacak')
    
    def action_gecici(self):
        """Geçici action - sadece model tanımı için"""
        return True
