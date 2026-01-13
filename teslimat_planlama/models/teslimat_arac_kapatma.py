"""Araç Kapatma Modeli - Araçların belirli günlerde kapatılması."""
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TeslimatAracKapatma(models.Model):
    """Araç Kapatma Kaydı.

    Araçların belirli günlerde kapatılmasını (bakım, arıza, vb.) yönetir.
    """

    _name = "teslimat.arac.kapatma"
    _description = "Araç Kapatma"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "baslangic_tarihi desc"
    _rec_name = "display_name"
    
    # Temel Bilgiler
    arac_id = fields.Many2one(
        "teslimat.arac",
        string="Araç",
        required=True,
        ondelete="cascade",
        help="Kapatılacak araç"
    )
    
    baslangic_tarihi = fields.Date(
        string="Başlangıç Tarihi",
        required=True,
        default=fields.Date.today,
        help="Araç kapatma başlangıç tarihi"
    )
    
    bitis_tarihi = fields.Date(
        string="Bitiş Tarihi",
        required=True,
        default=fields.Date.today,
        help="Araç kapatma bitiş tarihi"
    )
    
    sebep = fields.Selection(
        [
            ("bakim", "Bakım"),
            ("ariza", "Arıza"),
            ("kaza", "Kaza"),
            ("yakit", "Yakıt Sorunu"),
            ("surucu_yok", "Sürücü Yok"),
            ("diger", "Diğer"),
        ],
        string="Sebep",
        required=True,
        default="bakim",
        help="Araç kapatma sebebi"
    )
    
    aciklama = fields.Text(
        string="Açıklama",
        help="Detaylı açıklama (opsiyonel)"
    )
    
    # Sistem Bilgileri
    kapatan_kullanici_id = fields.Many2one(
        "res.users",
        string="Kapatan Kişi",
        default=lambda self: self.env.user,
        readonly=True,
        help="Araç kapatma işlemini yapan kullanıcı"
    )
    
    olusturma_tarihi = fields.Datetime(
        string="Oluşturma Tarihi",
        default=fields.Datetime.now,
        readonly=True
    )
    
    aktif = fields.Boolean(
        string="Aktif",
        default=True,
        help="Kapatma kaydı aktif mi?"
    )
    
    # Display Name
    display_name = fields.Char(
        string="İsim",
        compute="_compute_display_name",
        store=True
    )
    
    gun_sayisi = fields.Integer(
        string="Gün Sayısı",
        compute="_compute_gun_sayisi",
        store=True,
        help="Kapatma süresi (gün)"
    )
    
    @api.depends("arac_id", "baslangic_tarihi", "bitis_tarihi", "sebep")
    def _compute_display_name(self):
        """Display name hesapla."""
        for record in self:
            if record.arac_id and record.baslangic_tarihi and record.bitis_tarihi:
                sebep_dict = dict(self._fields['sebep'].selection)
                sebep_text = sebep_dict.get(record.sebep, record.sebep)
                
                if record.baslangic_tarihi == record.bitis_tarihi:
                    record.display_name = f"{record.arac_id.name} - {record.baslangic_tarihi.strftime('%d.%m.%Y')} ({sebep_text})"
                else:
                    record.display_name = f"{record.arac_id.name} - {record.baslangic_tarihi.strftime('%d.%m.%Y')} → {record.bitis_tarihi.strftime('%d.%m.%Y')} ({sebep_text})"
            else:
                record.display_name = "Yeni Araç Kapatma"
    
    @api.depends("baslangic_tarihi", "bitis_tarihi")
    def _compute_gun_sayisi(self):
        """Gün sayısını hesapla."""
        for record in self:
            if record.baslangic_tarihi and record.bitis_tarihi:
                delta = record.bitis_tarihi - record.baslangic_tarihi
                record.gun_sayisi = delta.days + 1
            else:
                record.gun_sayisi = 0
    
    @api.constrains("baslangic_tarihi", "bitis_tarihi")
    def _check_tarih_sirasi(self):
        """Bitiş tarihi başlangıçtan önce olamaz."""
        for record in self:
            if record.baslangic_tarihi and record.bitis_tarihi:
                if record.bitis_tarihi < record.baslangic_tarihi:
                    raise ValidationError(
                        "Bitiş tarihi başlangıç tarihinden önce olamaz!"
                    )
    
    @api.constrains("baslangic_tarihi", "bitis_tarihi", "arac_id")
    def _check_cakisan_kapatma(self):
        """Aynı araç için çakışan kapatma kaydı olmasın."""
        for record in self:
            if not record.aktif:
                continue
                
            # Çakışan kayıtları ara
            domain = [
                ("arac_id", "=", record.arac_id.id),
                ("id", "!=", record.id),
                ("aktif", "=", True),
                "|",
                "&",
                ("baslangic_tarihi", "<=", record.baslangic_tarihi),
                ("bitis_tarihi", ">=", record.baslangic_tarihi),
                "&",
                ("baslangic_tarihi", "<=", record.bitis_tarihi),
                ("bitis_tarihi", ">=", record.bitis_tarihi),
            ]
            
            cakisan = self.search(domain, limit=1)
            if cakisan:
                raise ValidationError(
                    f"Bu tarih aralığında {record.arac_id.name} için zaten bir kapatma kaydı var!\n"
                    f"Çakışan kayıt: {cakisan.display_name}"
                )
    
    @api.model
    def arac_kapali_mi(self, arac_id, tarih):
        """Belirli bir tarihte araç kapalı mı kontrol et.
        
        Args:
            arac_id: Araç ID
            tarih: Kontrol edilecek tarih
            
        Returns:
            tuple: (Kapalı mı?, Kapatma kaydı veya None)
        """
        if not arac_id or not tarih:
            return False, None
        
        kapatma = self.search([
            ("arac_id", "=", arac_id),
            ("baslangic_tarihi", "<=", tarih),
            ("bitis_tarihi", ">=", tarih),
            ("aktif", "=", True),
        ], limit=1)
        
        if kapatma:
            return True, kapatma
        return False, None
    
    def action_iptal_et(self):
        """Kapatma kaydını iptal et."""
        self.ensure_one()
        self.aktif = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Başarılı",
                "message": f"{self.arac_id.name} kapatma kaydı iptal edildi",
                "type": "success",
                "sticky": False,
            }
        }
    
    def action_aktif_et(self):
        """Kapatma kaydını tekrar aktif et."""
        self.ensure_one()
        self.aktif = True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Başarılı",
                "message": f"{self.arac_id.name} kapatma kaydı tekrar aktif edildi",
                "type": "success",
                "sticky": False,
            }
        }
