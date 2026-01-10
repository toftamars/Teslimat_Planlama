"""Teslimat İlçe Yönetimi Modeli."""
import logging
from typing import Optional

from odoo import api, fields, models

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

    name = fields.Char(string="İlçe Adı", required=True)
    state_id = fields.Many2one("res.country.state", string="Şehir (İl)", required=True, domain=[("country_id.code", "=", "TR")])
    # sehir_id field removed
    aktif = fields.Boolean(string="Aktif", default=True)

    # Yaka Belirleme
    yaka_tipi = fields.Selection(
        [
            ("anadolu", "Anadolu Yakası"),
            ("avrupa", "Avrupa Yakası"),
            ("belirsiz", "Belirsiz"),
        ],
        string="Yaka Tipi",
        compute="_compute_yaka_tipi",
        store=True,
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
        "teslimat.gun", through="teslimat.gun.ilce", string="Teslimat Günleri"
    )
    # Uygun araçlar - Many2many ilişkisinin ters tarafı (otomatik hesaplanır)
    # Bu alan araçların uygun_ilceler alanından otomatik olarak hesaplanır
    arac_ids = fields.Many2many(
        "teslimat.arac",
        compute="_compute_arac_ids",
        string="Uygun Araçlar",
        store=False,
    )

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

    def write(self, vals):
        """İlçe yaka tipi değiştiğinde ilgili araçların eşleştirmesini güncelle."""
        result = super().write(vals)
        if "yaka_tipi" in vals:
            # Bu ilçeyi uygun ilçeler listesinde bulunan araçları güncelle
            self._update_arac_ilce_eslesmesi()
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
            _logger.error("İlçe oluşturma hatası: %s", e)

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

