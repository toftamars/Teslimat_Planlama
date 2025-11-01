"""Teslimat Transfer Modeli."""
import logging
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class TeslimatTransfer(models.Model):
    """Teslimat Transfer.

    Transfer belgeleri ile entegre teslimat işlemleri.
    """

    _name = "teslimat.transfer"
    _description = "Teslimat Transfer"
    _order = "planlanan_tarih desc, sira_no"

    name = fields.Char(string="Transfer Adı", required=True)
    planlama_id = fields.Many2one(
        "teslimat.planlama", string="Teslimat Planlaması"
    )
    sira_no = fields.Integer(string="Sıra No", default=1)

    # Transfer Bilgileri
    transfer_no = fields.Char(
        string="Transfer No",
        help="Transfer belgesi numarası (DEPO/OUT/XXXXX)",
    )
    stock_picking_id = fields.Many2one(
        "stock.picking",
        string="Transfer Belgesi",
        domain=[("state", "in", ["waiting", "confirmed", "assigned", "done"])],
    )

    # Müşteri Bilgileri
    musteri_id = fields.Many2one("res.partner", string="Müşteri")

    # Konum Bilgileri
    kaynak_konum = fields.Char(string="Kaynak Konum")
    hedef_konum = fields.Char(string="Hedef Konum")

    # Ürün Bilgileri
    urun_id = fields.Many2one("product.product", string="Ürün")
    miktar = fields.Float(string="Miktar")
    birim = fields.Many2one("uom.uom", string="Birim", related="urun_id.uom_id")

    # Zaman Bilgileri
    planlanan_tarih = fields.Date(string="Planlanan Tarih")
    gerceklesen_tarih = fields.Date(string="Gerçekleşen Tarih")

    # Araç Bilgileri
    arac_id = fields.Many2one("teslimat.arac", string="Araç")

    # Durum
    durum = fields.Selection(
        [
            ("bekliyor", "Bekliyor"),
            ("hazirlaniyor", "Hazırlanıyor"),
            ("yolda", "Yolda"),
            ("tamamlandi", "Tamamlandı"),
            ("iptal", "İptal"),
        ],
        string="Durum",
        default="bekliyor",
    )

    notlar = fields.Text(string="Notlar")

    @api.onchange("transfer_no")
    def _onchange_transfer_no(self) -> None:
        """Transfer no değiştiğinde otomatik bilgi doldur."""
        if not self.transfer_no:
            return

        try:
            # Transfer belgesini bul
            picking = self.env["stock.picking"].search(
                [("name", "=", self.transfer_no)], limit=1
            )

            if picking:
                self.stock_picking_id = picking
                self._update_picking_data(picking)
            else:
                return {
                    "warning": {
                        "title": _("Uyarı"),
                        "message": _(
                            "Transfer belgesi bulunamadı: %s" % self.transfer_no
                        ),
                    }
                }
        except Exception as e:
            _logger.error("Transfer no onchange hatası: %s", e)
            return {
                "warning": {
                    "title": _("Hata"),
                    "message": _("Transfer bilgileri alınırken hata oluştu."),
                }
            }

    @api.onchange("stock_picking_id")
    def _onchange_stock_picking(self) -> None:
        """Stock picking seçildiğinde otomatik bilgi doldur."""
        if not self.stock_picking_id:
            return

        try:
            picking = self.stock_picking_id
            self._update_picking_data(picking)
        except Exception as e:
            _logger.error("Stock picking onchange hatası: %s", e)

    def _update_picking_data(self, picking: "stock.picking") -> None:
        """Transfer belgesi bilgilerini güncelle.

        Args:
            picking: Stock picking kaydı
        """
        # Müşteri bilgisi
        if picking.partner_id:
            self.musteri_id = picking.partner_id

        # Konum bilgileri
        if picking.location_id:
            self.kaynak_konum = picking.location_id.complete_name
        if picking.location_dest_id:
            self.hedef_konum = picking.location_dest_id.complete_name

        # Transfer no
        if picking.name:
            self.transfer_no = picking.name

        # Ürün bilgileri (ilk ürünü al)
        if picking.move_ids_without_package:
            first_move = picking.move_ids_without_package[0]
            self.urun_id = first_move.product_id
            self.miktar = first_move.quantity_done or first_move.product_uom_qty

    def action_transfer_belgesi_olustur(self) -> dict:
        """Teslimat belgesi oluşturma wizard'ını aç.

        Returns:
            dict: Wizard açma action'ı
        """
        self.ensure_one()
        if self.durum not in ["bekliyor", "hazirlaniyor"]:
            raise UserError(
                _(
                    "Sadece 'Bekliyor' veya 'Hazırlanıyor' durumundaki "
                    "transferler için teslimat belgesi oluşturulabilir."
                )
            )

        return {
            "name": _("Teslimat Belgesi Oluştur"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_transfer_no": self.transfer_no,
                "default_stock_picking_id": self.stock_picking_id.id,
                "default_musteri_id": self.musteri_id.id if self.musteri_id else False,
            },
        }

