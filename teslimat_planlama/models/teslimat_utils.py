"""Teslimat Yardımcı Fonksiyonlar."""
import re
from datetime import date, datetime
from typing import List, Optional, Tuple
from urllib.parse import urlencode

import pytz

from odoo import _

from .teslimat_constants import (
    GUN_KODU_MAP,
    ISTANBUL_TIMEZONE,
    SAME_DAY_DELIVERY_CUTOFF_HOUR,
    SMALL_VEHICLE_TYPES,
    get_arac_kapatma_sebep_label,
)


def normalize_turkce(adi: str) -> str:
    """İlçe/metin adını locale-bağımsız eşleştirme için normalize eder.

    Türkçe noktalı İ (U+0130) ve noktasız ı (U+0131) ASCII karşılığına çevrilir,
    sonra büyük harfe alınır. Diğer Türkçe harfler (Ş/Ö/Ü/Ç/Ğ) eşleştirmenin
    iki tarafında da korunduğu için ayrıca foldlanmaz.
    """
    if not adi:
        return ""
    return (adi or "").replace("İ", "I").replace("ı", "i").upper()


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


def _title_case_tr(text: str) -> str:
    """Resmi BÜYÜK HARF Türkçe adresleri Google Maps formatına çevir."""
    if not text:
        return ""
    return " ".join(_turkish_capitalize_word(word) for word in text.strip().split())


def _turkish_lower(text: str) -> str:
    """Resmi adreslerdeki ASCII I (ı) ve İ ayrımını koruyarak küçült."""
    return text.replace("I", "ı").replace("İ", "i").lower()


def _turkish_capitalize_word(word: str) -> str:
    """Tek kelimeyi Türkçe title case'e çevir."""
    lower = _turkish_lower(word)
    if not lower:
        return lower
    first = lower[0]
    if first == "i":
        return "İ" + lower[1:]
    if first == "ı":
        return "I" + lower[1:]
    return first.upper() + lower[1:]


def _parse_turkish_street_for_maps(street: str) -> Optional[Tuple[str, str, str]]:
    """Resmi sokak satırını Google Maps formatına ayır.

    Örnek girdi:
        ÖRNEK MAH. ÇINAR SK. NO: 5 İÇ KAPI NO: 3 KADIKÖY / İSTANBUL
    Örnek çıktı:
        ("Çınar Sokağı", "5", "Örnek")
    """
    if not street:
        return None

    text = street.strip()

    # Sokak sonundaki "ILCE / IL" kalıbını kaldır
    text = re.sub(
        r"\s+[A-Za-zÇĞİÖŞÜçğıöşü\s]+\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü\s]+$",
        "",
        text,
    ).strip()

    # İç kapı numarası haritalarda gürültü — ana kapı/blok no yeterli
    text = re.sub(r"\s*İÇ\s+KAPI\s+NO[:\s]*\d+", "", text, flags=re.IGNORECASE).strip()

    mahalle = ""
    mah_match = re.match(r"^(?P<mahalle>.+?)\s+MAH(?:\.|ALLESI)\s+", text, re.IGNORECASE)
    if mah_match:
        mahalle = _title_case_tr(mah_match.group("mahalle"))
        text = text[mah_match.end() :].strip()

    door_no = ""
    no_match = re.search(r"(?:BLOK\s+)?NO[:\s]*(?P<no>\d+)", text, re.IGNORECASE)
    if no_match:
        door_no = no_match.group("no")

    street_patterns = (
        (r"(?P<name>.+?)\s+SK\.", "Sokağı"),
        (r"(?P<name>.+?)\s+SOK\.", "Sokağı"),
        (r"(?P<name>.+?)\s+SOKAK", "Sokağı"),
        (r"(?P<name>.+?)\s+CD\.", "Caddesi"),
        (r"(?P<name>.+?)\s+CAD\.", "Caddesi"),
        (r"(?P<name>.+?)\s+CADDE", "Caddesi"),
        (r"(?P<name>.+?)\s+BULVAR", "Bulvarı"),
        (r"(?P<name>.+?)\s+BLV\.", "Bulvarı"),
    )
    for pattern, suffix in street_patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            sokak = f"{_title_case_tr(match.group('name').strip())} {suffix}"
            return sokak, door_no, mahalle

    return None


