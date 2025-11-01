"""Teslimat Belgesi Ürün Modeli."""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class TeslimatBelgesiUrun(models.Model):
    """Teslimat Belgesi Ürün.

    Teslimat belgesine ait ürünleri tutar.
    Transfer belgesinden otomatik oluşturulur.
    """

    _name = "teslimat.belgesi.urun"
    _description = "Teslimat Belgesi Ürün"
    _order = "sequence"

    teslimat_belgesi_id = fields.Many2one(
        "teslimat.belgesi",
        string="Teslimat Belgesi",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Sıra", default=1)

    # Ürün Bilgileri
    urun_id = fields.Many2one("product.product", string="Ürün", required=True)
    miktar = fields.Float(string="Miktar", required=True)
    birim = fields.Many2one("uom.uom", string="Birim", required=True)

    # Transfer Entegrasyonu
    stock_move_id = fields.Many2one(
        "stock.move", string="Transfer Satırı", readonly=True
    )
    transfer_no = fields.Char(
        string="Transfer No",
        related="teslimat_belgesi_id.transfer_no",
        readonly=True,
    )

