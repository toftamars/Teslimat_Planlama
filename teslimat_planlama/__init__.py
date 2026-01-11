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
        
        # İlçeleri ve haftalık programı otomatik yükle
        try:
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            # İstanbul ilçelerini oluştur (yoksa)
            ilce_model = env["teslimat.ilce"]
            istanbul = env["res.country.state"].search([
                ("country_id.code", "=", "TR"),
                ("name", "ilike", "istanbul")
            ], limit=1)
            
            if istanbul:
                # İlçe sayısını kontrol et
                ilce_sayisi = ilce_model.search_count([("state_id", "=", istanbul.id)])
                
                if ilce_sayisi < 10:  # Çok az ilçe varsa yükle
                    _logger.info("İstanbul ilçeleri yükleniyor...")
                    ilce_model.create_istanbul_districts_simple()
                    _logger.info("✓ İstanbul ilçeleri yüklendi")
                
                # Haftalık programı ZORUNLU uygula
                _logger.info("Haftalık program uygulanıyor...")
                ilce_model.apply_weekly_schedule()
                cr.commit()
                _logger.info("✓ Haftalık program uygulandı (gün-ilçe eşleştirmeleri oluşturuldu)")
            else:
                _logger.warning("İstanbul ili bulunamadı, haftalık program uygulanamadı")
                
        except Exception as e:
            _logger.warning("Haftalık program uygulama hatası (ignored): %s", e)
             
    except Exception as e:
        cr.rollback()
        _logger.warning("Eski model temizleme hatası (ignored): %s", e)

