from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class TeslimatHizliOlusturWizard(models.TransientModel):
    _name = 'teslimat.hizli.olustur.wizard'
    _description = 'Hızlı Teslimat Belgesi Oluştur'
    
    tarih = fields.Date(string='Teslimat Tarihi', required=True)
    arac_id = fields.Many2one('teslimat.arac', string='Araç')
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe')
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Context'ten değerleri al
        context = self.env.context
        active_model = context.get('active_model')
        active_id = context.get('active_id')
        
        _logger.info(f"WIZARD DEFAULT_GET - Active Model: {active_model}, Active ID: {active_id}")
        
        if active_model == 'teslimat.ana.sayfa.tarih' and active_id:
            tarih_record = self.env['teslimat.ana.sayfa.tarih'].browse(active_id)
            if tarih_record.exists():
                res['tarih'] = tarih_record.tarih
                if tarih_record.ana_sayfa_id:
                    if tarih_record.ana_sayfa_id.arac_id:
                        res['arac_id'] = tarih_record.ana_sayfa_id.arac_id.id
                    if tarih_record.ana_sayfa_id.ilce_id:
                        res['ilce_id'] = tarih_record.ana_sayfa_id.ilce_id.id
                        
                _logger.info(f"WIZARD - Tarih: {res.get('tarih')}, Araç: {res.get('arac_id')}, İlçe: {res.get('ilce_id')}")
        
        return res
    
    def action_olustur(self):
        """Teslimat belgesi oluştur"""
        self.ensure_one()
        
        vals = {
            'teslimat_tarihi': self.tarih,
            'durum': 'taslak'
        }
        
        if self.arac_id:
            vals['arac_id'] = self.arac_id.id
        if self.ilce_id:
            vals['ilce_id'] = self.ilce_id.id
            
        _logger.info(f"TESLİMAT BELGESİ OLUŞTURULUYOR - Vals: {vals}")
        
        # Belgeyi oluştur
        teslimat_belgesi = self.env['teslimat.belgesi'].create(vals)
        
        _logger.info(f"TESLİMAT BELGESİ OLUŞTURULDU - ID: {teslimat_belgesi.id}, No: {teslimat_belgesi.name}")
        
        # Form'u aç
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teslimat Belgesi',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat_belgesi.id,
            'view_mode': 'form',
            'target': 'current',
        }
