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
                _("Aynı gün teslimat yazılamaz!\n\n"
                  "İstanbul Saati: %(saat)02d:%(dakika)02d\n"
                  "Teslimat Tarihi: %(teslimat_tarihi)s\n\n"
                  "Saat 12:00'dan sonra bugüne teslimat planlanamaz.\n"
                  "Lütfen yarın veya sonraki günler için teslimat planlayın.") % {
                    "saat": saat,
                    "dakika": dakika,
                    "teslimat_tarihi": self.teslimat_tarihi,
                }
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
                # hata_mesaji zaten check_arac_kapatma içinde _() ile çevrildi
                raise ValidationError(hata_mesaji)

    def _validate_arac_ilce_uyumlulugu(self):
        """Araç-İlçe uyumluluğu kontrolü."""
        if self.ilce_id and self.arac_id:
            if self.ilce_id not in self.arac_id.uygun_ilceler:
                arac_tipi_label = dict(self.arac_id._fields["arac_tipi"].selection).get(
                    self.arac_id.arac_tipi, self.arac_id.arac_tipi
                )
                raise ValidationError(
                    _("Araç-İlçe Uyumsuzluğu!\n\n"
                      "Araç: %(arac)s (%(arac_tipi)s)\n"
                      "İlçe: %(ilce)s\n\n"
                      "Bu araç bu ilçeye teslimat yapamaz.\n"
                      "Lütfen uygun bir araç veya ilçe seçin.") % {
                        "arac": self.arac_id.name,
                        "arac_tipi": arac_tipi_label,
                        "ilce": self.ilce_id.name,
                    }
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
                            _("İlçe-Gün Eşleşmesi Hatası!\n\n"
                              "İlçe: %(ilce)s\n"
                              "Gün: %(gun)s\n\n"
                              "Bu ilçeye bu gün teslimat yapılamaz.\n"
                              "Lütfen uygun bir gün seçin.") % {
                                "ilce": self.ilce_id.name,
                                "gun": gun.name,
                            }
                        )

    def _validate_arac_kapasitesi(self, teslimat_tarihi=None, arac_id=None, ilce_id=None):
        """Araç kapasitesi kontrolü.

        Araç günlük limiti tüm ilçeler toplamı için geçerlidir (Ana Sayfa ile uyumlu).
        İlçe bazlı sayım yapılmaz; aynı araç+tarih için toplam teslimat sayılır.
        Opsiyonel parametreler write öncesi kontrol için (düzenle ile tarih değişince).
        """
        tarih = teslimat_tarihi if teslimat_tarihi is not None else self.teslimat_tarihi
        arac = arac_id if arac_id is not None else self.arac_id
        ilce = ilce_id if ilce_id is not None else self.ilce_id
        if tarih:
            tarih = fields.Date.to_date(tarih)
        if arac and tarih:
            # RULE A: araç+tarih, tüm ilçeler (Ana Sayfa ile aynı mantık)
            arac_id_val = arac.id if hasattr(arac, "id") else arac
            mevcut_teslimat_sayisi = self._say_arac_gunluk(arac_id_val, tarih, self.id)
            toplam = mevcut_teslimat_sayisi + 1
            arac_rec = arac if hasattr(arac, "gunluk_teslimat_limiti") else self.env["teslimat.arac"].browse(arac)
            limit = arac_rec.gunluk_teslimat_limiti
            if limit is None:
                limit = 0
            if limit > 0 and toplam > limit:
                ilce_rec = ilce if hasattr(ilce, "name") else (self.env["teslimat.ilce"].browse(ilce) if ilce else None)
                ilce_bilgi = f" - {ilce_rec.name}" if ilce_rec else ""
                raise ValidationError(
                    _("Araç Kapasitesi Dolu!\n\n"
                      "Araç: %(arac)s%(ilce_bilgi)s\n"
                      "Tarih: %(tarih)s\n"
                      "Kapasite: %(toplam)s/%(limit)s\n\n"
                      "Bu tarih için araç kapasitesi dolmuştur.\n"
                      "Lütfen farklı bir tarih veya araç seçin.") % {
                        "arac": arac_rec.name,
                        "ilce_bilgi": ilce_bilgi,
                        "tarih": tarih.strftime('%d.%m.%Y'),
                        "toplam": toplam,
                        "limit": limit,
                    }
                )

# İŞ KURALI: Araç günde TOPLAM en fazla gunluk_teslimat_limiti teslimat yapar
# (tüm ilçeler birlikte). İlçe BAŞINA ayrı tavan YOKTUR → bu kuralı RULE A
# (_validate_arac_kapasitesi) tek başına uygular. Eski ilçe-başına tavan kontrolü
# (_validate_ilce_gun_kapasitesi / RULE B) ve gun_ilce.maksimum_teslimat sayı
# limiti kaldırıldı. İlçe-gün EŞLEŞMESİ (_validate_ilce_gun_eslesmesi) = "o gün
# o ilçeye gidiliyor mu" programı, ayrı bir yes/no kontrolü olarak korunur.
