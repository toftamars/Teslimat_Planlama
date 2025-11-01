"""Teslimat Planlama Modeli."""
import logging
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TeslimatPlanlama(models.Model):
    """Teslimat Planlama.

    Genel teslimat planları oluşturma ve yönetimi.
    """

    _name = "teslimat.planlama"
    _description = "Teslimat Planlama"
    _order = "tarih desc"

    name = fields.Char(
        string="Plan Adı",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Yeni"),
    )
    tarih = fields.Date(
        string="Plan Tarihi", required=True, default=fields.Date.today
    )
    durum = fields.Selection(
        [
            ("taslak", "Taslak"),
            ("onaylandi", "Onaylandı"),
            ("calisiyor", "Çalışıyor"),
            ("tamamlandi", "Tamamlandı"),
            ("iptal", "İptal"),
        ],
        string="Durum",
        default="taslak",
        required=True,
    )

    # Kontakt bilgileri
    musteri_ids = fields.Many2many(
        "res.partner",
        string="Müşteriler",
        domain=[("customer_rank", ">", 0)],
    )

    # Transfer bilgileri
    transfer_ids = fields.One2many(
        "teslimat.transfer", "planlama_id", string="Transferler"
    )

    # Stok bilgileri
    urun_ids = fields.Many2many("product.product", string="Ürünler")

    # Planlama detayları
    baslangic_tarihi = fields.Datetime(string="Başlangıç Tarihi")
    bitis_tarihi = fields.Datetime(string="Bitiş Tarihi")
    notlar = fields.Text(string="Notlar")

    # Hesaplanan alanlar
    toplam_transfer = fields.Integer(
        string="Toplam Transfer", compute="_compute_toplamlar"
    )
    toplam_urun = fields.Integer(
        string="Toplam Ürün", compute="_compute_toplamlar"
    )

    @api.depends("transfer_ids", "urun_ids")
    def _compute_toplamlar(self) -> None:
        """Toplam transfer ve ürün sayısını hesapla."""
        for record in self:
            record.toplam_transfer = len(record.transfer_ids)
            record.toplam_urun = len(record.urun_ids)

    @api.model
    def create(self, vals: dict) -> "TeslimatPlanlama":
        """Sequence ile otomatik numaralandırma."""
        if vals.get("name", _("Yeni")) == _("Yeni"):
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("teslimat.planlama")
                or _("Yeni")
            )
        return super(TeslimatPlanlama, self).create(vals)

    def action_onayla(self) -> None:
        """Planı onayla."""
        self.ensure_one()
        if self.durum != "taslak":
            raise ValidationError(_("Sadece taslak planlar onaylanabilir."))
        self.write({"durum": "onaylandi"})

    def action_baslat(self) -> None:
        """Planı başlat."""
        self.ensure_one()
        if self.durum != "onaylandi":
            raise ValidationError(_("Sadece onaylanmış planlar başlatılabilir."))
        self.write({"durum": "calisiyor"})

    def action_tamamla(self) -> None:
        """Planı tamamla."""
        self.ensure_one()
        if self.durum != "calisiyor":
            raise ValidationError(_("Sadece çalışan planlar tamamlanabilir."))
        self.write({"durum": "tamamlandi"})

    def action_iptal(self) -> None:
        """Planı iptal et."""
        self.ensure_one()
        self.write({"durum": "iptal"})

