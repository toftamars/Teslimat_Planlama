"""Teslimat Ana Sayfa Tarih Modeli."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TeslimatAnaSayfaTarih(models.TransientModel):
    """Teslimat Ana Sayfa Tarih.

    Transient model - Tarih bazlı kapasite gösterimi için.
    """

    _name = "teslimat.ana.sayfa.tarih"
    _description = "Teslimat Ana Sayfa Tarih"

    ana_sayfa_id = fields.Many2one(
        "teslimat.ana.sayfa", string="Ana Sayfa", required=True, ondelete="cascade"
    )
    tarih = fields.Date(string="Tarih", required=True)
    gun_adi = fields.Char(string="Gün Adı", required=True)
    teslimat_sayisi = fields.Integer(string="Teslimat Sayısı", default=0)
    toplam_kapasite = fields.Integer(string="Toplam Kapasite", default=0)
    kalan_kapasite = fields.Integer(string="Kalan Kapasite", default=0)
    durum = fields.Selection(
        [
            ("bos", "Boş"),
            ("dolu_yakin", "Dolu Yakın"),
            ("dolu", "Dolu"),
        ],
        string="Durum",
    )
    durum_text = fields.Char(string="Durum Metni")
    durum_icon = fields.Char(string="Durum İkonu")

    def action_teslimat_olustur_from_tarih(self) -> dict:
        """Seçilen tarih için teslimat belgesi oluştur ve aç.

        Returns:
            dict: Teslimat belgesi form view action'ı
        """
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
            # musteri_id sonra doldurulacak
        })

        # Oluşturulan teslimat belgesini aç
        return {
            "name": _("Teslimat Belgesi"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi",
            "res_id": teslimat_belgesi.id,
            "view_mode": "form",
            "target": "current",  # Mevcut sayfada aç
        }

