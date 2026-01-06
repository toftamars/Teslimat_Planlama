"""Teslimat Gün Yönetimi Modeli."""
import logging
from datetime import timedelta
from typing import List, Optional

from odoo import api, fields, models
from odoo.exceptions import ValidationError

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
    mevcut_teslimat_sayisi = fields.Integer(
        string="Mevcut Teslimat Sayısı",
        compute="_compute_mevcut_teslimat",
        store=True,
    )
    kalan_teslimat_kapasitesi = fields.Integer(
        string="Kalan Teslimat Kapasitesi",
        compute="_compute_kalan_kapasite",
        store=True,
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

    @api.depends("ilce_ids", "ilce_ids.teslimat_sayisi")
    def _compute_mevcut_teslimat(self) -> None:
        """Bugün için mevcut teslimat sayısını hesapla."""
        for record in self:
            bugun = fields.Date.today()
            bugun_teslimatlar = record.ilce_ids.filtered(
                lambda i: i.tarih == bugun
            )
            record.mevcut_teslimat_sayisi = sum(
                bugun_teslimatlar.mapped("teslimat_sayisi")
            )

    @api.depends("gunluk_maksimum_teslimat", "mevcut_teslimat_sayisi")
    def _compute_kalan_kapasite(self) -> None:
        """Kalan teslimat kapasitesini hesapla."""
        for record in self:
            record.kalan_teslimat_kapasitesi = (
                record.gunluk_maksimum_teslimat - record.mevcut_teslimat_sayisi
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

    @api.model
    def get_uygun_gunler(
        self, ilce_id: Optional[int] = None, tarih: Optional[fields.Date] = None
    ) -> "TeslimatGun":
        """Belirli ilçe için uygun günleri getir (Dinamik - Database'den).

        Args:
            ilce_id: İlçe ID (opsiyonel)
            tarih: Tarih kontrolü için (opsiyonel)

        Returns:
            Recordset: Uygun günler
        """
        domain = [
            ("aktif", "=", True),
            ("gecici_kapatma", "=", False),
        ]

        # Tarih kontrolü
        if tarih:
            domain += [
                "|",
                ("kapatma_bitis", "=", False),
                ("kapatma_bitis", "<", tarih),
            ]

        # İlçe bazlı filtreleme (dinamik - database'den)
        if ilce_id:
            ilce = self.env["teslimat.ilce"].browse(ilce_id)
            if ilce.exists():
                # İlçe-gün eşleşmeleri database'den çekilir
                gun_ilce_ids = self.env["teslimat.gun.ilce"].search(
                    [("ilce_id", "=", ilce_id), ("maksimum_teslimat", ">", 0)]
                )
                gun_ids = gun_ilce_ids.mapped("gun_id").ids
                if gun_ids:
                    domain.append(("id", "in", gun_ids))
                else:
                    # Eşleşme yoksa boş döndür
                    return self.browse()

        return self.search(domain, order="sequence")

    @api.model
    def check_availability(
        self, date: fields.Date, district_id: Optional[int] = None
    ) -> dict:
        """Belirli bir tarih için teslimat günü müsaitlik kontrolü.

        Args:
            date: Kontrol edilecek tarih
            district_id: İlçe ID (opsiyonel)

        Returns:
            dict: Müsaitlik durumu ve bilgileri
        """
        if not date:
            return {"available": False, "reason": "Tarih belirtilmedi"}

        # Haftanın gününü belirle (0=Pazartesi, 1=Salı, vs.)
        day_mapping = {
            0: "pazartesi",
            1: "sali",
            2: "carsamba",
            3: "persembe",
            4: "cuma",
            5: "cumartesi",
            6: "pazar",
        }

        day_of_week = day_mapping.get(date.weekday())
        if not day_of_week:
            return {"available": False, "reason": "Geçersiz gün"}

        # Günü bul
        day = self.search([("gun_kodu", "=", day_of_week)], limit=1)
        if not day:
            return {
                "available": False,
                "reason": f"{day_of_week.capitalize()} günü bulunamadı",
            }

        # 1. Gün aktif mi?
        if not day.aktif:
            return {"available": False, "reason": f"{day.name} günü aktif değil"}

        # 2. Geçici kapatılmış mı?
        if day.gecici_kapatma:
            return {
                "available": False,
                "reason": f"{day.name} günü geçici olarak kapatılmış",
            }

        # 3. Kapatma tarihleri geçerli mi?
        if day.kapatma_baslangic and day.kapatma_bitis:
            if day.kapatma_baslangic <= date <= day.kapatma_bitis:
                return {
                    "available": False,
                    "reason": (
                        f"{day.name} günü "
                        f"{day.kapatma_baslangic.strftime('%d/%m/%Y')} - "
                        f"{day.kapatma_bitis.strftime('%d/%m/%Y')} "
                        "tarihleri arasında kapatılmış"
                    ),
                }

        # 4. İlçe o gün için tanımlı mı? (Dinamik - Database'den kontrol)
        if district_id:
            ilce = self.env["teslimat.ilce"].browse(district_id)
            if not ilce.exists():
                return {"available": False, "reason": "İlçe bulunamadı"}

            # Database'den ilçe-gün eşleşmesi kontrol edilir
            gun_ilce = self.env["teslimat.gun.ilce"].search(
                [("gun_id", "=", day.id), ("ilce_id", "=", district_id)],
                limit=1,
            )

            if not gun_ilce:
                return {
                    "available": False,
                    "reason": f"Seçilen ilçeye {day.name} günü teslimat yapılamaz",
                }

        # 5. Genel kapasite kontrolü
        if day.mevcut_teslimat_sayisi >= day.gunluk_maksimum_teslimat:
            return {
                "available": False,
                "reason": (
                    f"Günlük genel kapasite dolu "
                    f"({day.mevcut_teslimat_sayisi}/{day.gunluk_maksimum_teslimat})"
                ),
            }

        # Tüm kontroller geçildi - müsait
        gun_ilce = (
            self.env["teslimat.gun.ilce"]
            .search(
                [("gun_id", "=", day.id), ("ilce_id", "=", district_id)],
                limit=1,
            )
            if district_id
            else None
        )

        return {
            "available": True,
            "reason": "Müsait",
            "day_id": day.id,
            "day_name": day.name,
            "remaining_capacity": day.kalan_teslimat_kapasitesi,
            "district_capacity": gun_ilce.kalan_kapasite if gun_ilce else None,
        }

    @api.model
    def get_available_dates(
        self,
        start_date: fields.Date,
        end_date: fields.Date,
        district_id: Optional[int] = None,
        max_days: int = 7,
    ) -> List[dict]:
        """Belirli tarih aralığında müsait günleri getir.

        Args:
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi
            district_id: İlçe ID (opsiyonel)
            max_days: Maksimum gün sayısı

        Returns:
            List[dict]: Müsait tarihler listesi
        """
        if not start_date or not end_date:
            return []

        available_dates = []
        current_date = start_date

        while current_date <= end_date and len(available_dates) < max_days:
            availability = self.check_availability(current_date, district_id)

            if availability["available"]:
                available_dates.append(
                    {
                        "date": current_date,
                        "day_name": availability["day_name"],
                        "remaining_capacity": availability["remaining_capacity"],
                        "district_capacity": availability.get("district_capacity"),
                    }
                )

            current_date += timedelta(days=1)

        return available_dates

    @api.model
    def get_next_available_date(
        self, district_id: Optional[int] = None, start_date: Optional[fields.Date] = None
    ) -> Optional[dict]:
        """Bir sonraki müsait teslimat tarihini getir.

        Args:
            district_id: İlçe ID (opsiyonel)
            start_date: Başlangıç tarihi (varsayılan: bugün)

        Returns:
            Optional[dict]: Müsait tarih bilgisi veya None
        """
        if not start_date:
            start_date = fields.Date.today()

        # 30 gün ileriye kadar kontrol et
        end_date = start_date + timedelta(days=30)
        available_dates = self.get_available_dates(
            start_date, end_date, district_id, max_days=1
        )

        if available_dates:
            return available_dates[0]

        return None

