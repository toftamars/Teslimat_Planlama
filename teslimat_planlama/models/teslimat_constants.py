"""Teslimat Planlama - Sabitler ve Konstantlar.

Bu modül tüm projedeki sabit değerleri ve tekrarlanan mapping'leri içerir.
"""

# ============================================================================
# TESLİMAT LİMİTLERİ
# ============================================================================

# Günlük teslimat limiti (normal kullanıcılar için)
DAILY_DELIVERY_LIMIT = 7

# Aynı gün teslimat için son saat (İstanbul saati)
SAME_DAY_DELIVERY_CUTOFF_HOUR = 12

# ============================================================================
# ZAMAN DİLİMİ
# ============================================================================

# Türkiye saat dilimi
ISTANBUL_TIMEZONE = 'Europe/Istanbul'

# ============================================================================
# ARAÇ KAPATMA SEBEPLERİ
# ============================================================================

# Araç kapatma sebep kodları ve gösterim isimleri
ARAC_KAPATMA_SEBEP_LABELS = {
    "bakim": "Bakım",
    "ariza": "Arıza",
    "kaza": "Kaza",
    "yakit": "Yakıt Sorunu",
    "surucu_yok": "Sürücü Yok",
    "diger": "Diğer",
}

# Araç kapatma sebep selection field için
ARAC_KAPATMA_SEBEP_SELECTION = [
    ("bakim", "Bakım"),
    ("ariza", "Arıza"),
    ("kaza", "Kaza"),
    ("yakit", "Yakıt Sorunu"),
    ("surucu_yok", "Sürücü Yok"),
    ("diger", "Diğer"),
]

# ============================================================================
# GÜN KODLARI VE MAPPING
# ============================================================================

# Gün kodları mapping (weekday() -> kod)
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

# ============================================================================
# TESLİMAT DURUMLARI
# ============================================================================

# Aktif teslimat durumları
ACTIVE_STATUSES = ["taslak", "bekliyor", "hazir", "yolda", "teslim_edildi"]

# Yolda olan teslimat durumları
IN_TRANSIT_STATUSES = ["hazir", "yolda"]

# İptal durumu
CANCELLED_STATUS = "iptal"

# Tamamlanmış durum
COMPLETED_STATUS = "teslim_edildi"

# ============================================================================
# ARAÇ TİPLERİ
# ============================================================================

# Küçük araç tipleri
SMALL_VEHICLE_TYPES = ["kucuk_arac_1", "kucuk_arac_2", "ek_arac"]

# ============================================================================
# FORECASTING VE PLANLAMA
# ============================================================================

# Müsait günler listesinde gösterilecek gün sayısı
FORECAST_DAYS = 30

# Düşük kapasite eşiği (bu değerin üstündeyse "Boş" olarak gösterilir)
LOW_CAPACITY_THRESHOLD = 5

# ============================================================================
# KONUM VE COĞRAFİ SABİTLER
# ============================================================================

# İstanbul koordinat aralıkları (enlem, boylam)
ISTANBUL_LAT_RANGE = (40.5, 41.3)
ISTANBUL_LON_RANGE = (27.5, 29.9)

# ============================================================================
# GÜN KODLARI - WEEKDAY MAPPING
# ============================================================================

# Pazar günü weekday değeri
PAZAR_WEEKDAY = 6

# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def get_arac_kapatma_sebep_label(sebep_kodu: str) -> str:
    """Araç kapatma sebep kodunu gösterim ismeine çevir.

    Args:
        sebep_kodu: Sebep kodu (bakim, ariza, vb.)

    Returns:
        str: Gösterim ismi (Bakım, Arıza, vb.)
    """
    return ARAC_KAPATMA_SEBEP_LABELS.get(sebep_kodu, sebep_kodu)
