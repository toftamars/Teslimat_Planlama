"""Teslimat Gün-İlçe Eşleştirme Modeli."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .teslimat_constants import DAILY_DELIVERY_LIMIT

_logger = logging.getLogger(__name__)


class TeslimatGunIlce(models.Model):
    """Teslimat Gün-İlçe Eşleşmesi.

    Dinamik yönetim: Yöneticiler modül içinden ilçe-gün eşleştirmelerini
    yönetebilir. Bu model üzerinden CRUD işlemleri yapılır.
    """

    _name = "teslimat.gun.ilce"
    _description = "Teslimat Gün-İlçe Eşleşmesi"
    _order = "gun_id, ilce_id, tarih"

    gun_id = fields.Many2one("teslimat.gun", string="Gün", required=True, ondelete="cascade")
    ilce_id = fields.Many2one("teslimat.ilce", string="İlçe", required=True, ondelete="cascade")
    tarih = fields.Date(
        string="Tarih", 
        required=False,  # Opsiyonel: False ise genel kural (her hafta geçerli)
        help="Boş bırakılırsa her hafta geçerli genel kural. "
             "Tarih girilirse sadece o tarihe özel kural."
    )

    # Kapasite Bilgisi (Dinamik - Modülden ayarlanabilir)
    # Not: Gerçek kullanılan/kalan kapasite teslimat.belgesi sayımından gelir
    # (validators RULE B + Ana Sayfa). Burada yalnızca tavan (maksimum) tutulur.
    maksimum_teslimat = fields.Integer(string="Maksimum Teslimat", default=DAILY_DELIVERY_LIMIT)

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

    @api.model
    def hesapla_maksimum(self, gun_ilce, gun_kodu, ilce_adi, default_limit=DAILY_DELIVERY_LIMIT):
        """İlçe-gün için maksimum teslimat kapasitesini çöz — TEK KAYNAK.

        Hem Ana Sayfa gösterimi hem de teslimat belgesi validasyonu bu metodu
        kullanır; kapasite kuralı tek yerde tanımlı olur (kopya/drift önlenir).

        Öncelik sırası:
        1) Genel kural kaydı (gun_ilce) varsa  -> kaydın maksimum_teslimat'ı
        2) Yoksa haftalık programda ilçe eşleşiyorsa -> default_limit
        3) Hiçbiri -> 0 (o gün o ilçe programda yok)

        İlçe eşleştirmesi locale-bağımsız normalize_turkce ile yapılır
        (İ/ı tutarlılığı; gösterim ve validasyon aynı kuralı kullanır).
        """
        if gun_ilce:
            return gun_ilce.maksimum_teslimat

        from ..data.turkey_data import HAFTALIK_PROGRAM_SCHEDULE
        from .teslimat_utils import normalize_turkce

        ilce_adi_norm = normalize_turkce(ilce_adi or "")
        for program_ilce in HAFTALIK_PROGRAM_SCHEDULE.get(gun_kodu, []):
            prog_norm = normalize_turkce(program_ilce)
            if prog_norm in ilce_adi_norm or ilce_adi_norm in prog_norm:
                return default_limit
        return 0

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

    def init(self):
        """DB seviyesinde benzersizlik için partial unique index'ler.

        Python @api.constrains kullanıcı-dostu hata verir; aşağıdaki index'ler
        ise eşzamanlı yazım / veri import / shell gibi ORM-bypass senaryolarını
        da kapatarak çift kaydı DB seviyesinde engeller.

        Güvenli (savunmacı) kurulum: Eğer veritabanında ZATEN çift kayıt varsa
        index OLUŞTURULMAZ, yalnızca uyarı loglanır. Böylece modül upgrade'i
        hiçbir koşulda bozulmaz; sistem mevcut davranışıyla çalışmaya devam eder.

        Kural:
        - tarih BOŞ  (genel kural)  -> (gun_id, ilce_id) benzersiz
        - tarih DOLU (özel kural)   -> (gun_id, ilce_id, tarih) benzersiz
        """
        super().init()

        # 1) Mevcut çiftleri tespit et — varsa index kurma (upgrade'i bozma)
        self._cr.execute("""
            SELECT 1 FROM teslimat_gun_ilce
            WHERE tarih IS NULL
            GROUP BY gun_id, ilce_id HAVING COUNT(*) > 1
            LIMIT 1
        """)
        genel_cift = self._cr.fetchone()

        self._cr.execute("""
            SELECT 1 FROM teslimat_gun_ilce
            WHERE tarih IS NOT NULL
            GROUP BY gun_id, ilce_id, tarih HAVING COUNT(*) > 1
            LIMIT 1
        """)
        tarihli_cift = self._cr.fetchone()

        if genel_cift or tarihli_cift:
            _logger.warning(
                "teslimat.gun.ilce: Cift kayit mevcut -> benzersizlik index'leri "
                "OLUSTURULMADI. Lutfen ciftleri temizleyip modulu tekrar guncelleyin. "
                "Kontrol SQL: SELECT gun_id, ilce_id, tarih, COUNT(*) "
                "FROM teslimat_gun_ilce GROUP BY gun_id, ilce_id, tarih "
                "HAVING COUNT(*) > 1"
            )
            return

        # 2) Cift yok -> partial unique index'leri olustur (idempotent)
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS teslimat_gun_ilce_genel_unique
            ON teslimat_gun_ilce (gun_id, ilce_id)
            WHERE tarih IS NULL
        """)
        self._cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS teslimat_gun_ilce_tarihli_unique
            ON teslimat_gun_ilce (gun_id, ilce_id, tarih)
            WHERE tarih IS NOT NULL
        """)

