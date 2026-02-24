"""Stock Picking Inherit - Teslimat Entegrasyonu."""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Stock Picking Inherit.

    Transfer belgelerine teslimat entegrasyonu ekler.
    Smart button ile ilgili teslimatlar görüntülenir.
    """

    _inherit = "stock.picking"

    # Teslimat planlama alanları
    teslimat_planlama_id = fields.Many2one(
        "teslimat.planlama", string="Teslimat Planlaması"
    )
    teslimat_transfer_id = fields.Many2one(
        "teslimat.transfer", string="Teslimat Transfer"
    )

    # Teslimat Belgeleri
    teslimat_belgesi_ids = fields.One2many(
        "teslimat.belgesi",
        "stock_picking_id",
        string="Teslimat Belgeleri",
    )
    teslimat_belgesi_count = fields.Integer(
        string="Teslimat Sayısı",
        compute="_compute_teslimat_belgesi_count",
        store=False,
    )

    @api.depends("teslimat_belgesi_ids")
    def _compute_teslimat_belgesi_count(self) -> None:
        """Teslimat belgesi sayısını hesapla."""
        for picking in self:
            picking.teslimat_belgesi_count = len(picking.teslimat_belgesi_ids)

    def action_view_teslimat_belgeleri(self) -> dict:
        """Teslimat belgelerini görüntüle.

        Returns:
            dict: Teslimat belgeleri tree view'ı
        """
        self.ensure_one()
        return {
            "name": _("Teslimat Belgeleri"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi",
            "view_mode": "tree,form",
            "domain": [("stock_picking_id", "=", self.id)],
            "context": {"default_stock_picking_id": self.id},
        }
