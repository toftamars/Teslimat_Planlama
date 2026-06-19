"""Teslimat Gün Yönetimi Modeli."""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class TeslimatGun(models.Model):
    """Teslimat Gün Yönetimi.

    Haftanın günleri ve teslimat kapasitelerini yönetir.
    """

    _name = "teslimat.gun"
    _description = "Teslimat Gün Yönetimi"
    _order = "sequence"

    name = fields.Char(string="Gün Adı", required=True)
    sequence = fields.Integer(string="Sıra", default=10)
    gun_kodu = fields.Selection(
        [
            ("pazartesi", "Pazartesi"),
            ("sali", "Salı"),
            ("carsamba", "Çarşamba"),
            ("persembe", "Perşembe"),
            ("cuma", "Cuma"),
            ("cumartesi", "Cumartesi"),
            ("pazar", "Pazar"),
        ],
        string="Gün Kodu",
        required=True,
    )

    # Durum Bilgileri
    aktif = fields.Boolean(string="Aktif", default=True)
    gecici_kapatma = fields.Boolean(string="Geçici Kapatma")
    kapatma_sebebi = fields.Text(string="Kapatma Sebebi")
    kapatma_baslangic = fields.Date(string="Kapatma Başlangıç")
    kapatma_bitis = fields.Date(string="Kapatma Bitiş")

    # Kapasite Bilgileri (Dinamik - Modülden ayarlanabilir)
    gunluk_maksimum_teslimat = fields.Integer(
        string="Günlük Maksimum Teslimat", default=7
    )
    # İlçe Eşleşmeleri (Dinamik - Database'den yönetilir)
    ilce_ids = fields.One2many(
        "teslimat.gun.ilce", "gun_id", string="İlçe Eşleşmeleri"
    )

    # Yaka Bazlı Gruplandırma
    yaka_tipi = fields.Selection(
        [
            ("anadolu", "Anadolu Yakası"),
            ("avrupa", "Avrupa Yakası"),
            ("her_ikisi", "Her İkisi"),
        ],
        string="Yaka Tipi",
        default="her_ikisi",
    )

    def action_gecici_kapat(self) -> dict:
        """Günü geçici olarak kapatma wizard'ını aç.

        Returns:
            dict: Wizard açma action'ı
        """
        self.ensure_one()
        return {
            "name": "Gün Kapatma",
            "type": "ir.actions.act_window",
            "res_model": "teslimat.gun.kapatma.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_gun_id": self.id},
        }

    def action_aktif_et(self) -> None:
        """Günü aktif et ve kapatma bilgilerini temizle."""
        self.ensure_one()
        self.write(
            {
                "gecici_kapatma": False,
                "kapatma_sebebi": False,
                "kapatma_baslangic": False,
                "kapatma_bitis": False,
            }
        )
