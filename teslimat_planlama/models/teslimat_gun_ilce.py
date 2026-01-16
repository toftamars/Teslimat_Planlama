"""Teslimat Gün-İlçe Eşleştirme Modeli."""
import logging
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TeslimatGunIlce(models.Model):
    """Teslimat Gün-İlçe Eşleşmesi.

    Dinamik yönetim: Yöneticiler modül içinden ilçe-gün eşleştirmelerini
    yönetebilir. Bu model üzerinden CRUD işlemleri yapılır.
    """

    _name = "teslimat.gun.ilce"
    _description = "Teslimat Gün-İlçe Eşleşmesi"
    _order = "gun_id, ilce_id, tarih"
    _unique = ("gun_id", "ilce_id", "tarih")

    gun_id = fields.Many2one("teslimat.gun", string="Gün", required=True, ondelete="cascade")
    ilce_id = fields.Many2one("teslimat.ilce", string="İlçe", required=True, ondelete="cascade")
    tarih = fields.Date(
        string="Tarih", 
        required=False,  # Opsiyonel: False ise genel kural (her hafta geçerli)
        help="Boş bırakılırsa her hafta geçerli genel kural. "
             "Tarih girilirse sadece o tarihe özel kural."
    )

    # Kapasite Bilgileri (Dinamik - Modülden ayarlanabilir)
    maksimum_teslimat = fields.Integer(string="Maksimum Teslimat", default=10)
    teslimat_sayisi = fields.Integer(string="Teslimat Sayısı", default=0)
    kalan_kapasite = fields.Integer(
        string="Kalan Kapasite", compute="_compute_kalan_kapasite", store=True
    )

    # Özel Durumlar
    ozel_durum = fields.Selection(
        [
            ("normal", "Normal"),
            ("yogun", "Yoğun"),
            ("kapali", "Kapalı"),
            ("ozel", "Özel"),
        ],
        string="Özel Durum",
        default="normal",
    )

    notlar = fields.Text(string="Notlar")

    @api.depends("maksimum_teslimat", "teslimat_sayisi")
    def _compute_kalan_kapasite(self) -> None:
        """Kalan kapasiteyi hesapla."""
        for record in self:
            record.kalan_kapasite = record.maksimum_teslimat - record.teslimat_sayisi

    @api.constrains("teslimat_sayisi", "maksimum_teslimat")
    def _check_teslimat_kapasitesi(self) -> None:
        """Teslimat sayısı maksimum kapasiteyi aşamaz."""
        for record in self:
            if record.teslimat_sayisi > record.maksimum_teslimat:
                raise ValidationError(
                    _("Teslimat sayısı maksimum kapasiteyi aşamaz.")
                )

    @api.constrains("gun_id", "ilce_id", "tarih")
    def _check_unique_eslesme(self) -> None:
        """Aynı gün, ilçe ve tarih için tek kayıt olmalı.
        
        - Tarih boş ise: Genel kural (her hafta geçerli)
        - Tarih dolu ise: Özel kural (sadece o tarih için)
        """
        for record in self:
            domain = [
                    ("gun_id", "=", record.gun_id.id),
                    ("ilce_id", "=", record.ilce_id.id),
                    ("id", "!=", record.id),
            ]
            
            # Tarih kontrolü
            if record.tarih:
                domain.append(("tarih", "=", record.tarih))
            else:
                domain.append(("tarih", "=", False))
            
            existing = self.search(domain, limit=1)
            
            if existing:
                if record.tarih:
                    raise ValidationError(
                        _(
                            f"Bu gün ({record.gun_id.name}), ilçe ({record.ilce_id.name}) "
                            f"ve tarih ({record.tarih}) için zaten bir eşleştirme mevcut."
                        )
                    )
                else:
                raise ValidationError(
                    _(
                            f"Bu gün ({record.gun_id.name}) ve ilçe ({record.ilce_id.name}) "
                            f"için zaten genel bir kural mevcut."
                    )
                )

