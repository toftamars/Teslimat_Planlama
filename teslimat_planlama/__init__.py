from . import models
from . import wizards
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Post-install hook: İlk kurulumda gerekli verileri yükle."""
    import logging
    _logger = logging.getLogger(__name__)

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
                _logger.info("İstanbul ilçeleri yüklendi")

            # Haftalık programı uygula
            _logger.info("Haftalık program uygulanıyor...")
            ilce_model.apply_weekly_schedule()
            _logger.info("Haftalık program uygulandı")
        else:
            _logger.warning("İstanbul ili bulunamadı")

        env["teslimat.belgesi"].init_maps_config_parameters()

    except Exception:
        # Kurulum devam eder (ilçe + maps'in XML <function> fallback'i ayrıca yükler);
        # ama hatayı yutmak yerine ERROR + tam traceback logla ki teşhis edilebilsin.
        _logger.exception("Post-init hook hatası (kurulum devam ediyor)")
