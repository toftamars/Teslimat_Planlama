"""Teslimat Ana Sayfa Gün Modeli - Uygun günler listesi için."""
from datetime import date
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TeslimatAnaSayfaGun(models.TransientModel):
    """Teslimat Ana Sayfa Gün - Uygun günler listesi."""

    _name = "teslimat.ana.sayfa.gun"
    _description = "Teslimat Ana Sayfa - Uygun Günler"
    _order = "tarih"

    ana_sayfa_id = fields.Many2one(
        "teslimat.ana.sayfa", string="Ana Sayfa", required=True, ondelete="cascade"
    )
    tarih = fields.Date(string="Tarih", required=True)
    tarih_button = fields.Char(string="📅 Tarih", compute="_compute_tarih_button")
    gun_adi = fields.Char(string="Gün Adı", required=True)
    teslimat_sayisi = fields.Integer(string="Teslimat Sayısı", default=0)
    toplam_kapasite = fields.Integer(string="Toplam Kapasite", default=0)
    kalan_kapasite = fields.Integer(string="Kalan Kapasite", default=0)
    durum_text = fields.Char(string="Durum")

    @api.depends("tarih")
    def _compute_tarih_button(self):
        """Tarih buton label'ı oluştur."""
        for record in self:
            if record.tarih:
                record.tarih_button = record.tarih.strftime("%d.%m.%Y")
            else:
                record.tarih_button = ""

    @api.model
    def default_get(self, fields_list):
        """Form view açıldığında context'ten ana_sayfa_id al."""
        res = super().default_get(fields_list)
        
        # Context'ten ana_sayfa_id al
        if 'default_ana_sayfa_id' in self.env.context:
            res['ana_sayfa_id'] = self.env.context['default_ana_sayfa_id']
        
        return res

    def action_teslimat_olustur(self) -> dict:
        """Seçilen gün için teslimat belgesi wizard'ını aç."""
        self.ensure_one()

        if not self.ana_sayfa_id.arac_id:
            raise UserError(_("Araç seçimi gereklidir."))

        if not self.ana_sayfa_id.ilce_id:
            raise UserError(_("İlçe seçimi gereklidir."))

        # Wizard'ı aç
        context = {
            "default_teslimat_tarihi": self.tarih,
            "default_arac_id": self.ana_sayfa_id.arac_id.id,
            "default_ilce_id": self.ana_sayfa_id.ilce_id.id,
        }

        return {
            "name": _("Teslimat Belgesi Oluştur"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
