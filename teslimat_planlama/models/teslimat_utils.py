"""Teslimat Yardımcı Fonksiyonlar."""
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

import pytz

from .teslimat_constants import (
    ACTIVE_STATUSES,
    ARAC_KAPATMA_SEBEP_LABELS,
    CANCELLED_STATUS,
    COMPLETED_STATUS,
    FORECAST_DAYS,
    GUN_ESLESMESI,
    GUN_KODU_MAP,
    IN_TRANSIT_STATUSES,
    ISTANBUL_TIMEZONE,
    SAME_DAY_DELIVERY_CUTOFF_HOUR,
    SMALL_VEHICLE_TYPES,
    get_arac_kapatma_sebep_label,
)

if TYPE_CHECKING:
    from odoo import models


def calculate_day_count(start_date: date, end_date: date) -> int:
    """İki tarih arasındaki gün sayısını hesapla (başlangıç ve bitiş dahil).

    Args:
        start_date: Başlangıç tarihi
        end_date: Bitiş tarihi

    Returns:
        int: Gün sayısı (0 veya pozitif)
    """
    if not start_date or not end_date:
        return 0
    if end_date < start_date:
        return 0
    delta = end_date - start_date
    return delta.days + 1


def format_partner_address(partner) -> str:
    """Müşteri adresini formatla.
    
    Müşterinin tüm adres bilgilerini birleştirerek tek bir string döndürür.
    
    Args:
        partner: res.partner kaydı
        
    Returns:
        str: Formatlanmış adres string'i veya "Adres bilgisi bulunamadı"
    """
    if not partner:
        return ""
    
    adres_parcalari = []
    
    if partner.street:
        adres_parcalari.append(partner.street)
    if partner.street2:
        adres_parcalari.append(partner.street2)
    if partner.city:
        adres_parcalari.append(partner.city)
    if partner.state_id:
        adres_parcalari.append(partner.state_id.name)
    if partner.zip:
        adres_parcalari.append(partner.zip)
    if partner.country_id:
        adres_parcalari.append(partner.country_id.name)
    
    if adres_parcalari:
        return ", ".join(adres_parcalari)
    
    return "Adres bilgisi bulunamadı"


def get_gun_kodu(tarih: date) -> Optional[str]:
    """Tarih için gün kodunu döndür.

    Args:
        tarih: Kontrol edilecek tarih

    Returns:
        str: Gün kodu (pazartesi, sali, vb.) veya None
    """
    if not tarih:
        return None
    return GUN_KODU_MAP.get(tarih.weekday())


def is_pazar_gunu(tarih: date) -> bool:
    """Tarih pazar günü mü kontrol et.
    
    Args:
        tarih: Kontrol edilecek tarih
        
    Returns:
        bool: Pazar günü ise True
    """
    from .teslimat_constants import PAZAR_WEEKDAY
    
    if not tarih:
        return False
    return tarih.weekday() == PAZAR_WEEKDAY


def is_manager(env) -> bool:
    """Kullanıcının yönetici olup olmadığını kontrol et.

    Args:
        env: Odoo environment

    Returns:
        bool: Yönetici ise True
    """
    return env.user.has_group("teslimat_planlama.group_teslimat_manager")


def is_small_vehicle(arac) -> bool:
    """Araç küçük araç mı kontrol et.

    Args:
        arac: Araç kaydı (teslimat.arac)

    Returns:
        bool: Küçük araç ise True
    """
    if not arac:
        return False
    return arac.arac_tipi in SMALL_VEHICLE_TYPES


def get_istanbul_state(env):
    """İstanbul şehrini döndür (cached).

    Args:
        env: Odoo environment

    Returns:
        res.country.state: İstanbul kaydı veya None
    """
    # Cache key
    cache_key = '_istanbul_state_cache'

    # Check if already cached in environment context
    if hasattr(env, 'context') and cache_key in env.context:
        state_id = env.context[cache_key]
        if state_id:
            return env["res.country.state"].browse(state_id)
        return None

    # Search for Istanbul
    istanbul = env["res.country.state"].search(
        [("country_id.code", "=", "TR"), ("name", "=", "İstanbul")],
        limit=1
    )

    # Cache the result (store ID to avoid recordset serialization issues)
    if istanbul:
        env.context = dict(env.context, **{cache_key: istanbul.id})

    return istanbul


def validate_arac_ilce_eslesmesi(arac, ilce, bypass_for_manager: bool = True) -> tuple[bool, str]:
    """Araç-ilçe eşleştirmesini doğrula.
    
    Args:
        arac: Araç kaydı
        ilce: İlçe kaydı
        bypass_for_manager: Yöneticiler için kontrolü atla
        
    Returns:
        tuple: (Geçerli mi?, Mesaj)
    """
    if not arac or not ilce:
        return False, "Araç veya ilçe bulunamadı"
    
    # Yönetici kontrolü - Yöneticiler her şeyi yapabilir
    if bypass_for_manager and hasattr(arac, 'env') and is_manager(arac.env):
        return True, "Yönetici yetkisi - tüm eşleştirmeler geçerli ✓"
    
    # Küçük araçlar her yere gidebilir
    if arac.arac_tipi in SMALL_VEHICLE_TYPES:
        return True, "Küçük araç - tüm ilçelere gidebilir"
    
    # Yaka bazlı kontrol
    if arac.arac_tipi == "anadolu_yakasi":
        if ilce.yaka_tipi == "anadolu":
            return True, "Anadolu Yakası araç - Anadolu Yakası ilçe ✓"
        else:
            return False, f"Anadolu Yakası araç sadece Anadolu Yakası ilçelerine gidebilir (İlçe: {ilce.yaka_tipi})"
    
    elif arac.arac_tipi == "avrupa_yakasi":
        if ilce.yaka_tipi == "avrupa":
            return True, "Avrupa Yakası araç - Avrupa Yakası ilçe ✓"
        else:
            return False, f"Avrupa Yakası araç sadece Avrupa Yakası ilçelerine gidebilir (İlçe: {ilce.yaka_tipi})"
    
    return False, "Bilinmeyen araç tipi"


