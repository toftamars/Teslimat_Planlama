"""Res Partner Inherit - Teslimat Alanları."""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Res Partner Inherit.

    Müşterilere teslimat geçmişini (teslimat belgeleri) ekler.
    """

    _inherit = "res.partner"

    # Teslimat geçmişi
    teslimat_belgesi_ids = fields.One2many(
        "teslimat.belgesi",
        "musteri_id",
        string="Teslimat Belgeleri",
    )
