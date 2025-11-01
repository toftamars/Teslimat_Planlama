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
        """Override: Eski model referanslarını handle et.
        
        Odoo'nun base _process_ondelete metodu selection field'ları kontrol ederken
        model registry'ye erişmeye çalışır. Eğer model registry'de yoksa KeyError verir.
        Bu metod, eski teslimat.planlama.akilli modeli ve diğer silinmiş modeller için
        bu hatayı önler.
        """
        # Eski teslimat.planlama.akilli modeli için özel handling
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
        
        # Base metod selection field kontrolü yaparken model registry'ye erişir
        # Eğer model yoksa KeyError verir. Bu durumu handle etmek için
        # her kayıt için ayrı ayrı deneme yapıyoruz
        processed_count = 0
        skipped_count = 0
        
        for record in records_to_process:
            try:
                # Selection field'ları kontrol et - sadece registry'de olan modeller için
                selection_fields = record.field_id.filtered(lambda f: f.ttype == 'selection')
                skip_record = False
                
                for field in selection_fields:
                    try:
                        # selection_field_id kontrolü - model registry'de yoksa hata verebilir
                        if hasattr(field, 'selection_field_id') and field.selection_field_id:
                            model_name = field.selection_field_id.model
                            # Model registry'de yoksa bu kaydı atla
                            if model_name and model_name not in self.env.registry:
                                _logger.warning(
                                    "Selection field model'i registry'de yok, kayıt atlanıyor: %s (field: %s, record: %s)",
                                    model_name,
                                    field.name,
                                    record.model,
                                )
                                skip_record = True
                                break
                    except (KeyError, AttributeError) as field_error:
                        # Model registry hatası veya field yok
                        _logger.warning(
                            "Selection field kontrolü sırasında hata (ignored): %s (record: %s)",
                            field_error,
                            record.model,
                        )
                        skip_record = True
                        break
                
                if skip_record:
                    skipped_count += 1
                    continue
                
                # Kayıt güvenli görünüyor, tek kayıt için base metodu çağır
                try:
                    super(IrModel, record)._process_ondelete()
                    processed_count += 1
                except KeyError as ke:
                    # Model registry hatası - bu kaydı atla
                    _logger.warning(
                        "Model registry hatası, kayıt atlanıyor: %s (model: %s)",
                        ke,
                        record.model,
                    )
                    skipped_count += 1
                    continue
                    
            except Exception as e:
                # Beklenmeyen hatalar için log'la ama devam et
                error_str = str(e)
                if "teslimat.planlama.akilli" in error_str:
                    _logger.warning(
                        "teslimat.planlama.akilli hatası, kayıt atlanıyor: %s",
                        error_str,
                    )
                    skipped_count += 1
                else:
                    _logger.error(
                        "_process_ondelete sırasında beklenmeyen hata (kayıt atlanıyor): %s (model: %s)",
                        e,
                        record.model,
                    )
                    skipped_count += 1
        
        if processed_count > 0:
            _logger.info(
                "_process_ondelete tamamlandı: %s kayıt işlendi, %s kayıt atlandı",
                processed_count,
                skipped_count,
            )
        
        return None

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

