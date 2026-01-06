"""Teslimat İlçe Yönetimi Modeli."""
import logging
from typing import Optional

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# İlçe yaka tipi tanımları
ANADOLU_ILCELERI = [
    "Maltepe",
    "Kartal",
    "Pendik",
    "Tuzla",
    "Üsküdar",
    "Kadıköy",
    "Ataşehir",
    "Ümraniye",
    "Sancaktepe",
    "Çekmeköy",
    "Beykoz",
    "Şile",
    "Sultanbeyli",
]

AVRUPA_ILCELERI = [
    "Beyoğlu",
    "Şişli",
    "Beşiktaş",
    "Kağıthane",
    "Sarıyer",
    "Bakırköy",
    "Bahçelievler",
    "Güngören",
    "Esenler",
    "Bağcılar",
    "Eyüpsultan",
    "Gaziosmanpaşa",
    "Küçükçekmece",
    "Avcılar",
    "Başakşehir",
    "Sultangazi",
    "Arnavutköy",
    "Fatih",
    "Zeytinburnu",
    "Bayrampaşa",
    "Esenyurt",
    "Beylikdüzü",
    "Silivri",
    "Çatalca",
    "Büyükçekmece",
]


class TeslimatIlce(models.Model):
    """Teslimat İlçe Yönetimi.

    İlçeler ve teslimat bölge bilgilerini yönetir.
    """

    _name = "teslimat.ilce"
    _description = "Teslimat İlçe Yönetimi"
    _order = "sehir_id, name"

    name = fields.Char(string="İlçe Adı", required=True)
    sehir_id = fields.Many2one("teslimat.sehir", string="Şehir", required=True)
    aktif = fields.Boolean(string="Aktif", default=True)

    # Yaka Belirleme
    yaka_tipi = fields.Selection(
        [
            ("anadolu", "Anadolu Yakası"),
            ("avrupa", "Avrupa Yakası"),
            ("belirsiz", "Belirsiz"),
        ],
        string="Yaka Tipi",
        compute="_compute_yaka_tipi",
        store=True,
    )

    # Konum Bilgileri
    enlem = fields.Float(string="Enlem")
    boylam = fields.Float(string="Boylam")
    posta_kodu = fields.Char(string="Posta Kodu")

    # Teslimat Bilgileri
    teslimat_aktif = fields.Boolean(string="Teslimat Aktif", default=True)
    teslimat_suresi = fields.Integer(string="Teslimat Süresi (Gün)", default=1)
    teslimat_notlari = fields.Text(string="Teslimat Notları")

    # Özel Durumlar
    ozel_durum = fields.Selection(
        [
            ("normal", "Normal"),
            ("yogun", "Yoğun"),
            ("kapali", "Kapalı"),
            ("ozel", "Özel"),
        ],
        string="Özel Durum",
        default="normal",
    )

    # İlişkiler
    gun_ids = fields.Many2many(
        "teslimat.gun", through="teslimat.gun.ilce", string="Teslimat Günleri"
    )
    # Uygun araçlar - Many2many ilişkisinin ters tarafı (otomatik hesaplanır)
    # Bu alan araçların uygun_ilceler alanından otomatik olarak hesaplanır
    arac_ids = fields.Many2many(
        "teslimat.arac",
        compute="_compute_arac_ids",
        string="Uygun Araçlar",
        store=False,
    )

    @api.depends("name", "yaka_tipi")
    def _compute_arac_ids(self) -> None:
        """Bu ilçeyi uygun ilçeler listesinde bulunan araçları hesapla."""
        for record in self:
            # Bu ilçeyi uygun_ilceler listesinde bulunan araçları bul
            araclar = self.env["teslimat.arac"].search(
                [("uygun_ilceler", "in", [record.id])]
            )
            record.arac_ids = araclar

    @api.depends("name")
    def _compute_yaka_tipi(self) -> None:
        """İlçe adına göre yaka tipini otomatik belirle.

        İlçe adına göre Anadolu veya Avrupa yakası olarak
        otomatik olarak atar.
        """
        for record in self:
            if not record.name:
                record.yaka_tipi = "belirsiz"
                continue

            ilce_adi_lower = record.name.lower()

            # Anadolu yakası kontrolü
            if any(ilce.lower() in ilce_adi_lower for ilce in ANADOLU_ILCELERI):
                record.yaka_tipi = "anadolu"
            # Avrupa yakası kontrolü
            elif any(ilce.lower() in ilce_adi_lower for ilce in AVRUPA_ILCELERI):
                record.yaka_tipi = "avrupa"
            else:
                record.yaka_tipi = "belirsiz"

    def write(self, vals):
        """İlçe yaka tipi değiştiğinde ilgili araçların eşleştirmesini güncelle."""
        result = super().write(vals)
        if "yaka_tipi" in vals:
            # Bu ilçeyi uygun ilçeler listesinde bulunan araçları güncelle
            self._update_arac_ilce_eslesmesi()
        return result

    def _update_arac_ilce_eslesmesi(self) -> None:
        """İlçe yaka tipi değiştiğinde ilgili araçların eşleştirmesini güncelle.
        
        Yaka tipi değişen ilçe için, bu ilçeyi uygun ilçeler listesinde 
        bulunan araçların eşleştirmelerini yeniden hesapla.
        """
        for ilce in self:
            # Bu ilçeyi uygun ilçeler listesinde bulunan araçları bul
            araclar = self.env["teslimat.arac"].search(
                [("uygun_ilceler", "in", [ilce.id])]
            )
            
            # Her araç için eşleştirmeyi yeniden hesapla
            for arac in araclar:
                # Eğer araç yaka bazlı ise (küçük araç değilse)
                if arac.arac_tipi in ["anadolu_yakasi", "avrupa_yakasi"]:
                    # Araç tipine göre uygun ilçeleri yeniden hesapla
                    arac._update_uygun_ilceler()

    @api.model
    def create_istanbul_ilceleri(self) -> bool:
        """İstanbul ilçelerini otomatik oluştur.

        Returns:
            bool: İşlem başarılı ise True
        """
        istanbul = self.env["teslimat.sehir"].get_istanbul()

        ilce_listesi = [
            # Anadolu Yakası (13 ilçe)
            {"name": "Maltepe", "yaka_tipi": "anadolu"},
            {"name": "Kartal", "yaka_tipi": "anadolu"},
            {"name": "Pendik", "yaka_tipi": "anadolu"},
            {"name": "Tuzla", "yaka_tipi": "anadolu"},
            {"name": "Üsküdar", "yaka_tipi": "anadolu"},
            {"name": "Kadıköy", "yaka_tipi": "anadolu"},
            {"name": "Ataşehir", "yaka_tipi": "anadolu"},
            {"name": "Ümraniye", "yaka_tipi": "anadolu"},
            {"name": "Sancaktepe", "yaka_tipi": "anadolu"},
            {"name": "Çekmeköy", "yaka_tipi": "anadolu"},
            {"name": "Beykoz", "yaka_tipi": "anadolu"},
            {"name": "Şile", "yaka_tipi": "anadolu"},
            {"name": "Sultanbeyli", "yaka_tipi": "anadolu"},
            # Avrupa Yakası (23 ilçe)
            {"name": "Beyoğlu", "yaka_tipi": "avrupa"},
            {"name": "Şişli", "yaka_tipi": "avrupa"},
            {"name": "Beşiktaş", "yaka_tipi": "avrupa"},
            {"name": "Kağıthane", "yaka_tipi": "avrupa"},
            {"name": "Sarıyer", "yaka_tipi": "avrupa"},
            {"name": "Bakırköy", "yaka_tipi": "avrupa"},
            {"name": "Bahçelievler", "yaka_tipi": "avrupa"},
            {"name": "Güngören", "yaka_tipi": "avrupa"},
            {"name": "Esenler", "yaka_tipi": "avrupa"},
            {"name": "Bağcılar", "yaka_tipi": "avrupa"},
            {"name": "Eyüpsultan", "yaka_tipi": "avrupa"},
            {"name": "Gaziosmanpaşa", "yaka_tipi": "avrupa"},
            {"name": "Küçükçekmece", "yaka_tipi": "avrupa"},
            {"name": "Avcılar", "yaka_tipi": "avrupa"},
            {"name": "Başakşehir", "yaka_tipi": "avrupa"},
            {"name": "Sultangazi", "yaka_tipi": "avrupa"},
            {"name": "Arnavutköy", "yaka_tipi": "avrupa"},
            {"name": "Fatih", "yaka_tipi": "avrupa"},
            {"name": "Zeytinburnu", "yaka_tipi": "avrupa"},
            {"name": "Bayrampaşa", "yaka_tipi": "avrupa"},
            {"name": "Esenyurt", "yaka_tipi": "avrupa"},
            {"name": "Beylikdüzü", "yaka_tipi": "avrupa"},
            {"name": "Silivri", "yaka_tipi": "avrupa"},
            {"name": "Çatalca", "yaka_tipi": "avrupa"},
            {"name": "Büyükçekmece", "yaka_tipi": "avrupa"},
        ]

        for ilce_data in ilce_listesi:
            existing = self.search(
                [("name", "=", ilce_data["name"]), ("sehir_id", "=", istanbul.id)],
                limit=1,
            )
            if not existing:
                self.create(
                    {
                        "name": ilce_data["name"],
                        "sehir_id": istanbul.id,
                        "yaka_tipi": ilce_data["yaka_tipi"],
                        "teslimat_aktif": True,
                        "teslimat_suresi": 1,
                    }
                )

        return True

