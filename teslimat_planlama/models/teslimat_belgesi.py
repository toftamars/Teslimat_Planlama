"""Teslimat Belgesi Modeli."""
import logging

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
    is_manager,
)

_logger = logging.getLogger(__name__)


class TeslimatBelgesi(models.Model):
    """Teslimat Belgesi.

    Teslimat belgeleri ve durum takibi.
    User grubu günlük max 7 teslimat oluşturabilir.
    Manager grubu sınırsız teslimat oluşturabilir.

    Mixin'ler:
        - teslimat.belgesi.validators: Tüm validasyon metodları
    """

    _name = "teslimat.belgesi"
    _description = "Teslimat Belgesi"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "teslimat.belgesi.validators",  # Validasyon mixin
        "teslimat.belgesi.actions",  # Action ve onchange mixin
    ]
    _order = "teslimat_tarihi asc, name"

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
    location_id = fields.Many2one(
        "stock.location",
        string="Depo",
        related="stock_picking_id.location_id",
        readonly=True,
        help="Transfer belgesindeki kaynak konum (ürünün çıkacağı depo)",
    )
    transfer_olusturan_id = fields.Many2one(
        "res.users",
        string="Sorumlu Personel",
        domain=[("share", "=", False)],
        help="Sorumlu personel (yalnızca iç kullanıcılar)",
        tracking=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analitik hesap",
        help="Sistemdeki analitik hesap (wizard veya transferden)",
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
    can_user_cancel = fields.Boolean(
        string="İptal Edebilir",
        compute="_compute_can_user_cancel",
        help="Mevcut kullanıcı bu teslimatı iptal edebilir (yönetici veya transferi oluşturan)"
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

    def _get_next_sira_no(self, arac_id: int, teslimat_tarihi: fields.Date) -> int:
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

    def _check_arac_kapatma_on_create(self, arac_id: int, teslimat_tarihi: fields.Date) -> None:
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

    def _check_daily_limit(self, teslimat_tarihi: fields.Date) -> None:
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
    
    def write(self, vals: dict) -> bool:
        """Teslimat belgesi güncelleme.

        Tarih/araç/ilçe değişiyorsa kapasite kontrolleri write öncesi çalıştırılır
        (düzenle ile dolu güne kayıt engellenir).
        """
        self._check_iptal_yetkisi(vals)
        self._log_write_debug(vals)

        for record in self:
            record._check_archived_record_edit(vals)
            # Düzenle ile tarih/araç/ilçe değişince kapasite kontrolü (kaydetmeden önce)
            if not record._is_archived():
                record._check_capacity_on_write(vals)

        return super(TeslimatBelgesi, self).write(vals)

    def _is_archived(self) -> bool:
        """Kayıt teslim edilmiş veya iptal ise True."""
        return self.durum in [COMPLETED_STATUS, CANCELLED_STATUS]

    def _check_capacity_on_write(self, vals: dict) -> None:
        """Write öncesi kapasite kontrolleri (yeni değerlerle).

        Tarih/araç/ilçe değişince mutlaka çalışır; dolu güne kayıt engellenir.
        """
        relevant = {"teslimat_tarihi", "arac_id", "ilce_id"}
        if not (relevant & set(vals.keys())):
            return
        # Yeni değerler: vals'tan al, yoksa mevcut kayıttan (düzenle = çoğunlukla sadece tarih değişir)
        new_tarih = vals.get("teslimat_tarihi") or self.teslimat_tarihi
        if not new_tarih:
            return
        new_tarih = fields.Date.to_date(new_tarih)
        # Many2one bazen [id, name] gelir; id kullan
        raw_arac = vals.get("arac_id")
        if raw_arac is not None:
            new_arac_id = raw_arac[0] if isinstance(raw_arac, (list, tuple)) else raw_arac
        else:
            new_arac_id = self.arac_id.id if self.arac_id else None
        raw_ilce = vals.get("ilce_id")
        if raw_ilce is not None:
            new_ilce_id = raw_ilce[0] if isinstance(raw_ilce, (list, tuple)) else raw_ilce
        else:
            new_ilce_id = self.ilce_id.id if self.ilce_id else None
        if not new_arac_id or not new_ilce_id:
            return
        self._validate_arac_kapasitesi(
            teslimat_tarihi=new_tarih, arac_id=new_arac_id, ilce_id=new_ilce_id
        )
        self._validate_ilce_gun_kapasitesi(
            teslimat_tarihi=new_tarih, arac_id=new_arac_id, ilce_id=new_ilce_id
        )

    def _check_iptal_yetkisi(self, vals: dict) -> None:
        """İptal yetkisi kontrolü - yönetici veya transferi oluşturan iptal edebilir.

        Args:
            vals: Write değerleri

        Raises:
            UserError: Yetkisiz iptal denemesi
        """
        if "durum" not in vals or vals["durum"] != CANCELLED_STATUS:
            return
        user = self.env.user
        for record in self:
            if is_manager(record.env) or (
                record.transfer_olusturan_id and record.transfer_olusturan_id == user
            ):
                continue
            raise UserError(
                _(
                    "Teslimat iptal yetkisi yok!\n\n"
                    "Sadece yöneticiler veya bu transferi oluşturan kişi teslimatı iptal edebilir.\n"
                    "Lütfen yöneticinizle veya transferi oluşturan personelle iletişime geçin."
                )
            )

    def _log_write_debug(self, vals: dict) -> None:
        """Write işlemini debug log'la.

        Args:
            vals: Write değerleri
        """
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "WRITE: Records=%s, Keys=%s",
                [r.name for r in self],
                list(vals.keys())
            )

    def _check_archived_record_edit(self, vals: dict) -> None:
        """Arşivlenmiş kayıt düzenleme kontrolü.

        Args:
            vals: Write değerleri

        Raises:
            UserError: Yetkisiz arşivlenmiş kayıt düzenleme
        """
        if self.durum not in [COMPLETED_STATUS, CANCELLED_STATUS]:
            return  # Arşivlenmemiş, kontrol gereksiz

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "WRITE to archived: %s (status=%s)",
                self.name,
                self.durum
            )

        # Wizard'dan gelen alanlar (izin verilen)
        wizard_fields = {
            'durum', 'gercek_teslimat_saati', 'teslim_alan_kisi',
            'teslimat_fotografi', 'fotograf_dosya_adi', 'notlar',
            'message_main_attachment_id'  # mail.thread otomatik alan
        }

        extra_fields = set(vals.keys()) - wizard_fields

        if extra_fields:
            _logger.warning(
                "Archived record edit attempt: %s, extra_fields=%s",
                self.name,
                extra_fields
            )
            raise UserError(
                _(
                    "Teslim edilmiş teslimat belgeleri düzenlenemez!\n\n"
                    f"Belge: {self.name}\n"
                    f"Durum: Teslim Edildi\n"
                    f"Teslim Tarihi: {self.gercek_teslimat_saati or 'N/A'}\n"
                    f"Teslim Alan: {self.teslim_alan_kisi or 'N/A'}\n\n"
                    "Bu belge arşivlenmiştir ve değiştirilemez."
                )
            )
    
    def unlink(self) -> bool:
        """Teslimat belgesi silme - Kısıtlamalar.

        Returns:
            bool: Başarılı ise True
        """
        self._check_unlink_yetkisi()

        for record in self:
            record._check_completed_record_unlink()

        return super(TeslimatBelgesi, self).unlink()

    def _check_unlink_yetkisi(self) -> None:
        """Silme yetkisi kontrolü - sadece yöneticiler silebilir.

        Raises:
            UserError: Yetkisiz silme denemesi
        """
        if not is_manager(self.env):
            raise UserError(
                _(
                    "Teslimat belgelerini sadece yöneticiler silebilir!\n\n"
                    "Yönetici yetkisi gereklidir."
                )
            )

    def _check_completed_record_unlink(self) -> None:
        """Tamamlanmış kayıt silme kontrolü.

        Raises:
            UserError: Tamamlanmış kayıt silme denemesi
        """
        if self.durum == COMPLETED_STATUS:
            raise UserError(
                _(
                    "Teslim edilmiş teslimat belgeleri silinemez!\n\n"
                    f"Belge: {self.name}\n"
                    f"Durum: Teslim Edildi\n"
                    f"Teslim Tarihi: {self.gercek_teslimat_saati or 'N/A'}\n"
                    f"Teslim Alan: {self.teslim_alan_kisi or 'N/A'}\n\n"
                    "Bu belge arşivlenmiştir ve silinemez.\n"
                    "Veri bütünlüğü için teslim edilmiş belgeler korunur."
                )
            )

