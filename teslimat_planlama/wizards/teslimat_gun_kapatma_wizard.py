"""Teslimat Günü Kapatma Wizard'ı."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TeslimatGunKapatmaWizard(models.TransientModel):
    """Teslimat Günü Kapatma Wizard'ı.

    Yöneticiler tarafından günleri geçici olarak kapatmak için.
    """

    _name = "teslimat.gun.kapatma.wizard"
    _description = "Teslimat Günü Kapatma Wizard'ı"

    gun_id = fields.Many2one(
        "teslimat.gun", string="Gün", required=True, readonly=True
    )
    sure_siz = fields.Boolean(
        string="Süresiz Kapatma",
        default=False,
        help="İşaretlenirse kapatma bitiş tarihi girilmez",
    )
    kapatma_baslangic = fields.Date(string="Kapatma Başlangıç", required=True)
    kapatma_bitis = fields.Date(string="Kapatma Bitiş")
    kapatma_sebebi = fields.Text(string="Kapatma Sebebi", required=True)

    @api.onchange("sure_siz")
    def _onchange_sure_siz(self) -> None:
        """Süresiz kapatma seçildiğinde bitiş tarihini temizle."""
        if self.sure_siz:
            self.kapatma_bitis = False

    @api.onchange("kapatma_baslangic", "kapatma_bitis")
    def _onchange_tarihler(self) -> None:
        """Tarih kontrolleri."""
        if self.kapatma_baslangic and self.kapatma_bitis:
            if self.kapatma_baslangic > self.kapatma_bitis:
                return {
                    "warning": {
                        "title": _("Tarih Hatası"),
                        "message": _(
                            "Bitiş tarihi başlangıç tarihinden önce olamaz."
                        ),
                    }
                }

    def action_onayla(self) -> dict:
        """Günü kapat ve ana kayda dön.

        Returns:
            dict: Ana kayıt form view'ı
        """
        self.ensure_one()

        # Validasyonlar
        if not self.kapatma_sebebi:
            raise ValidationError(_("Kapatma sebebi zorunludur."))

        if not self.sure_siz and not self.kapatma_bitis:
            raise ValidationError(
                _("Süresiz kapatma seçilmediyse bitiş tarihi zorunludur.")
            )

        # Günü kapat
        vals = {
            "gecici_kapatma": True,
            "kapatma_sebebi": self.kapatma_sebebi,
            "kapatma_baslangic": self.kapatma_baslangic,
            "kapatma_bitis": self.kapatma_bitis if not self.sure_siz else False,
        }

        self.gun_id.write(vals)

        return {
            "type": "ir.actions.act_window",
            "name": _("Teslimat Günü"),
            "res_model": "teslimat.gun",
            "res_id": self.gun_id.id,
            "view_mode": "form",
            "target": "current",
        }

