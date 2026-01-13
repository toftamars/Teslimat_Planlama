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
    doluluk_yuzdesi = fields.Float(string="Doluluk %", compute="_compute_doluluk_yuzdesi", store=False)
    durum_text = fields.Char(string="Durum")
    tarih_str = fields.Char(string="Tarih", compute="_compute_tarih_str")

    @api.depends("teslimat_sayisi", "toplam_kapasite")
    def _compute_doluluk_yuzdesi(self):
        """Doluluk yüzdesini hesapla."""
        for rec in self:
            if rec.toplam_kapasite > 0:
                rec.doluluk_yuzdesi = (rec.teslimat_sayisi / rec.toplam_kapasite) * 100
            else:
                rec.doluluk_yuzdesi = 0.0

    @api.depends("tarih")
    def _compute_tarih_str(self):
        """Tarih field'ını formatlanmış string olarak hesapla."""
        gun_isimleri = {
            0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"
        }
        for rec in self:
            if rec.tarih:
                gun = gun_isimleri.get(rec.tarih.weekday(), "")
                rec.tarih_str = f"{rec.tarih.strftime('%d.%m.%Y')} {gun}"
            else:
                rec.tarih_str = "-"

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
