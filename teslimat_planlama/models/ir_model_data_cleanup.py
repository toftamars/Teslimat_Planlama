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
        # Bu model kayıtları için _process_ondelete çalıştırma (model yok)
        records_to_skip = self.filtered(lambda r: r.model == "teslimat.planlama.akilli")
        if records_to_skip:
            _logger.warning(
                "Eski teslimat.planlama.akilli model referansları atlanıyor: %s kayıt",
                len(records_to_skip),
            )
        
        # Sadece diğer kayıtlar için normal işlem yap
        records_to_process = self - records_to_skip
        if records_to_process:
            return super(IrModelData, records_to_process)._process_ondelete()
        return None


class IrModel(models.Model):
    """IR Model Inherit - Cleanup fonksiyonu."""

    _inherit = "ir.model"

    def _process_ondelete(self):
        """Override: Eski model referanslarını handle et."""
        # Eski teslimat.planlama.akilli modeli için özel handling
        # Bu model kayıtları için _process_ondelete çalıştırma (model registry'de yok)
        records_to_skip = self.filtered(lambda r: r.model == "teslimat.planlama.akilli")
        if records_to_skip:
            _logger.warning(
                "Eski teslimat.planlama.akilli model kaydı atlanıyor: %s kayıt",
                len(records_to_skip),
            )
        
        # Sadece diğer kayıtlar için normal işlem yap
        records_to_process = self - records_to_skip
        if not records_to_process:
            return None
        
        # Selection field kontrolü sırasında model registry hatası olabilir
        # Bu durumda KeyError yakalayıp ignore et
        try:
            return super(IrModel, records_to_process)._process_ondelete()
        except KeyError as e:
            # Model registry'de bulunamayan modeller için KeyError
            # Eski teslimat.planlama.akilli veya selection field referansları için
            error_str = str(e)
            if "teslimat.planlama.akilli" in error_str:
                _logger.warning(
                    "Model registry'de bulunamadı (teslimat.planlama.akilli), kayıt atlanıyor: %s",
                    error_str,
                )
                return None
            # Diğer KeyError'lar için de kontrol et (selection field referansları)
            # Bu durumda da kayıtları güvenli şekilde atlayalım
            _logger.warning(
                "Model registry hatası, kayıtlar güvenli şekilde atlanıyor: %s", error_str
            )
            return None
        except Exception as e:
            # Diğer beklenmeyen hatalar için tekrar fırlat
            _logger.error("_process_ondelete sırasında beklenmeyen hata: %s", e)
            raise

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

