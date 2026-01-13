"""Teslimat Ana Sayfa - Kapasite Sorgulama Modeli."""
import logging
from datetime import timedelta
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
            istanbul = self.env["res.country.state"].search(
                [("country_id.code", "=", "TR"), ("name", "=", "İstanbul")], limit=1
            )
            if istanbul:
                res['state_id'] = istanbul.id

        return res

    @api.onchange("arac_id")
    def _onchange_arac_id(self):
        """Araç seçildiğinde ilçe seçimini sıfırla ve İstanbul'u otomatik seç."""
        self.ilce_id = False

        # İstanbul'u otomatik seç
        istanbul = self.env["res.country.state"].search(
            [("country_id.code", "=", "TR"), ("name", "=", "İstanbul")], limit=1
        )
        if istanbul:
            self.state_id = istanbul

        # İl domain'ini sadece Türkiye ile sınırla
        return {"domain": {"state_id": [("country_id.code", "=", "TR")]}}

    @api.onchange("state_id")
    def _onchange_state_id(self):
        """İl seçildiğinde ilçe domain'ini güncelle - Seçilen araca uygun ilçeler göster."""
        self.ilce_id = False
        
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
            return {"domain": {"ilce_id": domain}}
            
        # Normal kullanıcılar için araç filtresi
        arac_tipi = self.arac_id.arac_tipi
        
        # Tüm aktif ilçeleri domain ile filtrele
        tum_ilceler = self.env["teslimat.ilce"].search(domain)
        
        uygun_ilce_ids = []
        if arac_tipi in ["kucuk_arac_1", "kucuk_arac_2", "ek_arac"]:
            # Küçük araçlar tüm ilçelere gidebilir
            uygun_ilce_ids = tum_ilceler.ids
        elif arac_tipi == "anadolu_yakasi":
            # Sadece Anadolu Yakası ilçeleri
            uygun_ilce_ids = tum_ilceler.filtered(
                lambda i: i.yaka_tipi == 'anadolu'
            ).ids
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

    # Eski metot yerine yenisini kullanıyoruz


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
                        f"✅ {record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılabilir "
                        "(Küçük araç - tüm ilçelere gidebilir)"
                    )
                else:
                    arac_tipi_label = dict(record.arac_id._fields["arac_tipi"].selection).get(
                        record.arac_id.arac_tipi, record.arac_id.arac_tipi
                    )
                    record.uygunluk_mesaji = (
                        f"✅ {record.ilce_id.name} ilçesine "
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
                        f"❌ {record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılamaz.\n\n"
                        f"Sebep: {mesaj}\n\n"
                        f"İlçe Yaka Tipi: {record.ilce_id.yaka_tipi}\n"
                        f"Araç Tipi: {arac_tipi_label}\n\n"
                        f"💡 Çözüm: Lütfen '🔄 Araç-İlçe Senkronizasyonu' menüsünden "
                        f"eşleştirmeleri güncelleyin."
                    )
                else:
                    record.uygunluk_mesaji = (
                        f"❌ {record.ilce_id.name} ilçesine "
                        f"{record.arac_id.name} ile teslimat yapılamaz. "
                        f"Bu araç ({arac_tipi_label}) bu ilçeye uygun değil."
                    )

    # Tarih listesi compute metodu kaldırıldı - artık gerekli değil
    
    @api.depends("ilce_id", "arac_id", "ilce_uygun_mu")
    def _compute_tarih_listesi_REMOVED(self) -> None:
        """Seçilen ilçe ve araç için uygun tarihleri hesapla (Optimized).
        
        Performans optimizasyonu: Batch sorgulama ile 90+ sorgu → ~10 sorgu.
        Yöneticiler için tüm günler gösterilir (ilçe-gün eşleşmesi kontrolü bypass).
        """
        from .teslimat_utils import is_manager
        
        for record in self:
            # Yönetici kontrolü
            yonetici_mi = is_manager(self.env)
            small_vehicle = record.arac_kucuk_mu
            # Yöneticiler veya küçük araçlar veya uygun ilçe kombinasyonu
            if record.arac_id and (
                yonetici_mi or small_vehicle or (record.ilce_id and record.ilce_uygun_mu)
            ):
                # Sonraki 30 günü kontrol et (Pazar günleri hariç)
                bugun = fields.Date.today()
                bitis_tarihi = bugun + timedelta(days=30)
                tarihler = []

                # PERFORMANS OPTİMİZASYONU: Batch sorgulama
                # 1. Tüm günler için teslimat sayılarını tek sorguda çek
                teslimat_domain = [
                    ("teslimat_tarihi", ">=", bugun),
                    ("teslimat_tarihi", "<=", bitis_tarihi),
                    ("arac_id", "=", record.arac_id.id),
                    ("durum", "in", ["taslak", "bekliyor", "hazir", "yolda"]),
                ]
                if record.ilce_id:
                    teslimat_domain.append(("ilce_id", "=", record.ilce_id.id))
                else:
                    teslimat_domain.append(("ilce_id", "=", False))

                # Batch: Tüm teslimatları tek sorguda çek
                tum_teslimatlar = self.env["teslimat.belgesi"].search(
                    teslimat_domain
                )
                
                # Python tarafında tarih bazlı grupla
                teslimat_sayisi_dict = {}
                for teslimat in tum_teslimatlar:
                    tarih = teslimat.teslimat_tarihi
                    teslimat_sayisi_dict[tarih] = (
                        teslimat_sayisi_dict.get(tarih, 0) + 1
                    )

                # 2. Gün kodları için mapping (utility'den al)
                from .teslimat_utils import GUN_KODU_MAP, GUN_ESLESMESI
                
                gun_kodu_map = GUN_KODU_MAP
                gun_eslesmesi = GUN_ESLESMESI

                # 3. Tüm günleri önceden çek (haftanın 7 günü için sadece 1 sorgu)
                gun_kodlari = list(gun_kodu_map.values())
                gunler = self.env["teslimat.gun"].search(
                    [("gun_kodu", "in", gun_kodlari)]
                )
                gun_dict = {gun.gun_kodu: gun for gun in gunler}

                # 4. İlçe-gün eşleşmelerini batch olarak çek (eğer ilçe varsa)
                gun_ilce_dict = {}
                if record.ilce_id:
                    # Tüm ilçe-gün eşleşmelerini çek (tarih bazlı ve genel)
                    gun_ilce_kayitlari = self.env["teslimat.gun.ilce"].search(
                        [
                            ("ilce_id", "=", record.ilce_id.id),
                            ("gun_id", "in", gunler.ids),
                        ]
                    )
                    
                    # DEBUG: Eşleşme sayısını logla
                    if not gun_ilce_kayitlari:
                        _logger.warning(
                            "⚠ İlçe '%s' için gün eşleşmesi bulunamadı! "
                            "Lütfen '🔄 Verileri Yükle/Güncelle' butonuna tıklayın.",
                            record.ilce_id.name
                        )
                    # Tarih bazlı eşleşmeler için dict oluştur
                    for gun_ilce in gun_ilce_kayitlari:
                        key = (gun_ilce.gun_id.id, gun_ilce.ilce_id.id, gun_ilce.tarih)
                        gun_ilce_dict[key] = gun_ilce
                    # Genel eşleşmeler için de (tarih olmadan)
                    for gun_ilce in gun_ilce_kayitlari.filtered(
                        lambda g: not g.tarih or g.tarih == bugun
                    ):
                        key_genel = (gun_ilce.gun_id.id, gun_ilce.ilce_id.id)
                        if key_genel not in gun_ilce_dict:
                            gun_ilce_dict[key_genel] = gun_ilce

                # Şimdi 30 günü loop et (sorgu yok, sadece hesaplama) - Pazar günleri hariç
                for i in range(30):
                    tarih = bugun + timedelta(days=i)
                    
                    # Pazar gününü atla - Tüm araçlar pazar günü kapalıdır
                    from .teslimat_utils import is_pazar_gunu
                    
                    if is_pazar_gunu(tarih):
                        continue
                    
                    gun_adi = tarih.strftime("%A")
                    gun_adi_tr = gun_eslesmesi.get(gun_adi, gun_adi)

                    # İlçe-gün uygunluğunu kontrol et
                    # Yöneticiler ve küçük araçlar için kısıt yok
                    ilce_uygun_mu = (
                        True
                        if (yonetici_mi or small_vehicle)
                        else self._check_ilce_gun_uygunlugu(record.ilce_id, tarih)
                    )

                    # Sadece uygun günleri ekle
                    if ilce_uygun_mu:
                        # Bu tarih için teslimat sayısını dict'ten al
                        teslimat_sayisi = teslimat_sayisi_dict.get(tarih, 0)

                        # Araç kapasitesi kontrolü - Dolu ise atla
                        if teslimat_sayisi >= record.arac_id.gunluk_teslimat_limiti:
                            continue  # Bu tarih kapasitesi dolu, listeye ekleme

                        # Gün bilgisini dict'ten al
                        gun_kodu = gun_kodu_map.get(tarih.weekday())
                        if not gun_kodu:
                            continue

                        gun = gun_dict.get(gun_kodu)
                        if not gun:
                            continue

                        # İlçe seçiliyse ilçe-gün eşleşmesi kontrol et
                        if record.ilce_id:
                            # Önce tarih bazlı eşleşmeyi kontrol et
                            key_tarih = (gun.id, record.ilce_id.id, tarih)
                            gun_ilce = gun_ilce_dict.get(key_tarih)
                            
                            # Eğer tarih bazlı eşleşme yoksa, genel eşleşmeyi kontrol et
                            if not gun_ilce:
                                key_genel = (gun.id, record.ilce_id.id)
                                gun_ilce = gun_ilce_dict.get(key_genel)

                            if gun_ilce:
                                toplam_kapasite = gun_ilce.maksimum_teslimat
                                kalan_kapasite = gun_ilce.kalan_kapasite

                                # İlçe-gün kapasitesi dolu ise atla
                                if kalan_kapasite <= 0:
                                    continue  # Kapasitesi dolu, listeye ekleme
                            else:
                                # Eşleşme yoksa gösterilmez
                                continue
                        else:
                            # Küçük araç için genel gün kapasitesi
                            toplam_kapasite = gun.gunluk_maksimum_teslimat
                            kalan_kapasite = gun.kalan_teslimat_kapasitesi

                            # Genel gün kapasitesi dolu ise atla
                            if kalan_kapasite <= 0:
                                continue  # Kapasitesi dolu, listeye ekleme

                        # Durum hesaplama
                        doluluk_orani = (
                            (teslimat_sayisi / toplam_kapasite * 100)
                            if toplam_kapasite > 0
                            else 0
                        )

                        if kalan_kapasite > 5 and doluluk_orani < 50:
                            durum = "bos"
                            durum_text = "🟢 Boş"
                            durum_icon = "fa-circle text-success"
                        elif kalan_kapasite <= 5 or (50 <= doluluk_orani < 90):
                            durum = "dolu_yakin"
                            durum_text = "🟡 Dolu Yakın"
                            durum_icon = "fa-circle text-warning"
                        else:
                            durum = "dolu"
                            durum_text = "🔴 Dolu"
                            durum_icon = "fa-circle text-danger"

                        tarihler.append(
                            {
                                "ana_sayfa_id": record.id,  # Ana sayfa ID'si ekle
                                "tarih": tarih,
                                "gun_adi": gun_adi_tr,
                                "teslimat_sayisi": teslimat_sayisi,
                                "toplam_kapasite": toplam_kapasite,
                                "kalan_kapasite": kalan_kapasite,
                                "durum": durum,
                                "durum_text": durum_text,
                                "durum_icon": durum_icon,
                            }
                        )

                # Tarih listesini güncelle
                tarih_komutlari = [(0, 0, data) for data in tarihler]
                record.uygun_gunler = [(5, 0, 0)] + tarih_komutlari

            else:
                record.uygun_gunler = [(5, 0, 0)]  # Tümünü sil

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
                gun_kodu_map = {
                    0: "pazartesi",
                    1: "sali",
                    2: "carsamba",
                    3: "persembe",
                    4: "cuma",
                    5: "cumartesi",
                    6: "pazar",
                }
                gun_kodu = gun_kodu_map.get(bugun.weekday())

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
                        
                        # Genel kural yoksa haftalık programa göre otomatik oluştur
                        if not gun_ilce:
                            # Haftalık programı kontrol et
                            from ..data.turkey_data import ANADOLU_ILCELERI, AVRUPA_ILCELERI
                            
                            ilce_adi_upper = record.ilce_id.name.upper()
                            schedule = {
                                'pazartesi': ['MALTEPE', 'KARTAL', 'PENDİK', 'TUZLA', 'SULTANBEYLİ', 'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'],
                                'sali': ['ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR', 'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'],
                                'carsamba': ['ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR', 'BAĞCILAR', 'BAHÇELİEVLER', 'BAKIRKÖY', 'GÜNGÖREN', 'ESENLER', 'ZEYTİNBURNU', 'BAYRAMPAŞA', 'FATİH'],
                                'persembe': ['MALTEPE', 'KARTAL', 'PENDİK', 'TUZLA', 'SULTANBEYLİ', 'BÜYÜKÇEKMECE', 'SİLİVRİ', 'ÇATALCA', 'ARNAVUTKÖY', 'BAKIRKÖY'],
                                'cuma': ['ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR', 'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'],
                                'cumartesi': ['BEYKOZ', 'ÇEKMEKÖY', 'SANCAKTEPE', 'ŞİLE', 'BÜYÜKÇEKMECE', 'SİLİVRİ', 'ÇATALCA', 'ARNAVUTKÖY', 'BAKIRKÖY']
                            }
                            
                            # Bugünün günü için programda bu ilçe var mı?
                            bugun_gun_programi = schedule.get(gun_kodu, [])
                            
                            # İlçe ismini normalize et (Türkçe karakterleri tolere et)
                            ilce_programda_var_mi = False
                            for program_ilce in bugun_gun_programi:
                                if program_ilce.upper() in ilce_adi_upper or ilce_adi_upper in program_ilce.upper():
                                    ilce_programda_var_mi = True
                                    break
                            
                            # Eğer programda varsa otomatik oluştur
                            if ilce_programda_var_mi:
                                gun_ilce = self.env["teslimat.gun.ilce"].create({
                                    'gun_id': gun.id,
                                    'ilce_id': record.ilce_id.id,
                                    'maksimum_teslimat': 7,  # Varsayılan kapasite
                                    'tarih': False,  # Genel kural
                                })
                                _logger.info(
                                    "✓ Otomatik gün-ilçe eşleşmesi oluşturuldu: %s - %s",
                                    gun.name,
                                    record.ilce_id.name
                                )

                        if gun_ilce:
                            record.toplam_kapasite = gun_ilce.maksimum_teslimat
                            record.kullanilan_kapasite = record.teslimat_sayisi  # Yukarıda hesaplanan gerçek teslimat sayısı
                            record.kalan_kapasite = record.toplam_kapasite - record.kullanilan_kapasite
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
        """Seçilen ilçe ve araç için uygun günleri hesapla."""
        from .teslimat_utils import is_manager, GUN_ESLESMESI, GUN_KODU_MAP
        
        for record in self:
            if not record.ilce_id or not record.arac_id or not record.ilce_uygun_mu:
                record.uygun_gunler = [(5, 0, 0)]
                continue
            
            yonetici_mi = is_manager(self.env)
            small_vehicle = record.arac_kucuk_mu
            
            # Sonraki 30 günü kontrol et (Pazar günleri hariç)
            bugun = fields.Date.today()
            bitis_tarihi = bugun + timedelta(days=30)
            uygun_gunler = []

            # Performans optimizasyonu: Batch sorgulama
            # İptal hariç TÜM durumlar kapasite doldurur (teslim_edildi dahil)
            teslimat_domain = [
                ("teslimat_tarihi", ">=", bugun),
                ("teslimat_tarihi", "<=", bitis_tarihi),
                ("arac_id", "=", record.arac_id.id),
                ("ilce_id", "=", record.ilce_id.id),
                ("durum", "!=", "iptal"),  # Sadece iptal hariç
            ]

            # DEBUG: Kapasite hesaplama (production'da kapatılmalı)
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug("Capacity calc: vehicle=%s, district=%s",
                            record.arac_id.name, record.ilce_id.name)

            tum_teslimatlar = self.env["teslimat.belgesi"].search(teslimat_domain)

            teslimat_sayisi_dict = {}
            for teslimat in tum_teslimatlar:
                tarih = teslimat.teslimat_tarihi
                teslimat_sayisi_dict[tarih] = teslimat_sayisi_dict.get(tarih, 0) + 1

            # Gün kodları için mapping
            gun_kodu_map = GUN_KODU_MAP
            gun_eslesmesi = GUN_ESLESMESI
            
            # Tüm günleri önceden çek
            gun_kodlari = list(gun_kodu_map.values())
            gunler = self.env["teslimat.gun"].search([("gun_kodu", "in", gun_kodlari)])
            gun_dict = {gun.gun_kodu: gun for gun in gunler}

            # İlçe-gün eşleşmelerini batch olarak çek
            gun_ilce_dict = {}
            gun_ilce_kayitlari = self.env["teslimat.gun.ilce"].search(
                [
                    ("ilce_id", "=", record.ilce_id.id),
                    ("gun_id", "in", gunler.ids),
                    ("tarih", "=", False),  # Genel kurallar
                ]
            )
            
            for gun_ilce in gun_ilce_kayitlari:
                key = (gun_ilce.gun_id.id, record.ilce_id.id)
                gun_ilce_dict[key] = gun_ilce

            # 30 günü loop et - Pazar günleri hariç
            for i in range(30):
                tarih = bugun + timedelta(days=i)
                
                # Pazar gününü atla
                from .teslimat_utils import is_pazar_gunu
                if is_pazar_gunu(tarih):
                    continue
                
                gun_adi = tarih.strftime("%A")
                gun_adi_tr = gun_eslesmesi.get(gun_adi, gun_adi)

                # İlçe-gün uygunluğunu kontrol et
                ilce_uygun_mu = (
                    True
                    if (yonetici_mi or small_vehicle)
                    else self._check_ilce_gun_uygunlugu(record.ilce_id, tarih)
                )

                # Sadece uygun günleri ekle
                if ilce_uygun_mu:
                    teslimat_sayisi = teslimat_sayisi_dict.get(tarih, 0)

                    # Araç kapasitesi kontrolü
                    if teslimat_sayisi >= record.arac_id.gunluk_teslimat_limiti:
                        continue

                    gun_kodu = gun_kodu_map.get(tarih.weekday())
                    if not gun_kodu:
                        continue

                    gun = gun_dict.get(gun_kodu)
                    if not gun:
                        continue

                    # İlçe-gün eşleşmesi kontrol et
                    key = (gun.id, record.ilce_id.id)
                    gun_ilce = gun_ilce_dict.get(key)
                    
                    # Eşleşme yoksa otomatik oluştur
                    if not gun_ilce:
                        # Haftalık programa göre kontrol et
                        from ..data.turkey_data import ANADOLU_ILCELERI, AVRUPA_ILCELERI
                        
                        ilce_adi_upper = record.ilce_id.name.upper()
                        schedule = {
                            'pazartesi': ['MALTEPE', 'KARTAL', 'PENDİK', 'TUZLA', 'SULTANBEYLİ', 'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'],
                            'sali': ['ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR', 'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'],
                            'carsamba': ['ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR', 'BAĞCILAR', 'BAHÇELİEVLER', 'BAKIRKÖY', 'GÜNGÖREN', 'ESENLER', 'ZEYTİNBURNU', 'BAYRAMPAŞA', 'FATİH'],
                            'persembe': ['MALTEPE', 'KARTAL', 'PENDİK', 'TUZLA', 'SULTANBEYLİ', 'BÜYÜKÇEKMECE', 'SİLİVRİ', 'ÇATALCA', 'ARNAVUTKÖY', 'BAKIRKÖY'],
                            'cuma': ['ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR', 'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'],
                            'cumartesi': ['BEYKOZ', 'ÇEKMEKÖY', 'SANCAKTEPE', 'ŞİLE', 'BÜYÜKÇEKMECE', 'SİLİVRİ', 'ÇATALCA', 'ARNAVUTKÖY', 'BAKIRKÖY']
                        }
                        
                        bugun_gun_programi = schedule.get(gun_kodu, [])
                        ilce_programda_var_mi = False
                        for program_ilce in bugun_gun_programi:
                            if program_ilce.upper() in ilce_adi_upper or ilce_adi_upper in program_ilce.upper():
                                ilce_programda_var_mi = True
                                break
                        
                        if ilce_programda_var_mi:
                            gun_ilce = self.env["teslimat.gun.ilce"].create({
                                'gun_id': gun.id,
                                'ilce_id': record.ilce_id.id,
                                'maksimum_teslimat': 7,
                                'tarih': False,
                            })
                            gun_ilce_dict[key] = gun_ilce

                    if gun_ilce:
                        toplam_kapasite = gun_ilce.maksimum_teslimat
                        # Kalan kapasite = Toplam - Gerçek teslimat sayısı
                        kalan_kapasite = toplam_kapasite - teslimat_sayisi

                        # Kapasitesi dolu ise atla (yöneticiler için göster)
                        if kalan_kapasite <= 0 and not yonetici_mi:
                            continue

                        # Durum hesaplama
                        if kalan_kapasite > 5:
                            durum_text = "🟢 Boş"
                        elif kalan_kapasite > 0:
                            durum_text = "🟡 Dolu Yakın"
                        else:
                            durum_text = "🔴 Dolu"

                        uygun_gunler.append({
                            "ana_sayfa_id": record.id,  # Ana sayfa ID'si ekle
                            "tarih": tarih,
                            "gun_adi": gun_adi_tr,
                            "teslimat_sayisi": teslimat_sayisi,
                            "toplam_kapasite": toplam_kapasite,
                            "kalan_kapasite": kalan_kapasite,
                            "durum_text": durum_text,
                        })

            # Günleri tarihe göre sırala ve kaydet
            uygun_gunler.sort(key=lambda x: x["tarih"])
            gun_komutlari = [(0, 0, data) for data in uygun_gunler]
            record.uygun_gunler = [(5, 0, 0)] + gun_komutlari

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
        """İlçeleri veritabanına yükle ve haftalık programı uygula."""
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
