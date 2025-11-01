"""Stock Picking Inherit - Teslimat Entegrasyonu."""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Stock Picking Inherit.

    Transfer belgelerine teslimat entegrasyonu ekler.
    Smart button ve kısayol butonu içerir.
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

    def action_teslimat_sihirbazi_ac(self) -> dict:
        """Transfer belgesinden teslimat sihirbazını aç.

        Returns:
            dict: Wizard açma action'ı
        """
        self.ensure_one()

        # Context hazırla - wizard'a bilgileri gönder
        context = {
            "default_transfer_id": self.id,
            "default_musteri_id": self.partner_id.id if self.partner_id else False,
        }

        # Teslimat Belgesi Wizard'ını aç
        return {
            "type": "ir.actions.act_window",
            "name": _("Teslimat Belgesi Oluştur"),
            "res_model": "teslimat.belgesi.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

