"""Teslimat Belgesi Oluşturma Wizard'ı."""
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.teslimat_planlama.data.turkey_data import (
    ANADOLU_ILCELERI,
    AVRUPA_ILCELERI,
)
from odoo.addons.teslimat_planlama.models.teslimat_utils import is_small_vehicle


class TeslimatBelgesiWizard(models.TransientModel):
    """Teslimat Belgesi Oluşturma Wizard'ı.

    Transfer belgesinden teslimat belgesi oluşturma için wizard.
    """

    _name = "teslimat.belgesi.wizard"
    _description = "Teslimat Belgesi Oluşturma Wizard'ı"

    # Temel Bilgiler
    teslimat_tarihi = fields.Date(
        string="Teslimat Tarihi",
        required=True,
        default=fields.Date.today,
        readonly=True,
    )
    arac_id = fields.Many2one("teslimat.arac", string="Araç", required=True)
    ilce_id = fields.Many2one(
        "teslimat.ilce",
        string="İlçe",
        required=False,
    )

    # Transfer No (stock.picking)
    transfer_id = fields.Many2one(
        "stock.picking",
        string="Transfer No",
        domain=[("state", "in", ["waiting", "confirmed", "assigned", "done"])],
        help="Transfer numarasına göre arayın (name). "
        "İptal ve taslak durumundaki transferler görünmez.",
    )

    # Müşteri ve Adres (otomatik dolar)
    musteri_id = fields.Many2one("res.partner", string="Müşteri", readonly=True)
    adres = fields.Char(string="Adres", readonly=True)
    musteri_telefon = fields.Char(string="Telefon", readonly=True, help="Transfer belgesindeki müşteri telefon numarası")
    manuel_telefon = fields.Char(string="Telefon (Opsiyonel)", required=False, help="İsteğe bağlı - farklı bir telefon numarası girebilirsiniz")

    # Kullanıcının elle doldurduğu alanlar
    transfer_olusturan_id = fields.Many2one(
        "res.users",
        string="Sorumlu Personel",
        help="İsteğe bağlı - sorumlu personel/kullanıcı",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analitik hesap",
        help="Sistemdeki analitik hesap - isteğe bağlı seçin",
    )

    # Hesaplanan alanlar
    arac_kucuk_mu = fields.Boolean(
        string="Küçük Araç",
        compute="_compute_arac_kucuk_mu",
        store=False,
    )

    @api.model
    def create(self, vals):
        """Create metodunu override et - context'ten veya Ana Sayfa kaydından ilce_id al."""
        ctx = self.env.context
        if "ilce_id" not in vals or not vals.get("ilce_id"):
            ilce_id = None
            if ctx.get("default_ana_sayfa_res_id"):
                try:
                    ana = self.env["teslimat.ana.sayfa"].browse(int(ctx["default_ana_sayfa_res_id"]))
                    if ana.exists() and ana.ilce_id:
                        ilce_id = ana.ilce_id.id
                except (TypeError, ValueError):
                    pass
            if ilce_id is None and ctx.get("default_ilce_id"):
                try:
                    ilce_id = int(ctx["default_ilce_id"])
                except (TypeError, ValueError):
                    pass
            if ilce_id:
                vals["ilce_id"] = ilce_id
        return super().create(vals)

    @api.model
    def default_get(self, fields_list: list) -> dict:
        """Varsayılan değerleri context'ten al.

        Args:
            fields_list: Alan listesi

        Returns:
            dict: Varsayılan değerler
        """
        res = super(TeslimatBelgesiWizard, self).default_get(fields_list)
        ctx = self.env.context

        # Tarih context'ten geliyorsa kullan
        if ctx.get("default_teslimat_tarihi"):
            tarih_str = ctx.get("default_teslimat_tarihi")
            if isinstance(tarih_str, str):
                try:
                    tarih = datetime.strptime(tarih_str, "%Y-%m-%d").date()
                    res["teslimat_tarihi"] = tarih
                except ValueError:
                    res["teslimat_tarihi"] = fields.Date.today()
            else:
                res["teslimat_tarihi"] = tarih_str

        # Araç context'ten geliyorsa kullan
        if ctx.get("default_arac_id"):
            res["arac_id"] = ctx.get("default_arac_id")

        # İlçe: Ana Sayfa'dan (Uygun Günler tıklanınca) otomatik atanır.
        # Önce Ana Sayfa kaydından sunucuda oku (en güvenilir), yoksa context default_ilce_id kullan.
        ilce_id = None
        ana_sayfa_res_id = ctx.get("default_ana_sayfa_res_id")
        if ana_sayfa_res_id:
            try:
                ana_id = int(ana_sayfa_res_id)
            except (TypeError, ValueError):
                ana_id = None
            if ana_id:
                ana = self.env["teslimat.ana.sayfa"].browse(ana_id)
                if ana.exists() and ana.ilce_id:
                    ilce_id = ana.ilce_id.id
        if ilce_id is None and ctx.get("default_ilce_id"):
            try:
                ilce_id = int(ctx.get("default_ilce_id"))
            except (TypeError, ValueError):
                ilce_id = None
        if ilce_id:
            ilce = self.env["teslimat.ilce"].browse(ilce_id)
            if ilce.exists():
                res["ilce_id"] = ilce_id
                if fields_list and "ilce_id" not in fields_list:
                    fields_list.append("ilce_id")

        # Transfer ID context'ten geliyorsa kullan; Sorumlu Personel = transfer'deki user_id
        if ctx.get("default_transfer_id") and "transfer_id" in (fields_list or []):
            picking_id = ctx.get("default_transfer_id")
            picking = self.env["stock.picking"].browse(picking_id)
            if picking.exists():
                res["transfer_id"] = picking_id
                if "teslimat_tarihi" in (fields_list or []) and not res.get(
                    "teslimat_tarihi"
                ):
                    res["teslimat_tarihi"] = fields.Date.today()
                if ctx.get("default_musteri_id") and "musteri_id" in (
                    fields_list or []
                ):
                    res["musteri_id"] = ctx.get("default_musteri_id")
                # Sorumlu Personel = sistemdeki user_id (transfer sorumlusu)
                if picking.user_id and "transfer_olusturan_id" in (fields_list or []):
                    res["transfer_olusturan_id"] = picking.user_id.id

        return res

    @api.depends("arac_id")
    def _compute_arac_kucuk_mu(self) -> None:
        """Araç küçük araç mı kontrol et."""
        for record in self:
            record.arac_kucuk_mu = bool(
                record.arac_id
                and record.arac_id.arac_tipi
                in ["kucuk_arac_1", "kucuk_arac_2", "ek_arac"]
            )
    
    @api.onchange("arac_id")
    def _onchange_arac_id(self) -> None:
        """Araç seçildiğinde ilçe domain'ini güncelle.

        Context'ten ilçe ID'si geliyorsa atar, yoksa domain günceller.
        Yöneticiler için tüm ilçeler gösterilir.
        """
        from odoo.addons.teslimat_planlama.models.teslimat_utils import is_manager

        # Context'ten ilçe ID'si geliyorsa ata
        ctx = self.env.context
        if ctx.get("default_ilce_id") and not self.ilce_id:
            ilce_id = ctx.get("default_ilce_id")
            self.ilce_id = ilce_id
            return {'value': {'ilce_id': ilce_id}}

        self.ilce_id = False

        if not self.arac_id:
            return {
                "domain": {
                    "ilce_id": [("aktif", "=", True), ("teslimat_aktif", "=", True)]
                }
            }
        
        # Yönetici kontrolü - Yöneticiler tüm ilçeleri görebilir
        if is_manager(self.env):
            return {
                "domain": {
                    "ilce_id": [("aktif", "=", True), ("teslimat_aktif", "=", True)]
                }
            }
        
        # Tüm aktif ilçeleri al
        tum_ilceler = self.env["teslimat.ilce"].search(
            [("aktif", "=", True), ("teslimat_aktif", "=", True)]
        )
        
        arac_tipi = self.arac_id.arac_tipi
        
        # Araç tipine göre filtrele
        if is_small_vehicle(self.arac_id):
            uygun_ilce_ids = tum_ilceler.ids
        elif arac_tipi == "anadolu_yakasi":
            uygun_ilce_ids = tum_ilceler.filtered(
                lambda i: any(ilce.lower() in i.name.lower() for ilce in ANADOLU_ILCELERI)
            ).ids
        elif arac_tipi == "avrupa_yakasi":
            uygun_ilce_ids = tum_ilceler.filtered(
                lambda i: any(ilce.lower() in i.name.lower() for ilce in AVRUPA_ILCELERI)
            ).ids
        else:
            uygun_ilce_ids = []
        
        return {
            "domain": {
                "ilce_id": [
                    ("aktif", "=", True),
                    ("teslimat_aktif", "=", True),
                    ("id", "in", uygun_ilce_ids),
                ]
            }
        }

    @api.onchange("transfer_id")
    def _onchange_transfer_id(self) -> None:
        """Transfer seçildiğinde sadece müşteri bilgilerini doldur. Analitik hesap ve Sorumlu Personel kullanıcı doldurur."""
        picking = self.transfer_id
        if not picking:
            return

        # 1. Transfer durumu kontrolü
        if picking.state in ["cancel", "draft"]:
            return {
                "warning": {
                    "title": _("Transfer Durumu Uyarısı"),
                    "message": _(
                        "Seçilen transfer iptal veya taslak durumunda. "
                        "Teslimat belgesi oluşturulamaz."
                    ),
                }
            }

        # 2. Mükerrer kontrol
        existing = self.env["teslimat.belgesi"].search(
            [("stock_picking_id", "=", picking.id)], limit=1
        )
        if existing:
            return {
                "warning": {
                    "title": _("Mükerrer Teslimat"),
                    "message": _(
                        "Bu transfer için zaten bir teslimat belgesi mevcut: %s"
                        % existing.name
                    ),
                }
            }

        # 3. Müşteri bilgileri
        if picking.partner_id:
            self.musteri_id = picking.partner_id
            partner = picking.partner_id

            # Adres bilgisi - utility fonksiyonu kullan
            from ..models.teslimat_utils import format_partner_address
            adres = format_partner_address(partner)
            if adres and adres != "Adres bilgisi bulunamadı":
                self.adres = adres
            else:
                # Fallback - contact_address kullan
                self.adres = partner.contact_address or partner.name

            # Telefon bilgisi - partner'dan al
            if partner.phone:
                self.musteri_telefon = partner.phone
            elif partner.mobile:
                self.musteri_telefon = partner.mobile
            else:
                self.musteri_telefon = ""

        # 4. Sorumlu Personel = transferdeki user_id (sistemdeki Sorumlu alanı)
        if picking.user_id:
            self.transfer_olusturan_id = picking.user_id

    def action_teslimat_olustur(self) -> dict:
        """Teslimat belgesi oluştur, SMS gönder ve yönlendir.
        
        Bu metod tüm validasyonları yapar, teslimat belgesi oluşturur ve
        kullanıcıyı oluşturulan belgeye yönlendirir.

        Returns:
            dict: Teslimat belgeleri list view'ı
            
        Raises:
            UserError: Validasyon hatası durumunda
        """
        self.ensure_one()
        
        # 1. Temel alan validasyonları
        self._validate_basic_fields()
        
        # 2. Tarih ve araç kısıtlamaları
        self._validate_date_and_vehicle_constraints()
        
        # 3. Kapasite kontrolü
        self._validate_capacity()
        
        # 4. İlçe-araç ve ilçe-gün uyumluluğu
        self._validate_ilce_arac_gun_compatibility()
        
        # 5. Teslimat belgesi oluştur ve SMS gönder
        teslimat = self._create_teslimat_belgesi()
        
        # 6. Kullanıcıyı oluşturulan belgeye yönlendir
        return self._redirect_to_teslimat(teslimat)
    
    def _validate_basic_fields(self) -> None:
        """Temel alanların dolu olup olmadığını kontrol et.
        
        Raises:
            UserError: Zorunlu alan eksikse
        """
        from ..models.teslimat_constants import SMALL_VEHICLE_TYPES
        
        if not self.arac_id:
            raise UserError(_("Araç seçimi zorunludur."))
        
        # Küçük araç değilse ilçe zorunlu
        if self.arac_id.arac_tipi not in SMALL_VEHICLE_TYPES and not self.ilce_id:
            raise UserError(_("Yaka bazlı araçlar için ilçe seçimi zorunludur."))
        
        if not self.transfer_id:
            raise UserError(_("Transfer belgesi seçimi zorunludur."))
        
        if not self.musteri_id:
            raise UserError(_("Müşteri seçimi zorunludur."))
    
    def _validate_date_and_vehicle_constraints(self) -> None:
        """Tarih ve araç kısıtlamalarını kontrol et.
        
        Pazar günü ve araç kapatma durumlarını kontrol eder.
        
        Raises:
            UserError: Tarih veya araç uygun değilse
        """
        from ..models.teslimat_utils import check_pazar_gunu_validation, check_arac_kapatma
        
        # Pazar günü kontrolü
        check_pazar_gunu_validation(self.teslimat_tarihi)
        
        # Araç kapatma kontrolü
        if self.arac_id and self.teslimat_tarihi:
            gecerli, hata_mesaji = check_arac_kapatma(
                self.env, self.arac_id.id, self.teslimat_tarihi, 
                bypass_for_manager=False
            )
            if not gecerli:
                raise UserError(_(hata_mesaji))
    
    def _validate_capacity(self) -> None:
        """Araç ve ilçe-gün kapasitelerini kontrol et.
        
        İki seviyeli kapasite kontrolü yapar:
        1. Araç kapasitesi (günlük teslimat limiti)
        2. İlçe-gün kapasitesi (eğer ilçe seçiliyse)
        
        Raises:
            UserError: Kapasite dolu ise
        """
        from ..models.teslimat_constants import CANCELLED_STATUS
        
        # 1. Araç kapasitesi kontrolü
        domain = [
            ("teslimat_tarihi", "=", self.teslimat_tarihi),
            ("arac_id", "=", self.arac_id.id),
            ("durum", "!=", CANCELLED_STATUS),
        ]
        
        if self.ilce_id:
            domain.append(("ilce_id", "=", self.ilce_id.id))
            bugun_teslimatlar = self.env["teslimat.belgesi"].search_count(domain)
            
            if bugun_teslimatlar >= self.arac_id.gunluk_teslimat_limiti:
                raise UserError(
                    _(
                        f"Araç kapasitesi dolu! Seçilen tarih için "
                        f"{self.ilce_id.name} ilçesine araç kapasitesi: "
                        f"{bugun_teslimatlar}/{self.arac_id.gunluk_teslimat_limiti}"
                    )
                )
        else:
            # İlçe yoksa (küçük araçlar için) genel kontrol
            bugun_teslimatlar = self.env["teslimat.belgesi"].search_count(domain)
            
            if bugun_teslimatlar >= self.arac_id.gunluk_teslimat_limiti:
                raise UserError(
                    _(
                        f"Araç kapasitesi dolu! Seçilen tarih için araç kapasitesi: "
                        f"{bugun_teslimatlar}/{self.arac_id.gunluk_teslimat_limiti}"
                    )
                )
        
        # 2. İlçe-gün kapasitesi kontrolü
        if self.ilce_id:
            self._validate_ilce_gun_capacity()
    
    def _validate_ilce_gun_capacity(self) -> None:
        """İlçe-gün kapasitesini kontrol et.
        
        Raises:
            UserError: İlçe-gün kapasitesi dolu ise
        """
        from ..models.teslimat_utils import get_gun_kodu
        
        gun_kodu = get_gun_kodu(self.teslimat_tarihi)
        if not gun_kodu:
            return
        
        gun = self.env["teslimat.gun"].search(
            [("gun_kodu", "=", gun_kodu)], limit=1
        )
        if not gun:
            return
        
        gun_ilce = self.env["teslimat.gun.ilce"].search(
            [
                ("gun_id", "=", gun.id),
                ("ilce_id", "=", self.ilce_id.id),
                ("tarih", "=", self.teslimat_tarihi),
            ],
            limit=1,
        )
        
        if gun_ilce and gun_ilce.kalan_kapasite <= 0:
            raise UserError(
                _(
                    f"İlçe-gün kapasitesi dolu! "
                    f"Seçilen tarih için {self.ilce_id.name} ilçesi "
                    f"{gun.name} günü kapasitesi dolu."
                )
            )
    
    def _validate_ilce_arac_gun_compatibility(self) -> None:
        """İlçe-araç ve ilçe-gün uyumluluğunu kontrol et.
        
        Küçük araçlar için bu kontroller atlanır.
        
        Raises:
            UserError: Uyumluluk yoksa
        """
        from ..models.teslimat_constants import SMALL_VEHICLE_TYPES
        
        small_vehicle = self.arac_id.arac_tipi in SMALL_VEHICLE_TYPES
        
        if small_vehicle or not self.ilce_id:
            return
        
        # 1. İlçe-araç uyumluluğu
        if self.ilce_id not in self.arac_id.uygun_ilceler:
            arac_tipi_label = dict(
                self.arac_id._fields["arac_tipi"].selection
            ).get(self.arac_id.arac_tipi, self.arac_id.arac_tipi)
            
            raise UserError(
                _(
                    f"{self.arac_id.name} ({arac_tipi_label}) "
                    f"{self.ilce_id.name} ilçesine uygun değil! "
                    "Lütfen uygun bir araç seçin."
                )
            )
        
        # 2. İlçe-gün uyumluluğu
        self._validate_ilce_gun_matching()
    
    def _validate_ilce_gun_matching(self) -> None:
        """İlçe-gün eşleşmesinin olup olmadığını kontrol et.
        
        Raises:
            UserError: İlçe-gün eşleşmesi yoksa
        """
        from ..models.teslimat_utils import get_gun_kodu
        
        gun_kodu = get_gun_kodu(self.teslimat_tarihi)
        if not gun_kodu:
            return
        
        gun = self.env["teslimat.gun"].search(
            [("gun_kodu", "=", gun_kodu)], limit=1
        )
        if not gun:
            return
        
        gun_ilce = self.env["teslimat.gun.ilce"].search(
            [
                ("gun_id", "=", gun.id),
                ("ilce_id", "=", self.ilce_id.id),
            ],
            limit=1,
        )
        
        if not gun_ilce:
            raise UserError(
                _(
                    f"Seçilen tarih ({gun.name}) için "
                    f"{self.ilce_id.name} ilçesine teslimat yapılamaz! "
                    f"İlçe-gün eşleştirmesi yok."
                )
            )
    
    def _create_teslimat_belgesi(self):
        """Teslimat belgesini oluştur ve SMS gönder.
        
        Returns:
            teslimat.belgesi: Oluşturulan teslimat belgesi
        """
        vals = {
            "teslimat_tarihi": self.teslimat_tarihi,
            "arac_id": self.arac_id.id,
            "ilce_id": self.ilce_id.id if self.ilce_id else False,
            "musteri_id": self.musteri_id.id if self.musteri_id else False,
            "stock_picking_id": self.transfer_id.id if self.transfer_id else False,
            "transfer_no": self.transfer_id.name if self.transfer_id else False,
            "durum": "hazir",
            "manuel_telefon": self.manuel_telefon if self.manuel_telefon else False,
            "transfer_olusturan_id": self.transfer_olusturan_id.id if self.transfer_olusturan_id else False,
            "analytic_account_id": self.analytic_account_id.id if self.analytic_account_id else False,
        }
        
        teslimat = self.env["teslimat.belgesi"].create(vals)
        
        # Transfer ürünlerini güncelle
        if self.transfer_id:
            teslimat._update_transfer_urunleri(self.transfer_id)
        
        # SMS gönder
        teslimat.send_teslimat_sms()
        
        return teslimat
    
    def _redirect_to_teslimat(self, teslimat) -> dict:
        """Kullanıcıyı oluşturulan teslimat belgesine yönlendir.
        
        Args:
            teslimat: Oluşturulan teslimat belgesi
            
        Returns:
            dict: Window action dictionary
        """
        return {
            "type": "ir.actions.act_window",
            "name": _("Teslimat Belgeleri"),
            "res_model": "teslimat.belgesi",
            "view_mode": "tree,form",
            "domain": [("id", "=", teslimat.id)],
            "target": "current",
        }

