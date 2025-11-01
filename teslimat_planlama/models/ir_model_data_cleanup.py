"""IR Model Data Cleanup - Eski model referanslarını temizle."""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrModelData(models.Model):
    """IR Model Data Inherit - Cleanup fonksiyonu."""

    _inherit = "ir.model.data"

    def _process_ondelete(self):
        """Override: Eski model referanslarını handle et."""
        # Eski teslimat.planlama.akilli modeli için özel handling
        for record in self:
            if record.model == "teslimat.planlama.akilli":
                # Model yoksa, sadece kaydı sil, model kontrolü yapma
                _logger.warning(
                    "Eski teslimat.planlama.akilli model referansı atlanıyor: %s", record.name
                )
                continue
        # Diğer kayıtlar için normal işlem
        return super(IrModelData, self)._process_ondelete()

    @api.model
    def _cleanup_old_teslimat_planlama_akilli(self) -> None:
        """Eski teslimat.planlama.akilli model referanslarını temizle."""
        try:
            # Eski ir.model.data kayıtlarını bul ve sil
            old_data = self.search(
                [
                    ("module", "=", "teslimat_planlama"),
                    ("model", "=", "teslimat.planlama.akilli"),
                ]
            )
            if old_data:
                _logger.info(
                    "Eski teslimat.planlama.akilli model referansları temizleniyor: %s kayıt",
                    len(old_data),
                )
                # _process_ondelete'yi bypass et
                old_data.with_context(skip_process_ondelete=True).unlink()

            # Eski ir.model kayıtlarını bul ve sil
            old_model = self.env["ir.model"].search(
                [("model", "=", "teslimat.planlama.akilli")]
            )
            if old_model:
                _logger.info(
                    "Eski teslimat.planlama.akilli model tanımı temizleniyor: %s kayıt",
                    len(old_model),
                )
                old_model.unlink()
        except Exception as e:
            _logger.warning("Eski model temizleme hatası (ignored): %s", e)