def _format_maps_location(city: str, state: str, zip_code: str) -> str:
    """34660 Üsküdar/İstanbul biçiminde konum parçası."""
    city_t = _title_case_tr(city)
    state_t = _title_case_tr(state)
    if zip_code and city_t and state_t:
        return f"{zip_code} {city_t}/{state_t}"
    if city_t and state_t:
        return f"{city_t}/{state_t}"
    if city_t:
        return city_t
    if state_t:
        return state_t
    return zip_code


def format_address_for_google_maps(partner) -> str:
    """Resmi müşteri adresini Google Maps'in anlayacağı formata çevir.

    Örnek: Çınar Sokağı No:5, Örnek, 34710 Kadıköy/İstanbul
    """
    if not partner:
        return ""

    lat = partner.partner_latitude
    lng = partner.partner_longitude
    if lat and lng:
        return f"{lat},{lng}"

    street = (partner.street or "").strip()
    city = (partner.city or "").strip()
    state = partner.state_id.name.strip() if partner.state_id else ""
    zip_code = (partner.zip or "").strip()
    location = _format_maps_location(city, state, zip_code)

    parsed = _parse_turkish_street_for_maps(street)
    if parsed:
        sokak, door_no, mahalle = parsed
        if door_no and mahalle and location:
            return f"{sokak} No:{door_no}, {mahalle}, {location}"
        if door_no and location:
            return f"{sokak} No:{door_no}, {location}"
        if mahalle and location:
            return f"{sokak}, {mahalle}, {location}"
        if location:
            return f"{sokak}, {location}"
        if door_no:
            return f"{sokak} No:{door_no}"
        return sokak

    # Resmi format parse edilemezse sadeleştirilmiş yedek
    return prepare_maps_destination_fallback(partner)


def prepare_maps_destination_fallback(partner) -> str:
    """Parse edilemeyen adresler için sadeleştirilmiş yedek format."""
    street = (partner.street or "").strip()
    street2 = (partner.street2 or "").strip()
    city = (partner.city or "").strip()
    state = partner.state_id.name.strip() if partner.state_id else ""
    zip_code = (partner.zip or "").strip()

    if street and " / " in street:
        prefix, suffix = street.rsplit(" / ", 1)
        suffix_norm = normalize_turkce(suffix)
        if state and suffix_norm == normalize_turkce(state):
            street = prefix.strip()
        elif city and suffix_norm == normalize_turkce(city):
            street = prefix.strip()

    if street and city:
        city_norm = normalize_turkce(city)
        street_norm = normalize_turkce(street)
        if street_norm.endswith(city_norm):
            street = street[: len(street) - len(city)].strip()

    location = _format_maps_location(city, state, zip_code)
    parts = _dedupe_address_parts([street, street2, location])
    return ", ".join(parts)


def prepare_maps_destination(partner) -> str:
    """Google Maps yol tarifi için hedef metnini hazırla."""
    return format_address_for_google_maps(partner)


def _dedupe_address_parts(parts: List[str]) -> List[str]:
    """Adres parçalarında büyük/küçük harf farkını yok sayarak tekrarı önle."""
    seen = set()
    result = []
    for part in parts:
        part = (part or "").strip()
        if not part:
            continue
        key = normalize_turkce(part)
        if key in seen:
            continue
        seen.add(key)
        result.append(part)
    return result


def build_google_maps_directions_url(
    destination: str,
    origin: Optional[str] = None,
    waypoints: Optional[str] = None,
) -> str:
    """Google Maps yol tarifi URL'si oluştur (query string tam encode)."""
    params = [("api", "1"), ("travelmode", "driving")]
    if origin:
        params.append(("origin", origin))
    params.append(("destination", destination))
    if waypoints:
        params.append(("waypoints", waypoints))
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


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


