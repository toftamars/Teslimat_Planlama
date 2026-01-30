"""Teslimat Ana Sayfa - Kapasite Sorgulama Modeli."""
import logging
from datetime import timedelta
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

            # Saat kontrolü için İstanbul saati
            from datetime import datetime
            import pytz
            istanbul_tz = pytz.timezone('Europe/Istanbul')
            simdi_istanbul = datetime.now(istanbul_tz)
            saat = simdi_istanbul.hour

            # 30 günü loop et - Pazar günleri hariç
            for i in range(30):
                tarih = bugun + timedelta(days=i)

                # Pazar gününü atla
                from .teslimat_utils import is_pazar_gunu
                if is_pazar_gunu(tarih):
                    continue

                # Aynı gün kontrolü: Saat 12:00 veya sonrası ise bugünü atla
                if tarih == bugun and saat >= 12:
                    _logger.info("Bugün atlandı (Saat 12:00 sonrası): %s", tarih)
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

                    # Varsayılan kapasite (programda varsa)
                    varsayilan_kapasite = 0
                    if not gun_ilce:
                        # Haftalık programa göre varsayılan kapasite belirle
                        # NOT: Compute içinde create() yapmıyoruz
                        from ..data.turkey_data import HAFTALIK_PROGRAM_SCHEDULE

                        ilce_adi_upper = record.ilce_id.name.upper()
                        bugun_gun_programi = HAFTALIK_PROGRAM_SCHEDULE.get(gun_kodu, [])

                        for program_ilce in bugun_gun_programi:
                            if program_ilce.upper() in ilce_adi_upper or ilce_adi_upper in program_ilce.upper():
                                varsayilan_kapasite = 7
                                break

                    if gun_ilce:
                        toplam_kapasite = gun_ilce.maksimum_teslimat
                    elif varsayilan_kapasite > 0:
                        toplam_kapasite = varsayilan_kapasite
                    else:
                        continue  # Programda yoksa bu günü atla

                    # Kalan kapasite = Toplam - Gerçek teslimat sayısı
                    kalan_kapasite = toplam_kapasite - teslimat_sayisi

                    # Kapasitesi dolu ise atla (yöneticiler için göster)
                    if kalan_kapasite <= 0 and not yonetici_mi:
                        continue

                    # Araç kapatma kontrolü
                    arac_kapali = False
                    if record.arac_id:
                        kapali, kapatma = self.env["teslimat.arac.kapatma"].arac_kapali_mi(
                            record.arac_id.id, tarih
                        )
                        if kapali and kapatma:
                            arac_kapali = True

                    # Durum hesaplama
                    if arac_kapali:
                        durum_text = "Kapalı"
                    elif kalan_kapasite < 0:
                        durum_text = f"Aşım ({teslimat_sayisi}/{toplam_kapasite})"
                    elif kalan_kapasite > 5:
                        durum_text = "Boş"
                    elif kalan_kapasite > 0:
                        durum_text = "Dolu Yakın"
                    else:
                        durum_text = "Dolu"

                    uygun_gunler.append({
                        "ana_sayfa_id": record.id,
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
