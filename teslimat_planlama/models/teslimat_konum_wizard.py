from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class TeslimatKonumWizard(models.TransientModel):
    _name = 'teslimat.konum.wizard'
    _description = 'Teslimat Konum Güncelleme Wizard'
    
    teslimat_id = fields.Many2one('teslimat.belgesi', string='Teslimat', required=True)
    current_latitude = fields.Float(string='Mevcut Enlem', digits=(10, 8), readonly=True)
    current_longitude = fields.Float(string='Mevcut Boylam', digits=(11, 8), readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        active_id = self.env.context.get('active_id')
        if active_id:
            teslimat = self.env['teslimat.belgesi'].browse(active_id)
            res['teslimat_id'] = teslimat.id
            res['current_latitude'] = teslimat.surucu_latitude
            res['current_longitude'] = teslimat.surucu_longitude
            
        return res
    
    def action_get_location(self):
        """Tarayıcıdan konum al ve güncelle"""
        return {
            'type': 'ir.actions.client',
            'tag': 'teslimat_get_location',
            'params': {
                'teslimat_id': self.teslimat_id.id,
                'wizard_id': self.id
            }
        }
