"""Teslimat Belgesi - Action ve Onchange Metodları.

Bu modül teslimat belgesi action ve onchange metodlarını içerir.
Mixin pattern kullanılarak ana model'den ayrılmıştır.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .teslimat_constants import (
    CANCELLED_STATUS,
    COMPLETED_STATUS,
    IN_TRANSIT_STATUSES,
    IN_TRANSIT_STATUS,
    READY_STATUS,
    get_arac_kapatma_sebep_label,
)
from .teslimat_utils import is_manager

_logger = logging.getLogger(__name__)


class TeslimatBelgesiActions(models.AbstractModel):
    """Teslimat Belgesi Action ve Onchange Mixin.

    Bu class teslimat belgesi için tüm action ve onchange metodlarını içerir.
    """

    _name = "teslimat.belgesi.actions"
    _description = "Teslimat Belgesi Action Mixin"

    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================

    @api.depends("musteri_id")
    def _compute_musteri_adres(self) -> None:
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

                record.musteri_adres = ", ".join(adres_parcalari)
            else:
                record.musteri_adres = ""

    @api.depends("durum")
    def _compute_is_readonly(self) -> None:
        """Teslim edilmiş belgeler salt okunurdur."""
        for record in self:
            record.is_readonly = record.durum == COMPLETED_STATUS

    # =========================================================================
    # ONCHANGE METHODS
    # =========================================================================

    @api.onchange("transfer_no")
    def _onchange_transfer_no(self) -> None:
        """Transfer no girildiğinde stock.picking kaydını bul ve doldur."""
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

        Not: Onchange içinde veritabanına create/unlink işlemi yapmak işlemi kilitler.
        Bu yüzden sadece Command metodlarını kullanıyoruz.

        Args:
            picking: Stock picking kaydı
        """
        # Mevcut ürünleri temizle (Command.clear)
        self.transfer_urun_ids = [(5, 0, 0)]

        # Transfer belgesi ürünlerini ekle
        if picking and picking.move_ids_without_package:
            lines = []
            for seq, move in enumerate(picking.move_ids_without_package, start=1):
                lines.append(
                    (
                        0,
                        0,
                        {
                            "sequence": seq,
                            "urun_id": move.product_id.id,
                            "miktar": move.quantity_done or move.product_uom_qty,
                            "birim": move.product_uom.id,
                            "stock_move_id": move.id,
                        },
                    )
                )
            self.transfer_urun_ids = [(5, 0, 0)] + lines

    # =========================================================================
    # ACTION METHODS
    # =========================================================================

    def action_yolda_yap(self) -> None:
        """Teslimat durumunu 'yolda' yap.

        Hazır durumundaki teslimatları yola çıkarır.
        """
        self.ensure_one()

        if self.durum != READY_STATUS:
            raise UserError(_("Sadece 'Hazır' durumdaki teslimatlar yola çıkarılabilir."))

        self.durum = IN_TRANSIT_STATUS

        # Chatter'a not ekle
        self.message_post(
            body=_("Sürücü yola çıktı. Teslimat yolda."),
            subject=_("Teslimat Yola Çıktı"),
        )

    def action_teslimat_tamamla(self) -> dict:
        """Teslimat tamamlama wizard'ını aç.

        Returns:
            dict: Wizard açma action'ı
        """
        self.ensure_one()

        if self.durum not in IN_TRANSIT_STATUSES:
            raise UserError(
                _("Sadece 'Hazır' veya 'Yolda' durumdaki teslimatlar tamamlanabilir.")
            )

        return {
            "name": _("Teslimat Tamamla"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.tamamlama.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_teslimat_belgesi_id": self.id},
        }

    def action_yol_tarifi(self) -> dict:
        """Google Maps ile yol tarifi aç.

        Returns:
            dict: URL action'ı
        """
        self.ensure_one()

        if not self.musteri_adres:
            raise UserError(_("Müşteri adresi bulunamadı!"))

        # Google Maps URL
        base_url = "https://www.google.com/maps/dir/?api=1"
        destination = self.musteri_adres.replace(" ", "+")
        url = f"{base_url}&destination={destination}"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_iptal_et(self) -> None:
        """Teslimatı iptal et (Sadece yönetici).

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

        if self.durum == CANCELLED_STATUS:
            raise UserError(_("Teslimat zaten iptal edilmiş."))

        if self.durum == COMPLETED_STATUS:
            raise UserError(_("Teslim edilmiş teslimat iptal edilemez."))

        # Durumu iptal yap
        self.durum = CANCELLED_STATUS

        # Chatter'a not ekle
        self.message_post(
            body=_("Teslimat yönetici tarafından iptal edildi."),
            subject=_("Teslimat İptal Edildi"),
        )

    def send_teslimat_sms(self) -> bool:
        """Müşteriye teslimat SMS'i gönder.

        Returns:
            bool: Başarılı ise True
        """
        self.ensure_one()

        if not self.musteri_telefon:
            raise UserError(_("Müşteri telefon numarası bulunamadı!"))

        try:
            # SMS içeriği
            mesaj = _(
                f"Sayın {self.musteri_id.name},\n\n"
                f"Teslimat No: {self.name}\n"
                f"Tarih: {self.teslimat_tarihi.strftime('%d.%m.%Y')}\n"
                f"Araç: {self.arac_id.name}\n\n"
                f"Teslimatınız yola çıkmıştır."
            )

            # SMS gönderme modülü (varsa)
            # TODO: Gerçek SMS entegrasyonu eklenebilir
            _logger.info("SMS gönderildi: %s - %s", self.musteri_telefon, mesaj)

            # Chatter'a not ekle
            self.message_post(
                body=_(f"SMS gönderildi: {self.musteri_telefon}"),
                subject=_("SMS Gönderildi"),
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
