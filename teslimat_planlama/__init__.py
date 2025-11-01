from . import models
from . import wizards


def post_init_hook(cr, registry):
    """Post-install/upgrade hook: Eski model referanslarını temizle."""
    env = registry['base'].env(cr=cr)
    # Eski teslimat.planlama.akilli model referanslarını temizle
    env['ir.model.data'].search([
        ('module', '=', 'teslimat_planlama'),
        ('model', '=', 'teslimat.planlama.akilli')
    ]).unlink()
    # Eski model tanımını temizle
    env['ir.model'].search([
        ('model', '=', 'teslimat.planlama.akilli')
    ]).unlink()
    cr.commit()

