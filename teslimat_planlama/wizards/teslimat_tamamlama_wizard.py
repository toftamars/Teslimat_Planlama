"""Teslimat Tamamlama Wizard'ı - Fotoğraf ve not ekleme."""
import logging
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TeslimatTamamlamaWizard(models.TransientModel):
    """Teslimat Tamamlama Wizard'ı.
    
    Teslimat tamamlanırken fotoğraf ve not eklenebilir.
    """

    _name = "teslimat.tamamlama.wizard"
    _description = "Teslimat Tamamlama Wizard'ı"

    teslimat_belgesi_id = fields.Many2one(
        "teslimat.belgesi",
        string="Teslimat Belgesi",
        required=True,
        readonly=True,
    )
    
    # Fotoğraf (opsiyonel)
    teslimat_fotografi = fields.Binary(
        string="Teslimat Fotoğrafı",
        help="Teslimat tamamlandığına dair fotoğraf yükleyebilirsiniz (opsiyonel)"
    )
    fotograf_dosya_adi = fields.Char(string="Dosya Adı")
    
    # Not (zorunlu)
    tamamlama_notu = fields.Text(
        string="Tamamlama Notu",
        required=True,
        help="Teslimat hakkında not eklemelisiniz (zorunlu)"
    )
    
    # Teslim alan kişi (zorunlu)
    teslim_alan_kisi = fields.Char(
        string="Teslim Alan Kişi",
        required=True,
        help="Teslimatı teslim alan kişinin adı (zorunlu)"
    )

    def action_teslimat_tamamla(self) -> dict:
        """Teslimatı tamamla - Fotoğraf ve notu kaydet."""
        self.ensure_one()
        
        teslimat = self.teslimat_belgesi_id
        
        if not teslimat:
            raise UserError(_("Teslimat belgesi bulunamadı."))
        
        # Zorunlu alanları kontrol et
        if not self.teslim_alan_kisi:
            raise UserError(_("Teslim alan kişi bilgisi zorunludur!"))
        
        if not self.tamamlama_notu:
            raise UserError(_("Tamamlama notu zorunludur!"))
        
        # Teslimat durumunu güncelle
        vals = {
            'durum': 'teslim_edildi',
            'gercek_teslimat_saati': fields.Datetime.now(),
            'teslim_alan_kisi': self.teslim_alan_kisi,
        }
        
        # Fotoğraf varsa belgede göster
        if self.teslimat_fotografi:
            vals['teslimat_fotografi'] = self.teslimat_fotografi
            vals['fotograf_dosya_adi'] = self.fotograf_dosya_adi or 'teslimat_fotografi.jpg'
        
        # Not ekle
        if self.tamamlama_notu:
            mevcut_not = teslimat.notlar or ""
            tarih_str = fields.Datetime.now().strftime('%d.%m.%Y %H:%M')
            yeni_not = f"\n\n[{tarih_str}] Teslim Notu:\n{self.tamamlama_notu}"
            vals['notlar'] = mevcut_not + yeni_not
        
        teslimat.write(vals)
        
        # Fotoğraf varsa chatter'a da ekle
        if self.teslimat_fotografi:
            attachment = self.env['ir.attachment'].create({
                'name': self.fotograf_dosya_adi or 'teslimat_fotografi.jpg',
                'type': 'binary',
                'datas': self.teslimat_fotografi,
                'res_model': 'teslimat.belgesi',
                'res_id': teslimat.id,
                'mimetype': 'image/jpeg',
            })
            
            # Chatter'a mesaj ekle
            teslimat.message_post(
                body=_("Teslimat tamamlandı - Fotoğraf eklendi"),
                attachment_ids=[attachment.id],
            )
            
            _logger.info("✓ Teslimat tamamlandı (Fotoğraflı): %s", teslimat.name)
        else:
            # Fotoğraf yoksa sadece chatter'a mesaj
            teslimat.message_post(
                body=_("Teslimat tamamlandı"),
            )
            _logger.info("✓ Teslimat tamamlandı: %s", teslimat.name)
        
        # Notification göster
        self.env.user.notify_success(
            message=_('Teslimat başarıyla tamamlandı!'),
            title=_('Başarılı'),
        )
        
        # Wizard'ı kapat ve teslimat belgesini göster
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'res_id': teslimat.id,
            'view_mode': 'form',
            'target': 'current',
        }
