from . import models
from . import wizards
from odoo import api, SUPERUSER_ID


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
        
        # 1. Eski stil (column 'selection' in ir_model_fields) - Odoo 14 öncesi veya bazı migration durumları
        cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='ir_model_fields' AND column_name='selection'")
        if cr.fetchone():
            cr.execute("""
                UPDATE ir_model_fields 
                SET selection = REPLACE(selection, 'teslimat.planlama.akilli,', '')
                WHERE ttype = 'selection' 
                AND selection LIKE '%teslimat.planlama.akilli%'
            """)
            updated_fields = cr.rowcount
            if updated_fields:
                _logger.info("Selection field'ları güncellendi (legacy): %s", updated_fields)

        # 2. Yeni stil (table 'ir_model_fields_selection') - Odoo 15 ve sonrası
        # Selection değerlerini içeren kayıtları sil
        cr.execute("""
            DELETE FROM ir_model_fields_selection 
            WHERE value LIKE '%teslimat.planlama.akilli%'
        """)
        deleted_selections = cr.rowcount
        if deleted_selections:
             _logger.info("ir_model_fields_selection kayıtları silindi: %s", deleted_selections)
        
        cr.commit()
        _logger.info("Eski teslimat.planlama.akilli model referansları temizlendi")
        
        # NOT: İlçe ve araç eşleştirmeleri artık kod seviyesinde (create/write) yapılıyor
        # Otomatik hook'lara gerek yok
             
    except Exception as e:
        cr.rollback()
        _logger.warning("Eski model temizleme hatası (ignored): %s", e)

