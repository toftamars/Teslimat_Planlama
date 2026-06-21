# -*- coding: utf-8 -*-
"""
SMS Helper - SMS işlemleri için helper (Arıza Onarım ile aynı sistem).

Odoo sms modülü (sms.sms) kullanır; sorunsuz çalışır.
"""

import logging

_logger = logging.getLogger(__name__)

PARAM_SMS_DISABLED = "teslimat_planlama.sms_disabled"
_TRUTHY_VALUES = frozenset({"true", "1", "yes"})


def _parse_config_flag(value):
    """Sistem parametresi değerini boolean bayrağa çevir."""
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY_VALUES


def is_sms_disabled(env):
    """SMS geçici kapalı mı?

    ir.config_parameter.get_param ormcache kullanır; çoklu worker ortamında
    eski değer kalabiliyor. Bu yüzden doğrudan SQL ile okunur.
    """
    env.cr.execute(
        "SELECT value FROM ir_config_parameter WHERE key = %s",
        [PARAM_SMS_DISABLED],
    )
    row = env.cr.fetchone()
    if not row:
        return False
    return _parse_config_flag(row[0])


class SMSHelper:
    """SMS işlemleri için helper metodlar."""

    @staticmethod
    def _mask_phone(phone):
        """Loglarda PII sızıntısını önlemek için telefonu maskele (son 4 hane görünür)."""
        if not phone:
            return "-"
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) <= 4:
            return "***"
        return "***" + digits[-4:]

    @staticmethod
    def send_sms(env, partner, message, record_name="", phone_override=None):
        """
        SMS gönderir (Odoo sms.sms ile).

        Args:
            env: Odoo environment
            partner: res.partner record (telefon için; phone_override yoksa mobile/phone kullanılır)
            message: SMS mesajı
            record_name: Kayıt adı (log için)
            phone_override: Opsiyonel; verilirse bu numara kullanılır (örn. manuel_telefon)

        Returns:
            bool: Gönderildiyse True; devre dışı / hata / telefon yoksa False
        """
        if is_sms_disabled(env):
            _logger.info(
                "SMS devre dışı (%s=True) - Kayıt: %s",
                PARAM_SMS_DISABLED,
                record_name,
            )
            return False

        phone_number = phone_override
        if not phone_number and partner:
            phone_number = (partner.mobile or partner.phone or "").strip() or None
        if not phone_number:
            _logger.warning(
                "SMS gönderilemedi: Partner veya telefon yok - Kayıt: %s",
                record_name,
            )
            return False

        # Gevşek sağlık kontrolü: bariz geçersiz numarayı (digit < 7) atla.
        # Format dayatma yok — gerçek numaraları (uluslararası/+90/sabit hat) elemez.
        if len([ch for ch in phone_number if ch.isdigit()]) < 7:
            _logger.warning(
                "SMS gönderilemedi: geçersiz telefon (%s) - Kayıt: %s",
                SMSHelper._mask_phone(phone_number),
                record_name,
            )
            return False

        try:
            sms = env["sms.sms"].sudo().create(
                {
                    "number": phone_number,
                    "body": message,
                    "partner_id": partner.id if partner else False,
                }
            )
            sms.sudo().send()
            _logger.info(
                "SMS gönderildi: %s - %s",
                record_name,
                SMSHelper._mask_phone(phone_number),
            )
            return True
        except Exception:
            # Best-effort SMS: hata teslimatı bloklamaz. Traceback ile logla.
            _logger.exception("SMS hatası - Kayıt: %s", record_name)
            return False
