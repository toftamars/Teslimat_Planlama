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
    
    # Not (opsiyonel)
    tamamlama_notu = fields.Text(
        string="Tamamlama Notu",
        help="Teslimat hakkında not ekleyebilirsiniz (opsiyonel)"
    )
    
    # Teslim alan kişi
    teslim_alan_kisi = fields.Char(
        string="Teslim Alan Kişi",
        help="Teslimatı teslim alan kişinin adı"
    )

    def action_teslimat_tamamla(self) -> dict:
        """Teslimatı tamamla - Fotoğraf ve notu kaydet."""
        self.ensure_one()
        
        teslimat = self.teslimat_belgesi_id
        
        if not teslimat:
            raise UserError(_("Teslimat belgesi bulunamadı."))
        
        # Teslimat durumunu güncelle
        vals = {
            'durum': 'teslim_edildi',
            'gercek_teslimat_saati': fields.Datetime.now(),
        }
        
        # Teslim alan kişi
        if self.teslim_alan_kisi:
            vals['teslim_alan_kisi'] = self.teslim_alan_kisi
        
        # Not varsa ekle
        if self.tamamlama_notu:
            mevcut_not = teslimat.notlar or ""
            tarih_str = fields.Datetime.now().strftime('%d.%m.%Y %H:%M')
            yeni_not = f"\n\n[{tarih_str}] Teslim Notu:\n{self.tamamlama_notu}"
            vals['notlar'] = mevcut_not + yeni_not
        
        teslimat.write(vals)
        
        # Fotoğraf varsa chatter'a ekle
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
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Başarılı'),
                'message': _('Teslimat başarıyla tamamlandı!'),
                'type': 'success',
                'sticky': False,
            }
        }
