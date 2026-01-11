"""Teslimat Planlama Utility Fonksiyonları."""
import logging
from typing import Dict, Optional

from odoo import fields

_logger = logging.getLogger(__name__)

# Gün kodu mapping'i (weekday() → gun_kodu)
GUN_KODU_MAP = {
    0: "pazartesi",
    1: "sali",
    2: "carsamba",
    3: "persembe",
    4: "cuma",
    5: "cumartesi",
    6: "pazar",
}

# Türkçe gün adları mapping'i
GUN_ESLESMESI = {
    "Monday": "Pazartesi",
    "Tuesday": "Salı",
    "Wednesday": "Çarşamba",
    "Thursday": "Perşembe",
    "Friday": "Cuma",
    "Saturday": "Cumartesi",
    "Sunday": "Pazar",
}


def get_gun_kodu(tarih: fields.Date) -> Optional[str]:
    """Tarihten gün kodunu döndür.
    
    Args:
        tarih: Kontrol edilecek tarih
        
    Returns:
        Optional[str]: Gün kodu (pazartesi, sali, vs.) veya None
    """
    if not tarih:
        return None
    date_obj = fields.Date.to_date(tarih)
    return GUN_KODU_MAP.get(date_obj.weekday())


def is_pazar_gunu(tarih: fields.Date) -> bool:
    """Tarihin pazar günü olup olmadığını kontrol et.
    
    Args:
        tarih: Kontrol edilecek tarih
        
    Returns:
        bool: Pazar günü ise True, değilse False
    """
    if not tarih:
        return False
    date_obj = fields.Date.to_date(tarih)
    return date_obj.weekday() == 6


def check_pazar_gunu_validation(tarih: fields.Date) -> None:
    """Pazar günü kontrolü yap, pazar ise hata fırlat.
    
    Args:
        tarih: Kontrol edilecek tarih
        
    Raises:
        UserError: Tarih pazar günü ise
    """
    from odoo.exceptions import UserError
    from odoo import _
    
    if is_pazar_gunu(tarih):
        raise UserError(
            _(
                "Pazar günü teslimat yapılamaz! "
                "Tüm araçlar pazar günü kapalıdır. "
                "Lütfen başka bir tarih seçin."
            )
        )


def get_turkce_gun_adi(ingilizce_gun: str) -> str:
    """İngilizce gün adını Türkçe'ye çevir.
    
    Args:
        ingilizce_gun: İngilizce gün adı (Monday, Tuesday, vs.)
        
    Returns:
        str: Türkçe gün adı
    """
    return GUN_ESLESMESI.get(ingilizce_gun, ingilizce_gun)

