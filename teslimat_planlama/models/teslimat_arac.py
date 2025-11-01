"""Teslimat Araç Yönetimi Modeli."""
import logging
from typing import List, Optional

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TeslimatArac(models.Model):
    """Teslimat Araç Yönetimi.

    Araçlar, kapasiteleri ve durumlarını yönetir.
    Varsayılan günlük teslimat limiti: 7 (user grubu için)
    Yöneticiler bu limiti değiştirebilir.
    """

    _name = "teslimat.arac"
    _description = "Teslimat Araç Yönetimi"
    _order = "name"

    name = fields.Char(string="Araç Adı", required=True)
    arac_tipi = fields.Selection(
        [
            ("anadolu_yakasi", "Anadolu Yakası"),
            ("avrupa_yakasi", "Avrupa Yakası"),
            ("kucuk_arac_1", "Küçük Araç 1"),
            ("kucuk_arac_2", "Küçük Araç 2"),
            ("ek_arac", "Ek Araç"),
        ],
        string="Araç Tipi",
        required=True,
    )

    # Kapasite Bilgileri (Dinamik - Modülden ayarlanabilir)
    # Varsayılan: 7 teslimat/gün (user grubu için)
    gunluk_teslimat_limiti = fields.Integer(
        string="Günlük Teslimat Limiti", default=7
    )
    mevcut_kapasite = fields.Integer(
        string="Mevcut Kapasite",
        compute="_compute_mevcut_kapasite",
        store=True,
    )
    kalan_kapasite = fields.Integer(
        string="Kalan Kapasite",
        compute="_compute_kalan_kapasite",
        store=True,
    )

    # Durum Bilgileri
    aktif = fields.Boolean(string="Aktif", default=True)
    gecici_kapatma = fields.Boolean(string="Geçici Kapatma")
    kapatma_sebebi = fields.Text(string="Kapatma Sebebi")
    kapatma_baslangic = fields.Datetime(string="Kapatma Başlangıç")
    kapatma_bitis = fields.Datetime(string="Kapatma Bitiş")

    # İlçe Uyumluluğu
    uygun_ilceler = fields.Many2many("teslimat.ilce", string="Uygun İlçeler")

    # Teslimat Geçmişi
    teslimat_ids = fields.One2many(
        "teslimat.belgesi", "arac_id", string="Teslimatlar"
    )

    # Transfer Geçmişi
    transfer_ids = fields.One2many(
        "teslimat.transfer", "arac_id", string="Transferler"
    )

    @api.depends("teslimat_ids", "teslimat_ids.durum", "teslimat_ids.teslimat_tarihi")
    def _compute_mevcut_kapasite(self) -> None:
        """Bugün için mevcut kapasiteyi hesapla."""
        for record in self:
            bugun = fields.Date.today()
            bugun_teslimatlar = record.teslimat_ids.filtered(
                lambda t: t.teslimat_tarihi == bugun
                and t.durum in ["hazir", "yolda"]
            )
            record.mevcut_kapasite = len(bugun_teslimatlar)

    @api.depends("gunluk_teslimat_limiti", "mevcut_kapasite")
    def _compute_kalan_kapasite(self) -> None:
        """Kalan kapasiteyi hesapla."""
        for record in self:
            record.kalan_kapasite = (
                record.gunluk_teslimat_limiti - record.mevcut_kapasite
            )

    @api.constrains("gunluk_teslimat_limiti")
    def _check_gunluk_limit(self) -> None:
        """Günlük teslimat limiti 0'dan büyük olmalıdır."""
        for record in self:
            if record.gunluk_teslimat_limiti <= 0:
                raise ValidationError(
                    _("Günlük teslimat limiti 0'dan büyük olmalıdır.")
                )

    def action_gecici_kapat(self) -> dict:
        """Aracı geçici olarak kapatma wizard'ını aç (Yöneticiler için).

        Returns:
            dict: Wizard açma action'ı
        """
        self.ensure_one()
        return {
            "name": "Geçici Kapatma",
            "type": "ir.actions.act_window",
            "res_model": "teslimat.arac.kapatma.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_arac_id": self.id},
        }

    def action_aktif_et(self) -> None:
        """Aracı aktif et ve kapatma bilgilerini temizle."""
        self.ensure_one()
        self.write(
            {
                "gecici_kapatma": False,
                "kapatma_sebebi": False,
                "kapatma_baslangic": False,
                "kapatma_bitis": False,
            }
        )

    @api.model
    def get_uygun_araclar(
        self,
        ilce_id: Optional[int] = None,
        tarih: Optional[fields.Date] = None,
        teslimat_sayisi: int = 1,
    ) -> "TeslimatArac":
        """Belirli ilçe ve tarih için uygun araçları getir.

        Args:
            ilce_id: İlçe ID
            tarih: Tarih (opsiyonel)
            teslimat_sayisi: Gereken teslimat sayısı

        Returns:
            Recordset: Uygun araçlar
        """
        domain = [
            ("aktif", "=", True),
            ("gecici_kapatma", "=", False),
            ("kalan_kapasite", ">=", teslimat_sayisi),
        ]

        # İlçe uyumluluğu kontrolü
        if ilce_id:
            ilce = self.env["teslimat.ilce"].browse(ilce_id)
            if ilce.exists():
                ilce_yaka = ilce.yaka_tipi

                # Küçük araçlar ve ek araç her ilçeye gidebilir
                # Yaka bazlı araçlar sadece kendi yakalarına gidebilir
                if ilce_yaka == "anadolu":
                    domain.append(
                        (
                            "arac_tipi",
                            "in",
                            ["anadolu_yakasi", "kucuk_arac_1", "kucuk_arac_2", "ek_arac"],
                        )
                    )
                elif ilce_yaka == "avrupa":
                    domain.append(
                        (
                            "arac_tipi",
                            "in",
                            ["avrupa_yakasi", "kucuk_arac_1", "kucuk_arac_2", "ek_arac"],
                        )
                    )

        # Kapatma tarihi kontrolü
        if tarih:
            domain += [
                "|",
                ("kapatma_bitis", "=", False),
                ("kapatma_bitis", "<", tarih),
            ]

        return self.search(domain, order="kalan_kapasite desc")

