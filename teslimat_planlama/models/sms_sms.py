# -*- coding: utf-8 -*-
"""sms.sms genişletmesi — teslimat_planlama.sms_disabled parametresine uyum."""

import logging

from odoo import fields, models

from .sms_helper import PARAM_SMS_DISABLED, is_sms_disabled

_logger = logging.getLogger(__name__)

# Tüm teslimat SMS metinlerinde ortak imza
_TESLIMAT_SMS_MARKER = "Teslimat No:"


class SmsSms(models.Model):
    _inherit = "sms.sms"

    teslimat_planlama_sms = fields.Boolean(
        string="Teslimat Planlama SMS",
        default=False,
        index=True,
        help="Teslimat Planlama modülünden oluşturulan SMS kaydı.",
    )

    def _teslimat_planlama_records(self):
        """Teslimat modülünden gelen SMS kayıtlarını ayır."""
        return self.filtered(
            lambda sms: sms.teslimat_planlama_sms
            or (sms.body and _TESLIMAT_SMS_MARKER in sms.body)
        )

    def send(
        self,
        unlink_failed=False,
        unlink_sent=True,
        auto_commit=False,
        raise_exception=False,
    ):
        if is_sms_disabled(self.env):
            blocked = self._teslimat_planlama_records().filtered(
                lambda sms: sms.state == "outgoing"
            )
            if blocked:
                blocked.action_set_canceled()
                _logger.info(
                    "Teslimat SMS iptal (%s etkin) — %s kayıt",
                    PARAM_SMS_DISABLED,
                    len(blocked),
                )
            self = self - blocked
            if not self:
                return True
        return super().send(
            unlink_failed=unlink_failed,
            unlink_sent=unlink_sent,
            auto_commit=auto_commit,
            raise_exception=raise_exception,
        )
