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
    gun_adi = fields.Char(string="Gün Adı", required=True)
    teslimat_sayisi = fields.Integer(string="Teslimat Sayısı", default=0)
    toplam_kapasite = fields.Integer(string="Toplam Kapasite", default=0)
    kalan_kapasite = fields.Integer(string="Kalan Kapasite", default=0)
    durum_text = fields.Char(string="Durum")

    def action_teslimat_olustur(self) -> dict:
        """Seçilen gün için teslimat belgesi oluştur ve aç."""
        self.ensure_one()

        if not self.ana_sayfa_id.arac_id:
            raise UserError(_("Araç seçimi gereklidir."))

        if not self.ana_sayfa_id.ilce_id:
            raise UserError(_("İlçe seçimi gereklidir."))

        # Yeni teslimat belgesi oluştur
        teslimat_belgesi = self.env["teslimat.belgesi"].create({
            "teslimat_tarihi": self.tarih,
            "arac_id": self.ana_sayfa_id.arac_id.id,
            "ilce_id": self.ana_sayfa_id.ilce_id.id,
        })

        # Oluşturulan teslimat belgesini aç
        return {
            "name": _("Teslimat Belgesi"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi",
            "res_id": teslimat_belgesi.id,
            "view_mode": "form",
            "target": "current",
        }
