from . import models
from . import wizards
from odoo import api, SUPERUSER_ID


def pre_init_hook(cr):
    """Pre-install/upgrade hook: Eski model referanslarını temizle (modeller yüklenmeden önce)."""
    import logging
    _logger = logging.getLogger(__name__)

    try:
        # Eski teslimat.arac.ilce.sync.wizard modelini temizle
        _logger.info("🧹 Eski wizard modeli temizleniyor...")

        # Önce tüm ilişkili kayıtları bul ve geçici olarak sakla
        cr.execute("""
            SELECT id FROM ir_model WHERE model = 'teslimat.arac.ilce.sync.wizard'
        """)
        old_model_ids = [row[0] for row in cr.fetchall()]

        if old_model_ids:
            _logger.info("Bulunan eski model ID'leri: %s", old_model_ids)

            # ir_model_constraint kayıtlarını sil
            cr.execute("""
                DELETE FROM ir_model_constraint
                WHERE model IN %s
            """, (tuple(old_model_ids),))
            deleted_constraints = cr.rowcount
            if deleted_constraints:
                _logger.info("✓ ir_model_constraint silindi: %s kayıt", deleted_constraints)

            # ir_model_relation kayıtlarını sil
            cr.execute("""
                DELETE FROM ir_model_relation
                WHERE model IN %s
            """, (tuple(old_model_ids),))
            deleted_relations = cr.rowcount
            if deleted_relations:
                _logger.info("✓ ir_model_relation silindi: %s kayıt", deleted_relations)

        # ir_model_data kayıtlarını sil (hem model hem de name ile)
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'teslimat_planlama'
            AND (model = 'teslimat.arac.ilce.sync.wizard' OR name LIKE '%sync_wizard%' OR name LIKE '%arac_ilce_sync%')
        """)
        deleted_data = cr.rowcount
        if deleted_data:
            _logger.info("✓ ir_model_data (sync.wizard) silindi: %s kayıt", deleted_data)

        # res_id'ye göre de sil (eğer model_id referansı varsa)
        if old_model_ids:
            cr.execute("""
                DELETE FROM ir_model_data
                WHERE model = 'ir.model' AND res_id IN %s
            """, (tuple(old_model_ids),))
            deleted_model_refs = cr.rowcount
            if deleted_model_refs:
                _logger.info("✓ ir_model referansları silindi: %s kayıt", deleted_model_refs)

        # ir_model_fields_selection tablosundaki referansları ÖNCE temizle (Odoo 15+)
        cr.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name='ir_model_fields_selection'
        """)
        if cr.fetchone():
            cr.execute("""
                DELETE FROM ir_model_fields_selection
                WHERE field_id IN (
                    SELECT id FROM ir_model_fields
                    WHERE model = 'teslimat.arac.ilce.sync.wizard'
                )
            """)
            deleted_selections = cr.rowcount
            if deleted_selections:
                _logger.info("✓ ir_model_fields_selection kayıtları silindi: %s kayıt", deleted_selections)

        cr.execute("""
            DELETE FROM ir_model_fields
            WHERE model = 'teslimat.arac.ilce.sync.wizard'
        """)
        deleted_fields = cr.rowcount
        if deleted_fields:
            _logger.info("✓ ir_model_fields (sync.wizard) silindi: %s kayıt", deleted_fields)

        cr.execute("""
            DELETE FROM ir_model
            WHERE model = 'teslimat.arac.ilce.sync.wizard'
        """)
        deleted_model = cr.rowcount
        if deleted_model:
            _logger.info("✓ ir_model (sync.wizard) silindi: %s kayıt", deleted_model)

        cr.execute("""
            DELETE FROM ir_model_access
            WHERE model_id NOT IN (SELECT id FROM ir_model)
        """)
        deleted_access = cr.rowcount
        if deleted_access:
            _logger.info("✓ Orphan access rights silindi: %s kayıt", deleted_access)

        cr.commit()
        _logger.info("✅ Eski wizard modeli başarıyla temizlendi")

    except Exception as e:
        cr.rollback()
        _logger.warning("⚠️ Eski model temizleme hatası (ignored): %s", e)


def post_init_hook(cr, registry):
    """Post-install/upgrade hook: Eski model referanslarını temizle."""
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        # SQL direkt ile temizle (ORM çalışmadan önce)

        # 1. Eski teslimat.planlama.akilli modelini temizle
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'teslimat_planlama'
            AND model = 'teslimat.planlama.akilli'
        """)
        deleted_data = cr.rowcount
        if deleted_data:
            _logger.info("Eski ir_model_data (akilli) kayıtları silindi: %s", deleted_data)

        # 2. Eski teslimat.arac.ilce.sync.wizard modelini temizle
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'teslimat_planlama'
            AND model = 'teslimat.arac.ilce.sync.wizard'
        """)
        deleted_data_wizard = cr.rowcount
        if deleted_data_wizard:
            _logger.info("Eski ir_model_data (sync.wizard) kayıtları silindi: %s", deleted_data_wizard)
        
        # Eski ir.model kayıtlarını sil
        cr.execute("""
            DELETE FROM ir_model
            WHERE model IN ('teslimat.planlama.akilli', 'teslimat.arac.ilce.sync.wizard')
        """)
        deleted_model = cr.rowcount
        if deleted_model:
            _logger.info("Eski ir_model kayıtları silindi: %s", deleted_model)
        
        # Eski ir.model.fields kayıtlarını sil (model referansı olan field'lar)
        cr.execute("""
            DELETE FROM ir_model_fields
            WHERE model IN ('teslimat.planlama.akilli', 'teslimat.arac.ilce.sync.wizard')
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
            
            # Tüm internal user'lara Teslimat Kullanıcısı grubunu ata
            try:
                _logger.info("Teslimat grupları atanıyor...")
                teslimat_user_group = env.ref('teslimat_planlama.group_teslimat_user')
                internal_users = env['res.users'].search([
                    ('share', '=', False),  # Internal users only
                    ('active', '=', True)
                ])
                
                for user in internal_users:
                    if teslimat_user_group.id not in user.groups_id.ids:
                        user.write({'groups_id': [(4, teslimat_user_group.id)]})
                
                cr.commit()
                _logger.info("✓ %s kullanıcıya Teslimat Kullanıcısı grubu atandı", len(internal_users))
            except Exception as e:
                _logger.warning("Grup atama hatası (ignored): %s", e)
                
        except Exception as e:
            _logger.warning("Haftalık program uygulama hatası (ignored): %s", e)
             
    except Exception as e:
        cr.rollback()
        _logger.warning("Eski model temizleme hatası (ignored): %s", e)

