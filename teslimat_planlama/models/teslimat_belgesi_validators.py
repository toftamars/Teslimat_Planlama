"""Teslimat Belgesi - Validasyon Metodları.

Bu modül teslimat belgesi validasyon metodlarını içerir.
Mixin pattern kullanılarak ana model'den ayrılmıştır.
"""

from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .teslimat_constants import (
    CANCELLED_STATUS,
    COMPLETED_STATUS,
    SMALL_VEHICLE_TYPES,
)
from .teslimat_utils import (
    check_arac_kapatma,
    get_gun_kodu,
    is_manager,
    is_pazar_gunu,
)


class TeslimatBelgesiValidators(models.AbstractModel):
    """Teslimat Belgesi Validasyon Mixin.

    Bu class teslimat belgesi için tüm validasyon metodlarını içerir.
    """

    _name = "teslimat.belgesi.validators"
    _description = "Teslimat Belgesi Validasyon Mixin"

    @api.constrains("teslimat_tarihi", "arac_id", "ilce_id", "durum")
    def _check_teslimat_validations(self):
        """Teslimat belgesi validasyonları.

        Tüm kritik validasyonları çalıştırır.
        """
        for record in self:
            # Teslim edilmiş veya iptal belgeleri kontrol etme
            if record.durum in [COMPLETED_STATUS, CANCELLED_STATUS]:
                continue

            # Validasyon kontrollerini sırayla çalıştır
            record._validate_ayni_gun_teslimat()
            record._validate_pazar_gunu()
            record._validate_arac_kapatma()

            # Yönetici ve küçük araç kontrolü (birçok validasyonda kullanılıyor)
            yonetici_mi = is_manager(self.env)
            small_vehicle = record.arac_id and record.arac_id.arac_tipi in SMALL_VEHICLE_TYPES

            # Yönetici ve küçük araçlar için bazı kontroller atlanır
            if not yonetici_mi and not small_vehicle:
                record._validate_arac_ilce_uyumlulugu()
                record._validate_ilce_gun_eslesmesi()

            record._validate_arac_kapasitesi()
            record._validate_ilce_gun_kapasitesi()

    def _validate_ayni_gun_teslimat(self):
        """Aynı gün teslimat kontrolü (12:00 sonrası yasak)."""
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        simdi_istanbul = datetime.now(istanbul_tz)
        bugun = simdi_istanbul.date()
        saat = simdi_istanbul.hour
        dakika = simdi_istanbul.minute

        if self.teslimat_tarihi == bugun and (saat >= 12):
            raise ValidationError(
                _(f"Aynı gün teslimat yazılamaz!\n\n"
                  f"İstanbul Saati: {saat:02d}:{dakika:02d}\n"
                  f"Teslimat Tarihi: {self.teslimat_tarihi}\n\n"
                  f"Saat 12:00'dan sonra bugüne teslimat planlanamaz.\n"
                  f"Lütfen yarın veya sonraki günler için teslimat planlayın.")
            )

    def _validate_pazar_gunu(self):
        """Pazar günü kontrolü."""
        if is_pazar_gunu(self.teslimat_tarihi):
            raise ValidationError(
                _("Pazar günü teslimat yapılamaz!\n\n"
                  "Lütfen farklı bir gün seçin.")
            )

    def _validate_arac_kapatma(self):
        """Araç kapatma kontrolü."""
        if self.teslimat_tarihi and self.arac_id:
            gecerli, hata_mesaji = check_arac_kapatma(
                self.env, self.arac_id.id, self.teslimat_tarihi, bypass_for_manager=False
            )
            if not gecerli:
                raise ValidationError(_(hata_mesaji))

    def _validate_arac_ilce_uyumlulugu(self):
        """Araç-İlçe uyumluluğu kontrolü."""
        if self.ilce_id and self.arac_id:
            if self.ilce_id not in self.arac_id.uygun_ilceler:
                arac_tipi_label = dict(self.arac_id._fields["arac_tipi"].selection).get(
                    self.arac_id.arac_tipi, self.arac_id.arac_tipi
                )
                raise ValidationError(
                    _(f"Araç-İlçe Uyumsuzluğu!\n\n"
                      f"Araç: {self.arac_id.name} ({arac_tipi_label})\n"
                      f"İlçe: {self.ilce_id.name}\n\n"
                      f"Bu araç bu ilçeye teslimat yapamaz.\n"
                      f"Lütfen uygun bir araç veya ilçe seçin.")
                )

    def _validate_ilce_gun_eslesmesi(self):
        """İlçe-gün eşleşmesi kontrolü."""
        if self.ilce_id and self.arac_id:
            gun_kodu = get_gun_kodu(self.teslimat_tarihi)

            if gun_kodu:
                gun = self.env["teslimat.gun"].search(
                    [("gun_kodu", "=", gun_kodu)], limit=1
                )
                if gun:
                    gun_ilce = self.env["teslimat.gun.ilce"].search(
                        [
                            ("gun_id", "=", gun.id),
                            ("ilce_id", "=", self.ilce_id.id),
                            ("tarih", "=", False),  # Genel kurallar
                        ],
                        limit=1,
                    )

                    if not gun_ilce:
                        raise ValidationError(
                            _(f"İlçe-Gün Eşleşmesi Hatası!\n\n"
                              f"İlçe: {self.ilce_id.name}\n"
                              f"Gün: {gun.name}\n\n"
                              f"Bu ilçeye bu gün teslimat yapılamaz.\n"
                              f"Lütfen uygun bir gün seçin.")
                        )

    def _validate_arac_kapasitesi(self):
        """Araç kapasitesi kontrolü."""
        if self.arac_id and self.teslimat_tarihi:
            domain = [
                ("teslimat_tarihi", "=", self.teslimat_tarihi),
                ("arac_id", "=", self.arac_id.id),
                ("durum", "!=", "iptal"),  # Sadece iptal hariç
                ("id", "!=", self.id),  # Kendisini hariç tut
            ]

            # İlçe bazlı kontrol
            if self.ilce_id:
                domain.append(("ilce_id", "=", self.ilce_id.id))

            mevcut_teslimat_sayisi = self.env["teslimat.belgesi"].search_count(domain)

            # +1 ekle (kendisi için)
            toplam = mevcut_teslimat_sayisi + 1

            if toplam > self.arac_id.gunluk_teslimat_limiti:
                ilce_bilgi = f" - {self.ilce_id.name}" if self.ilce_id else ""
                raise ValidationError(
                    _(f"Araç Kapasitesi Dolu!\n\n"
                      f"Araç: {self.arac_id.name}{ilce_bilgi}\n"
                      f"Tarih: {self.teslimat_tarihi.strftime('%d.%m.%Y')}\n"
                      f"Kapasite: {toplam}/{self.arac_id.gunluk_teslimat_limiti}\n\n"
                      f"Bu tarih için araç kapasitesi dolmuştur.\n"
                      f"Lütfen farklı bir tarih veya araç seçin.")
                )

    def _validate_ilce_gun_kapasitesi(self):
        """İlçe-gün kapasitesi kontrolü (çakışma / aşım engeli).

        Ana Sayfa'da görünen 'son X kapasite' ile aynı kural: aynı (araç, ilçe, tarih)
        için kayıt sayısı ilçe-gün maksimum_teslimat'ı aşmasın. Başka personel aynı
        güne teslimat yazdıysa kaydetmek isteyen kullanıcıya uyarı verilir.
        Yönetici bypass edilir (acil durum override).
        """
        if is_manager(self.env):
            return
        if not self.ilce_id or not self.arac_id or not self.teslimat_tarihi:
            return
        tarih = fields.Date.to_date(self.teslimat_tarihi)
        gun_kodu = get_gun_kodu(tarih)
        if not gun_kodu:
            return
        gun = self.env["teslimat.gun"].search([("gun_kodu", "=", gun_kodu)], limit=1)
        if not gun:
            return
        gun_ilce = self.env["teslimat.gun.ilce"].search(
            [
                ("gun_id", "=", gun.id),
                ("ilce_id", "=", self.ilce_id.id),
                ("tarih", "=", False),
            ],
            limit=1,
        )
        if not gun_ilce:
            return
        maksimum = gun_ilce.maksimum_teslimat
        domain = [
            ("teslimat_tarihi", "=", tarih),
            ("arac_id", "=", self.arac_id.id),
            ("ilce_id", "=", self.ilce_id.id),
            ("durum", "!=", "iptal"),
            ("id", "!=", self.id),
        ]
        mevcut = self.env["teslimat.belgesi"].search_count(domain)
        toplam = mevcut + 1
        if toplam > maksimum:
            raise ValidationError(
                _(
                    "İlçe-Gün Kapasitesi Dolu!\n\n"
                    "Bu tarih ve ilçe için kapasite başka bir teslimat ile doldurulmuş.\n"
                    "Araç: %(arac)s\n"
                    "İlçe: %(ilce)s\n"
                    "Tarih: %(tarih)s\n"
                    "Kapasite: %(toplam)s/%(maks)s\n\n"
                    "Lütfen sayfayı yenileyip güncel kapasiteye göre farklı bir gün seçin."
                )
                % {
                    "arac": self.arac_id.name,
                    "ilce": self.ilce_id.name,
                    "tarih": tarih.strftime("%d.%m.%Y"),
                    "toplam": toplam,
                    "maks": maksimum,
                }
            )
