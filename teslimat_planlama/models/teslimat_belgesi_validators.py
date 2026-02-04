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
            record._validate_gecmis_tarih()
            record._validate_ayni_gun_teslimat()
            record._validate_pazar_gunu()
            record._validate_arac_kapatma()

            # İlçe-gün eşleşmesi herkes için geçerli (düzenle ile tarih değişince de)
            record._validate_ilce_gun_eslesmesi()

            # Yönetici ve küçük araç kontrolü (araç-ilçe uyumluluğu için)
            yonetici_mi = is_manager(self.env)
            small_vehicle = record.arac_id and record.arac_id.arac_tipi in SMALL_VEHICLE_TYPES

            if not yonetici_mi and not small_vehicle:
                record._validate_arac_ilce_uyumlulugu()

            record._validate_arac_kapasitesi()
            record._validate_ilce_gun_kapasitesi()

    def _validate_gecmis_tarih(self):
        """Geçmiş tarihe teslimat kaydı yasak (düzenle ile de)."""
        if not self.teslimat_tarihi:
            return
        istanbul_tz = pytz.timezone("Europe/Istanbul")
        simdi_istanbul = datetime.now(istanbul_tz)
        bugun = simdi_istanbul.date()
        if self.teslimat_tarihi < bugun:
            raise ValidationError(
                _(
                    "Geçmiş tarihe teslimat kaydedilemez!\n\n"
                    "Seçilen tarih: %(tarih)s\n"
                    "Bugün: %(bugun)s\n\n"
                    "Lütfen bugün veya ileri bir tarih seçin."
                )
                % {
                    "tarih": self.teslimat_tarihi.strftime("%d.%m.%Y"),
                    "bugun": bugun.strftime("%d.%m.%Y"),
                }
            )

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

    def _validate_arac_kapasitesi(self, teslimat_tarihi=None, arac_id=None, ilce_id=None):
        """Araç kapasitesi kontrolü.

        Opsiyonel parametreler write öncesi kontrol için (düzenle ile tarih değişince).
        """
        tarih = teslimat_tarihi if teslimat_tarihi is not None else self.teslimat_tarihi
        arac = arac_id if arac_id is not None else self.arac_id
        ilce = ilce_id if ilce_id is not None else self.ilce_id
        if arac and tarih:
            domain = [
                ("teslimat_tarihi", "=", tarih),
                ("arac_id", "=", arac.id if hasattr(arac, "id") else arac),
                ("durum", "!=", "iptal"),  # Sadece iptal hariç
                ("id", "!=", self.id),  # Kendisini hariç tut
            ]

            # İlçe bazlı kontrol
            if ilce:
                domain.append(("ilce_id", "=", ilce.id if hasattr(ilce, "id") else ilce))

            mevcut_teslimat_sayisi = self.env["teslimat.belgesi"].search_count(domain)

            # +1 ekle (kendisi için)
            toplam = mevcut_teslimat_sayisi + 1
            arac_rec = arac if hasattr(arac, "gunluk_teslimat_limiti") else self.env["teslimat.arac"].browse(arac)
            limit = arac_rec.gunluk_teslimat_limiti

            if toplam > limit:
                ilce_rec = ilce if hasattr(ilce, "name") else (self.env["teslimat.ilce"].browse(ilce) if ilce else None)
                ilce_bilgi = f" - {ilce_rec.name}" if ilce_rec else ""
                raise ValidationError(
                    _(f"Araç Kapasitesi Dolu!\n\n"
                      f"Araç: {arac_rec.name}{ilce_bilgi}\n"
                      f"Tarih: {tarih.strftime('%d.%m.%Y')}\n"
                      f"Kapasite: {toplam}/{limit}\n\n"
                      f"Bu tarih için araç kapasitesi dolmuştur.\n"
                      f"Lütfen farklı bir tarih veya araç seçin.")
                )

    def _validate_ilce_gun_kapasitesi(self, teslimat_tarihi=None, arac_id=None, ilce_id=None):
        """İlçe-gün kapasitesi kontrolü (çakışma / aşım engeli).

        Ana Sayfa'da görünen kapasite ile aynı kural: aynı (araç, ilçe, tarih)
        için kayıt sayısı ilçe-gün maksimum_teslimat'ı (ve araç günlük limiti) aşmasın.
        Opsiyonel parametreler write öncesi kontrol için (düzenle ile tarih değişince).
        """
        tarih = teslimat_tarihi if teslimat_tarihi is not None else self.teslimat_tarihi
        arac = arac_id if arac_id is not None else self.arac_id
        ilce = ilce_id if ilce_id is not None else self.ilce_id
        if not ilce or not arac or not tarih:
            return
        tarih = fields.Date.to_date(tarih)
        gun_kodu = get_gun_kodu(tarih)
        if not gun_kodu:
            return
        gun = self.env["teslimat.gun"].search([("gun_kodu", "=", gun_kodu)], limit=1)
        if not gun:
            return
        ilce_id_val = ilce.id if hasattr(ilce, "id") else ilce
        arac_id_val = arac.id if hasattr(arac, "id") else arac
        gun_ilce = self.env["teslimat.gun.ilce"].search(
            [
                ("gun_id", "=", gun.id),
                ("ilce_id", "=", ilce_id_val),
                ("tarih", "=", False),
            ],
            limit=1,
        )
        if not gun_ilce:
            return
        maksimum = gun_ilce.maksimum_teslimat
        arac_rec = arac if hasattr(arac, "gunluk_teslimat_limiti") else self.env["teslimat.arac"].browse(arac)
        arac_limiti = (arac_rec.gunluk_teslimat_limiti or 0)
        if arac_limiti > 0:
            maksimum = min(maksimum, arac_limiti)
        domain = [
            ("teslimat_tarihi", "=", tarih),
            ("arac_id", "=", arac_id_val),
            ("ilce_id", "=", ilce_id_val),
            ("durum", "!=", "iptal"),
            ("id", "!=", self.id),
        ]
        mevcut = self.env["teslimat.belgesi"].search_count(domain)
        toplam = mevcut + 1
        if toplam > maksimum:
            ilce_rec = ilce if hasattr(ilce, "name") else self.env["teslimat.ilce"].browse(ilce)
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
                    "arac": arac_rec.name,
                    "ilce": ilce_rec.name,
                    "tarih": tarih.strftime("%d.%m.%Y"),
                    "toplam": toplam,
                    "maks": maksimum,
                }
            )
