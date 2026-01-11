"""Teslimat Yardımcı Fonksiyonlar ve Sabitler."""
from datetime import date
from typing import Optional

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


def validate_arac_ilce_eslesmesi(arac, ilce) -> tuple[bool, str]:
    """Araç-ilçe eşleştirmesini doğrula.
    
    Args:
        arac: Araç kaydı
        ilce: İlçe kaydı
        
    Returns:
        tuple: (Geçerli mi?, Mesaj)
    """
    if not arac or not ilce:
        return False, "Araç veya ilçe bulunamadı"
    
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
