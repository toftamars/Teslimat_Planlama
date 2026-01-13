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
                _logger.info("✓ İstanbul ilçeleri yüklendi")

            # Haftalık programı uygula
            _logger.info("Haftalık program uygulanıyor...")
            ilce_model.apply_weekly_schedule()
            cr.commit()
            _logger.info("✓ Haftalık program uygulandı")
        else:
            _logger.warning("İstanbul ili bulunamadı")

        # Tüm internal user'lara Teslimat Kullanıcısı grubunu ata
        try:
            _logger.info("Teslimat grupları atanıyor...")
            teslimat_user_group = env.ref('teslimat_planlama.group_teslimat_user')
            internal_users = env['res.users'].search([
                ('share', '=', False),
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
        _logger.warning("Post-init hook hatası (ignored): %s", e)
