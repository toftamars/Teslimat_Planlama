"""Araç Kapatma Wizard - Hızlı araç kapatma işlemi."""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TeslimatAracKapatmaWizard(models.TransientModel):
    """Araç Kapatma Wizard.
    
    Yöneticilerin hızlıca araç kapatma kaydı oluşturması için wizard.
    """
    
    _name = "teslimat.arac.kapatma.wizard"
    _description = "Araç Kapatma Wizard"
    
    arac_id = fields.Many2one(
        "teslimat.arac",
        string="Araç",
        required=True,
        help="Kapatılacak araç"
    )
    
    baslangic_tarihi = fields.Date(
        string="Başlangıç Tarihi",
        required=True,
        default=fields.Date.today,
        help="Kapatma başlangıç tarihi"
    )
    
    bitis_tarihi = fields.Date(
        string="Bitiş Tarihi",
        required=True,
        default=fields.Date.today,
        help="Kapatma bitiş tarihi"
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
        default="bakim"
    )
    
    aciklama = fields.Text(
        string="Açıklama",
        help="Detaylı açıklama (opsiyonel)"
    )
    
    gun_sayisi = fields.Integer(
        string="Gün Sayısı",
        compute="_compute_gun_sayisi",
        help="Toplam kapatma süresi"
    )
    
    @api.depends("baslangic_tarihi", "bitis_tarihi")
    def _compute_gun_sayisi(self):
        """Gün sayısını hesapla."""
        for record in self:
            if record.baslangic_tarihi and record.bitis_tarihi:
                if record.bitis_tarihi < record.baslangic_tarihi:
                    record.gun_sayisi = 0
                else:
                    delta = record.bitis_tarihi - record.baslangic_tarihi
                    record.gun_sayisi = delta.days + 1
            else:
                record.gun_sayisi = 0
    
    @api.constrains("baslangic_tarihi", "bitis_tarihi")
    def _check_tarih_sirasi(self):
        """Bitiş tarihi kontrolü."""
        for record in self:
            if record.baslangic_tarihi and record.bitis_tarihi:
                if record.bitis_tarihi < record.baslangic_tarihi:
                    raise UserError(
                        "Bitiş tarihi başlangıç tarihinden önce olamaz!"
                    )
    
    def action_kapat(self):
        """Araç kapatma kaydı oluştur."""
        self.ensure_one()
        
        # Validasyonlar
        if not self.arac_id:
            raise UserError("Lütfen bir araç seçin!")
        
        if not self.sebep:
            raise UserError("Lütfen bir sebep seçin!")
        
        if self.bitis_tarihi < self.baslangic_tarihi:
            raise UserError("Bitiş tarihi başlangıç tarihinden önce olamaz!")
        
        # Kapatma kaydı oluştur
        kapatma = self.env["teslimat.arac.kapatma"].create({
            "arac_id": self.arac_id.id,
            "baslangic_tarihi": self.baslangic_tarihi,
            "bitis_tarihi": self.bitis_tarihi,
            "sebep": self.sebep,
            "aciklama": self.aciklama,
        })
        
        _logger.info(
            "Araç kapatma kaydı oluşturuldu: %s (%s - %s)",
            self.arac_id.name,
            self.baslangic_tarihi,
            self.bitis_tarihi,
        )
        
        # Başarı mesajı göster ve kapatma kaydına git
        return {
            "type": "ir.actions.act_window",
            "res_model": "teslimat.arac.kapatma",
            "res_id": kapatma.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_notification": {
                    "title": "Başarılı!",
                    "message": f"{self.arac_id.name} başarıyla kapatıldı ({self.gun_sayisi} gün)",
                    "type": "success",
                }
            }
        }
