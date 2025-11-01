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
        
        # Her kayıt için ayrı ayrı işlem yap - selection field kontrolü sırasında hata olabilir
        for record in records_to_process:
            try:
                # Selection field'ları kontrol et - model registry'de olmayan modeller için hata olabilir
                selection_fields = record.field_id.filtered(lambda f: f.ttype == 'selection')
                for field in selection_fields:
                    if field.selection_field_id and field.selection_field_id.model:
                        model_name = field.selection_field_id.model
                        # Model registry'de yoksa atla
                        if model_name not in self.env.registry:
                            _logger.warning(
                                "Selection field model'i registry'de yok, atlanıyor: %s (field: %s)",
                                model_name,
                                field.name,
                            )
                            continue
            except Exception as field_error:
                _logger.warning(
                    "Field kontrolü sırasında hata (ignored): %s", field_error
                )
        
        # Selection field kontrolü sırasında model registry hatası olabilir
        # Bu durumda KeyError yakalayıp ignore et
        try:
            return super(IrModel, records_to_process)._process_ondelete()
        except KeyError as e:
            # Model registry'de bulunamayan modeller için KeyError
            # Eski teslimat.planlama.akilli veya selection field referansları için
            error_str = str(e)
            _logger.warning(
                "Model registry hatası (KeyError), kayıtlar güvenli şekilde atlanıyor: %s",
                error_str,
            )
            return None
        except Exception as e:
            # Diğer beklenmeyen hatalar için tekrar fırlat
            error_str = str(e)
            if "teslimat.planlama.akilli" in error_str:
                _logger.warning(
                    "teslimat.planlama.akilli hatası, kayıtlar güvenli şekilde atlanıyor: %s",
                    error_str,
                )
                return None
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

