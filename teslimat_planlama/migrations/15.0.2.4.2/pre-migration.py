# -*- coding: utf-8 -*-
"""Pre-migration: kaldırılan teslimat.planlama + teslimat.transfer metadata temizliği.

teslimat.planlama ve teslimat.transfer modelleri kaldırıldı (yetim/yarım alt-sistem).
Odoo upgrade'in sonundaki `_process_end` adımı, bu modellere ait artık
ir.model.fields / ir.model.fields.selection kayıtlarını silerken `_process_ondelete`
içinde modeli registry'den yüklemeye çalışıyor (Selection 'durum' alanı yüzünden) ve
`KeyError: 'teslimat.transfer'` ile upgrade'i bloke ediyordu.

Bu script, model yüklenmeden önce ilgili metadata'yı güvenle (savepoint'li) siler;
böylece `_process_end` temizleyecek bir şey bulamaz ve hata oluşmaz.
"""
import logging

_logger = logging.getLogger(__name__)

REMOVED_MODELS = ("teslimat.planlama", "teslimat.transfer")


def _safe(cr, sql, params=None):
    """Tek bir adımı savepoint ile çalıştır; hata olursa o adımı atlayıp devam et."""
    cr.execute("SAVEPOINT teslimat_premig")
    try:
        cr.execute(sql, params or ())
        cr.execute("RELEASE SAVEPOINT teslimat_premig")
    except Exception as exc:  # noqa: BLE001 - migration robustluğu için bilinçli geniş yakalama
        cr.execute("ROLLBACK TO SAVEPOINT teslimat_premig")
        _logger.warning("teslimat pre-migration adımı atlandı: %s | %s", sql.split("\n")[0].strip(), exc)


def migrate(cr, version):
    if not version:
        return

    _logger.info("teslimat_planlama 15.0.2.4.2 pre-migration: kaldırılan modellerin metadata temizliği")

    # Önce m2m ilişki (rel) tablolarının adlarını al ve fiziksel olarak düşür.
    cr.execute("SAVEPOINT teslimat_premig")
    rel_names = []
    try:
        cr.execute(
            "SELECT name FROM ir_model_relation "
            "WHERE model IN (SELECT id FROM ir_model WHERE model IN %s)",
            (REMOVED_MODELS,),
        )
        rel_names = [r[0] for r in cr.fetchall()]
        cr.execute("RELEASE SAVEPOINT teslimat_premig")
    except Exception as exc:  # noqa: BLE001
        cr.execute("ROLLBACK TO SAVEPOINT teslimat_premig")
        _logger.warning("ir_model_relation okunamadı: %s", exc)

    for rel in rel_names:
        _safe(cr, 'DROP TABLE IF EXISTS "%s" CASCADE' % rel)

    # 1) Selection seçenekleri (asıl çökme noktası).
    _safe(
        cr,
        "DELETE FROM ir_model_fields_selection "
        "WHERE field_id IN (SELECT id FROM ir_model_fields WHERE model IN %s)",
        (REMOVED_MODELS,),
    )

    # 2) Bu modellerin alanlarına ait ir_model_data (xmlid) kayıtları.
    _safe(
        cr,
        "DELETE FROM ir_model_data WHERE model = 'ir.model.fields' "
        "AND res_id IN (SELECT id FROM ir_model_fields WHERE model IN %s)",
        (REMOVED_MODELS,),
    )
    _safe(
        cr,
        "DELETE FROM ir_model_data WHERE model = 'ir.model.fields.selection' "
        "AND module = 'teslimat_planlama' "
        "AND res_id NOT IN (SELECT id FROM ir_model_fields_selection)",
    )

    # 3) Alanlar: hem bu modellerin üzerindeki, hem de bunlara işaret eden (relation) alanlar.
    _safe(cr, "DELETE FROM ir_model_fields WHERE model IN %s OR relation IN %s", (REMOVED_MODELS, REMOVED_MODELS))

    # 4) Erişim kuralları.
    _safe(
        cr,
        "DELETE FROM ir_model_access "
        "WHERE model_id IN (SELECT id FROM ir_model WHERE model IN %s)",
        (REMOVED_MODELS,),
    )

    # 5) İlişki ve constraint metadata.
    _safe(
        cr,
        "DELETE FROM ir_model_relation "
        "WHERE model IN (SELECT id FROM ir_model WHERE model IN %s)",
        (REMOVED_MODELS,),
    )
    _safe(
        cr,
        "DELETE FROM ir_model_constraint "
        "WHERE model IN (SELECT id FROM ir_model WHERE model IN %s)",
        (REMOVED_MODELS,),
    )

    # 6) ir.model kayıtlarına ait ir_model_data.
    _safe(
        cr,
        "DELETE FROM ir_model_data WHERE model = 'ir.model' "
        "AND res_id IN (SELECT id FROM ir_model WHERE model IN %s)",
        (REMOVED_MODELS,),
    )

    # 7) ir.model satırları.
    _safe(cr, "DELETE FROM ir_model WHERE model IN %s", (REMOVED_MODELS,))

    # 8) Fiziksel tabloları düşür.
    _safe(cr, 'DROP TABLE IF EXISTS "teslimat_planlama" CASCADE')
    _safe(cr, 'DROP TABLE IF EXISTS "teslimat_transfer" CASCADE')

    # 9) Kaldırılan view/action/sequence/erişim xmlid'leri.
    _safe(
        cr,
        "DELETE FROM ir_model_data WHERE module = 'teslimat_planlama' AND name IN ("
        "'view_teslimat_planlama_tree','view_teslimat_planlama_form','view_teslimat_planlama_search',"
        "'action_teslimat_planlama','seq_teslimat_planlama',"
        "'view_teslimat_transfer_tree','view_teslimat_transfer_form','view_teslimat_transfer_search',"
        "'action_teslimat_transfer',"
        "'access_teslimat_planlama_all','access_teslimat_planlama_manager',"
        "'access_teslimat_transfer_all','access_teslimat_transfer_manager')",
    )

    _logger.info("teslimat_planlama pre-migration tamamlandı.")
