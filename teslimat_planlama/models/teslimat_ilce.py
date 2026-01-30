"""Teslimat İlçe Yönetimi Modeli."""
import logging
from typing import Optional

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# İlçe yaka tipi tanımları
from ..data.turkey_data import ANADOLU_ILCELERI, AVRUPA_ILCELERI


class TeslimatIlce(models.Model):
    """Teslimat İlçe Yönetimi.

    İlçeler ve teslimat bölge bilgilerini yönetir.
    """

    _name = "teslimat.ilce"
    _description = "Teslimat İlçe Yönetimi"
    _order = "state_id, name"

    _sql_constraints = [
        ('name_state_unique', 'UNIQUE(name, state_id)', 'Aynı şehirde aynı isimde iki ilçe olamaz!'),
    ]

    name = fields.Char(string="İlçe Adı", required=True)
    state_id = fields.Many2one("res.country.state", string="Şehir (İl)", required=True, domain=[("country_id.code", "=", "TR")])
    # sehir_id field removed
    aktif = fields.Boolean(string="Aktif", default=True)

    # Yaka Belirleme - STORE=TRUE (Performans ve güvenilirlik için)
    yaka_tipi = fields.Selection(
        [
            ("anadolu", "Anadolu Yakası"),
            ("avrupa", "Avrupa Yakası"),
            ("belirsiz", "Belirsiz"),
        ],
        string="Yaka Tipi",
        compute="_compute_yaka_tipi",
        store=True,
        readonly=False,  # Manuel düzeltme için
    )

    # Konum Bilgileri
    enlem = fields.Float(string="Enlem")
    boylam = fields.Float(string="Boylam")
    posta_kodu = fields.Char(string="Posta Kodu")

    # Teslimat Bilgileri
    teslimat_aktif = fields.Boolean(string="Teslimat Aktif", default=True)
    teslimat_suresi = fields.Integer(string="Teslimat Süresi (Gün)", default=1)
    teslimat_notlari = fields.Text(string="Teslimat Notları")

    # Özel Durumlar
    ozel_durum = fields.Selection(
        [
            ("normal", "Normal"),
            ("yogun", "Yoğun"),
            ("kapali", "Kapalı"),
            ("ozel", "Özel"),
        ],
        string="Özel Durum",
        default="normal",
    )

    # İlişkiler
    gun_ids = fields.Many2many(
        "teslimat.gun", 
        "teslimat_ilce_gun_rel", 
        "ilce_id", 
        "gun_id", 
        string="Teslimat Günleri"
    )
    # Uygun araçlar - Many2many ilişkisinin ters tarafı (otomatik hesaplanır)
    # Bu alan araçların uygun_ilceler alanından otomatik olarak hesaplanır
    arac_ids = fields.Many2many(
        "teslimat.arac",
        compute="_compute_arac_ids",
        string="Uygun Araçlar",
        store=False,
    )

    @api.model
    def apply_weekly_schedule(self):
        """Kullanıcının verdiği haftalık teslimat programını uygula."""
        schedule = {
            'pazartesi': [
                'MALTEPE', 'KARTAL', 'PENDİK', 'TUZLA', 'SULTANBEYLİ',
                'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'
            ],
            'sali': [
                'ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR',
                'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'
            ],
            'carsamba': [
                'ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR',
                'BAĞCILAR', 'BAHÇELİEVLER', 'BAKIRKÖY', 'GÜNGÖREN', 'ESENLER', 'ZEYTİNBURNU', 'BAYRAMPAŞA', 'FATİH'
            ],
            'persembe': [
                'MALTEPE', 'KARTAL', 'PENDİK', 'TUZLA', 'SULTANBEYLİ',
                'BÜYÜKÇEKMECE', 'SİLİVRİ', 'ÇATALCA', 'ARNAVUTKÖY', 'BAKIRKÖY'
            ],
            'cuma': [
                'ÜSKÜDAR', 'KADIKÖY', 'ÜMRANİYE', 'ATAŞEHİR',
                'ŞİŞLİ', 'BEŞİKTAŞ', 'BEYOĞLU', 'KAĞITHANE'
            ],
            'cumartesi': [
                'BEYKOZ', 'ÇEKMEKÖY', 'SANCAKTEPE', 'ŞİLE',
                'BÜYÜKÇEKMECE', 'SİLİVRİ', 'ÇATALCA', 'ARNAVUTKÖY', 'BAKIRKÖY'
            ]
        }

        # Tüm araçların ve günlerin limitlerini 7 yap
        self.env['teslimat.arac'].search([]).write({'gunluk_teslimat_limiti': 7})
        self.env['teslimat.gun'].search([('aktif', '=', True)]).write({'gunluk_maksimum_teslimat': 7})

        for gun_kodu, ilce_isimleri in schedule.items():
            gun = self.env['teslimat.gun'].search([('gun_kodu', '=', gun_kodu)], limit=1)
            if not gun:
                continue
            
            for isim in ilce_isimleri:
                # İsmi tam eşleştir veya Türkçe karakterleri tolere et
                ilce = self.search([
                    ('state_id.name', 'ilike', 'İstanbul'),
                    '|', ('name', '=ilike', isim), ('name', '=ilike', isim.replace('İ', 'i'))
                ], limit=1)
                
                if ilce:
                    # Eskiden kalma "sadece bugünlük" kayıtları temizle
                    old_specific_records = self.env['teslimat.gun.ilce'].search([
                        ('gun_id', '=', gun.id),
                        ('ilce_id', '=', ilce.id),
                        ('tarih', '!=', False)
                    ])
                    if old_specific_records:
                        old_specific_records.unlink()

                    # Genel (her hafta geçerli) kuralı oluştur/güncelle
                    existing_rel = self.env['teslimat.gun.ilce'].search([
                        ('gun_id', '=', gun.id),
                        ('ilce_id', '=', ilce.id),
                        ('tarih', '=', False)
                    ], limit=1)
                    
                    if not existing_rel:
                        self.env['teslimat.gun.ilce'].create({
                            'gun_id': gun.id,
                            'ilce_id': ilce.id,
                            'maksimum_teslimat': 7,
                            'tarih': False,
                        })
                    else:
                        existing_rel.write({'maksimum_teslimat': 7})
        return True

    @api.depends("name", "yaka_tipi")
    def _compute_arac_ids(self) -> None:
        """Bu ilçeyi uygun ilçeler listesinde bulunan araçları hesapla."""
        for record in self:
            # Bu ilçeyi uygun_ilceler listesinde bulunan araçları bul
            araclar = self.env["teslimat.arac"].search(
                [("uygun_ilceler", "in", [record.id])]
            )
            record.arac_ids = araclar

    @api.depends("name")
    def _compute_yaka_tipi(self) -> None:
        """İlçe adına göre yaka tipini otomatik belirle.

        İlçe adına göre Anadolu veya Avrupa yakası olarak
        otomatik olarak atar.
        
        Bu compute method her zaman çalışır ve yaka tipini garanti eder.
        """
        for record in self:
            if not record.name:
                record.yaka_tipi = "belirsiz"
                continue

            ilce_adi_lower = record.name.lower()

            # Anadolu yakası kontrolü
            if any(ilce.lower() in ilce_adi_lower for ilce in ANADOLU_ILCELERI):
                record.yaka_tipi = "anadolu"
            # Avrupa yakası kontrolü
            elif any(ilce.lower() in ilce_adi_lower for ilce in AVRUPA_ILCELERI):
                record.yaka_tipi = "avrupa"
            else:
                record.yaka_tipi = "belirsiz"
    
    @api.constrains("name", "yaka_tipi", "state_id")
    def _check_yaka_tipi_gecerli(self) -> None:
        """İstanbul ilçeleri için yaka tipi ZORUNLU kontrol.
        
        Bu constraint kod seviyesinde garanti eder ki:
        - İstanbul ilçeleri mutlaka anadolu veya avrupa yakası olsun
        - Belirsiz yaka tipi kabul edilmesin
        
        NOT: Data yükleme sırasında (module install/upgrade) bu kontrol atlanır.
        """
        # Data yükleme modunda ise constraint'i atla
        if self.env.context.get('install_mode') or self.env.context.get('module'):
            return
            
        for record in self:
            # Sadece İstanbul ilçeleri için kontrol
            if record.state_id and 'istanbul' in record.state_id.name.lower():
                if record.yaka_tipi == "belirsiz":
                    raise ValidationError(
                        _(
                            f"İstanbul ilçesi '{record.name}' için yaka tipi belirsiz olamaz!\n\n"
                            f"Lütfen ilçe adını kontrol edin veya yöneticiye başvurun.\n\n"
                            f"Anadolu Yakası İlçeleri: {', '.join(ANADOLU_ILCELERI[:5])}...\n"
                            f"Avrupa Yakası İlçeleri: {', '.join(AVRUPA_ILCELERI[:5])}..."
                        )
                    )

    @api.model_create_multi
    def create(self, vals_list):
        """İlçe oluşturulduğunda ZORUNLU yaka tipini hesapla ve araçları güncelle.
        
        Bu method kod seviyesinde garanti eder ki:
        - Her yeni ilçe mutlaka yaka tipine sahip olsun
        - İlgili araçlar otomatik güncellensin
        """
        records = super().create(vals_list)
        for record in records:
            # Yaka tipini hesapla - compute method otomatik çalışır
            # Ama yine de force edelim
            record._compute_yaka_tipi()
            
            # İstanbul ilçeleri için yaka tipi kontrolü
            if record.state_id and 'istanbul' in record.state_id.name.lower():
                if record.yaka_tipi == "belirsiz":
                    _logger.warning(
                        "İstanbul ilçesi '%s' için yaka tipi belirsiz! "
                        "Constraint tarafından engellenecek.",
                        record.name
                    )
            
            # İlgili araçların eşleştirmesini güncelle
            record._update_arac_ilce_eslesmesi()
            
            _logger.info(
                "İlçe oluşturuldu: %s (%s) - Yaka: %s",
                record.name,
                record.state_id.name if record.state_id else "N/A",
                record.yaka_tipi
            )
        return records

    def write(self, vals):
        """İlçe yaka tipi değiştiğinde ilgili araçların eşleştirmesini güncelle."""
        result = super().write(vals)
        if "yaka_tipi" in vals or "name" in vals:
            # Bu ilçeyi uygun ilçeler listesinde bulunan araçları güncelle
            self._update_arac_ilce_eslesmesi()
            for record in self:
                _logger.info(
                    "İlçe güncellendi: %s - Yaka: %s",
                    record.name,
                    record.yaka_tipi
                )
        return result

    def _update_arac_ilce_eslesmesi(self) -> None:
        """İlçe yaka tipi değiştiğinde ilgili araçların eşleştirmesini güncelle.
        
        Yaka tipi değişen ilçe için, bu ilçeyi uygun ilçeler listesinde 
        bulunan araçların eşleştirmelerini yeniden hesapla.
        """
        for ilce in self:
            # Bu ilçeyi uygun ilçeler listesinde bulunan araçları bul
            araclar = self.env["teslimat.arac"].search(
                [("uygun_ilceler", "in", [ilce.id])]
            )
            
            # Her araç için eşleştirmeyi yeniden hesapla
            for arac in araclar:
                # Eğer araç yaka bazlı ise (küçük araç değilse)
                if arac.arac_tipi in ["anadolu_yakasi", "avrupa_yakasi"]:
                    # Araç tipine göre uygun ilçeleri yeniden hesapla
                    arac._update_uygun_ilceler()

    @api.model
    def create_districts(self) -> None:
        """Türkiye ilçelerini data dosyasından oluştur."""
        try:
            from ..data.turkey_data import TURKEY_DISTRICTS
            
            # Türkiye kaydını bul
            turkey = self.env["res.country"].search([("code", "=", "TR")], limit=1)
            if not turkey:
                _logger.warning("Türkiye (TR) ülkesi bulunamadı, ilçeler oluşturulmadı.")
                return

            count = 0
            for city_name, districts in TURKEY_DISTRICTS.items():
                # Şehir ismini normalize et (Odoo'da genelde düzgün kayıtlıdır ama biz garantileyelim)
                # Odoo'da 'İstanbul' veya 'Istanbul' olabilir.
                
                # 1. Tam eşleşme
                state = self.env["res.country.state"].search(
                    [("country_id", "=", turkey.id), ("name", "=", city_name)], 
                    limit=1
                )
                
                # 2. Case-insensitive eşleşme
                if not state:
                    state = self.env["res.country.state"].search(
                        [("country_id", "=", turkey.id), ("name", "=ilike", city_name)], 
                        limit=1
                    )
                
                # 3. Özel durumlar (İstanbul, İzmir, vb. Türkçe karakter sorunu)
                if not state:
                    search_name = city_name
                    if "İ" in search_name:
                        search_name = search_name.replace("İ", "I") # İstanbul -> Istanbul
                        state = self.env["res.country.state"].search(
                            [("country_id", "=", turkey.id), ("name", "=ilike", search_name)], 
                            limit=1
                        )

                if not state:
                    _logger.warning("Şehir bulunamadı, atlanıyor: %s", city_name)
                    continue

                for district_name in districts:
                    # İlçe var mı kontrol et
                    existing = self.search(
                        [("name", "=", district_name), ("state_id", "=", state.id)],
                        limit=1
                    )
                    
                    if not existing:
                        self.create({
                            "name": district_name,
                            "state_id": state.id,
                            "teslimat_aktif": True,
                            "yaka_tipi": "belirsiz",
                        })
                        count += 1
                        
            if count > 0:
                _logger.info("%s adet ilçe oluşturuldu.", count)
                
            # İstanbul özelinde yaka tiplerini güncelle
            self._update_istanbul_yaka_tipleri()

        except Exception as e:
            _logger.exception("İlçe oluşturma hatası:")
            raise UserError(
                f"İlçe oluşturma işlemi sırasında hata oluştu:\n{str(e)}"
            )

    def _update_istanbul_yaka_tipleri(self):
        """İstanbul ilçelerinin yaka tiplerini güncelle."""
        istanbul = self.env["res.country.state"].search([("name", "ilike", "İstanbul")], limit=1)
        if not istanbul:
            return

        ilceler = self.search([("state_id", "=", istanbul.id)])
        for ilce in ilceler:
            ilce._compute_yaka_tipi()

    @api.model
    def create_istanbul_districts_simple(self):
        """İstanbul ilçelerini basit yöntemle oluştur."""
        # İstanbul'u bul
        istanbul = self.env["res.country.state"].search([
            ("country_id.code", "=", "TR"),
            ("name", "ilike", "istanbul")
        ], limit=1)
        
        if not istanbul:
            _logger.error("İstanbul ili bulunamadı!")
            return
            
        from ..data.turkey_data import TURKEY_DISTRICTS
        
        # İstanbul ilçelerini al
        istanbul_districts = TURKEY_DISTRICTS.get("İstanbul", [])
        
        count = 0
        for district_name in istanbul_districts:
            existing = self.search([
                ("name", "=", district_name),
                ("state_id", "=", istanbul.id)
            ], limit=1)
            
            if not existing:
                self.create({
                    "name": district_name,
                    "state_id": istanbul.id,
                    "teslimat_aktif": True,
                })
                count += 1
        
        if count > 0:
            _logger.info("%s adet İstanbul ilçesi oluşturuldu.", count)
            self._update_istanbul_yaka_tipleri()

