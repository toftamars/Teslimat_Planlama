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
    )
    ilce_id = fields.Many2one(
        "teslimat.ilce",
        string="İlçe",
        # Domain onchange ile dinamik olarak güncelleniyor
    )

    @api.onchange("state_id", "arac_id")
    def _onchange_filters(self):
        """İl veya Araç seçildiğinde ilçe domain'ini güncelle."""
        self.ilce_id = False
        
        domain = [("aktif", "=", True), ("teslimat_aktif", "=", True)]
        
        # İl filtresi
        if self.state_id:
            domain.append(("state_id", "=", self.state_id.id))
            
        # Araç filtresi
        if self.arac_id:
            arac_tipi = self.arac_id.arac_tipi
            
            # Tüm aktif ilçeleri domain ile filtrele
            tum_ilceler = self.env["teslimat.ilce"].search(domain)
            
            uygun_ilce_ids = []
            if arac_tipi in ["kucuk_arac_1", "kucuk_arac_2", "ek_arac"]:
                uygun_ilce_ids = tum_ilceler.ids
            elif arac_tipi == "anadolu_yakasi":
                # Sadece İstanbul Anadolu
                uygun_ilce_ids = tum_ilceler.filtered(
                    lambda i: i.state_id.name == 'İstanbul' and i.yaka_tipi == 'anadolu'
                ).ids
            elif arac_tipi == "avrupa_yakasi":
                 # Sadece İstanbul Avrupa
                uygun_ilce_ids = tum_ilceler.filtered(
                    lambda i: i.state_id.name == 'İstanbul' and i.yaka_tipi == 'avrupa'
                ).ids
            else:
                 # Diğer araçlar için uygun_ilceler alanına bakılabilir veya hepsi
                 # Şimdilik hepsi diyelim veya boş
                 uygun_ilce_ids = tum_ilceler.ids

            domain.append(("id", "in", uygun_ilce_ids))
        
        return {"domain": {"ilce_id": domain}}

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

    # Tarih listesi (computed)
    tarih_listesi = fields.One2many(
        "teslimat.ana.sayfa.tarih",
        "ana_sayfa_id",
        string="Tarih Listesi",
        compute="_compute_tarih_listesi",
        store=False,
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
                record.uygunluk_mesaji = (
                    f"❌ {record.ilce_id.name} ilçesine "
                    f"{record.arac_id.name} ile teslimat yapılamaz. "
                    f"Bu araç ({arac_tipi_label}) bu ilçeye uygun değil."
                )

    @api.depends("ilce_id", "arac_id", "ilce_uygun_mu")
    def _compute_tarih_listesi(self) -> None:
        """Seçilen ilçe ve araç için uygun tarihleri hesapla (Optimized).
        
        Performans optimizasyonu: Batch sorgulama ile 90+ sorgu → ~10 sorgu.
        """
        for record in self:
            small_vehicle = record.arac_kucuk_mu
            if record.arac_id and (
                small_vehicle or (record.ilce_id and record.ilce_uygun_mu)
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
                    teslimat_domain, fields=["teslimat_tarihi"]
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

                    # İlçe-gün uygunluğunu kontrol et (küçük araçlar için kısıt yok)
                    ilce_uygun_mu = (
                        True
                        if small_vehicle
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
                                "ana_sayfa_id": record.id,
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
                record.tarih_listesi = [(5, 0, 0)]  # Tümünü sil
                for tarih_data in tarihler:
                    self.env["teslimat.ana.sayfa.tarih"].create(tarih_data)

            else:
                record.tarih_listesi = [(5, 0, 0)]  # Tümünü sil

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
        
        gun_kodu = get_gun_kodu(tarih)

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

                # Bugün için teslimat sayısı
                record.teslimat_sayisi = self.env["teslimat.belgesi"].search_count(
                    [
                        ("teslimat_tarihi", "=", bugun),
                        ("ilce_id", "=", record.ilce_id.id),
                        ("durum", "in", ["taslak", "bekliyor", "hazir", "yolda"]),
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
                        gun_ilce = self.env["teslimat.gun.ilce"].search(
                            [("gun_id", "=", gun.id), ("ilce_id", "=", record.ilce_id.id)],
                            limit=1,
                        )

                        if gun_ilce:
                            record.toplam_kapasite = gun_ilce.maksimum_teslimat
                            record.kullanilan_kapasite = gun_ilce.teslimat_sayisi
                            record.kalan_kapasite = gun_ilce.kalan_kapasite
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

    def action_sorgula(self) -> None:
        """Kapasite sorgulamasını yenile."""
        self.ensure_one()
        # Compute field'lar otomatik yenilenecek
        return True

