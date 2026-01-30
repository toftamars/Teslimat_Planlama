"""Teslimat Belgesi Modeli."""
import logging
from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .teslimat_constants import (
    CANCELLED_STATUS,
    COMPLETED_STATUS,
    DAILY_DELIVERY_LIMIT,
    SMALL_VEHICLE_TYPES,
    get_arac_kapatma_sebep_label,
)
from .teslimat_utils import (
    check_arac_kapatma,
    check_pazar_gunu_validation,
    get_gun_kodu,
    is_manager,
    is_pazar_gunu,
)

_logger = logging.getLogger(__name__)


class TeslimatBelgesi(models.Model):
    """Teslimat Belgesi.

    Teslimat belgeleri ve durum takibi.
    User grubu günlük max 7 teslimat oluşturabilir.
    Manager grubu sınırsız teslimat oluşturabilir.
    """

    _name = "teslimat.belgesi"
    _description = "Teslimat Belgesi"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "teslimat_tarihi desc, name"

    # Performans: Composite indeksler (kapasite sorgularında kritik)
    _sql_constraints = []

    name = fields.Char(
        string="Teslimat No",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Yeni"),
    )
    teslimat_tarihi = fields.Date(
        string="Teslimat Tarihi", required=True, default=fields.Date.today, index=True
    )

    # Müşteri Bilgileri
    musteri_id = fields.Many2one(
        "res.partner",
        string="Müşteri",
        required=True,
        domain=[("customer_rank", ">", 0)],
        tracking=True,
    )
    musteri_telefon = fields.Char(
        string="Müşteri Telefon", related="musteri_id.phone", readonly=True
    )
    manuel_telefon = fields.Char(
        string="Telefon (Opsiyonel)",
        help="Wizard'dan girilen opsiyonel telefon numarası"
    )
    musteri_adres = fields.Text(
        string="Müşteri Adresi",
        compute="_compute_musteri_adres",
        store=False,
        help="Müşterinin tam adresi"
    )
    
    @api.depends("musteri_id")
    def _compute_musteri_adres(self):
        """Müşteri adresini hesapla."""
        for record in self:
            if record.musteri_id:
                adres_parcalari = []
                if record.musteri_id.street:
                    adres_parcalari.append(record.musteri_id.street)
                if record.musteri_id.street2:
                    adres_parcalari.append(record.musteri_id.street2)
                if record.musteri_id.city:
                    adres_parcalari.append(record.musteri_id.city)
                if record.musteri_id.state_id:
                    adres_parcalari.append(record.musteri_id.state_id.name)
                if record.musteri_id.zip:
                    adres_parcalari.append(record.musteri_id.zip)
                if record.musteri_id.country_id:
                    adres_parcalari.append(record.musteri_id.country_id.name)
                
                if adres_parcalari:
                    record.musteri_adres = ", ".join(adres_parcalari)
                else:
                    record.musteri_adres = "Adres bilgisi bulunamadı"
            else:
                record.musteri_adres = ""

    # Araç ve İlçe Bilgileri
    arac_id = fields.Many2one(
        "teslimat.arac", string="Araç", required=True, tracking=True, index=True
    )
    ilce_id = fields.Many2one(
        "teslimat.ilce", string="İlçe", required=True, tracking=True, index=True
    )
    surucu_id = fields.Many2one(
        "res.partner",
        string="Sürücü",
        # domain=[("is_driver", "=", True)],  # Geçici olarak kaldırıldı - modül upgrade edildikten sonra aktif edilebilir
        tracking=True,
    )

    # Transfer Belgesi Entegrasyonu
    transfer_no = fields.Char(
        string="Transfer No", help="Transfer belgesi numarası", tracking=True
    )
    stock_picking_id = fields.Many2one(
        "stock.picking",
        string="Transfer Belgesi",
        domain=[("state", "in", ["waiting", "confirmed", "assigned", "done"])],
        tracking=True,
    )

    # Ürün Bilgileri (Transfer belgesindeki tüm ürünler)
    transfer_urun_ids = fields.One2many(
        "teslimat.belgesi.urun",
        "teslimat_belgesi_id",
        string="Transfer Ürünleri",
    )

    # Durum
    durum = fields.Selection(
        [
            ("taslak", "Taslak"),
            ("bekliyor", "Bekliyor"),
            ("hazir", "Hazır"),
            ("yolda", "Yolda"),
            ("teslim_edildi", "Teslim Edildi"),
            ("iptal", "İptal"),
        ],
        string="Durum",
        default="taslak",
        required=True,
        tracking=True,
        index=True,
    )

    # Sıra
    sira_no = fields.Integer(string="Sıra No", default=1)

    # Teslim Bilgileri
    teslim_alan_kisi = fields.Char(
        string="Teslim Alan Kişi",
        help="Teslimatı teslim alan kişinin adı soyadı (tamamlanırken doldurulur)",
    )
    gercek_teslimat_saati = fields.Datetime(string="Gerçek Teslimat Saati")

    # Notlar
    notlar = fields.Text(string="Notlar")
    
    # Teslimat Fotoğrafı
    teslimat_fotografi = fields.Binary(
        string="Teslimat Fotoğrafı",
        attachment=True,
        help="Teslimat tamamlandığında eklenen fotoğraf"
    )
    fotograf_dosya_adi = fields.Char(string="Fotoğraf Dosya Adı")
    
    # UI Control
    is_readonly = fields.Boolean(
        string="Salt Okunur",
        compute="_compute_is_readonly",
        help="Teslim edilmiş belgeler salt okunurdur"
    )

    @api.model
    def create(self, vals: dict) -> "TeslimatBelgesi":
        """Teslimat belgesi oluştur.

        Args:
            vals: Create değerleri

        Returns:
            TeslimatBelgesi: Oluşturulan kayıt
        """
        # Otomatik değer atamaları
        self._prepare_vals_for_create(vals)

        # Validasyonlar
        teslimat_tarihi = vals.get("teslimat_tarihi", fields.Date.today())
        arac_id = vals.get("arac_id")

        check_pazar_gunu_validation(teslimat_tarihi, bypass_for_manager=True, env=self.env)
        self._check_arac_kapatma_on_create(arac_id, teslimat_tarihi)
        self._check_daily_limit(teslimat_tarihi)

        return super(TeslimatBelgesi, self).create(vals)

    def _prepare_vals_for_create(self, vals: dict) -> None:
        """Create için vals'u hazırla (sequence ve sıra no).

        Args:
            vals: Create değerleri (in-place güncellenir)
        """
        # Sequence ile otomatik numaralandırma
        if vals.get("name", _("Yeni")) == _("Yeni"):
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("teslimat.belgesi")
                or _("Yeni")
            )

        # Sıra numarası otomatik ata
        if not vals.get("sira_no"):
            vals["sira_no"] = self._get_next_sira_no(
                vals.get("arac_id"),
                vals.get("teslimat_tarihi", fields.Date.today())
            )

    def _get_next_sira_no(self, arac_id, teslimat_tarihi):
        """Aynı araç ve tarih için sıradaki sıra numarasını döndür.

        Args:
            arac_id: Araç ID
            teslimat_tarihi: Teslimat tarihi

        Returns:
            int: Sıradaki sıra numarası
        """
        if not arac_id or not teslimat_tarihi:
            return 1

        son_teslimat = self.search(
            [
                ("arac_id", "=", arac_id),
                ("teslimat_tarihi", "=", teslimat_tarihi),
            ],
            order="sira_no desc",
            limit=1,
        )

        return son_teslimat.sira_no + 1 if son_teslimat else 1

    def _check_arac_kapatma_on_create(self, arac_id, teslimat_tarihi):
        """Create sırasında araç kapatma kontrolü yap.

        Args:
            arac_id: Araç ID
            teslimat_tarihi: Teslimat tarihi

        Raises:
            ValidationError: Araç kapalı ise
        """
        if not arac_id or not teslimat_tarihi:
            return

        kapali, kapatma = self.env["teslimat.arac.kapatma"].arac_kapali_mi(
            arac_id, teslimat_tarihi
        )

        if kapali and kapatma:
            sebep_text = get_arac_kapatma_sebep_label(kapatma.sebep)
            kapatan_kisi = kapatma.kapatan_kullanici_id.name or "Bilinmiyor"
            arac_name = self.env["teslimat.arac"].browse(arac_id).name

            raise ValidationError(
                _(
                    f"Bu tarihte araç kapalı! Teslimat oluşturulamaz.\n\n"
                    f"Tarih: {teslimat_tarihi.strftime('%d.%m.%Y')}\n"
                    f"Araç: {arac_name}\n"
                    f"Sebep: {sebep_text}\n"
                    f"Kapatan: {kapatan_kisi}\n"
                    f"{('Açıklama: ' + kapatma.aciklama) if kapatma.aciklama else ''}"
                )
            )

    def _check_daily_limit(self, teslimat_tarihi):
        """Günlük teslimat limiti kontrolü (sadece user grubu için).

        Args:
            teslimat_tarihi: Teslimat tarihi

        Raises:
            UserError: Limit aşıldı ise
        """
        user = self.env.user
        if user.has_group("teslimat_planlama.group_teslimat_manager"):
            return  # Yöneticiler için limit yok

        bugun_teslimat_sayisi = self.search_count(
            [
                ("teslimat_tarihi", "=", teslimat_tarihi),
                ("create_uid", "=", user.id),
            ]
        )

        if bugun_teslimat_sayisi >= DAILY_DELIVERY_LIMIT:
            raise UserError(
                _(
                    f"Günlük teslimat limiti aşıldı! "
                    f"Bugün için en fazla {DAILY_DELIVERY_LIMIT} teslimat "
                    f"oluşturabilirsiniz. Yönetici yetkisi gereklidir."
                )
            )
    
    def write(self, vals):
        """Teslimat belgesi güncelleme - Teslim edilmiş belgelerde kısıtlama.

        Teslim edilmiş belgeler düzenlenemez (sadece yöneticiler için izin var).
        İptal işlemi sadece yöneticiler tarafından yapılabilir.
        """
        # İptal yetkisi kontrolü - Sadece yöneticiler iptal edebilir
        if 'durum' in vals and vals['durum'] == 'iptal':
            if not is_manager(self.env):
                raise UserError(
                    _(
                        "Teslimat iptal yetkisi yok!\n\n"
                        "Sadece yöneticiler teslimat belgelerini iptal edebilir.\n"
                        "Lütfen yöneticinizle iletişime geçin."
                    )
                )

        # DEBUG: Write işlemlerini logla (Production'da kapatılmalı)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("WRITE: Records=%s, Keys=%s", [r.name for r in self], list(vals.keys()))

        for record in self:
            # Teslim edilmiş ve iptal edilmiş belgelerde değişiklik yapılamaz
            # AMA: Eğer wizard tamamlama işleminden geliyorsa (durum değişikliği), izin ver
            if record.durum in ['teslim_edildi', 'iptal']:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug("WRITE to archived: %s (status=%s)", record.name, record.durum)

                # Sadece wizard'dan gelen alanları kontrol et
                # message_main_attachment_id: mail modülünden, message_post çağrısı sonrası otomatik eklenir
                wizard_fields = {
                    'durum', 'gercek_teslimat_saati', 'teslim_alan_kisi',
                    'teslimat_fotografi', 'fotograf_dosya_adi', 'notlar',
                    'message_main_attachment_id'  # mail.thread - message_post sonrası otomatik
                }
                extra_fields = set(vals.keys()) - wizard_fields

                if extra_fields:
                    _logger.warning("Archived record edit attempt: %s, extra_fields=%s", record.name, extra_fields)
                    # Wizard dışı değişiklik - engelle
                    raise UserError(
                        _(
                            "Teslim edilmiş teslimat belgeleri düzenlenemez!\n\n"
                            f"Belge: {record.name}\n"
                            f"Durum: Teslim Edildi\n"
                            f"Teslim Tarihi: {record.gercek_teslimat_saati or 'N/A'}\n"
                            f"Teslim Alan: {record.teslim_alan_kisi or 'N/A'}\n\n"
                            "Bu belge arşivlenmiştir ve değiştirilemez."
                        )
                    )
                # Whitelist OK - no log needed

        return super(TeslimatBelgesi, self).write(vals)
    
    def unlink(self):
        """Teslimat belgesi silme - Kısıtlamalar.
        
        - Sadece yöneticiler silebilir
        - Teslim edilmiş belgeler silinemez (yönetici bile)
        """
        # Yönetici kontrolü
        if not self.env.user.has_group("teslimat_planlama.group_teslimat_manager"):
            raise UserError(
                _(
                    "Teslimat belgelerini sadece yöneticiler silebilir!\n\n"
                    "Yönetici yetkisi gereklidir."
                )
            )
        
        # Teslim edilmiş belge kontrolü
        for record in self:
            if record.durum == 'teslim_edildi':
                raise UserError(
                    _(
                        "Teslim edilmiş teslimat belgeleri silinemez!\n\n"
                        f"Belge: {record.name}\n"
                        f"Durum: Teslim Edildi\n"
                        f"Teslim Tarihi: {record.gercek_teslimat_saati or 'N/A'}\n"
                        f"Teslim Alan: {record.teslim_alan_kisi or 'N/A'}\n\n"
                        "Bu belge arşivlenmiştir ve silinemez.\n"
                        "Veri bütünlüğü için teslim edilmiş belgeler korunur."
                    )
                )
        
        return super(TeslimatBelgesi, self).unlink()

    @api.constrains("teslimat_tarihi", "arac_id", "ilce_id", "durum")
    def _check_teslimat_validations(self):
        """Teslimat belgesi validasyonları.

        Tüm kritik validasyonları çalıştırır.
        """
        for record in self:
            # Teslim edilmiş veya iptal belgeleri kontrol etme
            if record.durum in [COMPLETED_STATUS, CANCELLED_STATUS]:
                continue

            # Validasyon kontrollerini sırayla çalıştır
            record._validate_ayni_gun_teslimat()
            record._validate_pazar_gunu()
            record._validate_arac_kapatma()

            # Yönetici ve küçük araç kontrolü (birçok validasyonda kullanılıyor)
            yonetici_mi = is_manager(self.env)
            small_vehicle = record.arac_id and record.arac_id.arac_tipi in SMALL_VEHICLE_TYPES

            # Yönetici ve küçük araçlar için bazı kontroller atlanır
            if not yonetici_mi and not small_vehicle:
                record._validate_arac_ilce_uyumlulugu()
                record._validate_ilce_gun_eslesmesi()

            record._validate_arac_kapasitesi()

    def _validate_ayni_gun_teslimat(self):
        """Aynı gün teslimat kontrolü (12:00 sonrası yasak)."""
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        simdi_istanbul = datetime.now(istanbul_tz)
        bugun = simdi_istanbul.date()
        saat = simdi_istanbul.hour
        dakika = simdi_istanbul.minute

        if self.teslimat_tarihi == bugun and (saat >= 12):
            raise ValidationError(
                _(f"Aynı gün teslimat yazılamaz!\n\n"
                  f"İstanbul Saati: {saat:02d}:{dakika:02d}\n"
                  f"Teslimat Tarihi: {self.teslimat_tarihi}\n\n"
                  f"Saat 12:00'dan sonra bugüne teslimat planlanamaz.\n"
                  f"Lütfen yarın veya sonraki günler için teslimat planlayın.")
            )

    def _validate_pazar_gunu(self):
        """Pazar günü kontrolü."""
        if is_pazar_gunu(self.teslimat_tarihi):
            raise ValidationError(
                _("Pazar günü teslimat yapılamaz!\n\n"
                  "Lütfen farklı bir gün seçin.")
            )

    def _validate_arac_kapatma(self):
        """Araç kapatma kontrolü."""
        if self.teslimat_tarihi and self.arac_id:
            gecerli, hata_mesaji = check_arac_kapatma(
                self.env, self.arac_id.id, self.teslimat_tarihi, bypass_for_manager=False
            )
            if not gecerli:
                raise ValidationError(_(hata_mesaji))

    def _validate_arac_ilce_uyumlulugu(self):
        """Araç-İlçe uyumluluğu kontrolü."""
        if self.ilce_id and self.arac_id:
            if self.ilce_id not in self.arac_id.uygun_ilceler:
                arac_tipi_label = dict(self.arac_id._fields["arac_tipi"].selection).get(
                    self.arac_id.arac_tipi, self.arac_id.arac_tipi
                )
                raise ValidationError(
                    _(f"Araç-İlçe Uyumsuzluğu!\n\n"
                      f"Araç: {self.arac_id.name} ({arac_tipi_label})\n"
                      f"İlçe: {self.ilce_id.name}\n\n"
                      f"Bu araç bu ilçeye teslimat yapamaz.\n"
                      f"Lütfen uygun bir araç veya ilçe seçin.")
                )

    def _validate_ilce_gun_eslesmesi(self):
        """İlçe-gün eşleşmesi kontrolü."""
        if self.ilce_id and self.arac_id:
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
                            ("tarih", "=", False),  # Genel kurallar
                        ],
                        limit=1,
                    )

                    if not gun_ilce:
                        raise ValidationError(
                            _(f"İlçe-Gün Eşleşmesi Hatası!\n\n"
                              f"İlçe: {self.ilce_id.name}\n"
                              f"Gün: {gun.name}\n\n"
                              f"Bu ilçeye bu gün teslimat yapılamaz.\n"
                              f"Lütfen uygun bir gün seçin.")
                        )

    def _validate_arac_kapasitesi(self):
        """Araç kapasitesi kontrolü."""
        if self.arac_id and self.teslimat_tarihi:
            domain = [
                ("teslimat_tarihi", "=", self.teslimat_tarihi),
                ("arac_id", "=", self.arac_id.id),
                ("durum", "!=", "iptal"),  # Sadece iptal hariç
                ("id", "!=", self.id),  # Kendisini hariç tut
            ]

            # İlçe bazlı kontrol
            if self.ilce_id:
                domain.append(("ilce_id", "=", self.ilce_id.id))

            mevcut_teslimat_sayisi = self.env["teslimat.belgesi"].search_count(domain)

            # +1 ekle (kendisi için)
            toplam = mevcut_teslimat_sayisi + 1

            if toplam > self.arac_id.gunluk_teslimat_limiti:
                ilce_bilgi = f" - {self.ilce_id.name}" if self.ilce_id else ""
                raise ValidationError(
                    _(f"Araç Kapasitesi Dolu!\n\n"
                      f"Araç: {self.arac_id.name}{ilce_bilgi}\n"
                      f"Tarih: {self.teslimat_tarihi.strftime('%d.%m.%Y')}\n"
                      f"Kapasite: {toplam}/{self.arac_id.gunluk_teslimat_limiti}\n\n"
                      f"Bu tarih için araç kapasitesi dolmuştur.\n"
                      f"Lütfen farklı bir tarih veya araç seçin.")
                )

    @api.depends("durum")
    def _compute_is_readonly(self) -> None:
        """Teslim edilmiş belgeler salt okunurdur."""
        for record in self:
            record.is_readonly = record.durum == 'teslim_edildi'
    
    @api.onchange("transfer_no")
    def _onchange_transfer_no(self) -> None:
        """Transfer no değiştiğinde otomatik bilgi doldur."""
        if not self.transfer_no:
            return

        try:
            # Transfer belgesini bul
            picking = self.env["stock.picking"].search(
                [("name", "=", self.transfer_no)], limit=1
            )

            if picking:
                self.stock_picking_id = picking
                self._onchange_stock_picking()
            else:
                return {
                    "warning": {
                        "title": _("Uyarı"),
                        "message": _(
                            f"Transfer belgesi bulunamadı: {self.transfer_no}"
                        ),
                    }
                }
        except Exception as e:
            _logger.exception("Transfer no onchange hatası:")
            return {
                "warning": {
                    "title": _("Hata"),
                    "message": _(
                        f"Transfer bilgileri alınırken hata oluştu: {str(e)}"
                    ),
                }
            }

    @api.onchange("stock_picking_id")
    def _onchange_stock_picking(self) -> None:
        """Stock picking seçildiğinde otomatik bilgi doldur."""
        if not self.stock_picking_id:
            return

        try:
            picking = self.stock_picking_id

            # Müşteri bilgisi
            if picking.partner_id:
                self.musteri_id = picking.partner_id

            # Transfer no
            if picking.name:
                self.transfer_no = picking.name

            # Transfer ürünlerini güncelle
            self._update_transfer_urunleri(picking)
        except Exception as e:
            _logger.exception("Stock picking onchange hatası:")
            return {
                "warning": {
                    "title": _("Hata"),
                    "message": _(
                        f"Transfer belgesi bilgileri alınırken hata oluştu: {str(e)}"
                    ),
                }
            }

    @api.onchange("musteri_id")
    def _onchange_musteri(self) -> None:
        """Müşteri değiştiğinde bilgileri güncelle."""
        if not self.musteri_id:
            return

        # Müşteri adres bilgileri varsa kullanılabilir
        # Buraya ek bilgiler eklenebilir
        pass

    def _update_transfer_urunleri(self, picking: "stock.picking") -> None:
        """Transfer belgesindeki ürünleri güncelle (Bellek içi komutlar kullanarak).
        
        Onchange içinde veritabanına create/unlink işlemi yapmak işlemi kilitler.
        O yüzden Odoo komutlarını kullanıyoruz.
        """
        lines = []
        sequence = 1
        for move in picking.move_ids_without_package:
            lines.append((0, 0, {
                "sequence": sequence,
                "urun_id": move.product_id.id,
                "miktar": move.quantity_done or move.product_uom_qty,
                "birim": move.product_uom.id,
                "stock_move_id": move.id,
            }))
            sequence += 1
        
        self.transfer_urun_ids = [(5, 0, 0)] + lines

    def action_yolda_yap(self) -> None:
        """Teslimat durumunu 'yolda' yap (sürücüler için).

        Sürücü yola çıktığında bu butona basar.
        Durum 'hazir' → 'yolda' olur.
        """
        self.ensure_one()

        if self.durum != "hazir":
            raise UserError(
                _("Sadece 'Hazır' durumundaki teslimatlar yola çıkarılabilir.")
            )

        # Durumu yolda yap
        self.durum = "yolda"

        # Chatter'a not ekle
        self.message_post(
            body=_("Sürücü yola çıktı. Teslimat yolda."),
            subject=_("Teslimat Yolda"),
        )

    def action_teslimat_tamamla(self) -> dict:
        """Teslimat tamamlama wizard'ını aç."""
        self.ensure_one()

        if self.durum not in ["hazir", "yolda"]:
            raise UserError(
                _("Sadece 'Hazır' veya 'Yolda' durumundaki teslimatlar tamamlanabilir.")
            )

        # Wizard'ı aç
        return {
            "name": _("Teslimatı Tamamla"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.tamamlama.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_teslimat_belgesi_id": self.id,
            },
        }

    def action_yol_tarifi(self) -> dict:
        """Müşteri konumuna Google Maps ile yol tarifi başlat.

        Returns:
            dict: Google Maps URL action
        """
        self.ensure_one()
        
        if not self.musteri_id:
            raise UserError(_("Müşteri bilgisi bulunamadı. Yol tarifi başlatılamaz."))
        
        # Müşteri adres bilgilerini topla
        partner = self.musteri_id
        adres_parcalari = []
        
        if partner.street:
            adres_parcalari.append(partner.street)
        if partner.street2:
            adres_parcalari.append(partner.street2)
        if partner.city:
            adres_parcalari.append(partner.city)
        if partner.state_id:
            adres_parcalari.append(partner.state_id.name)
        if partner.country_id:
            adres_parcalari.append(partner.country_id.name)
        
        # Adres oluştur
        if adres_parcalari:
            adres = ", ".join(adres_parcalari)
        else:
            # Adres yoksa sadece müşteri adını kullan
            adres = partner.name
        
        # Google Maps URL oluştur (directions API)
        import urllib.parse
        encoded_address = urllib.parse.quote(adres)
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_address}"
        
        return {
            "type": "ir.actions.act_url",
            "url": google_maps_url,
            "target": "new",
        }

    def action_iptal_et(self) -> None:
        """Teslimatı iptal et (sadece yöneticiler).

        Yöneticiler bu butona basarak teslimatı iptal edebilir.
        Durum 'iptal' olur ve chatter'a not eklenir.
        """
        self.ensure_one()

        # Yönetici kontrolü (write metodunda da var ama burada da kontrol edelim)
        if not is_manager(self.env):
            raise UserError(
                _(
                    "Teslimat iptal yetkisi yok!\n\n"
                    "Sadece yöneticiler teslimat belgelerini iptal edebilir.\n"
                    "Lütfen yöneticinizle iletişime geçin."
                )
            )

        # Zaten iptal veya teslim edilmiş ise hata ver
        if self.durum == "iptal":
            raise UserError(_("Bu teslimat zaten iptal edilmiş."))

        if self.durum == "teslim_edildi":
            raise UserError(
                _("Teslim edilmiş teslimat iptal edilemez!")
            )

        # Durumu iptal yap
        self.durum = "iptal"

        # Chatter'a not ekle
        self.message_post(
            body=_("Teslimat yönetici tarafından iptal edildi."),
            subject=_("Teslimat İptal Edildi"),
        )

    def send_teslimat_sms(self) -> bool:
        """Teslimat SMS'i gönder ve chatter'a kaydet.

        Returns:
            bool: SMS gönderimi başarılı ise True
        """
        self.ensure_one()

        if not self.musteri_id:
            _logger.warning("SMS gönderilemedi: Müşteri bilgisi yok")
            return False

        if not self.musteri_telefon:
            _logger.warning("SMS gönderilemedi: Müşteri telefon numarası yok")
            self.message_post(
                body=_(
                    "SMS gönderilemedi: Müşteri telefon numarası bulunamadı."
                ),
                subject=_("SMS Gönderim Hatası"),
            )
            return False

        # Tarih formatı
        tarih_formati = self.teslimat_tarihi.strftime("%d.%m.%Y")

        # SMS içeriği
        sms_icerigi = (
            f"Sayın {self.musteri_id.name}, "
            f"teslimatınız {tarih_formati} tarihinde planlanmıştır. "
            f"Teslimat No: {self.name}. "
            f"Bilgilendirme için teşekkür ederiz."
        )

        try:
            # SMS gönderme (mock - gerçek implementasyonda SMS API kullanılabilir)
            # Örnek: self.env['sms.api'].send_sms(phone, message)
            _logger.info(
                "SMS gönderiliyor: %s -> %s", self.musteri_telefon, sms_icerigi
            )

            # SMS gönderim bilgisini chatter'a ekle
            self.message_post(
                body=_(
                    f"📱 SMS Gönderildi\n"
                    f"Alıcı: {self.musteri_id.name}\n"
                    f"Telefon: {self.musteri_telefon}\n"
                    f"Mesaj: {sms_icerigi}\n"
                    f"Tarih: {fields.Datetime.now().strftime('%d.%m.%Y %H:%M')}"
                ),
                subject=_("Teslimat Planlama SMS"),
                message_type="notification",
            )

            return True

        except Exception as e:
            _logger.error("SMS gönderim hatası: %s", e)
            self.message_post(
                body=_(
                    f"SMS gönderilemedi: {str(e)}\n"
                    f"Alıcı: {self.musteri_id.name}\n"
                    f"Telefon: {self.musteri_telefon}"
                ),
                subject=_("SMS Gönderim Hatası"),
                message_type="notification",
            )
            return False