def check_pazar_gunu_validation(tarih, bypass_for_manager: bool = True, env=None) -> None:
    """Pazar günü kontrolü yap ve hata fırlat.

    Args:
        tarih: Kontrol edilecek tarih
        bypass_for_manager: Yöneticiler için kontrolü atla
        env: Odoo environment (yönetici kontrolü için)

    Raises:
        ValidationError: Pazar günü ise
    """
    from odoo.exceptions import ValidationError

    # Yönetici kontrolü
    if bypass_for_manager and env and is_manager(env):
        return  # Yöneticiler pazar günü de teslimat oluşturabilir

    if is_pazar_gunu(tarih):
        raise ValidationError(
            "Pazar günü teslimat yapılamaz! "
            "Lütfen başka bir gün seçin."
        )


# İstanbul timezone instance
_ISTANBUL_TZ = pytz.timezone(ISTANBUL_TIMEZONE)


def get_istanbul_time() -> datetime:
    """İstanbul saatini döndür.

    Returns:
        datetime: İstanbul timezone'unda şimdiki zaman
    """
    return datetime.now(_ISTANBUL_TZ)


def check_ayni_gun_saat_kontrolu(teslimat_tarihi: date, bypass_for_manager: bool = True, env=None) -> tuple[bool, str]:
    """Aynı gün teslimat için saat kontrolü yap.

    Saat 12:00'den sonra aynı güne teslimat yazılamaz.

    Args:
        teslimat_tarihi: Teslimat tarihi
        bypass_for_manager: Yöneticiler için kontrolü atla
        env: Odoo environment (yönetici kontrolü için)

    Returns:
        tuple: (Geçerli mi?, Mesaj)
    """
    # Yönetici kontrolü
    if bypass_for_manager and env and is_manager(env):
        return True, "Yönetici yetkisi - saat kontrolü atlandı"

    simdi = get_istanbul_time()
    bugun = simdi.date()

    if teslimat_tarihi != bugun:
        return True, "Farklı gün - saat kontrolü gerekmiyor"

    saat = simdi.hour
    dakika = simdi.minute

    if saat >= SAME_DAY_DELIVERY_CUTOFF_HOUR:
        return False, (
            f"Aynı gün teslimat yazılamaz!\n\n"
            f"İstanbul Saati: {saat:02d}:{dakika:02d}\n"
            f"Saat {SAME_DAY_DELIVERY_CUTOFF_HOUR}:00'dan sonra bugüne teslimat planlanamaz."
        )

    return True, f"Saat kontrolü geçti (şu an: {saat:02d}:{dakika:02d})"


def check_arac_kapatma(env, arac_id: int, teslimat_tarihi: date, bypass_for_manager: bool = True) -> tuple[bool, Optional[str]]:
    """Araç kapatma kontrolü yap.

    Args:
        env: Odoo environment
        arac_id: Araç ID
        teslimat_tarihi: Teslimat tarihi
        bypass_for_manager: Yöneticiler için kontrolü atla

    Returns:
        tuple: (Geçerli mi?, Hata mesajı veya None)
    """
    # Yönetici kontrolü
    if bypass_for_manager and is_manager(env):
        return True, None

    if not arac_id or not teslimat_tarihi:
        return True, None

    kapali, kapatma = env["teslimat.arac.kapatma"].arac_kapali_mi(arac_id, teslimat_tarihi)

    if kapali and kapatma:
        sebep_text = get_arac_kapatma_sebep_label(kapatma.sebep)
        kapatan_kisi = kapatma.kapatan_kullanici_id.name or "Bilinmiyor"
        arac = env["teslimat.arac"].browse(arac_id)
        arac_name = arac.name if arac else "Bilinmiyor"

        mesaj = (
            f"Bu tarihte araç kapalı!\n\n"
            f"Tarih: {teslimat_tarihi.strftime('%d.%m.%Y')}\n"
            f"Araç: {arac_name}\n"
            f"Sebep: {sebep_text}\n"
            f"Kapatan: {kapatan_kisi}"
        )
        if kapatma.aciklama:
            mesaj += f"\nAçıklama: {kapatma.aciklama}"
        mesaj += "\n\nLütfen başka bir tarih seçin."

        return False, mesaj

    return True, None


# Haftalık program sabiti (tekrarlayan kod önleme)
HAFTALIK_PROGRAM = {
    "pazartesi": 0,
    "sali": 1,
    "carsamba": 2,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}
