"""Teslimat Ana Sayfa - Kapasite Sorgulama Modeli."""
import logging
from datetime import date, timedelta
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .teslimat_utils import GUN_KODU_MAP, get_gun_kodu, get_istanbul_state, is_small_vehicle

_logger = logging.getLogger(__name__)


class TeslimatAnaSayfa(models.TransientModel):
    """Teslimat Ana Sayfa - Kapasite Sorgulama.

    Transient model - Kapasite sorgulama için kullanılır.
    """

    _name = "teslimat.ana.sayfa"
    _description = "Teslimat Ana Sayfa - Kapasite Sorgulama"

    arac_id = fields.Many2one(
        "teslimat.arac",
        string="Araç",
        domain=[("aktif", "=", True), ("gecici_kapatma", "=", False)],
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="İl",
        domain=[("country_id.code", "=", "TR")],
        # Default değer default_get'te ayarlanıyor
    )
    ilce_id = fields.Many2one(
        "teslimat.ilce",
        string="İlçe",
        # Domain onchange ile dinamik olarak güncelleniyor
    )

    @api.model
    def default_get(self, fields_list):
        """Form açılırken İstanbul'u otomatik seç."""
        res = super(TeslimatAnaSayfa, self).default_get(fields_list)

        # İstanbul'u varsayılan olarak seç
        if 'state_id' in fields_list and not res.get('state_id'):
            istanbul = get_istanbul_state(self.env)
            if istanbul:
                res['state_id'] = istanbul.id

        return res

    @api.onchange("arac_id")
    def _onchange_arac_id(self):
        """Araç seçildiğinde ilçe seçimini sıfırla ve İstanbul'u otomatik seç."""
        _logger.info("=== ONCHANGE ARAC_ID ===")
        _logger.info("Araç: %s", self.arac_id.name if self.arac_id else None)
        
        self.ilce_id = False

        # İstanbul'u otomatik seç
        istanbul = get_istanbul_state(self.env)
        if istanbul:
            self.state_id = istanbul
            _logger.info("İstanbul otomatik set edildi: %s", istanbul.name)
            
            # İlçe domain'ini de hemen hesapla
            result = self._compute_ilce_domain()
            _logger.info("İlçe domain: %s", result)
            return result

        # İl domain'ini sadece Türkiye ile sınırla
        return {"domain": {"state_id": [("country_id.code", "=", "TR")]}}

    def _compute_ilce_domain(self):
        """İlçe domain'ini hesapla - Ortak metod."""
        if not self.arac_id:
            return {"domain": {"ilce_id": [("id", "in", [])]}}
        
        domain = [
            ("aktif", "=", True),
            ("teslimat_aktif", "=", True)
        ]

        # İl filtresi (İstanbul)
        if self.state_id:
            domain.append(("state_id", "=", self.state_id.id))
        
        # Yönetici kontrolü - Yöneticiler tüm ilçeleri görebilir
        from .teslimat_utils import is_manager
        
        if is_manager(self.env):
            # Yöneticiler için kısıtlama yok
            _logger.info("Yönetici - Tüm ilçeler gösteriliyor")
            return {"domain": {"ilce_id": domain}}
            
        # Normal kullanıcılar için araç filtresi
        arac_tipi = self.arac_id.arac_tipi
        
        # Tüm aktif ilçeleri domain ile filtrele
        tum_ilceler = self.env["teslimat.ilce"].search(domain)
        _logger.info("Toplam aktif ilçe: %s", len(tum_ilceler))
        
        uygun_ilce_ids = []
        if is_small_vehicle(self.arac_id):
            # Küçük araçlar tüm ilçelere gidebilir
            uygun_ilce_ids = tum_ilceler.ids
            _logger.info("Küçük araç - Tüm ilçeler: %s", len(uygun_ilce_ids))
        elif arac_tipi == "anadolu_yakasi":
            # Sadece Anadolu Yakası ilçeleri
            uygun_ilce_ids = tum_ilceler.filtered(
                lambda i: i.yaka_tipi == 'anadolu'
            ).ids
            _logger.info("Anadolu Yakası - Uygun ilçeler: %s", len(uygun_ilce_ids))
        elif arac_tipi == "avrupa_yakasi":
            # Sadece Avrupa Yakası ilçeleri
            uygun_ilce_ids = tum_ilceler.filtered(
                lambda i: i.yaka_tipi == 'avrupa'
            ).ids
        else:
            # Diğer araçlar için araçın uygun ilçeler listesine bak
            if self.arac_id.uygun_ilceler:
                uygun_ilce_ids = self.arac_id.uygun_ilceler.filtered(
                    lambda i: i.id in tum_ilceler.ids
                ).ids
            else:
                uygun_ilce_ids = []

        return {"domain": {"ilce_id": [("id", "in", uygun_ilce_ids)]}}
    
    @api.onchange("state_id")
    def _onchange_state_id(self):
        """İl seçildiğinde ilçe domain'ini güncelle."""
        _logger.info("=== ONCHANGE STATE_ID ===")
        _logger.info("İl: %s", self.state_id.name if self.state_id else None)
        
        self.ilce_id = False
        return self._compute_ilce_domain()

    # Hesaplanan alanlar
    arac_kucuk_mu = fields.Boolean(
        string="Küçük Araç",
        compute="_compute_arac_kucuk_mu",
        store=False,
    )
    ilce_uygun_mu = fields.Boolean(
        string="İlçe Uygun",
        compute="_compute_ilce_uygunluk",
        store=False,
    )
    uygunluk_mesaji = fields.Text(
        string="Uygunluk Mesajı", compute="_compute_ilce_uygunluk", store=False
    )


    # İlçe kapasite bilgileri
    toplam_kapasite = fields.Integer(
        string="Toplam Kapasite", compute="_compute_kapasite_bilgileri", store=False
    )
    kullanilan_kapasite = fields.Integer(
        string="Kullanılan Kapasite",
        compute="_compute_kapasite_bilgileri",
        store=False,
    )
    kalan_kapasite = fields.Integer(
        string="Kalan Kapasite", compute="_compute_kapasite_bilgileri", store=False
    )
    teslimat_sayisi = fields.Integer(
        string="Teslimat Sayısı",
        compute="_compute_kapasite_bilgileri",
        store=False,
    )

    # Uygun araçlar
    uygun_arac_ids = fields.Many2many(
        "teslimat.arac",
        string="Uygun Araçlar",
        compute="_compute_uygun_araclar",
        store=False,
    )

    # Uygun günler listesi
    uygun_gunler = fields.One2many(
        "teslimat.ana.sayfa.gun",
        "ana_sayfa_id",
        string="Uygun Günler",
        compute="_compute_uygun_gunler",
        store=False,
    )

    @api.depends("arac_id")
    def _compute_arac_kucuk_mu(self) -> None:
        """Araç küçük araç mı kontrol et."""
        for record in self:
            record.arac_kucuk_mu = bool(
                record.arac_id
                and record.arac_id.arac_tipi
                in ["kucuk_arac_1", "kucuk_arac_2", "ek_arac"]
            )

    @api.depends("ilce_id", "arac_id")
    def _compute_ilce_uygunluk(self) -> None:
        """İlçe-arac uygunluğunu kontrol et (Many2many ilişkisini kullanarak)."""
        for record in self:
            if not record.ilce_id or not record.arac_id:
                record.ilce_uygun_mu = False
                record.uygunluk_mesaji = "Lütfen araç ve ilçe seçin"
                continue

            # Validasyon fonksiyonunu kullan
            from .teslimat_utils import validate_arac_ilce_eslesmesi
            
            gecerli, mesaj = validate_arac_ilce_eslesmesi(record.arac_id, record.ilce_id)
            
            # Many2many ilişkisini kullanarak kontrol et
            if record.ilce_id in record.arac_id.uygun_ilceler:
                record.ilce_uygun_mu = True
                if record.arac_kucuk_mu:
                    record.uygunluk_mesaji = (
                        f"{record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılabilir "
                        "(Küçük araç - tüm ilçelere gidebilir)"
                    )
                else:
                    arac_tipi_label = dict(record.arac_id._fields["arac_tipi"].selection).get(
                        record.arac_id.arac_tipi, record.arac_id.arac_tipi
                    )
                    record.uygunluk_mesaji = (
                        f"{record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılabilir "
                        f"({arac_tipi_label})"
                    )
            else:
                record.ilce_uygun_mu = False
                arac_tipi_label = dict(record.arac_id._fields["arac_tipi"].selection).get(
                    record.arac_id.arac_tipi, record.arac_id.arac_tipi
                )
                
                # Detaylı hata mesajı
                if not gecerli:
                    record.uygunluk_mesaji = (
                        f"{record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılamaz.\n\n"
                        f"Sebep: {mesaj}\n\n"
                        f"İlçe Yaka Tipi: {record.ilce_id.yaka_tipi}\n"
                        f"Araç Tipi: {arac_tipi_label}\n\n"
                        f"Çözüm: Lütfen 'Araç-İlçe Senkronizasyonu' menüsünden "
                        f"eşleştirmeleri güncelleyin."
                    )
                else:
                    record.uygunluk_mesaji = (
                        f"{record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılamaz. "
                        f"Bu araç ({arac_tipi_label}) bu ilçeye uygun değil."
                    )


    def _check_ilce_gun_uygunlugu(
        self, ilce: Optional[models.Model], tarih: fields.Date
    ) -> bool:
        """İlçe-gün uygunluğunu kontrol et (Dinamik - Database'den).

        Args:
            ilce: İlçe kaydı
            tarih: Kontrol edilecek tarih

        Returns:
            bool: Uygun ise True
        """
        if not ilce:
            return False

        # Gün kodunu belirle
        from .teslimat_utils import get_gun_kodu
        
        tarih_obj = fields.Date.to_date(tarih)
        gun_kodu = get_gun_kodu(tarih_obj)

        if not gun_kodu:
            return False

        # Günü bul
        gun = self.env["teslimat.gun"].search([("gun_kodu", "=", gun_kodu)], limit=1)
        if not gun:
            return False

        # Database'den ilçe-gün eşleşmesi kontrol et
        gun_ilce = self.env["teslimat.gun.ilce"].search(
            [("gun_id", "=", gun.id), ("ilce_id", "=", ilce.id)], limit=1
        )

        return bool(gun_ilce)

    @api.depends("ilce_id", "arac_id")
    def _compute_kapasite_bilgileri(self) -> None:
        """İlçe kapasite bilgilerini hesapla."""
        for record in self:
            if record.ilce_id and record.arac_id:
                bugun = fields.Date.today()

                # Bugün için teslimat sayısı (iptal hariç tüm durumlar)
                record.teslimat_sayisi = self.env["teslimat.belgesi"].search_count(
                    [
                        ("teslimat_tarihi", "=", bugun),
                        ("ilce_id", "=", record.ilce_id.id),
                        ("durum", "!=", "iptal"),  # Sadece iptal hariç
                    ]
                )

                # Gün kodunu belirle
                gun_kodu = get_gun_kodu(bugun)

                if gun_kodu:
                    gun = self.env["teslimat.gun"].search(
                        [("gun_kodu", "=", gun_kodu)], limit=1
                    )

                    if gun:
                        # Database'den ilçe-gün eşleşmesi kontrol et
                        # Önce genel kuralı ara (tarih=False)
                        gun_ilce = self.env["teslimat.gun.ilce"].search(
                            [
                                ("gun_id", "=", gun.id),
                                ("ilce_id", "=", record.ilce_id.id),
                                ("tarih", "=", False),  # Genel kural
                            ],
                            limit=1,
                        )
                        
                        # Genel kural yoksa haftalık programa göre varsayılan kapasite kullan
                        # NOT: Compute içinde create() yapmıyoruz - veri tutarlılığı için
                        varsayilan_kapasite = 0
                        if not gun_ilce:
                            # Haftalık programı kontrol et
                            from ..data.turkey_data import HAFTALIK_PROGRAM_SCHEDULE

                            ilce_adi_upper = record.ilce_id.name.upper()
                            bugun_gun_programi = HAFTALIK_PROGRAM_SCHEDULE.get(gun_kodu, [])

                            # İlçe ismini normalize et (Türkçe karakterleri tolere et)
                            for program_ilce in bugun_gun_programi:
                                if program_ilce.upper() in ilce_adi_upper or ilce_adi_upper in program_ilce.upper():
                                    varsayilan_kapasite = 7  # Programda var, varsayılan kapasite
                                    break

                        if gun_ilce:
                            record.toplam_kapasite = gun_ilce.maksimum_teslimat
                            record.kullanilan_kapasite = record.teslimat_sayisi
                            record.kalan_kapasite = record.toplam_kapasite - record.kullanilan_kapasite
                        elif varsayilan_kapasite > 0:
                            # Programda var ama gun_ilce kaydı yok - varsayılan kapasite kullan
                            record.toplam_kapasite = varsayilan_kapasite
                            record.kullanilan_kapasite = record.teslimat_sayisi
                            record.kalan_kapasite = varsayilan_kapasite - record.teslimat_sayisi
                        else:
                            record.toplam_kapasite = 0
                            record.kullanilan_kapasite = 0
                            record.kalan_kapasite = 0
                    else:
                        record.toplam_kapasite = 0
                        record.kullanilan_kapasite = 0
                        record.kalan_kapasite = 0
                else:
                    record.toplam_kapasite = 0
                    record.kullanilan_kapasite = 0
                    record.kalan_kapasite = 0
            else:
                record.toplam_kapasite = 0
                record.kullanilan_kapasite = 0
                record.kalan_kapasite = 0
                record.teslimat_sayisi = 0

    @api.depends("ilce_id")
    def _compute_uygun_araclar(self) -> None:
        """Seçilen ilçeye uygun araçları hesapla."""
        for record in self:
            if record.ilce_id:
                bugun = fields.Date.today()
                araclar = self.env["teslimat.arac"].get_uygun_araclar(
                    ilce_id=record.ilce_id.id, tarih=bugun
                )
                record.uygun_arac_ids = araclar
            else:
                record.uygun_arac_ids = False

    @api.depends("ilce_id", "arac_id", "ilce_uygun_mu")
    def _compute_uygun_gunler(self) -> None:
        """Seçilen ilçe ve araç için uygun günleri hesapla.
        
        Bu metod sonraki 30 günü analiz eder ve her gün için:
        - İlçe-gün uygunluğunu kontrol eder
        - Kapasite durumunu hesaplar
        - Araç kapatma durumunu kontrol eder
        """
        from .teslimat_utils import is_manager
        from .teslimat_constants import FORECAST_DAYS, SAME_DAY_DELIVERY_CUTOFF_HOUR
        
        for record in self:
            if not record.ilce_id or not record.arac_id or not record.ilce_uygun_mu:
                record.uygun_gunler = [(5, 0, 0)]
                continue
            
            yonetici_mi = is_manager(self.env)
            small_vehicle = record.arac_kucuk_mu
            bugun = fields.Date.today()
            
            # 1. Teslimat sayılarını batch olarak al (N+1 query önleme)
            teslimat_sayisi_by_date = self._get_teslimat_sayilari_batch(
                record.arac_id.id, record.ilce_id.id, bugun, FORECAST_DAYS
            )
            
            # 2. Gün ve ilçe-gün eşleşmelerini batch olarak al
            gun_dict, gun_ilce_dict = self._get_gun_ilce_mappings_batch(record.ilce_id.id)
            
            # 3. Saat kontrolü için İstanbul saati
            from .teslimat_utils import get_istanbul_time
            simdi_istanbul = get_istanbul_time()
            saat = simdi_istanbul.hour
            
            # 4. Her günü kontrol et ve uygun günleri topla
            uygun_gunler = []
            for i in range(FORECAST_DAYS):
                tarih = bugun + timedelta(days=i)
                
                # Temel kontroller (Pazar, aynı gün saat kontrolü)
                if not self._is_date_available(tarih, bugun, saat, SAME_DAY_DELIVERY_CUTOFF_HOUR):
                    continue
                
                # İlçe-gün uygunluğu
                if not (yonetici_mi or small_vehicle):
                    if not self._check_ilce_gun_uygunlugu(record.ilce_id, tarih):
                        continue
                
                # Kapasite ve durum hesaplama
                gun_data = self._calculate_day_capacity_status(
                    record, tarih, teslimat_sayisi_by_date, gun_dict, 
                    gun_ilce_dict, yonetici_mi
                )

                if gun_data:
                    uygun_gunler.append(gun_data)

            # 5. Günleri tarihe göre sırala ve kaydet
            uygun_gunler.sort(key=lambda x: x["tarih"])
            gun_komutlari = [(0, 0, data) for data in uygun_gunler]
            record.uygun_gunler = [(5, 0, 0)] + gun_komutlari
    
    def _get_teslimat_sayilari_batch(
        self, arac_id: int, ilce_id: int, bugun: date, forecast_days: int
    ) -> dict:
        """Teslimat sayılarını batch olarak al (N+1 query önleme).

        Sayım araç + tarih bazında yapılır (ilçe filtresi yok): Aynı araç-gün
        için tüm ilçelerdeki teslimatlar toplamı gösterilir. Böylece Ataşehir veya
        Kadıköy sorgulandığında aynı gün için aynı toplam (örn. 4) görünür.
        
        Args:
            arac_id: Araç ID
            ilce_id: İlçe ID (sorgu bağlamı için; domain'de kullanılmaz)
            bugun: Bugünün tarihi
            forecast_days: Kaç gün ilerisi kontrol edilecek
            
        Returns:
            dict: {tarih: teslimat_sayisi} mapping (araç+gün toplamı)
        """
        from .teslimat_constants import CANCELLED_STATUS
        
        bitis_tarihi = bugun + timedelta(days=forecast_days)
        
        # Araç + tarih bazında say (ilçe yok): tüm ilçelerdeki teslimat toplamı
        domain = [
            ("teslimat_tarihi", ">=", bugun),
            ("teslimat_tarihi", "<=", bitis_tarihi),
            ("arac_id", "=", arac_id),
            ("durum", "!=", CANCELLED_STATUS),
        ]
        rows = self.env["teslimat.belgesi"].search_read(
            domain, ["teslimat_tarihi"], order="teslimat_tarihi"
        )
        teslimat_sayisi_dict = {}
        for row in rows:
            tarih = row.get("teslimat_tarihi")
            if tarih:
                if isinstance(tarih, str):
                    try:
                        tarih = fields.Date.from_string(tarih)
                    except ValueError:
                        continue
                teslimat_sayisi_dict[tarih] = teslimat_sayisi_dict.get(tarih, 0) + 1
        if _logger.isEnabledFor(logging.DEBUG):
            arac = self.env["teslimat.arac"].browse(arac_id)
            ilce = self.env["teslimat.ilce"].browse(ilce_id)
            _logger.debug(
                "Capacity calc: vehicle=%s, district=%s, dates=%d",
                arac.name, ilce.name, len(teslimat_sayisi_dict)
            )
        return teslimat_sayisi_dict
    
    def _get_gun_ilce_mappings_batch(self, ilce_id: int) -> tuple:
        """Gün ve ilçe-gün eşleşmelerini batch olarak al.
        
        Args:
            ilce_id: İlçe ID
            
        Returns:
            tuple: (gun_dict, gun_ilce_dict)
                gun_dict: {gun_kodu: gun_record}
                gun_ilce_dict: {(gun_id, ilce_id): gun_ilce_record}
        """
        from .teslimat_constants import GUN_KODU_MAP
        
        # Tüm günleri önceden çek
        gun_kodlari = list(GUN_KODU_MAP.values())
        gunler = self.env["teslimat.gun"].search([("gun_kodu", "in", gun_kodlari)])
        gun_dict = {gun.gun_kodu: gun for gun in gunler}
        
        # İlçe-gün eşleşmelerini batch olarak çek
        gun_ilce_kayitlari = self.env["teslimat.gun.ilce"].search([
            ("ilce_id", "=", ilce_id),
            ("gun_id", "in", gunler.ids),
            ("tarih", "=", False),  # Genel kurallar
        ])
        
        gun_ilce_dict = {
            (gun_ilce.gun_id.id, ilce_id): gun_ilce
            for gun_ilce in gun_ilce_kayitlari
        }
        
        return gun_dict, gun_ilce_dict
    
    def _is_date_available(
        self, tarih: date, bugun: date, saat: int, cutoff_hour: int
    ) -> bool:
        """Tarihin teslimat için uygun olup olmadığını kontrol et.
        
        Args:
            tarih: Kontrol edilecek tarih
            bugun: Bugünün tarihi
            saat: Şu anki saat (İstanbul)
            cutoff_hour: Aynı gün teslimat için son saat
            
        Returns:
            bool: Tarih uygunsa True
        """
        from .teslimat_utils import is_pazar_gunu
        
        # Pazar gününü atla
        if is_pazar_gunu(tarih):
            return False
        
        # Aynı gün kontrolü: Saat cutoff'tan sonra ise bugünü atla
        if tarih == bugun and saat >= cutoff_hour:
            _logger.info("Bugün atlandı (Saat %d:00 sonrası): %s", cutoff_hour, tarih)
            return False
        
        return True
    
    def _calculate_day_capacity_status(
        self,
        record,
        tarih: date,
        teslimat_sayisi_by_date: dict,
        gun_dict: dict,
        gun_ilce_dict: dict,
        yonetici_mi: bool,
    ) -> dict:
        """Belirli bir gün için kapasite durumunu hesapla.
        
        Args:
            record: Ana sayfa kaydı
            tarih: Hesaplanacak tarih
            teslimat_sayisi_by_date: Teslimat sayıları mapping
            gun_dict: Gün kayıtları mapping
            gun_ilce_dict: İlçe-gün eşleşmeleri mapping
            yonetici_mi: Kullanıcı yönetici mi
            
        Returns:
            dict: Gün bilgileri veya None (uygun değilse)
        """
        from .teslimat_constants import GUN_KODU_MAP, GUN_ESLESMESI, DAILY_DELIVERY_LIMIT
        
        teslimat_sayisi = teslimat_sayisi_by_date.get(tarih, 0)
        
        # Araç kapasitesi kontrolü
        if teslimat_sayisi >= record.arac_id.gunluk_teslimat_limiti:
            return None
        
        gun_kodu = GUN_KODU_MAP.get(tarih.weekday())
        if not gun_kodu:
            return None
        
        gun = gun_dict.get(gun_kodu)
        if not gun:
            return None
        
        # İlçe-gün eşleşmesi ve kapasite hesaplama
        key = (gun.id, record.ilce_id.id)
        gun_ilce = gun_ilce_dict.get(key)
        
        toplam_kapasite = self._get_toplam_kapasite(
            gun_ilce, gun_kodu, record.ilce_id.name, DAILY_DELIVERY_LIMIT
        )
        
        if toplam_kapasite == 0:
            return None  # Programda yoksa bu günü atla
        
        kalan_kapasite = toplam_kapasite - teslimat_sayisi
        
        # Kapasitesi dolu ise atla (yöneticiler için göster)
        if kalan_kapasite <= 0 and not yonetici_mi:
            return None
        
        # Araç kapatma kontrolü
        arac_kapali = self._check_arac_kapali(record.arac_id.id, tarih)
        
        # Durum hesaplama
        durum_text = self._get_durum_text(
            arac_kapali, kalan_kapasite, teslimat_sayisi, toplam_kapasite
        )
        
        # Gün adını Türkçe'ye çevir
        gun_adi = tarih.strftime("%A")
        gun_adi_tr = GUN_ESLESMESI.get(gun_adi, gun_adi)
        
        return {
            "ana_sayfa_id": record.id,
            "tarih": tarih,
            "gun_adi": gun_adi_tr,
            "teslimat_sayisi": teslimat_sayisi,
            "toplam_kapasite": toplam_kapasite,
            "kalan_kapasite": kalan_kapasite,
            "durum_text": durum_text,
        }
    
    def _get_toplam_kapasite(
        self, gun_ilce, gun_kodu: str, ilce_adi: str, default_limit: int
    ) -> int:
        """İlçe-gün için toplam kapasiteyi hesapla.
        
        Args:
            gun_ilce: İlçe-gün eşleşme kaydı (varsa)
            gun_kodu: Gün kodu (pazartesi, sali, vb.)
            ilce_adi: İlçe adı
            default_limit: Varsayılan limit
            
        Returns:
            int: Toplam kapasite (0 ise programda yok)
        """
        if gun_ilce:
            return gun_ilce.maksimum_teslimat
        
        # Haftalık programa göre varsayılan kapasite belirle
        from ..data.turkey_data import HAFTALIK_PROGRAM_SCHEDULE
        
        ilce_adi_upper = ilce_adi.upper()
        bugun_gun_programi = HAFTALIK_PROGRAM_SCHEDULE.get(gun_kodu, [])
        
        for program_ilce in bugun_gun_programi:
            if (program_ilce.upper() in ilce_adi_upper or 
                ilce_adi_upper in program_ilce.upper()):
                return default_limit
        
        return 0  # Programda yoksa
    
    def _check_arac_kapali(self, arac_id: int, tarih: date) -> bool:
        """Aracın belirtilen tarihte kapalı olup olmadığını kontrol et.
        
        Args:
            arac_id: Araç ID
            tarih: Kontrol edilecek tarih
            
        Returns:
            bool: Araç kapalı ise True
        """
        if not arac_id:
            return False
        
        kapali, kapatma = self.env["teslimat.arac.kapatma"].arac_kapali_mi(
            arac_id, tarih
        )
        return kapali and kapatma
    
    def _get_durum_text(
        self, arac_kapali: bool, kalan_kapasite: int, 
        teslimat_sayisi: int, toplam_kapasite: int
    ) -> str:
        """Kapasite durumu için metin oluştur.
        
        Args:
            arac_kapali: Araç kapalı mı
            kalan_kapasite: Kalan kapasite
            teslimat_sayisi: Mevcut teslimat sayısı
            toplam_kapasite: Toplam kapasite
            
        Returns:
            str: Durum metni
        """
        from .teslimat_constants import LOW_CAPACITY_THRESHOLD
        
        if arac_kapali:
            return "Kapalı"
        elif kalan_kapasite < 0:
            return f"Aşım ({teslimat_sayisi}/{toplam_kapasite})"
        elif kalan_kapasite > LOW_CAPACITY_THRESHOLD:
            return "Boş"
        elif kalan_kapasite > 0:
            return "Dolu Yakın"
        else:
            return "Dolu"

    def action_sorgula(self) -> None:
        """Kapasite sorgulamasını yenile.
        
        İlçe yaka tipini kontrol eder ve gerekirse düzeltir.
        Araç eşleştirmelerini otomatik günceller.
        """
        self.ensure_one()
        
        # İlçe seçildiyse yaka tipini kontrol et ve düzelt
        if self.ilce_id:
            # Yaka tipini yeniden hesapla (sudo ile izin gerektirmeden)
            self.ilce_id.sudo()._compute_yaka_tipi()
            
            # Eğer yaka tipi değiştiyse ilgili araçları güncelle
            self.ilce_id.sudo()._update_arac_ilce_eslesmesi()
        
        # Araç seçildiyse uygun ilçelerini kontrol et ve güncelle
        if self.arac_id:
            # Uygun ilçeleri yeniden hesapla (sudo ile izin gerektirmeden)
            self.arac_id.sudo()._update_uygun_ilceler()
        
        # Compute field'lar otomatik yenilenecek
        return True

    def action_load_districts(self):
        """İlçeleri veritabanına yükle ve haftalık programı uygula.

        Sadece yöneticiler bu işlemi yapabilir.
        """
        from .teslimat_utils import is_manager
        from odoo.exceptions import UserError

        if not is_manager(self.env):
            raise UserError(_("Bu işlem sadece yöneticiler tarafından yapılabilir."))

        self.env["teslimat.ilce"].create_istanbul_districts_simple()
        self.env["teslimat.ilce"].apply_weekly_schedule()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Başarılı'),
                'message': _('İlçeler yüklendi ve haftalık program uygulandı.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_teslimat_wizard_from_tarih(self, gun_record_id, tarih):
        """Tarih ile teslimat wizard'ını aç - Tree view'dan çağrılır."""
        self.ensure_one()
        
        if not self.arac_id:
            raise UserError(_("Araç seçimi gereklidir."))

        if not self.ilce_id:
            raise UserError(_("İlçe seçimi gereklidir."))

        # Tarih string'den date'e çevir
        from datetime import datetime
        if isinstance(tarih, str):
            tarih = datetime.strptime(tarih, '%Y-%m-%d').date()

        # Wizard'ı aç
        context = {
            "default_teslimat_tarihi": tarih,
            "default_arac_id": self.arac_id.id,
            "default_ilce_id": self.ilce_id.id,
        }

        return {
            "name": _("Teslimat Belgesi Oluştur"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

# Sürüm 15.0.2.1.0 - Kod temizliği ve kapasite sorgulama kararlı hale getirildi.
