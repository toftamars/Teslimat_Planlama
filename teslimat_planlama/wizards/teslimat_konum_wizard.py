"""Sürücü Konum Güncelleme Wizard'ı."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TeslimatKonumWizard(models.TransientModel):
    """Sürücü Konum Güncelleme Wizard'ı.

    Sürücüler teslimat belgesi için konum güncelleme yapabilir.
    """

    _name = "teslimat.konum.wizard"
    _description = "Sürücü Konum Güncelleme Wizard'ı"

    teslimat_belgesi_id = fields.Many2one(
        "teslimat.belgesi",
        string="Teslimat Belgesi",
        required=True,
        readonly=True,
    )
    enlem = fields.Float(string="Enlem", required=True)
    boylam = fields.Float(string="Boylam", required=True)

    @api.onchange("enlem", "boylam")
    def _onchange_konum(self) -> None:
        """Konum değiştiğinde validasyon yap."""
        if self.enlem and self.boylam:
            # Basit validasyon: İstanbul koordinatları aralığı
            if not (40.5 <= self.enlem <= 41.3):
                return {
                    "warning": {
                        "title": _("Koordinat Uyarısı"),
                        "message": _(
                            "Enlem değeri İstanbul koordinatları dışında görünüyor."
                        ),
                    }
                }
            if not (27.5 <= self.boylam <= 29.9):
                return {
                    "warning": {
                        "title": _("Koordinat Uyarısı"),
                        "message": _(
                            "Boylam değeri İstanbul koordinatları dışında görünüyor."
                        ),
                    }
                }

    def action_guncelle(self) -> dict:
        """Konumu güncelle ve ana kayda dön.

        Returns:
            dict: Teslimat belgesi form view'ı
        """
        self.ensure_one()

        # Validasyonlar
        if not self.enlem or not self.boylam:
            raise UserError(_("Enlem ve boylam değerleri zorunludur."))

        # Konumu güncelle
        self.teslimat_belgesi_id.write(
            {
                "enlem": self.enlem,
                "boylam": self.boylam,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Teslimat Belgesi"),
            "res_model": "teslimat.belgesi",
            "res_id": self.teslimat_belgesi_id.id,
            "view_mode": "form",
            "target": "current",
        }

