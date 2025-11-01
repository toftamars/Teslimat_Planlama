from . import models
from . import wizards


def post_init_hook(cr, registry):
    """Post-install/upgrade hook: Eski model referanslarını temizle."""
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        # SQL direkt ile temizle (ORM çalışmadan önce)
        # Eski ir.model.data kayıtlarını sil
        cr.execute("""
            DELETE FROM ir_model_data 
            WHERE module = 'teslimat_planlama' 
            AND model = 'teslimat.planlama.akilli'
        """)
        deleted_data = cr.rowcount
        if deleted_data:
            _logger.info("Eski ir_model_data kayıtları silindi: %s", deleted_data)
        
        # Eski ir.model kayıtlarını sil
        cr.execute("""
            DELETE FROM ir_model 
            WHERE model = 'teslimat.planlama.akilli'
        """)
        deleted_model = cr.rowcount
        if deleted_model:
            _logger.info("Eski ir_model kayıtları silindi: %s", deleted_model)
        
        # Eski ir.model.fields kayıtlarını sil (model referansı olan field'lar)
        cr.execute("""
            DELETE FROM ir_model_fields 
            WHERE model = 'teslimat.planlama.akilli'
        """)
        deleted_fields = cr.rowcount
        if deleted_fields:
            _logger.info("Eski ir_model_fields kayıtları silindi: %s", deleted_fields)
        
        # Selection field'larındaki referansları temizle
        # ir_model_fields tablosunda selection tipindeki field'ları kontrol et
        cr.execute("""
            UPDATE ir_model_fields 
            SET selection = REPLACE(selection, 'teslimat.planlama.akilli,', '')
            WHERE ttype = 'selection' 
            AND selection LIKE '%teslimat.planlama.akilli%'
        """)
        updated_fields = cr.rowcount
        if updated_fields:
            _logger.info("Selection field'ları güncellendi: %s", updated_fields)
        
        cr.commit()
        _logger.info("Eski teslimat.planlama.akilli model referansları temizlendi")
    except Exception as e:
        cr.rollback()
        _logger.warning("Eski model temizleme hatası (ignored): %s", e)

