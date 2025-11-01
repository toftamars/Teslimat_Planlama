"""Res Partner Inherit - Teslimat Alanları."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Res Partner Inherit.

    Müşterilere teslimat tercihleri ve konum bilgileri ekler.
    """

    _inherit = "res.partner"

    # Teslimat planlama alanları
    # NOT: Bu field'lar geçici olarak devre dışı bırakıldı.
    # Modül upgrade edildikten sonra aşağıdaki satırları aktif edin:
    # teslimat_bolgesi = fields.Char(string="Teslimat Bölgesi")
    # teslimat_suresi = fields.Integer(string="Teslimat Süresi (Gün)", default=1)
    # teslimat_notlari = fields.Text(string="Teslimat Notları")

    # Konum bilgileri
    enlem = fields.Float(string="Enlem")
    boylam = fields.Float(string="Boylam")

    # Teslimat tercihleri
    tercih_edilen_teslimat_gunu = fields.Selection(
        [
            ("pazartesi", "Pazartesi"),
            ("sali", "Salı"),
            ("carsamba", "Çarşamba"),
            ("persembe", "Perşembe"),
            ("cuma", "Cuma"),
            ("cumartesi", "Cumartesi"),
            ("pazar", "Pazar"),
        ],
        string="Tercih Edilen Teslimat Günü",
    )

    tercih_edilen_teslimat_saati = fields.Selection(
        [
            ("09:00", "09:00"),
            ("10:00", "10:00"),
            ("11:00", "11:00"),
            ("12:00", "12:00"),
            ("13:00", "13:00"),
            ("14:00", "14:00"),
            ("15:00", "15:00"),
            ("16:00", "16:00"),
            ("17:00", "17:00"),
        ],
        string="Tercih Edilen Teslimat Saati",
    )

    # Sürücü kontrolü
    # NOT: Bu field geçici olarak devre dışı bırakıldı.
    # Modül upgrade edildikten sonra aşağıdaki satırları aktif edin:
    # is_driver = fields.Boolean(
    #     string="Sürücü",
    #     default=False,
    #     help="Bu kişi teslimat sürücüsü mü?",
    # )

    # Teslimat geçmişi
    teslimat_planlama_ids = fields.One2many(
        "teslimat.planlama",
        "musteri_ids",  # Many2many field name
        string="Teslimat Planlamaları",
    )
    teslimat_belgesi_ids = fields.One2many(
        "teslimat.belgesi",
        "musteri_id",
        string="Teslimat Belgeleri",
    )

    # Hesaplanan alanlar
    konum_bilgisi = fields.Char(
        string="Konum Bilgisi",
        compute="_compute_konum_bilgisi",
        store=True,
    )

    @api.depends("enlem", "boylam")
    def _compute_konum_bilgisi(self) -> None:
        """Konum bilgisini hesapla."""
        for partner in self:
            if partner.enlem and partner.boylam:
                partner.konum_bilgisi = f"{partner.enlem}, {partner.boylam}"
            else:
                partner.konum_bilgisi = "Konum bilgisi yok"

