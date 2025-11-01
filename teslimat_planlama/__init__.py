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
        
        # Eski ir.model kayıtlarını sil
        cr.execute("""
            DELETE FROM ir_model 
            WHERE model = 'teslimat.planlama.akilli'
        """)
        
        cr.commit()
        _logger.info("Eski teslimat.planlama.akilli model referansları temizlendi")
    except Exception as e:
        cr.rollback()
        _logger.warning("Eski model temizleme hatası (ignored): %s", e)

