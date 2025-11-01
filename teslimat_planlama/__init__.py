from . import models
from . import wizards


def post_init_hook(cr, registry):
    """Post-install/upgrade hook: Eski model referanslarını temizle."""
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Eski teslimat.planlama.akilli model referanslarını temizle
    try:
        old_data = env['ir.model.data'].search([
            ('module', '=', 'teslimat_planlama'),
            ('model', '=', 'teslimat.planlama.akilli')
        ])
        if old_data:
            old_data.unlink()
        # Eski model tanımını temizle
        old_model = env['ir.model'].search([
            ('model', '=', 'teslimat.planlama.akilli')
        ])
        if old_model:
            old_model.unlink()
        cr.commit()
    except Exception:
        # Model yoksa hata verme, sadece log
        cr.rollback()

