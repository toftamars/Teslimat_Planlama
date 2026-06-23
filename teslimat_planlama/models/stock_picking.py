"""Stock Picking Inherit - Teslimat Entegrasyonu."""
import logging

from odoo import _, api, fields, models

from .teslimat_constants import CANCELLED_STATUS, COMPLETED_STATUS

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Stock Picking Inherit.

    Transfer belgelerine teslimat entegrasyonu ekler.
    Smart button ile ilgili teslimatlar görüntülenir.
    """

    _inherit = "stock.picking"

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

    # =========================================================================
    # İPTAL YAYILIMI (Transfer iptal → Teslimat belgesi iptal)
    # =========================================================================

    def action_cancel(self) -> bool:
        """Transfer iptal edilince bağlı teslimat belgelerini de iptal et.

        Müşteri siparişini iptal ettirdiğinde sale order iptali bu picking'i
        ``action_cancel`` ile iptal eder. Bu override, transfere bağlı ve henüz
        teslim edilmemiş teslimat belgelerini otomatik olarak 'İptal' durumuna
        çeker. Önce gerçek iptal (super) çalışır; başarısız olursa yayılım
        yapılmaz.

        Returns:
            bool: super().action_cancel() sonucu
        """
        res = super().action_cancel()
        self._iptal_bagli_teslimatlar()
        return res

    def _iptal_bagli_teslimatlar(self) -> None:
        """Transfere bağlı teslimat belgelerini iptal et.

        Kurallar:
          - Bekleyen/hazır/yolda/taslak teslimatlar 'İptal' yapılır.
          - 'Teslim Edildi' olanlar KORUNUR (mal fiziksel teslim edilmiş);
            chatter'a uyarı düşülür, manuel kontrol istenir.
          - Zaten 'İptal' olanlar atlanır.

        İptal, ``from_picking_cancel`` context'i ile yapılır: teslimat
        belgesindeki manuel iptal yetki kontrolü atlanır (kullanıcı zaten
        transferi/siparişi iptal etme yetkisine sahiptir). sudo kullanılır ki
        teslimat başka bir kullanıcıya ait olsa bile cascade her zaman başarılı
        olsun.
        """
        for picking in self:
            teslimatlar = picking.teslimat_belgesi_ids
            if not teslimatlar:
                continue

            iptal_edilecek = teslimatlar.filtered(
                lambda t: t.durum not in (CANCELLED_STATUS, COMPLETED_STATUS)
            )
            tamamlanan = teslimatlar.filtered(
                lambda t: t.durum == COMPLETED_STATUS
            )

            if iptal_edilecek:
                iptal_edilecek.with_context(
                    from_picking_cancel=True
                ).sudo().write({"durum": CANCELLED_STATUS})
                for teslimat in iptal_edilecek:
                    teslimat.sudo().message_post(
                        body=_(
                            "Bağlı transfer belgesi (%s) iptal edildiği için "
                            "teslimat belgesi otomatik olarak iptal edildi."
                        ) % picking.name
                    )
                _logger.info(
                    "Transfer %s iptal edildi; %d teslimat belgesi otomatik iptal edildi.",
                    picking.name,
                    len(iptal_edilecek),
                )

            for teslimat in tamamlanan:
                teslimat.sudo().message_post(
                    body=_(
                        "Bağlı transfer belgesi (%s) iptal edildi, ancak bu "
                        "teslimat zaten 'Teslim Edildi' durumunda olduğu için "
                        "korundu. Lütfen manuel kontrol edin."
                    ) % picking.name
                )