def is_super_manager(env) -> bool:
    """Kullanıcının süper yönetici olup olmadığını kontrol et.

    Süper yönetici, teslim edilmiş belgeler dahil tüm teslimat belgelerini
    koşulsuz olarak silebilir.

    Args:
        env: Odoo environment

    Returns:
        bool: Süper yönetici ise True
    """
    return env.user.has_group("teslimat_planlama.group_teslimat_super_manager")


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
    """İstanbul şehrini döndür.

    Args:
        env: Odoo environment

    Returns:
        res.country.state: İstanbul kaydı (yoksa boş recordset)
    """
    # Not: ORM zaten search sonucunu cache'liyor; ekstra context-cache gerekmez.
    return env["res.country.state"].search(
        [("country_id.code", "=", "TR"), ("name", "=", "İstanbul")],
        limit=1,
    )


def validate_arac_ilce_eslesmesi(arac, ilce, bypass_for_manager: bool = True) -> tuple[bool, str]:
    """Araç-ilçe eşleştirmesini doğrula (CANLI yaka kuralı).

    Mimari (araç-ilçe uyumu — kaynak ilişkisi):
      Bu "kural"dır: arac_tipi ↔ ilce.yaka_tipi'ni CANLI karşılaştırır
      (aktif/teslimat_aktif'e BAKMAZ). Yetkili KAPI DEĞİLDİR — sadece ekran
      mesajı ve yumuşak UI domain'i içindir. Asıl kapı (teslimat engeli)
      `arac.uygun_ilceler` ÜYELİĞİdir (validators + wizard); o liste bu
      kuralın `_update_uygun_ilceler` ile üretilmiş materialized cache'idir.
      Kapıyı buna çevirme: inaktif-ilçe engeli sessizce kalkar.
    
    Args:
        arac: Araç kaydı
        ilce: İlçe kaydı
        bypass_for_manager: Yöneticiler için kontrolü atla
        
    Returns:
        tuple: (Geçerli mi?, Mesaj)
    """
    if not arac or not ilce:
        return False, _("Araç veya ilçe bulunamadı")

    # Yönetici kontrolü - Yöneticiler her şeyi yapabilir
    if bypass_for_manager and hasattr(arac, 'env') and is_manager(arac.env):
        return True, _("Yönetici yetkisi - tüm eşleştirmeler geçerli")

    # Küçük araçlar her yere gidebilir
    if arac.arac_tipi in SMALL_VEHICLE_TYPES:
        return True, _("Küçük araç - tüm ilçelere gidebilir")

    # Yaka bazlı kontrol
    if arac.arac_tipi == "anadolu_yakasi":
        if ilce.yaka_tipi == "anadolu":
            return True, _("Anadolu Yakası araç - Anadolu Yakası ilçe")
        else:
            return False, _("Anadolu Yakası araç sadece Anadolu Yakası ilçelerine gidebilir (İlçe: %(yaka)s)") % {"yaka": ilce.yaka_tipi}

    elif arac.arac_tipi == "avrupa_yakasi":
        if ilce.yaka_tipi == "avrupa":
            return True, _("Avrupa Yakası araç - Avrupa Yakası ilçe")
        else:
            return False, _("Avrupa Yakası araç sadece Avrupa Yakası ilçelerine gidebilir (İlçe: %(yaka)s)") % {"yaka": ilce.yaka_tipi}

    return False, _("Bilinmeyen araç tipi")


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
            _("Pazar günü teslimat yapılamaz! "
              "Lütfen başka bir gün seçin.")
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

        mesaj = _(
            "Bu tarihte araç kapalı!\n\n"
            "Tarih: %(tarih)s\n"
            "Araç: %(arac)s\n"
            "Sebep: %(sebep)s\n"
            "Kapatan: %(kapatan)s"
        ) % {
            "tarih": teslimat_tarihi.strftime('%d.%m.%Y'),
            "arac": arac_name,
            "sebep": sebep_text,
            "kapatan": kapatan_kisi,
        }
        if kapatma.aciklama:
            mesaj += _("\nAçıklama: %(aciklama)s") % {"aciklama": kapatma.aciklama}
        mesaj += _("\n\nLütfen başka bir tarih seçin.")

        return False, mesaj

    return True, None
