from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TeslimatGunKapatmaWizard(models.TransientModel):
    _name = 'teslimat.gun.kapatma.wizard'
    _description = 'Teslimat Günü Geçici Kapatma Sihirbazı'

    gun_id = fields.Many2one('teslimat.gun', string='Teslimat Günü', required=True, readonly=True)
    kapatma_sebebi = fields.Text(string='Kapatma Sebebi', required=True,
                                 help='Örn: Araç bakımı, Resmi tatil, Hava durumu...')
    sure_siz = fields.Boolean(string='Süresiz Kapatma', default=False,
                              help='İşaretlenirse tarih aralığı olmadan kapatılır')
    kapatma_baslangic = fields.Date(string='Kapatma Başlangıç Tarihi', default=fields.Date.context_today)
    kapatma_bitis = fields.Date(string='Kapatma Bitiş Tarihi')

    @api.onchange('sure_siz')
    def _onchange_sure_siz(self):
        if self.sure_siz:
            self.kapatma_baslangic = False
            self.kapatma_bitis = False
        else:
            self.kapatma_baslangic = fields.Date.context_today(self)

    @api.onchange('kapatma_baslangic', 'kapatma_bitis')
    def _onchange_tarihler(self):
        if self.kapatma_baslangic and self.kapatma_bitis:
            if self.kapatma_baslangic > self.kapatma_bitis:
                return {
                    'warning': {
                        'title': _('Uyarı'),
                        'message': _('Başlangıç tarihi, bitiş tarihinden sonra olamaz.')
                    }
                }

    def action_onayla(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Bu işlem için teslimat yöneticisi yetkisi gereklidir.'))

        if not self.sure_siz and (not self.kapatma_baslangic or not self.kapatma_bitis):
            raise UserError(_('Tarih aralığı belirtilmelidir (veya Süresiz Kapatma seçilmelidir).'))

        write_vals = {
            'gecici_kapatma': True,
            'kapatma_sebebi': self.kapatma_sebebi,
        }

        if not self.sure_siz:
            write_vals.update({
                'kapatma_baslangic': self.kapatma_baslangic,
                'kapatma_bitis': self.kapatma_bitis,
            })
        else:
            write_vals.update({
                'kapatma_baslangic': False,
                'kapatma_bitis': False,
            })

        self.gun_id.write(write_vals)

        if self.sure_siz:
            mesaj = _('%s günü süresiz olarak kapatıldı.') % (self.gun_id.name)
        else:
            mesaj = _('%s günü %s - %s tarihleri arasında kapatıldı.') % (
                self.gun_id.name,
                self.kapatma_baslangic.strftime('%d/%m/%Y'),
                self.kapatma_bitis.strftime('%d/%m/%Y'),
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Başarılı'),
                'message': mesaj,
                'type': 'success',
            }
        }

    def action_iptal(self):
        return {'type': 'ir.actions.act_window_close'}


