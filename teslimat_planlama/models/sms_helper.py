# -*- coding: utf-8 -*-
"""
SMS Helper - SMS işlemleri için helper (Arıza Onarım ile aynı sistem).

Odoo sms modülü (sms.sms) kullanır; sorunsuz çalışır.
"""

import logging

_logger = logging.getLogger(__name__)


class SMSHelper:
    """SMS işlemleri için helper metodlar."""

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
            bool: Başarılı ise True, değilse False
        """
        phone_number = phone_override
        if not phone_number and partner:
            phone_number = (partner.mobile or partner.phone or "").strip() or None
        if not phone_number:
            _logger.warning(
                "SMS gönderilemedi: Partner veya telefon yok - Kayıt: %s",
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
            _logger.info("SMS gönderildi: %s - %s", record_name, phone_number)
            return True
        except Exception as e:
            _logger.error("SMS hatası: %s - %s", record_name, str(e))
            return False
