"""Teslimat Araç Yönetimi Modeli."""
import logging
from typing import List, Optional

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .teslimat_utils import is_small_vehicle

_logger = logging.getLogger(__name__)


class TeslimatArac(models.Model):
    """Teslimat Araç Yönetimi.

    Araçlar, kapasiteleri ve durumlarını yönetir.
    Varsayılan günlük teslimat limiti: 7 (user grubu için)
    Yöneticiler bu limiti değiştirebilir.
    """

    _name = "teslimat.arac"
    _description = "Teslimat Araç Yönetimi"
    _order = "name"

    name = fields.Char(string="Araç Adı", required=True)
    arac_tipi = fields.Selection(
        [
            ("anadolu_yakasi", "Anadolu Yakası"),
            ("avrupa_yakasi", "Avrupa Yakası"),
            ("kucuk_arac_1", "Küçük Araç 1"),
            ("kucuk_arac_2", "Küçük Araç 2"),
            ("ek_arac", "Ek Araç"),
        ],
        string="Araç Tipi",
        required=True,
    )

    # Kapasite Bilgileri (Dinamik - Modülden ayarlanabilir)
    # Varsayılan: 7 teslimat/gün (user grubu için)
    gunluk_teslimat_limiti = fields.Integer(
        string="Günlük Teslimat Limiti", default=7
    )
    mevcut_kapasite = fields.Integer(
        string="Mevcut Kapasite",
        compute="_compute_mevcut_kapasite",
        store=True,
    )
    kalan_kapasite = fields.Integer(
        string="Kalan Kapasite",
        compute="_compute_kalan_kapasite",
        store=True,
    )

    # Durum Bilgileri
    aktif = fields.Boolean(string="Aktif", default=True)
    active = fields.Boolean(
        string="Aktif",
        related="aktif",
        store=True,
        readonly=False,
        help="Arşivlenen araçlar listede gizlenir. Arşivden çıkararak tekrar kullanılabilir.",
    )
    gecici_kapatma = fields.Boolean(string="Geçici Kapatma")
    kapatma_sebebi = fields.Text(string="Kapatma Sebebi")
    kapatma_baslangic = fields.Datetime(string="Kapatma Başlangıç")
    kapatma_bitis = fields.Datetime(string="Kapatma Bitiş")

    # İlçe Uyumluluğu
    uygun_ilceler = fields.Many2many("teslimat.ilce", string="Uygun İlçeler")

    # Teslimat Geçmişi
    teslimat_ids = fields.One2many(
        "teslimat.belgesi", "arac_id", string="Teslimatlar"
    )

    # Transfer Geçmişi
    transfer_ids = fields.One2many(
        "teslimat.transfer", "arac_id", string="Transferler"
    )

    @api.depends("teslimat_ids", "teslimat_ids.durum", "teslimat_ids.teslimat_tarihi")
    def _compute_mevcut_kapasite(self) -> None:
        """Bugün için mevcut kapasiteyi hesapla.

        İptal hariç TÜM durumlar kapasite doldurur (teslim_edildi dahil).
        """
        for record in self:
            bugun = fields.Date.today()
            bugun_teslimatlar = record.teslimat_ids.filtered(
                lambda t: t.teslimat_tarihi == bugun
                and t.durum != "iptal"  # Sadece iptal hariç
            )
            record.mevcut_kapasite = len(bugun_teslimatlar)

    @api.depends("gunluk_teslimat_limiti", "mevcut_kapasite")
    def _compute_kalan_kapasite(self) -> None:
        """Kalan kapasiteyi hesapla."""
        for record in self:
            record.kalan_kapasite = (
                record.gunluk_teslimat_limiti - record.mevcut_kapasite
            )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Araç adı benzersiz olmalıdır!'),
    ]

    @api.constrains("gunluk_teslimat_limiti")
    def _check_gunluk_limit(self) -> None:
        """Günlük teslimat limiti 0'dan büyük olmalıdır."""
        for record in self:
            if record.gunluk_teslimat_limiti <= 0:
                raise ValidationError(
                    _("Günlük teslimat limiti 0'dan büyük olmalıdır.")
                )

    @api.constrains("arac_tipi", "uygun_ilceler")
    def _check_uygun_ilceler_dolu(self) -> None:
        """Araç tipine göre uygun ilçeler ZORUNLU olarak dolu olmalı.
        
        Bu constraint kod seviyesinde garanti eder ki:
        - Her araç mutlaka ilçe eşleştirmesine sahip olsun
        - Yanlış eşleştirme yapılmasın
        
        NOT: Data yükleme sırasında (module install/upgrade) bu kontrol atlanır.
        Çünkü data dosyasında write() çağrısı yapılırken henüz ilçeler yüklenmemiş olabilir.
        """
        # Data yükleme modunda ise constraint'i atla
        if self.env.context.get('install_mode') or self.env.context.get('module'):
            return
            
        for record in self:
            if not record.arac_tipi:
                continue
                
            # Uygun ilçeler boş olamaz
            if not record.uygun_ilceler:
                raise ValidationError(
                    _(
                        f"Araç '{record.name}' için uygun ilçeler tanımlanmalıdır!\n\n"
                        f"Araç Tipi: {dict(record._fields['arac_tipi'].selection).get(record.arac_tipi)}\n\n"
                        f"Bu hata, araç kaydedilirken otomatik eşleştirme yapılmadığı anlamına gelir.\n"
                        f"Lütfen aracı tekrar kaydedin veya yöneticiye başvurun."
                    )
                )

    def _update_uygun_ilceler(self) -> None:
        """Araç tipine göre uygun ilçeleri otomatik eşleştir.
        
        - Anadolu Yakası araçları → Sadece Anadolu Yakası ilçeleri
        - Avrupa Yakası araçları → Sadece Avrupa Yakası ilçeleri
        - Küçük araçlar ve ek araç → Tüm ilçeler
        """
        for record in self:
            if not record.arac_tipi:
                continue

            # Küçük araçlar ve ek araç tüm ilçelere gidebilir
            if is_small_vehicle(record):
                # Tüm aktif ilçeleri al
                tum_ilceler = self.env["teslimat.ilce"].search(
                    [("aktif", "=", True), ("teslimat_aktif", "=", True)]
                )
                record.uygun_ilceler = [(6, 0, tum_ilceler.ids)]
            elif record.arac_tipi == "anadolu_yakasi":
                # Sadece Anadolu Yakası ilçeleri
                anadolu_ilceler = self.env["teslimat.ilce"].search(
                    [
                        ("yaka_tipi", "=", "anadolu"),
                        ("aktif", "=", True),
                        ("teslimat_aktif", "=", True),
                    ]
                )
                record.uygun_ilceler = [(6, 0, anadolu_ilceler.ids)]
            elif record.arac_tipi == "avrupa_yakasi":
                # Sadece Avrupa Yakası ilçeleri
                avrupa_ilceler = self.env["teslimat.ilce"].search(
                    [
                        ("yaka_tipi", "=", "avrupa"),
                        ("aktif", "=", True),
                        ("teslimat_aktif", "=", True),
                    ]
                )
                record.uygun_ilceler = [(6, 0, avrupa_ilceler.ids)]

    @api.model_create_multi
    def create(self, vals_list):
        """Araç oluşturulduğunda ZORUNLU ilçe eşleştirmesi yap.
        
        Bu method kod seviyesinde garanti eder ki:
        - Her yeni araç mutlaka ilçe eşleştirmesine sahip olsun
        - Eşleştirme başarısız olursa kayıt oluşturulmasın
        
        NOT: Data yükleme sırasında kontrol daha esnek yapılır.
        """
        records = super().create(vals_list)
        
        # Data yükleme modunda mı?
        data_mode = self.env.context.get('install_mode') or self.env.context.get('module')
        
        for record in records:
            if not record.arac_tipi:
                if not data_mode:
                    raise ValidationError(
                        _(
                            f"Araç '{record.name}' için araç tipi tanımlanmalıdır!\n"
                            f"Lütfen araç tipini seçin."
                        )
                    )
                continue
            
            # Otomatik ilçe eşleştirmesi - ZORUNLU
            record._update_uygun_ilceler()
            
            # Eşleştirme kontrolü (sadece normal modda)
            if not data_mode and not record.uygun_ilceler:
                raise ValidationError(
                    _(
                        f"Araç '{record.name}' için ilçe eşleştirmesi yapılamadı!\n\n"
                        f"Araç Tipi: {dict(record._fields['arac_tipi'].selection).get(record.arac_tipi)}\n\n"
                        f"Olası sebepler:\n"
                        f"- İlçe kayıtları eksik olabilir\n"
                        f"- Yaka tipleri tanımlı olmayabilir\n\n"
                        f"Lütfen yöneticiye başvurun."
                    )
                )
            
            _logger.info(
                "Araç oluşturuldu: %s (%s) - %s ilçe eşleştirildi",
                record.name,
                record.arac_tipi,
                len(record.uygun_ilceler)
            )
        return records

    def write(self, vals):
        """Araç tipi değiştiğinde otomatik ilçe eşleştirmesini güncelle."""
        result = super().write(vals)
        if "arac_tipi" in vals:
            # Araç tipi değiştiğinde ZORUNLU yeniden eşleştirme
            for record in self:
                eski_ilce_sayisi = len(record.uygun_ilceler)
                record._update_uygun_ilceler()
                yeni_ilce_sayisi = len(record.uygun_ilceler)
                _logger.info(
                    "Araç güncellendi: %s (%s) - İlçe eşleştirmesi: %s → %s",
                    record.name,
                    record.arac_tipi,
                    eski_ilce_sayisi,
                    yeni_ilce_sayisi
                )
        return result

    @api.constrains("uygun_ilceler", "arac_tipi")
    def _check_ilce_uygunlugu(self) -> None:
        """Araç tipine göre ilçe uygunluğunu kontrol et.
        
        Yaka bazlı araçlar sadece kendi yakalarındaki ilçelere atanabilir.
        """
        for record in self:
            if not record.arac_tipi or not record.uygun_ilceler:
                continue

            # Küçük araçlar ve ek araç için kontrol yok
            if is_small_vehicle(record):
                continue

            # Yaka bazlı araçlar için kontrol
            if record.arac_tipi == "anadolu_yakasi":
                yanlis_ilceler = record.uygun_ilceler.filtered(
                    lambda i: i.yaka_tipi != "anadolu"
                )
                if yanlis_ilceler:
                    raise ValidationError(
                        _(
                            "Anadolu Yakası araç sadece Anadolu Yakası "
                            "ilçelerine atanabilir! "
                            f"Yanlış ilçeler: {', '.join(yanlis_ilceler.mapped('name'))}"
                        )
                    )
            elif record.arac_tipi == "avrupa_yakasi":
                yanlis_ilceler = record.uygun_ilceler.filtered(
                    lambda i: i.yaka_tipi != "avrupa"
                )
                if yanlis_ilceler:
                    raise ValidationError(
                        _(
                            "Avrupa Yakası araç sadece Avrupa Yakası "
                            "ilçelerine atanabilir! "
                            f"Yanlış ilçeler: {', '.join(yanlis_ilceler.mapped('name'))}"
                        )
                    )

    def action_update_uygun_ilceler(self) -> dict:
        """Tek bir aracın ilçe eşleştirmesini güncelle (Yöneticiler için).
        
        Returns:
            dict: Bilgilendirme mesajı
        """
        self.ensure_one()
        
        eski_sayisi = len(self.uygun_ilceler)
        self._update_uygun_ilceler()
        yeni_sayisi = len(self.uygun_ilceler)
        
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("İlçe Eşleştirmesi Güncellendi"),
                "message": _(
                    f"Araç: {self.name}\n"
                    f"Araç Tipi: {dict(self._fields['arac_tipi'].selection).get(self.arac_tipi)}\n"
                    f"Önceki İlçe Sayısı: {eski_sayisi}\n"
                    f"Yeni İlçe Sayısı: {yeni_sayisi}\n\n"
                    f"✓ Eşleştirme başarıyla güncellendi!"
                ),
                "type": "success",
                "sticky": False,
            },
        }
    
    @api.model
    def action_sync_all_arac_ilce(self) -> dict:
        """Tüm araçların ilçe eşleştirmelerini güncelle (Yöneticiler için).
        
        Tree view'dan toplu olarak çağrılır.
        
        Returns:
            dict: Bilgilendirme mesajı
        """
        result = self.sync_all_arac_ilce_eslesmesi()
        
        mesaj = (
            f"✓ Senkronizasyon Tamamlandı!\n\n"
            f"Güncellenen Araç Sayısı: {result['guncellenen_sayisi']}\n"
            f"Hata Sayısı: {result['hata_sayisi']}\n\n"
        )
        
        if result['detaylar']:
            mesaj += "Detaylar:\n" + "\n".join(result['detaylar'][:10])
            if len(result['detaylar']) > 10:
                mesaj += f"\n... ve {len(result['detaylar']) - 10} araç daha"
        
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Toplu Senkronizasyon Tamamlandı"),
                "message": _(mesaj),
                "type": "success",
                "sticky": True,
            },
        }

    def action_gecici_kapat(self) -> dict:
        """Aracı geçici olarak kapatma wizard'ını aç (Yöneticiler için).

        Returns:
            dict: Wizard açma action'ı
        """
        self.ensure_one()
        return {
            "name": "Geçici Kapatma",
            "type": "ir.actions.act_window",
            "res_model": "teslimat.arac.kapatma.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_arac_id": self.id},
        }

    def action_aktif_et(self) -> None:
        """Aracı aktif et ve kapatma bilgilerini temizle."""
        self.ensure_one()
        self.write(
            {
                "gecici_kapatma": False,
                "kapatma_sebebi": False,
                "kapatma_baslangic": False,
                "kapatma_bitis": False,
            }
        )

    @api.model
    def get_uygun_araclar(
        self,
        ilce_id: Optional[int] = None,
        tarih: Optional[fields.Date] = None,
        teslimat_sayisi: int = 1,
    ) -> "TeslimatArac":
        """Belirli ilçe ve tarih için uygun araçları getir.

        Args:
            ilce_id: İlçe ID
            tarih: Tarih (opsiyonel)
            teslimat_sayisi: Gereken teslimat sayısı

        Returns:
            Recordset: Uygun araçlar
        """
        domain = [
            ("aktif", "=", True),
            ("gecici_kapatma", "=", False),
            ("kalan_kapasite", ">=", teslimat_sayisi),
        ]

        # İlçe uyumluluğu kontrolü (Many2many ilişkisini kullanarak)
        if ilce_id:
            ilce = self.env["teslimat.ilce"].browse(ilce_id)
            if ilce.exists():
                # Bu ilçeyi uygun ilçeler listesinde bulunan araçları filtrele
                domain.append(("uygun_ilceler", "in", [ilce_id]))

        # Kapatma tarihi kontrolü
        if tarih:
            domain += [
                "|",
                ("kapatma_bitis", "=", False),
                ("kapatma_bitis", "<", tarih),
            ]

        return self.search(domain, order="kalan_kapasite desc")

    @api.model
    def sync_all_arac_ilce_eslesmesi(self) -> dict:
        """Tüm araçların ilçe eşleştirmelerini MANUEL olarak güncelle.
        
        Bu metod SADECE manuel olarak (wizard veya kod ile) çağrılır.
        Otomatik cron job veya hook kullanılmaz.
        Tüm araçların uygun ilçelerini araç tipine göre otomatik eşleştirir.
        
        Returns:
            dict: İşlem sonucu bilgisi
        """
        araclar = self.search([])
        guncellenen_sayisi = 0
        hata_sayisi = 0
        detaylar = []
        
        _logger.info("=" * 60)
        _logger.info("Araç-İlçe Eşleştirme Senkronizasyonu Başlatıldı")
        _logger.info("=" * 60)
        
        for arac in araclar:
            try:
                if arac.arac_tipi:
                    eski_sayisi = len(arac.uygun_ilceler)
                    arac._update_uygun_ilceler()
                    yeni_sayisi = len(arac.uygun_ilceler)
                    
                    if eski_sayisi != yeni_sayisi:
                        detaylar.append(
                            f"{arac.name} ({arac.arac_tipi}): {eski_sayisi} → {yeni_sayisi} ilçe"
                        )
                        _logger.info(
                            "%s (%s): %s → %s ilçe",
                            arac.name,
                            arac.arac_tipi,
                            eski_sayisi,
                            yeni_sayisi
                        )
                    guncellenen_sayisi += 1
                else:
                    _logger.warning("%s: Araç tipi tanımlı değil, atlandı", arac.name)
            except Exception as e:
                hata_sayisi += 1
                _logger.exception("%s: Senkronizasyon hatası", arac.name)
        
        _logger.info("=" * 60)
        _logger.info("Senkronizasyon Tamamlandı")
        _logger.info("  - Güncellenen: %s araç", guncellenen_sayisi)
        _logger.info("  - Hata: %s araç", hata_sayisi)
        _logger.info("=" * 60)
        
        return {
            "success": True,
            "message": f"{guncellenen_sayisi} araç için ilçe eşleştirmesi güncellendi.",
            "guncellenen_sayisi": guncellenen_sayisi,
            "hata_sayisi": hata_sayisi,
            "detaylar": detaylar,
        }

