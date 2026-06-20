"""Teslimat Belgesi - Action ve Onchange Metodları.

Bu modül teslimat belgesi action ve onchange metodlarını içerir.
Mixin pattern kullanılarak ana model'den ayrılmıştır.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .teslimat_constants import (
    CANCELLED_STATUS,
    COMPLETED_STATUS,
    IN_TRANSIT_STATUSES,
    IN_TRANSIT_STATUS,
    READY_STATUS,
)
from .teslimat_utils import (
    build_google_maps_directions_url,
    is_manager,
    prepare_maps_destination,
)
from .teslimat_route_service import (
    is_route_api_configured,
    sort_deliveries_by_traffic,
)
from . import sms_helper

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

    def _compute_can_user_cancel(self) -> None:
        """İptal butonunu göstermek için: yönetici veya transferi oluşturan kişi."""
        user = self.env.user
        manager = is_manager(self.env)
        for record in self:
            record.can_user_cancel = manager or (
                record.transfer_olusturan_id and record.transfer_olusturan_id == user
            )

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
                            "Transfer belgesi bulunamadı: %(transfer_no)s"
                        ) % {"transfer_no": self.transfer_no},
                    }
                }
        except Exception as e:
            _logger.exception("Transfer no onchange hatası:")
            return {
                "warning": {
                    "title": _("Hata"),
                    "message": _(
                        "Transfer bilgileri alınırken hata oluştu: %(hata)s"
                    ) % {"hata": str(e)},
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
                        "Transfer belgesi bilgileri alınırken hata oluştu: %(hata)s"
                    ) % {"hata": str(e)},
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

    def _update_transfer_urunleri(self, picking) -> None:
        """Transfer belgesindeki ürünleri ORM Command tuple'larıyla güncelle.

        İki yoldan çağrılır:
          1. _onchange_stock_picking (NewId / bellek-içi): Command kullanımı
             onchange içinde DB create/unlink kilidini önler.
          2. Wizard create sonrası gerçek kayıt (teslimat_belgesi_wizard.py):
             aynı Command'lar burada write'a çevrilir.
        Her iki bağlamda da (5,0,0) clear + (0,0,vals) add doğru çalışır.

        Args:
            picking: Stock picking kaydı
        """
        # Tek atama: önce temizle (5,0,0), transfer satırları varsa ekle.
        commands = [(5, 0, 0)]
        if picking and picking.move_ids_without_package:
            for seq, move in enumerate(picking.move_ids_without_package, start=1):
                commands.append(
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
        self.transfer_urun_ids = commands

    # =========================================================================
    # ACTION METHODS
    # =========================================================================

    def action_yolda_yap(self) -> None:
        """Teslimat durumunu 'yolda' yap ve müşteriye yolda SMS'i gönder."""
        self.ensure_one()

        if self.durum != READY_STATUS:
            raise UserError(_("Sadece 'Hazır' durumdaki teslimatlar yola çıkarılabilir."))

        self.durum = IN_TRANSIT_STATUS

        # Chatter'a not ekle
        self.message_post(
            body=_("Sürücü yola çıktı. Teslimat yolda."),
            subject=_("Teslimat Yola Çıktı"),
        )

        # Müşteriye 1. SMS: Yolda bilgisi
        self.send_sms_yolda()

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

        destination = prepare_maps_destination(self.musteri_id)
        if not destination:
            raise UserError(_("Müşteri adresi bulunamadı!"))

        return {
            "type": "ir.actions.act_url",
            "url": build_google_maps_directions_url(destination),
            "target": "new",
        }

    def action_trafik_sirasina_gore_sirala(self) -> dict:
        """Seçili teslimatları Google Routes API ile trafik süresine göre sırala."""
        if not self:
            raise UserError(_("Lütfen en az bir teslimat seçin."))

        count, minutes = sort_deliveries_by_traffic(self)
        message = _("%(count)s teslimat trafik sırasına göre sıralandı.") % {
            "count": count,
        }
        if minutes:
            message += " " + _("Tahmini rota süresi: ~%(min)s dk.") % {"min": minutes}

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Rota sıralandı"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def action_rota_optimizasyonu(self) -> dict:
        """Seçili teslimatların adreslerini Google Maps çoklu durak ile aç.

        Liste görünümünde birden fazla teslimat seçildiğinde Aksiyon menüsünden
        çağrılır. Adresi olan teslimatlar sırayla waypoints olarak Google Maps'e
        gönderilir.

        Returns:
            dict: ir.actions.act_url ile yeni sekmede harita açar

        Raises:
            UserError: Hiç kayıt seçilmediyse veya hiçbirinde adres yoksa
        """
        if not self:
            raise UserError(_("Lütfen en az bir teslimat seçin."))

        records = self
        arac_ids = records.mapped("arac_id")
        tarihler = records.mapped("teslimat_tarihi")
        if (
            is_route_api_configured(self.env)
            and len(arac_ids) == 1
            and len(tarihler) == 1
            and len(records) >= 2
        ):
            try:
                sort_deliveries_by_traffic(records)
            except UserError as exc:
                _logger.warning("Rota öncesi trafik sıralaması atlandı: %s", exc.args[0])

        records = records.sorted(key=lambda r: (r.sira_no, r.id))

        # Adresi olan kayıtları filtrele (Maps için optimize edilmiş hedef)
        adresli = []
        for rec in records:
            if not rec.musteri_id:
                continue
            adres = prepare_maps_destination(rec.musteri_id)
            if adres:
                adresli.append((rec, adres))

        if not adresli:
            raise UserError(
                _(
                    "Seçili teslimatların hiçbirinde müşteri adresi bulunamadı.\n\n"
                    "Müşteri kaydında adres (sokak, ilçe, il) tanımlı olmalıdır."
                )
            )

        # Google Maps: max 9 waypoints + origin + destination = 11 durak
        if len(adresli) > 11:
            adresli = adresli[:11]
            _logger.warning(
                "Rota optimizasyonu: 11'den fazla adres seçildi, ilk 11 kullanıldı"
            )

        adresler = [a for _, a in adresli]

        if len(adresler) == 1:
            url = build_google_maps_directions_url(adresler[0])
        else:
            origin = adresler[0]
            destination = adresler[-1]
            waypoints = "|".join(adresler[1:-1]) if len(adresler) > 2 else None
            url = build_google_maps_directions_url(
                destination,
                origin=origin,
                waypoints=waypoints,
            )

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_iptal_et(self) -> None:
        """Teslimatı iptal et (Yönetici veya transferi oluşturan).

        Yönetici veya 'Transferi oluşturan' kişi bu butona basarak teslimatı iptal edebilir.
        Durum 'iptal' olur ve chatter'a not eklenir.
        """
        self.ensure_one()

        # Yetki: yönetici veya bu transferi oluşturan kişi
        user = self.env.user
        if not (is_manager(self.env) or (self.transfer_olusturan_id and self.transfer_olusturan_id == user)):
            raise UserError(
                _(
                    "Teslimat iptal yetkisi yok!\n\n"
                    "Sadece yöneticiler veya bu transferi oluşturan kişi teslimatı iptal edebilir.\n"
                    "Lütfen yöneticinizle veya transferi oluşturan personelle iletişime geçin."
                )
            )

        if self.durum == CANCELLED_STATUS:
            raise UserError(_("Teslimat zaten iptal edilmiş."))

        if self.durum == COMPLETED_STATUS:
            raise UserError(_("Teslim edilmiş teslimat iptal edilemez."))

        # Durumu iptal yap
        self.durum = CANCELLED_STATUS

        # Chatter'a not ekle
        who = _("yönetici") if is_manager(self.env) else _("transferi oluşturan kişi")
        self.message_post(
            body=_("Teslimat %s tarafından iptal edildi.") % who,
            subject=_("Teslimat İptal Edildi"),
        )

    def _get_sms_telefon(self) -> str:
        """SMS için kullanılacak telefon numarası (manuel veya müşteri)."""
        self.ensure_one()
        return (self.manuel_telefon or self.musteri_telefon or "").strip() or (
            self.musteri_id.mobile or self.musteri_id.phone or ""
        ).strip()

    def _send_sms_mesaj(self, mesaj: str, konu: str = None) -> bool:
        """Müşteriye SMS metnini gönder (Odoo sms.sms ile), chatter'a not düş."""
        self.ensure_one()
        telefon = self._get_sms_telefon()
        if not telefon:
            _logger.warning("SMS atlanıyor: telefon yok (teslimat %s)", self.name)
            return False
        if not self.musteri_id:
            _logger.warning("SMS atlanıyor: müşteri yok (teslimat %s)", self.name)
            return False
        # Odoo sms modülü ile gönder (Arıza Onarım ile aynı sistem)
        sms_sent = sms_helper.SMSHelper.send_sms(
            self.sudo().env,
            self.musteri_id,
            mesaj,
            record_name=self.name,
            phone_override=telefon,
        )
        # PII: chatter kalıcı/değişmez kayıt → telefonu maskele (son 4 hane).
        # Tam numara form alanlarında (musteri_telefon/manuel_telefon) durur.
        maskeli_telefon = sms_helper.SMSHelper._mask_phone(telefon)
        telefon_kaynak = _("manuel") if self.manuel_telefon else _("müşteri")
        if sms_sent:
            self.message_post(
                body=_("SMS gönderildi: %(telefon)s (%(kaynak)s)\n\n%(mesaj)s") % {
                    "telefon": maskeli_telefon,
                    "kaynak": telefon_kaynak,
                    "mesaj": mesaj,
                },
                subject=konu or _("SMS Gönderildi"),
                message_type="notification",
            )
        else:
            self.message_post(
                body=_(
                    "SMS gönderilemedi (servis hatası). "
                    "Alıcı: %(alici)s, Telefon: %(telefon)s (%(kaynak)s)"
                ) % {
                    "alici": self.musteri_id.name or "-",
                    "telefon": maskeli_telefon,
                    "kaynak": telefon_kaynak,
                },
                subject=_("SMS Gönderim Hatası"),
                message_type="notification",
            )
        return sms_sent

    def send_sms_yolda(self) -> bool:
        """Müşteriye 'yolda' SMS'i gönder (1. SMS).

        Ekiplerimiz ürün teslimatı ve kurulum için adresinize doğru yola çıkmıştır.
        """
        self.ensure_one()
        telefon = self._get_sms_telefon()
        if not telefon:
            raise UserError(_("Müşteri telefon numarası bulunamadı! SMS gönderilemedi."))
        mesaj = _(
            "Sayın %(musteri)s, ekiplerimiz ürün teslimatı ve kurulum için "
            "adresinize doğru yola çıkmıştır. Teslimat No: %(no)s"
        ) % {"musteri": self.musteri_id.name or "Müşteri", "no": self.name}
        return self._send_sms_mesaj(mesaj, konu=_("SMS (Yolda) Gönderildi"))

    def send_sms_tamamlandi(self) -> bool:
        """Müşteriye 'teslimat tamamlandı' SMS'i gönder (2. SMS)."""
        self.ensure_one()
        telefon = self._get_sms_telefon()
        if not telefon:
            _logger.warning("Tamamlandı SMS atlanıyor: telefon yok (teslimat %s)", self.name)
            return False
        mesaj = _(
            "Sayın %(musteri)s, ürün teslimatınız ve kurulumunuz tamamlanmıştır. "
            "Bizi tercih ettiğiniz için teşekkür ederiz. Teslimat No: %(no)s"
        ) % {"musteri": self.musteri_id.name or "Müşteri", "no": self.name}
        return self._send_sms_mesaj(mesaj, konu=_("SMS (Tamamlandı) Gönderildi"))

    def send_teslimat_sms(self) -> bool:
        """Müşteriye teslimat oluşturulduğunda SMS'i gönder (wizard sonrası)."""
        self.ensure_one()
        telefon = self._get_sms_telefon()
        if not telefon:
            raise UserError(_("Müşteri telefon numarası bulunamadı!"))

        mesaj = _(
            "Sayın %(musteri)s, Teslimat No: %(no)s, Tarih: %(tarih)s, "
            "Araç: %(arac)s. Teslimatınız planlanmıştır."
        ) % {
            "musteri": self.musteri_id.name or "Müşteri",
            "no": self.name,
            "tarih": self.teslimat_tarihi.strftime("%d.%m.%Y"),
            "arac": self.arac_id.name or "-",
        }
        return self._send_sms_mesaj(mesaj, konu=_("SMS Gönderildi"))
