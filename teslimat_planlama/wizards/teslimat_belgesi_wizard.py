"""Teslimat Belgesi Oluşturma Wizard'ı."""
import logging
from datetime import datetime
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.teslimat_planlama.models.teslimat_ilce import (
    ANADOLU_ILCELERI,
    AVRUPA_ILCELERI,
)
from odoo.addons.teslimat_planlama.models.teslimat_utils import is_small_vehicle

_logger = logging.getLogger(__name__)


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

    # Hesaplanan alanlar
    arac_kucuk_mu = fields.Boolean(
        string="Küçük Araç",
        compute="_compute_arac_kucuk_mu",
        store=False,
    )

    @api.model
    def create(self, vals):
        """Create metodunu override et - context'ten ilce_id al."""
        ctx = self.env.context

        _logger.info("=== WIZARD CREATE ===")
        _logger.info("Context: %s", ctx)
        _logger.info("Vals before: %s", vals)

        # Context'ten ilce_id al ve vals'a ekle
        if ctx.get("default_ilce_id") and "ilce_id" not in vals:
            vals["ilce_id"] = ctx.get("default_ilce_id")
            _logger.info("İlçe ID vals'a eklendi: %s", vals["ilce_id"])

        _logger.info("Vals after: %s", vals)
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

        _logger.info("=" * 80)
        _logger.info("WIZARD DEFAULT_GET - BASLANGIC")
        _logger.info("=" * 80)
        _logger.info("Context keys: %s", list(ctx.keys()))
        _logger.info("fields_list: %s", fields_list)

        # Tarih context'ten geliyorsa kullan
        if ctx.get("default_teslimat_tarihi"):
            tarih_str = ctx.get("default_teslimat_tarihi")
            _logger.info("✓ Tarih bulundu: %s (type: %s)", tarih_str, type(tarih_str))
            if isinstance(tarih_str, str):
                try:
                    tarih = datetime.strptime(tarih_str, "%Y-%m-%d").date()
                    res["teslimat_tarihi"] = tarih
                    _logger.info("✓ Tarih parse edildi: %s", tarih)
                except ValueError:
                    res["teslimat_tarihi"] = fields.Date.today()
                    _logger.warning("⚠ Tarih parse edilemedi, bugün kullanıldı")
            else:
                res["teslimat_tarihi"] = tarih_str
        else:
            _logger.warning("✗ Context'te default_teslimat_tarihi YOK")

        # Araç context'ten geliyorsa kullan
        if ctx.get("default_arac_id"):
            arac_id = ctx.get("default_arac_id")
            res["arac_id"] = arac_id
            _logger.info("✓ Araç ID atandı: %s", arac_id)
        else:
            _logger.warning("✗ Context'te default_arac_id YOK")

        # İlçe context'ten geliyorsa kullan - ZORUNLU ATAMA
        if ctx.get("default_ilce_id"):
            ilce_id = ctx.get("default_ilce_id")
            
            # İlçe kaydını doğrula
            ilce = self.env["teslimat.ilce"].browse(ilce_id)
            if ilce.exists():
                res["ilce_id"] = ilce_id
                _logger.info("✓✓✓ İLÇE ID ATANDI: %s - %s ✓✓✓", ilce_id, ilce.name)
                
                # fields_list'e ilce_id'yi ekle (Odoo'nun default_get'e dahil etmesi için)
                if fields_list and 'ilce_id' not in fields_list:
                    fields_list.append('ilce_id')
            else:
                _logger.error("✗✗✗ İLÇE KAYDI BULUNAMADI: %s ✗✗✗", ilce_id)
        else:
            _logger.error("✗✗✗ CONTEXT'TE default_ilce_id YOK! ✗✗✗")

        _logger.info("=" * 80)
        _logger.info("WIZARD DEFAULT_GET - SONUC")
        _logger.info("Result dict: %s", res)
        _logger.info("=" * 80)

        # Transfer ID context'ten geliyorsa kullan
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

        return res

    @api.model
    def create(self, vals):
        """Wizard oluşturulurken context'ten ilçe ID'sini garanti al."""
        ctx = self.env.context
        
        # Eğer vals'ta ilce_id yoksa ve context'te varsa, ekle
        if not vals.get('ilce_id') and ctx.get('default_ilce_id'):
            ilce_id = ctx.get('default_ilce_id')
            vals['ilce_id'] = ilce_id
            _logger.info("🟢 CREATE: İlçe ID vals'a eklendi: %s", ilce_id)
        
        return super(TeslimatBelgesiWizard, self).create(vals)
    
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
    def _onchange_arac_id(self):
        """Araç değiştiğinde context'ten ilçe ID'sini kontrol et ve ata."""
        # Context'ten ilçe ID'si geliyorsa ata
        ctx = self.env.context
        if ctx.get("default_ilce_id") and not self.ilce_id:
            ilce_id = ctx.get("default_ilce_id")
            _logger.info("🔵 ONCHANGE: Context'ten ilçe atanıyor: %s", ilce_id)
            self.ilce_id = ilce_id
            return {'value': {'ilce_id': ilce_id}}

    @api.onchange("arac_id")
    def _onchange_arac_id(self) -> None:
        """Araç seçildiğinde ilçe domain'ini güncelle.
        
        Yöneticiler için tüm ilçeler gösterilir.
        """
        from odoo.addons.teslimat_planlama.models.teslimat_utils import is_manager
        
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
        """Transfer seçildiğinde müşteri bilgilerini otomatik doldur."""
        import logging
        _logger = logging.getLogger(__name__)

        picking = self.transfer_id
        _logger.info("=== ONCHANGE TRANSFER_ID ===")
        _logger.info("Picking: %s", picking)

        if picking:
            _logger.info("Picking name: %s", picking.name)
            _logger.info("Picking partner_id: %s", picking.partner_id)
            _logger.info("Picking state: %s", picking.state)

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
                _logger.info("Setting musteri_id to: %s", picking.partner_id)
                self.musteri_id = picking.partner_id
                # Adres bilgisi - partner'dan al
                partner = picking.partner_id
                adres_parts = []
                if partner.street:
                    adres_parts.append(partner.street)
                if partner.street2:
                    adres_parts.append(partner.street2)
                if partner.city:
                    adres_parts.append(partner.city)
                if partner.state_id:
                    adres_parts.append(partner.state_id.name)
                if adres_parts:
                    self.adres = ", ".join(adres_parts)
                else:
                    # Fallback - contact_address kullan
                    self.adres = partner.contact_address or partner.name
            else:
                _logger.warning("Picking has no partner_id!")

    def action_teslimat_olustur(self) -> dict:
        """Teslimat belgesi oluştur, SMS gönder ve yönlendir.

        Returns:
            dict: Teslimat belgeleri list view'ı
        """
        self.ensure_one()

        # Validasyonlar
        if not self.arac_id:
            raise UserError(_("Araç seçimi zorunludur."))

        # Küçük araç değilse ilçe zorunlu
        small_vehicle = self.arac_id.arac_tipi in [
            "kucuk_arac_1",
            "kucuk_arac_2",
            "ek_arac",
        ]
        if not small_vehicle and not self.ilce_id:
            raise UserError(_("Yaka bazlı araçlar için ilçe seçimi zorunludur."))

        # Transfer zorunlu
        if not self.transfer_id:
            raise UserError(_("Transfer belgesi seçimi zorunludur."))

        # Müşteri zorunlu
        if not self.musteri_id:
            raise UserError(_("Müşteri seçimi zorunludur."))

        # Pazar günü kontrolü - Tüm araçlar pazar günü kapalıdır
        from ..models.teslimat_utils import check_pazar_gunu_validation
        
        check_pazar_gunu_validation(self.teslimat_tarihi)

        # Kapasite kontrolü - Araç + İlçe (Günlük maksimum 7 teslimat)
        # İlçe bazlı kontrol: Aynı araç aynı gün farklı ilçelere gidebilir
        # İptal hariç TÜM durumlar kapasite doldurur (teslim_edildi dahil)
        domain = [
            ("teslimat_tarihi", "=", self.teslimat_tarihi),
            ("arac_id", "=", self.arac_id.id),
            ("durum", "!=", "iptal"),  # Sadece iptal hariç
        ]
        
        # Eğer ilçe seçiliyse ilçe bazlı kontrol yap
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

        # Kapasite kontrolü - İlçe-Gün (eğer ilçe seçiliyse)
        if self.ilce_id:
            from ..models.teslimat_utils import get_gun_kodu
            
            gun_kodu = get_gun_kodu(self.teslimat_tarihi)
            if gun_kodu:
                gun = self.env["teslimat.gun"].search(
                    [("gun_kodu", "=", gun_kodu)], limit=1
                )
                if gun:
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

        # İlçe-Araç uyumluluğu kontrolü (Many2many ilişkisini kullanarak)
        if not small_vehicle and self.ilce_id and self.arac_id:
            if self.ilce_id not in self.arac_id.uygun_ilceler:
                arac_tipi_label = dict(self.arac_id._fields["arac_tipi"].selection).get(
                    self.arac_id.arac_tipi, self.arac_id.arac_tipi
                )
                raise UserError(
                    _(
                        f"{self.arac_id.name} ({arac_tipi_label}) "
                        f"{self.ilce_id.name} ilçesine uygun değil! "
                        "Lütfen uygun bir araç seçin."
                    )
                )

        # İlçe-Gün uyumluluğu kontrolü (küçük araçlar hariç)
        if not small_vehicle and self.ilce_id:
            from ..models.teslimat_utils import get_gun_kodu
            
            gun_kodu = get_gun_kodu(self.teslimat_tarihi)
            if gun_kodu:
                gun = self.env["teslimat.gun"].search(
                    [("gun_kodu", "=", gun_kodu)], limit=1
                )
                if gun:
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

        # Teslimat belgesi oluştur
        vals = {
            "teslimat_tarihi": self.teslimat_tarihi,
            "arac_id": self.arac_id.id,
            "ilce_id": self.ilce_id.id if self.ilce_id else False,
            "musteri_id": self.musteri_id.id if self.musteri_id else False,
            "stock_picking_id": self.transfer_id.id if self.transfer_id else False,
            "transfer_no": self.transfer_id.name if self.transfer_id else False,
            "durum": "hazir",  # Teslimat belgesi hazır durumunda oluşturulur
        }

        teslimat = self.env["teslimat.belgesi"].create(vals)

        # Transfer ürünlerini güncelle
        if self.transfer_id:
            teslimat._update_transfer_urunleri(self.transfer_id)

        # SMS gönder
        teslimat.send_teslimat_sms()

        # Teslimat belgeleri listesine yönlendir
        return {
            "type": "ir.actions.act_window",
            "name": _("Teslimat Belgeleri"),
            "res_model": "teslimat.belgesi",
            "view_mode": "tree,form",
            "domain": [("id", "=", teslimat.id)],
            "target": "current",
        }

