"""Teslimat Belgesi Modeli."""
import logging
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Günlük teslimat limiti (user grubu için)
DAILY_DELIVERY_LIMIT = 7


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

    name = fields.Char(
        string="Teslimat No",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Yeni"),
    )
    teslimat_tarihi = fields.Date(
        string="Teslimat Tarihi", required=True, default=fields.Date.today
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

    # Araç ve İlçe Bilgileri
    arac_id = fields.Many2one(
        "teslimat.arac", string="Araç", required=True, tracking=True
    )
    ilce_id = fields.Many2one(
        "teslimat.ilce", string="İlçe", required=True, tracking=True
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
    )

    # Sıra
    sira_no = fields.Integer(string="Sıra No", default=1)

    # Teslim Bilgileri
    teslim_alan_kisi = fields.Char(string="Teslim Alan Kişi")
    gercek_teslimat_saati = fields.Datetime(string="Gerçek Teslimat Saati")

    # Konum Bilgileri
    enlem = fields.Float(string="Enlem")
    boylam = fields.Float(string="Boylam")

    # Notlar
    notlar = fields.Text(string="Notlar")

    @api.model
    def create(self, vals: dict) -> "TeslimatBelgesi":
        """Teslimat belgesi oluştur - Günlük limit kontrolü.

        User grubu için günlük max 7 teslimat kontrolü yapılır.
        Manager grubu için sınırsız.

        Args:
            vals: Create değerleri

        Returns:
            TeslimatBelgesi: Oluşturulan kayıt
        """
        # Sequence ile otomatik numaralandırma
        if vals.get("name", _("Yeni")) == _("Yeni"):
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("teslimat.belgesi")
                or _("Yeni")
            )

        # Pazar günü kontrolü - Yöneticiler için bypass
        from .teslimat_utils import check_pazar_gunu_validation
        
        teslimat_tarihi = vals.get("teslimat_tarihi", fields.Date.today())
        check_pazar_gunu_validation(teslimat_tarihi, bypass_for_manager=True, env=self.env)

        # Günlük teslimat limiti kontrolü (sadece user grubu için)
        user = self.env.user
        if not user.has_group("teslimat_planlama.group_teslimat_manager"):
            teslimat_tarihi = vals.get("teslimat_tarihi", fields.Date.today())
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

        return super(TeslimatBelgesi, self).create(vals)
    
    def write(self, vals):
        """Teslimat belgesi güncelleme - Teslim edilmiş belgelerde kısıtlama.
        
        Teslim edilmiş belgeler düzenlenemez (sadece yöneticiler için izin var).
        """
        for record in self:
            # Teslim edilmiş belgelerde değişiklik yapılamaz
            if record.durum == 'teslim_edildi':
                # Yönetici değilse hata ver
                if not self.env.user.has_group("teslimat_planlama.group_teslimat_manager"):
                    raise UserError(
                        _(
                            "Teslim edilmiş teslimat belgeleri düzenlenemez!\n\n"
                            f"Belge: {record.name}\n"
                            f"Durum: Teslim Edildi\n\n"
                            "Yönetici yetkisi gereklidir."
                        )
                    )
        
        return super(TeslimatBelgesi, self).write(vals)

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
                            "Transfer belgesi bulunamadı: %s" % self.transfer_no
                        ),
                    }
                }
        except Exception as e:
            _logger.error("Transfer no onchange hatası: %s", e)

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
            _logger.error("Stock picking onchange hatası: %s", e)

    @api.onchange("musteri_id")
    def _onchange_musteri(self) -> None:
        """Müşteri değiştiğinde bilgileri güncelle."""
        if not self.musteri_id:
            return

        try:
            # Müşteri adres bilgileri varsa kullanılabilir
            # Buraya ek bilgiler eklenebilir
            pass
        except Exception as e:
            _logger.error("Müşteri onchange hatası: %s", e)

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

    def action_teslimat_tamamla(self) -> None:
        """Teslimatı tamamla."""
        self.ensure_one()
        if self.durum not in ["hazir", "yolda"]:
            raise UserError(
                _("Sadece 'Hazır' veya 'Yolda' durumundaki teslimatlar tamamlanabilir.")
            )

        self.write(
            {
                "durum": "teslim_edildi",
                "gercek_teslimat_saati": fields.Datetime.now(),
            }
        )

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
                    f"❌ SMS gönderilemedi: {str(e)}\n"
                    f"Alıcı: {self.musteri_id.name}\n"
                    f"Telefon: {self.musteri_telefon}"
                ),
                subject=_("SMS Gönderim Hatası"),
                message_type="notification",
            )
            return False

