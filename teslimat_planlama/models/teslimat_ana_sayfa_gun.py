"""Teslimat Ana Sayfa Gün Modeli - Uygun günler listesi için."""
from datetime import date
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TeslimatAnaSayfaGun(models.TransientModel):
    """Teslimat Ana Sayfa Gün - Uygun günler listesi."""

    _name = "teslimat.ana.sayfa.gun"
    _description = "Teslimat Ana Sayfa - Uygun Günler"
    _order = "tarih"

    ana_sayfa_id = fields.Many2one(
        "teslimat.ana.sayfa", string="Ana Sayfa", required=True, ondelete="cascade"
    )
    tarih = fields.Date(string="Tarih", required=True)
    gun_adi = fields.Char(string="Gün Adı", required=True)
    teslimat_sayisi = fields.Integer(string="Teslimat Sayısı", default=0)
    toplam_kapasite = fields.Integer(string="Toplam Kapasite", default=0)
    kalan_kapasite = fields.Integer(string="Kalan Kapasite", default=0)
    doluluk_yuzdesi = fields.Float(string="Doluluk %", compute="_compute_doluluk_yuzdesi", store=False)
    durum_text = fields.Char(string="Durum")
    tarih_str = fields.Char(string="Tarih", compute="_compute_tarih_str")
    
    # Araç Kapatma Bilgileri
    arac_kapali_mi = fields.Boolean(
        string="Araç Kapalı",
        compute="_compute_arac_kapatma",
        store=False,
        help="Bu tarihte araç kapalı mı?"
    )
    kapatma_sebep = fields.Char(
        string="Kapatma Sebebi",
        compute="_compute_arac_kapatma",
        store=False
    )
    kapatma_aciklama = fields.Text(
        string="Kapatma Açıklama",
        compute="_compute_arac_kapatma",
        store=False
    )
    kapatan_kisi = fields.Char(
        string="Kapatan Kişi",
        compute="_compute_arac_kapatma",
        store=False
    )

    @api.depends("teslimat_sayisi", "toplam_kapasite")
    def _compute_doluluk_yuzdesi(self):
        """Doluluk yüzdesini hesapla - 0-1 aralığında (widget="percentage" için).
        
        Not: Odoo'nun percentage widget'ı değeri 0-1 aralığında bekler ve otomatik 100 ile çarpar.
        Bu yüzden burada 100 ile çarpmıyoruz.
        """
        for rec in self:
            if rec.toplam_kapasite > 0:
                # Doluluk oranını 0-1 aralığında hesapla (widget="percentage" otomatik 100 ile çarpar)
                oran = rec.teslimat_sayisi / rec.toplam_kapasite
                # Maksimum 1.0 ile sınırla (aşım durumunda %100 gösterilir)
                rec.doluluk_yuzdesi = min(oran, 1.0)
            else:
                rec.doluluk_yuzdesi = 0.0

    @api.depends("tarih")
    def _compute_tarih_str(self):
        """Tarih field'ını formatlanmış string olarak hesapla."""
        gun_isimleri = {
            0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"
        }
        for rec in self:
            if rec.tarih:
                gun = gun_isimleri.get(rec.tarih.weekday(), "")
                rec.tarih_str = f"{rec.tarih.strftime('%d.%m.%Y')} {gun}"
            else:
                rec.tarih_str = "-"
    
    @api.depends("tarih", "ana_sayfa_id.arac_id")
    def _compute_arac_kapatma(self):
        """Araç kapatma bilgilerini hesapla."""
        sebep_dict = {
            "bakim": "Bakım",
            "ariza": "Arıza",
            "kaza": "Kaza",
            "yakit": "Yakıt Sorunu",
            "surucu_yok": "Sürücü Yok",
            "diger": "Diğer",
        }
        
        for rec in self:
            if not rec.tarih or not rec.ana_sayfa_id.arac_id:
                rec.arac_kapali_mi = False
                rec.kapatma_sebep = ""
                rec.kapatma_aciklama = ""
                rec.kapatan_kisi = ""
                continue
            
            # Araç kapatma kontrolü
            kapali, kapatma = self.env["teslimat.arac.kapatma"].arac_kapali_mi(
                rec.ana_sayfa_id.arac_id.id,
                rec.tarih
            )
            
            if kapali and kapatma:
                rec.arac_kapali_mi = True
                rec.kapatma_sebep = sebep_dict.get(kapatma.sebep, kapatma.sebep)
                rec.kapatma_aciklama = kapatma.aciklama or ""
                rec.kapatan_kisi = kapatma.kapatan_kullanici_id.name or ""
            else:
                rec.arac_kapali_mi = False
                rec.kapatma_sebep = ""
                rec.kapatma_aciklama = ""
                rec.kapatan_kisi = ""

    def action_teslimat_olustur(self) -> dict:
        """Seçilen gün için teslimat belgesi wizard'ını aç."""
        self.ensure_one()

        if not self.ana_sayfa_id.arac_id:
            raise UserError(_("Araç seçimi gereklidir."))

        if not self.ana_sayfa_id.ilce_id:
            raise UserError(_("İlçe seçimi gereklidir."))
        
        # Araç kapalı mı kontrol et
        if self.arac_kapali_mi:
            raise UserError(
                f"Bu tarihte araç kapalı!\n\n"
                f"📅 Tarih: {self.tarih_str}\n"
                f"⚠️ Sebep: {self.kapatma_sebep}\n"
                f"👤 Kapatan: {self.kapatan_kisi}\n\n"
                f"Lütfen başka bir tarih veya araç seçin."
            )

        # Wizard'ı aç
        context = {
            "default_teslimat_tarihi": self.tarih,
            "default_arac_id": self.ana_sayfa_id.arac_id.id,
            "default_ilce_id": self.ana_sayfa_id.ilce_id.id,
        }

        return {
            "name": _("Teslimat Belgesi Oluştur"),
            "type": "ir.actions.act_window",
            "res_model": "teslimat.belgesi.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
