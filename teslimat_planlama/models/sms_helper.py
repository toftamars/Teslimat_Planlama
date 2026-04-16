# -*- coding: utf-8 -*-
"""
SMS Helper - SMS işlemleri için helper.

Odoo 19: sms.api (IAP tabanlı) kullanır.
Geriye dönük uyumluluk için sms.sms modeli de denenir.
"""

import logging

_logger = logging.getLogger(__name__)


class SMSHelper:
    """SMS işlemleri için helper metodlar."""

    @staticmethod
    def send_sms(env, partner, message, record_name="", phone_override=None):
        """
        SMS gönderir (Odoo 19: sms.api veya sms.sms ile).

        Odoo 19'da SMS gönderimi IAP (In-App Purchase) servisi üzerinden yapılır.
        sms.api modeli öncelikli denenir; yoksa sms.sms modeli kullanılır.

        Args:
            env: Odoo environment
            partner: res.partner kaydı (telefon için; phone_override yoksa mobile/phone kullanılır)
            message: SMS metni
            record_name: Kayıt adı (log için)
            phone_override: Opsiyonel; verilirse bu numara kullanılır (örn. manuel_telefon)

        Returns:
            bool: Başarılı ise True, değilse False
        """
        # Sistem parametresi ile SMS devre dışı bırakılabilir
        try:
            param = env["ir.config_parameter"].sudo().get_param(
                "teslimat_planlama.sms_disabled"
            ) or ""
            if param.lower() in ("true", "1", "yes"):
                _logger.info(
                    "SMS devre dışı (teslimat_planlama.sms_disabled) - Kayıt: %s",
                    record_name,
                )
                return True
        except Exception:
            pass

        phone_number = phone_override
        if not phone_number and partner:
            phone_number = (partner.mobile or partner.phone or "").strip() or None
        if not phone_number:
            _logger.warning(
                "SMS gönderilemedi: Partner veya telefon yok - Kayıt: %s",
                record_name,
            )
            return False

        # Odoo 19: sms.api modeli (IAP) öncelikli
        try:
            if "sms.api" in env:
                env["sms.api"].sudo()._send_sms([phone_number], message)
                _logger.info("SMS gönderildi (sms.api): %s - %s", record_name, phone_number)
                return True
        except Exception as e:
            _logger.debug("sms.api denemesi başarısız: %s", str(e))

        # Geri dönüş: sms.sms modeli (Odoo 14–19 arası çalışır)
        try:
            sms = env["sms.sms"].sudo().create(
                {
                    "number": phone_number,
                    "body": message,
                    "partner_id": partner.id if partner else False,
                }
            )
            sms.sudo().send()
            _logger.info("SMS gönderildi (sms.sms): %s - %s", record_name, phone_number)
            return True
        except Exception as e:
            _logger.error("SMS hatası: %s - %s", record_name, str(e))
            return False
