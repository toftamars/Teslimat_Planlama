from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TeslimatBelgesi(models.Model):
    _name = 'teslimat.belgesi'
    _description = 'Teslimat Belgesi'
    _order = 'teslimat_tarihi desc, name'

    name = fields.Char(string='Teslimat No', required=True, copy=False, readonly=True, 
                      default=lambda self: _('Yeni'))
    teslimat_tarihi = fields.Date(string='Teslimat Tarihi', required=True, default=fields.Date.today)
    
    # Müşteri Bilgileri
    musteri_id = fields.Many2one('res.partner', string='Müşteri', required=True, 
                                domain=[('customer_rank', '>', 0)])
    
    # Araç ve İlçe Bilgileri
    arac_id = fields.Many2one('teslimat.arac', string='Araç', required=True)
    ilce_id = fields.Many2one('teslimat.ilce', string='İlçe', required=True)
    surucu_id = fields.Many2one('res.partner', string='Sürücü', domain="[('is_driver','=',True)]")
    
    # Planlama İlişkileri
    planlama_akilli_id = fields.Many2one('teslimat.planlama.akilli', string='Akıllı Planlama')
    
    # Sıra ve Öncelik
    sira_no = fields.Integer(string='Sıra No', default=1)
    oncelik_puani = fields.Integer(string='Öncelik Puanı', default=0)
    
    # Transfer Belgesi Entegrasyonu
    transfer_no = fields.Char(string='Transfer No', help='Transfer belgesi numarası')
    stock_picking_id = fields.Many2one('stock.picking', string='Transfer Belgesi')
    
    # Ürün Bilgileri
    urun_id = fields.Many2one('product.product', string='Ürün', required=True)
    miktar = fields.Float(string='Miktar', required=True)
    birim = fields.Many2one('uom.uom', string='Birim', related='urun_id.uom_id', readonly=True)
    
    # Durum Bilgileri
    durum = fields.Selection([
        ('taslak', 'Taslak'),
        ('hazir', 'Hazır'),
        ('yolda', 'Yolda'),
        ('teslim_edildi', 'Teslim Edildi'),
        ('iptal', 'İptal')
    ], string='Durum', default='taslak', required=True)
    
    # Zaman Bilgileri
    planlanan_teslimat_saati = fields.Selection([
        ('09:00', '09:00'),
        ('10:00', '10:00'),
        ('11:00', '11:00'),
        ('12:00', '12:00'),
        ('13:00', '13:00'),
        ('14:00', '14:00'),
        ('15:00', '15:00'),
        ('16:00', '16:00'),
        ('17:00', '17:00')
    ], string='Planlanan Teslimat Saati')
    
    gercek_teslimat_saati = fields.Datetime(string='Gerçek Teslimat Saati')
    
    # Notlar
    notlar = fields.Text(string='Notlar')
    
    # Hesaplanan Alanlar
    yaka_tipi = fields.Selection([
        ('anadolu', 'Anadolu Yakası'),
        ('avrupa', 'Avrupa Yakası'),
        ('belirsiz', 'Belirsiz')
    ], string='Yaka Tipi', related='ilce_id.yaka_tipi', store=True, readonly=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Yeni')) == _('Yeni'):
            vals['name'] = self.env['ir.sequence'].next_by_code('teslimat.belgesi') or _('Yeni')
        return super(TeslimatBelgesi, self).create(vals)
    
    @api.onchange('transfer_no')
    def _onchange_transfer_no(self):
        """Transfer no girildiğinde bilgileri otomatik doldur"""
        if self.transfer_no:
            picking = self.env['stock.picking'].search([
                ('name', '=', self.transfer_no)
            ], limit=1)
            
            if picking:
                self.stock_picking_id = picking.id
                self._onchange_stock_picking()
    
    @api.onchange('stock_picking_id')
    def _onchange_stock_picking(self):
        """Transfer belgesi seçildiğinde bilgileri otomatik doldur"""
        if self.stock_picking_id:
            picking = self.stock_picking_id
            
            # Müşteri bilgisi
            if picking.partner_id:
                self.musteri_id = picking.partner_id.id
            
            # Ürün ve miktar bilgileri
            if picking.move_ids_without_package:
                move = picking.move_ids_without_package[0]
                self.urun_id = move.product_id.id
                self.miktar = move.product_uom_qty
            
            # Teslimat no
            if not self.name:
                self.name = f"T-{picking.name}"
    
    @api.onchange('musteri_id')
    def _onchange_musteri(self):
        """Müşteri seçildiğinde ilçe bilgisini otomatik doldur"""
        if self.musteri_id and self.musteri_id.state_id:
            # Müşterinin bulunduğu ilçeyi bul
            ilce = self.env['teslimat.ilce'].search([
                ('name', 'ilike', self.musteri_id.state_id.name)
            ], limit=1)
            if ilce:
                self.ilce_id = ilce.id
    
    @api.onchange('ilce_id')
    def _onchange_ilce(self):
        """İlçe seçildiğinde uygun günleri göster ve uyarı ver"""
        if not self.ilce_id:
            return
        
        # İlçe için uygun günleri bul
        uygun_gunler = self.env['teslimat.gun'].get_uygun_gunler(self.ilce_id.id)
        
        if not uygun_gunler:
            return {
                'warning': {
                    'title': 'İlçe Uyarısı',
                    'message': f'{self.ilce_id.name} ilçesi için hiçbir günde teslimat yapılamaz!'
                }
            }
        
        # Uygun günleri listele
        gun_isimleri = [gun.name for gun in uygun_gunler]
        gun_listesi = ', '.join(gun_isimleri)
        
        # Uyarı mesajı göster
        return {
            'warning': {
                'title': 'Teslimat Günleri',
                'message': f'{self.ilce_id.name} ilçesi şu günlerde teslimat yapılır:\n{gun_listesi}\n\nSadece bu günlerde teslimat oluşturabilirsiniz.'
            }
        }
    
    @api.onchange('teslimat_tarihi')
    def _onchange_teslimat_tarihi(self):
        """Teslimat tarihi seçildiğinde ilçe-gün uygunluğunu kontrol et"""
        if not self.teslimat_tarihi or not self.ilce_id:
            return
        
        # Seçilen tarih için ilçe uygunluğunu kontrol et
        availability = self.env['teslimat.gun'].check_availability(
            self.teslimat_tarihi, 
            self.ilce_id.id
        )
        
        if not availability['available']:
            return {
                'warning': {
                    'title': 'Tarih Uygun Değil',
                    'message': f'{self.teslimat_tarihi.strftime("%d/%m/%Y")} tarihinde {self.ilce_id.name} ilçesine teslimat yapılamaz!\n\nSebep: {availability["reason"]}\n\nLütfen uygun bir tarih seçin.'
                }
            }
        
        # Uygun tarih seçildiğinde bilgi ver
        return {
            'warning': {
                'title': 'Tarih Uygun',
                'message': f'{self.teslimat_tarihi.strftime("%d/%m/%Y")} tarihinde {self.ilce_id.name} ilçesine teslimat yapılabilir.\n\nGün: {availability["day_name"]}\nKalan Kapasite: {availability["remaining_capacity"]}'
            }
        }
    
    @api.onchange('arac_id', 'teslimat_tarihi')
    def _onchange_arac_date(self):
        """Araç ve tarih değiştiğinde otomatik kontroller"""
        if not self.arac_id or not self.teslimat_tarihi:
            return
        
        # Kontrol edilen kriterler:
        # 1. Aracın günlük teslimat limiti dolmuş mu?
        # 2. Teslimat yöneticisi yetkisi var mı?
        # 3. Uyarı mesajları göster
        
        warnings = []
        errors = []
        
        # 1. Araç kapasite kontrolü
        if self.arac_id:
            # Aynı gün aynı araç için mevcut teslimat sayısını hesapla
            domain = [
                ('arac_id', '=', self.arac_id.id),
                ('teslimat_tarihi', '=', self.teslimat_tarihi),
                ('durum', 'in', ['hazir', 'yolda'])
            ]
            # Yeni kayıt (NewId) için id != koşulu eklenmez
            exclude_id = getattr(self._origin, 'id', False) or False
            if exclude_id:
                domain.append(('id', '!=', exclude_id))

            gunluk_teslimat = self.env['teslimat.belgesi'].search_count(domain)
            
            kalan_kapasite = self.arac_id.gunluk_teslimat_limiti - gunluk_teslimat
            
            if kalan_kapasite <= 0:
                errors.append(f"Bu araç için günlük teslimat limiti dolu! (Limit: {self.arac_id.gunluk_teslimat_limiti})")
            elif kalan_kapasite <= 2:
                warnings.append(f"Araç kapasitesi kritik seviyede! (Kalan: {kalan_kapasite})")
            else:
                warnings.append(f"Araç kapasitesi: {kalan_kapasite}/{self.arac_id.gunluk_teslimat_limiti}")
            
            # Araç durumu kontrolü
            if self.arac_id.gecici_kapatma:
                errors.append(f"Araç geçici olarak kapatılmış! Sebep: {self.arac_id.kapatma_sebebi or 'Belirtilmemiş'}")
            
            if not self.arac_id.aktif:
                errors.append("Araç aktif değil!")
        
        # 2. Tarih uygunluk kontrolü - KALDIRILDI
        # Tarih kontrolü artık yapılmıyor, kullanıcı istediği tarihi seçebilir
        
        # 3. İlçe-araç uyumluluğu kontrolü
        if self.arac_id and self.ilce_id:
            if self.arac_id.arac_tipi in ['anadolu_yakasi', 'avrupa_yakasi']:
                if self.arac_id.arac_tipi == 'anadolu_yakasi' and self.ilce_id.yaka_tipi == 'avrupa':
                    errors.append("Anadolu Yakası aracı Avrupa Yakası ilçesine gidemez!")
                elif self.arac_id.arac_tipi == 'avrupa_yakasi' and self.ilce_id.yaka_tipi == 'anadolu':
                    errors.append("Avrupa Yakası aracı Anadolu Yakası ilçesine gidemez!")
        
        # 4. Teslimat yöneticisi yetkisi kontrolü
        user = self.env.user
        is_manager = user.has_group('stock.group_stock_manager')
        
        if not is_manager and errors:
            # Yönetici olmayan kullanıcı için ek uyarı
            warnings.append("Bazı hatalar var. Teslimat yöneticisi onayı gerekebilir.")
        
        # Uyarı ve hata mesajlarını göster
        if errors:
            return {
                'warning': {
                    'title': 'Teslimat Hatası',
                    'message': '\n'.join(errors)
                }
            }
        
        if warnings:
            return {
                'warning': {
                    'title': 'Teslimat Uyarısı',
                    'message': '\n'.join(warnings)
                }
            }
    
    def action_hazirla(self):
        """Teslimatı hazır duruma getir"""
        self.write({'durum': 'hazir'})
    
    def action_yola_cik(self):
        """Teslimatı yolda durumuna getir"""
        self.write({'durum': 'yolda'})
    
    def action_teslim_et(self):
        """Teslimatı tamamla"""
        self.write({
            'durum': 'teslim_edildi',
            'gercek_teslimat_saati': fields.Datetime.now()
        })
    
    def action_iptal(self):
        """Teslimatı iptal et"""
        self.write({'durum': 'iptal'})
    
    @api.constrains('arac_id', 'teslimat_tarihi')
    def _check_arac_kapasitesi(self):
        """Araç kapasitesi kontrolü"""
        for record in self:
            if record.arac_id and record.teslimat_tarihi:
                # Aynı gün aynı araç için teslimat sayısını kontrol et
                gunluk_teslimat = self.search_count([
                    ('arac_id', '=', record.arac_id.id),
                    ('teslimat_tarihi', '=', record.teslimat_tarihi),
                    ('durum', 'in', ['hazir', 'yolda']),
                    ('id', '!=', record.id)
                ])
                
                if gunluk_teslimat >= record.arac_id.gunluk_teslimat_limiti:
                    raise ValidationError(_('Bu araç için günlük teslimat limiti aşıldı!'))
    

    
    @api.model
    def default_get(self, fields_list):
        """Context'ten varsayılan değerleri al"""
        defaults = super().default_get(fields_list)
        
        # Context'ten gelen değerleri al
        context = self.env.context
        
        # Tarih alanını context'ten al
        if 'default_teslimat_tarihi' in context and context['default_teslimat_tarihi']:
            try:
                # Tarih string'ini date objesine çevir
                tarih_str = context['default_teslimat_tarihi']
                if isinstance(tarih_str, str):
                    from datetime import datetime
                    tarih_obj = datetime.strptime(tarih_str, '%Y-%m-%d').date()
                    defaults['teslimat_tarihi'] = tarih_obj
                else:
                    defaults['teslimat_tarihi'] = tarih_str
            except:
                defaults['teslimat_tarihi'] = context['default_teslimat_tarihi']
            
        # Araç alanını context'ten al
        if 'default_arac_id' in context and context['default_arac_id']:
            defaults['arac_id'] = context['default_arac_id']
            
        # İlçe alanını context'ten al
        if 'default_ilce_id' in context and context['default_ilce_id']:
            defaults['ilce_id'] = context['default_ilce_id']
            
        return defaults

    @api.model
    def create(self, vals):
        """Teslimat belgesi oluşturulduktan sonra teslimat belgeleri listesine yönlendir"""
        result = super().create(vals)
        
        # Kaydet butonuna basıldığında teslimat belgeleri listesine yönlendir
        if self.env.context.get('from_form'):
            return {
                'type': 'ir.actions.act_window',
                'name': 'Teslimat Belgeleri',
                'res_model': 'teslimat.belgesi',
                'view_mode': 'tree,form',
                'target': 'current',
                'domain': [],
                'context': {},
            }
        
        return result
