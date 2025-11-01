"""Teslimat Şehir Yönetimi Modeli."""
import logging
from typing import Optional

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TeslimatSehir(models.Model):
    """Teslimat Şehir Yönetimi.

    Şehirler ve teslimat bilgilerini yönetir.
    """

    _name = "teslimat.sehir"
    _description = "Teslimat Şehir Yönetimi"
    _order = "name"

    name = fields.Char(string="Şehir Adı", required=True)
    ulke_id = fields.Many2one(
        "res.country",
        string="Ülke",
        default=lambda self: self.env.ref("base.tr", raise_if_not_found=False),
    )
    aktif = fields.Boolean(string="Aktif", default=True)

    # İlçe İlişkisi
    ilce_ids = fields.One2many("teslimat.ilce", "sehir_id", string="İlçeler")

    # Teslimat Bilgileri
    teslimat_aktif = fields.Boolean(string="Teslimat Aktif", default=True)
    varsayilan_teslimat_suresi = fields.Integer(
        string="Varsayılan Teslimat Süresi (Gün)", default=1
    )

    @api.model
    def get_istanbul(self) -> "TeslimatSehir":
        """İstanbul şehrini getir veya oluştur.

        Returns:
            TeslimatSehir: İstanbul şehir kaydı
        """
        istanbul = self.search([("name", "ilike", "İstanbul")], limit=1)
        if not istanbul:
            istanbul = self.create(
                {
                    "name": "İstanbul",
                    "ulke_id": self.env.ref("base.tr", raise_if_not_found=False).id,
                    "teslimat_aktif": True,
                    "varsayilan_teslimat_suresi": 1,
                }
            )
        return istanbul

