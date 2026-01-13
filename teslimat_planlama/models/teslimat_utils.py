"""Teslimat Yardımcı Fonksiyonlar ve Sabitler."""
from datetime import date
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from odoo import models

# Gün kodları mapping
GUN_KODU_MAP = {
    0: "pazartesi",
    1: "sali",
    2: "carsamba",
    3: "persembe",
    4: "cuma",
    5: "cumartesi",
    6: "pazar",
}

# Gün isimleri eşleşmesi (İngilizce -> Türkçe)
GUN_ESLESMESI = {
    "Monday": "Pazartesi",
    "Tuesday": "Salı",
    "Wednesday": "Çarşamba",
    "Thursday": "Perşembe",
    "Friday": "Cuma",
    "Saturday": "Cumartesi",
    "Sunday": "Pazar",
}


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
    if not tarih:
        return False
    return tarih.weekday() == 6  # 6 = Pazar


def is_manager(env) -> bool:
    """Kullanıcının yönetici olup olmadığını kontrol et.
    
    Args:
        env: Odoo environment
        
    Returns:
        bool: Yönetici ise True
    """
    return env.user.has_group("teslimat_planlama.group_teslimat_manager")


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
    if arac.arac_tipi in ["kucuk_arac_1", "kucuk_arac_2", "ek_arac"]:
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
