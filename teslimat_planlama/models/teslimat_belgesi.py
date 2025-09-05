from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TeslimatBelgesiUrun(models.Model):
    _name = 'teslimat.belgesi.urun'
    _description = 'Teslimat Belgesi Ürünleri'
    _order = 'sequence, id'

    teslimat_belgesi_id = fields.Many2one('teslimat.belgesi', string='Teslimat Belgesi', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sıra', default=10)
    
    # Ürün Bilgileri
    urun_id = fields.Many2one('product.product', string='Ürün', required=True)
    miktar = fields.Float(string='Miktar', required=True)
    birim = fields.Many2one('uom.uom', string='Birim', related='urun_id.uom_id', readonly=True)
    
    # Transfer Bilgileri
    stock_move_id = fields.Many2one('stock.move', string='Transfer Satırı')
    transfer_no = fields.Char(string='Transfer No', related='teslimat_belgesi_id.transfer_no', readonly=True)


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
    musteri_telefon = fields.Char(string='Müşteri Telefon', related='musteri_id.phone', readonly=True)
    
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
    
    # Ürün Bilgileri (Transfer belgesindeki tüm ürünler)
    transfer_urun_ids = fields.One2many('teslimat.belgesi.urun', 'teslimat_belgesi_id', string='Transfer Ürünleri')
    
    # Eski alanlar (geriye uyumluluk için)
    urun_id = fields.Many2one('product.product', string='Ürün', required=False)
    miktar = fields.Float(string='Miktar', required=False)
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
    
    # Teslim Bilgileri
    teslim_alan_kisi = fields.Char(string='Teslim Alan Kişi', help='Ürünü teslim alan kişinin adı')
    teslim_fotografi = fields.Binary(string='Teslim Fotoğrafı', help='Teslimat fotoğrafı (opsiyonel)')
    teslim_fotografi_filename = fields.Char(string='Fotoğraf Dosya Adı')
    
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
    
    @api.onchange('stock_picking_id')
    def _onchange_stock_picking_id(self):
        """Transfer belgesi seçildiğinde durum kontrolü yap"""
        if self.stock_picking_id:
            # Transfer durumu kontrolü
            if self.stock_picking_id.state in ['cancel', 'draft']:
                return {
                    'warning': {
                        'title': 'Transfer Durumu Uyarısı',
                        'message': f'Transfer {self.stock_picking_id.name} durumu "{self.stock_picking_id.state}" olduğu için teslimat belgesi oluşturulamaz!\n\n'
                                 f'Lütfen onaylanmış veya tamamlanmış bir transfer seçin.'
                    }
                }
            
            # Mükerrer teslimat kontrolü
            existing = self.env['teslimat.belgesi'].search([
                ('stock_picking_id', '=', self.stock_picking_id.id)
            ], limit=1)
            if existing:
                return {
                    'warning': {
                        'title': 'Mükerrer Teslimat Uyarısı',
                        'message': f'Transfer {self.stock_picking_id.name} için zaten bir teslimat belgesi mevcut!\n\n'
                                 f'Teslimat No: {existing.name}\n'
                                 f'Durum: {existing.durum}\n\n'
                                 f'Lütfen farklı bir transfer seçin.'
                    }
                }
            
            # Transfer bilgilerini doldur
            if self.stock_picking_id.partner_id:
                self.musteri_id = self.stock_picking_id.partner_id.id
                self.transfer_no = self.stock_picking_id.name
            
            # Transfer belgesindeki tüm ürünleri getir
            self._update_transfer_urunleri()

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
        """İlçe seçildiğinde uygun günleri kontrol et"""
        if not self.ilce_id:
            return
        
        # İlçe için uygun günleri bul (kod ile çalışır)
        uygun_gunler = self.env['teslimat.gun'].get_uygun_gunler(self.ilce_id.id)
        
        if not uygun_gunler:
            return {
                'warning': {
                    'title': 'İlçe Uyarısı',
                    'message': f'{self.ilce_id.name} ilçesi için hiçbir günde teslimat yapılamaz!'
                }
            }
        
        # Eğer tarih seçilmişse, uyumluluğu kontrol et
        if self.teslimat_tarihi:
            availability = self.env['teslimat.gun'].check_availability(
                self.teslimat_tarihi, 
                self.ilce_id.id
            )
            
            if not availability['available']:
                return {
                    'warning': {
                        'title': 'Uyumsuzluk Uyarısı',
                        'message': f'{self.teslimat_tarihi.strftime("%d/%m/%Y")} tarihinde {self.ilce_id.name} ilçesine teslimat yapılamaz!\n\nSebep: {availability["reason"]}\n\nLütfen uygun bir tarih seçin.'
                    }
                }
        
        # Her şey uyumluysa uyarı verme
        return {}
    
    @api.onchange('teslimat_tarihi')
    def _onchange_teslimat_tarihi(self):
        """Teslimat tarihi seçildiğinde ilçe-gün uygunluğunu kontrol et"""
        if not self.teslimat_tarihi or not self.ilce_id:
            return
        
        # Seçilen tarih için ilçe uygunluğunu kontrol et (kod ile çalışır)
        availability = self.env['teslimat.gun'].check_availability(
            self.teslimat_tarihi, 
            self.ilce_id.id
        )
        
        if not availability['available']:
            return {
                'warning': {
                    'title': 'Uyumsuzluk Uyarısı',
                    'message': f'{self.teslimat_tarihi.strftime("%d/%m/%Y")} tarihinde {self.ilce_id.name} ilçesine teslimat yapılamaz!\n\nSebep: {availability["reason"]}\n\nLütfen uygun bir tarih seçin.'
                }
            }
        
        # Her şey uyumluysa uyarı verme
        return {}
    
    @api.onchange('arac_id')
    def _onchange_arac(self):
        """Araç seçildiğinde ilçe uyumluluğunu kontrol et"""
        if not self.arac_id or not self.ilce_id:
            return
        
        # Araç ve ilçe uyumluluğunu kontrol et
        arac_tipi = self.arac_id.arac_tipi
        ilce_yaka = self.ilce_id.yaka_tipi
        
        # Küçük araçlar ve ek araç için kısıtlama yok
        if arac_tipi in ['kucuk_arac_1', 'kucuk_arac_2', 'ek_arac']:
            return {}
        
        # Yaka bazlı araçlar için kısıtlama
        if arac_tipi == 'anadolu_yakasi' and ilce_yaka != 'anadolu':
            return {
                'warning': {
                    'title': 'Uyumsuzluk Uyarısı',
                    'message': f'{self.arac_id.name} aracı sadece Anadolu Yakası ilçelerine gidebilir!\n\n{self.ilce_id.name} ilçesi {ilce_yaka} yakasında.\n\nLütfen uygun bir araç veya ilçe seçin.'
                }
            }
        
        if arac_tipi == 'avrupa_yakasi' and ilce_yaka != 'avrupa':
            return {
                'warning': {
                    'title': 'Uyumsuzluk Uyarısı',
                    'message': f'{self.arac_id.name} aracı sadece Avrupa Yakası ilçelerine gidebilir!\n\n{self.ilce_id.name} ilçesi {ilce_yaka} yakasında.\n\nLütfen uygun bir araç veya ilçe seçin.'
                }
            }
        
        # Her şey uyumluysa uyarı verme
        return {}

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
            # Normal kapasite durumunda uyarı verme
            
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
        """Teslimatı yolda durumuna getir ve müşteriye SMS gönder"""
        self.write({'durum': 'yolda'})
        
        # Müşteriye SMS gönder
        self._send_delivery_sms()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Başarılı',
                'message': f'Teslimat yolda durumuna getirildi ve müşteriye SMS gönderildi! (No: {self.name})',
                'type': 'success',
            }
        }
    
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
        
        # DEBUG: Context'i logla
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"TESLİMAT BELGESİ DEFAULT_GET - Context: {context}")
        
        # Tarih alanını context'ten al
        if 'default_teslimat_tarihi' in context and context['default_teslimat_tarihi']:
            try:
                # Tarih string'ini date objesine çevir
                tarih_str = context['default_teslimat_tarihi']
                _logger.info(f"Tarih string: {tarih_str}, Type: {type(tarih_str)}")
                if isinstance(tarih_str, str):
                    from datetime import datetime
                    tarih_obj = datetime.strptime(tarih_str, '%Y-%m-%d').date()
                    defaults['teslimat_tarihi'] = tarih_obj
                    _logger.info(f"Tarih objesi oluşturuldu: {tarih_obj}")
                else:
                    defaults['teslimat_tarihi'] = tarih_str
            except Exception as e:
                _logger.error(f"Tarih dönüştürme hatası: {e}")
                defaults['teslimat_tarihi'] = context['default_teslimat_tarihi']
            
        # Araç alanını context'ten al
        if 'default_arac_id' in context and context['default_arac_id']:
            defaults['arac_id'] = context['default_arac_id']
            _logger.info(f"Araç ID set edildi: {context['default_arac_id']}")
            
        # İlçe alanını context'ten al
        if 'default_ilce_id' in context and context['default_ilce_id']:
            defaults['ilce_id'] = context['default_ilce_id']
            _logger.info(f"İlçe ID set edildi: {context['default_ilce_id']}")
        
        _logger.info(f"Final defaults: {defaults}")
        return defaults

    @api.constrains('arac_id', 'teslimat_tarihi')
    def _check_arac_gunluk_limit(self):
        """Her araç günlük maksimum 7 teslimat yapabilir"""
        for record in self:
            if record.arac_id and record.teslimat_tarihi:
                # Pazar günü teslimat yapılamaz kontrolü
                if record.teslimat_tarihi.weekday() == 6:  # 6 = Pazar
                    raise ValidationError(
                        f"Pazar günü teslimat yapılamaz! {record.teslimat_tarihi} tarihi pazar günüdür."
                    )
                
                # Aynı araç ve tarihte kaç teslimat var
                mevcut_teslimat_sayisi = self.search_count([
                    ('arac_id', '=', record.arac_id.id),
                    ('teslimat_tarihi', '=', record.teslimat_tarihi),
                    ('id', '!=', record.id)  # Kendisi hariç
                ])
                
                if mevcut_teslimat_sayisi >= 7:
                    raise ValidationError(
                        f"Seçtiğiniz tarih ve araç için günlük teslimat limiti dolmuştur.\n\n"
                        f"Araç: {record.arac_id.name}\n"
                        f"Tarih: {record.teslimat_tarihi}\n"
                        f"Mevcut Teslimat: {mevcut_teslimat_sayisi}/7\n\n"
                        f"Lütfen farklı bir tarih veya araç seçin."
                    )

    @api.model
    def create(self, vals):
        """Teslimat belgesi oluşturulduktan sonra belge no atar, durumu hazır yapar"""
        # Transfer belgesi durumu kontrolü
        if vals.get('stock_picking_id'):
            picking = self.env['stock.picking'].browse(vals['stock_picking_id'])
            if picking.state in ['cancel', 'draft']:
                raise ValidationError(_(f"Transfer {picking.name} durumu '{picking.state}' olduğu için teslimat belgesi oluşturulamaz!\n\nLütfen onaylanmış veya tamamlanmış bir transfer seçin."))
            
            # Mükerrer teslimat kontrolü
            existing = self.env['teslimat.belgesi'].search([
                ('stock_picking_id', '=', vals['stock_picking_id'])
            ], limit=1)
            if existing:
                raise ValidationError(_(f"Transfer {picking.name} için zaten bir teslimat belgesi mevcut!\n\n"
                                      f"Teslimat No: {existing.name}\n"
                                      f"Durum: {existing.durum}\n\n"
                                      f"Lütfen farklı bir transfer seçin."))
        
        # Belge no otomatik oluştur
        if vals.get('name', _('Yeni')) == _('Yeni'):
            vals['name'] = self.env['ir.sequence'].next_by_code('teslimat.belgesi') or _('Yeni')
        
        # Durum otomatik olarak 'hazır' yapılır
        vals['durum'] = 'hazir'
        
        result = super().create(vals)
        
        # Transfer ürünlerini güncelle
        if result.stock_picking_id:
            result._update_transfer_urunleri()
        
        # Teslimat planlandığında müşteriye SMS gönder
        if result.musteri_id and result.musteri_id.phone:
            result._send_planning_sms()
        
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
    
    def _update_transfer_urunleri(self):
        """Transfer belgesindeki tüm ürünleri teslimat belgesine getir"""
        if not self.stock_picking_id:
            return
        
        # Mevcut ürünleri temizle
        self.transfer_urun_ids = [(5, 0, 0)]
        
        # Transfer belgesindeki tüm ürünleri getir
        urun_listesi = []
        for move in self.stock_picking_id.move_ids_without_package:
            if move.product_id and move.product_uom_qty > 0:
                urun_listesi.append((0, 0, {
                    'urun_id': move.product_id.id,
                    'miktar': move.product_uom_qty,
                    'stock_move_id': move.id,
                    'sequence': move.sequence or 10
                }))
        
        self.transfer_urun_ids = urun_listesi
    
    def action_yol_tarifi(self):
        """Müşteri adresine yol tarifi aç ve SMS gönder"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== YOL TARİFİ BUTONUNA BASILDI ===")
        _logger.info(f"Müşteri: {self.musteri_id.name if self.musteri_id else 'YOK'}")
        _logger.info(f"Telefon: {self.musteri_id.phone if self.musteri_id else 'YOK'}")
        _logger.info(f"Adres: {self.musteri_id.street if self.musteri_id else 'YOK'}")
        
        if not self.musteri_id or not self.musteri_id.street:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Uyarı',
                    'message': 'Müşteri adresi bulunamadı!',
                    'type': 'warning',
                }
            }
        
        # Müşteriye SMS gönder
        if self.musteri_id.phone:
            _logger.info("SMS GÖNDERİLİYOR - Yol Tarifi")
            self._send_delivery_sms()
        else:
            _logger.warning("SMS GÖNDERİLEMEDİ - Telefon numarası yok!")
        
        # Adres bilgisini hazırla
        adres = f"{self.musteri_id.street or ''}"
        if self.musteri_id.street2:
            adres += f", {self.musteri_id.street2}"
        if self.musteri_id.city:
            adres += f", {self.musteri_id.city}"
        if self.musteri_id.zip:
            adres += f" {self.musteri_id.zip}"
        
        # Google Maps URL oluştur
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={adres}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': maps_url,
            'target': 'new',
        }
    
    def action_teslimat_tamamla(self):
        """Sürücü teslimatı tamamlar"""
        self.ensure_one()
        
        # Sürücü yetkisi kontrolü
        if not self._check_surucu_yetkisi():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Yetki Hatası',
                    'message': 'Bu işlem için sürücü yetkisine sahip olmalısınız!',
                    'type': 'danger',
                }
            }
        
        # Teslimat durumu kontrolü
        if self.durum not in ['hazir', 'yolda']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Durum Hatası',
                    'message': 'Sadece hazır veya yolda durumundaki teslimatlar tamamlanabilir!',
                    'type': 'warning',
                }
            }
        
        return {
            'name': 'Teslimat Tamamla',
            'type': 'ir.actions.act_window',
            'res_model': 'teslimat.belgesi',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('teslimat_planlama.view_teslimat_belgesi_tamamla_form').id,
            'target': 'new',
            'context': {
                'default_id': self.id,
                'form_view_initial_mode': 'edit'
            }
        }
    
    def _check_surucu_yetkisi(self):
        """Kullanıcının sürücü yetkisi olup olmadığını kontrol et"""
        # Sürücü grubu kontrolü - doğru grup adı
        if self.env.user.has_group('teslimat_planlama.group_teslimat_driver'):
            return True
        
        # Alternatif: is_driver field kontrolü
        if hasattr(self.env.user.partner_id, 'is_driver') and self.env.user.partner_id.is_driver:
            return True
        
        # Debug için log
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"SÜRÜCÜ YETKİ KONTROLÜ - Kullanıcı: {self.env.user.name}, Gruplar: {[g.name for g in self.env.user.groups_id]}")
        
        return False
    
    def action_teslimat_tamamla_kaydet(self):
        """Teslimat tamamlama bilgilerini kaydet"""
        self.ensure_one()
        
        # Teslim alan kişi kontrolü
        if not self.teslim_alan_kisi or not self.teslim_alan_kisi.strip():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Hata',
                    'message': 'Teslim alan kişi bilgisi zorunludur!',
                    'type': 'danger',
                }
            }
        
        # Debug log
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"TESLİMAT TAMAMLA KAYDET - Mevcut veriler:")
        _logger.info(f"teslim_alan_kisi: {self.teslim_alan_kisi}")
        _logger.info(f"teslim_fotografi var mı: {bool(self.teslim_fotografi)}")
        _logger.info(f"teslim_fotografi_filename: {self.teslim_fotografi_filename}")
        
        # Güncellenecek veriler
        update_vals = {
            'durum': 'teslim_edildi',
            'gercek_teslimat_saati': fields.Datetime.now(),
            'teslim_alan_kisi': self.teslim_alan_kisi
        }
        
        # Fotoğraf bilgilerini ekle
        if self.teslim_fotografi:
            update_vals['teslim_fotografi'] = self.teslim_fotografi
            update_vals['teslim_fotografi_filename'] = self.teslim_fotografi_filename or 'teslimat_foto.jpg'
        
        # Veritabanına kaydet
        self.write(update_vals)
        
        # Teslimat tamamlandığında müşteriye SMS gönder
        if self.musteri_id and self.musteri_id.phone:
            _logger.info("SMS GÖNDERİLİYOR - Teslimat Tamamlandı")
            self._send_completion_sms()
        else:
            _logger.warning("SMS GÖNDERİLEMEDİ - Müşteri veya telefon numarası yok!")
        
        # Debug: Kaydedilen verileri kontrol et
        self.refresh()
        _logger.info(f"Kaydedilen veriler - teslim_alan_kisi: {self.teslim_alan_kisi}")
        _logger.info(f"Kaydedilen veriler - teslim_fotografi var mı: {bool(self.teslim_fotografi)}")
        _logger.info(f"Kaydedilen veriler - teslim_fotografi_filename: {self.teslim_fotografi_filename}")
        
        # Ana teslimat belgesi formuna yönlendir
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teslimat Belgesi',
            'res_model': 'teslimat.belgesi',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {}
        }
    
    def _send_delivery_sms(self):
        """Müşteriye teslimat SMS'i gönder"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== _send_delivery_sms ÇAĞRILDI ===")
        
        if not self.musteri_id or not self.musteri_id.phone:
            _logger.warning("SMS GÖNDERİLEMEDİ - Müşteri veya telefon yok!")
            return
        
        # Tahmini süre hesaplama (basit hesaplama - gerçek uygulamada Google Maps API kullanılabilir)
        tahmini_sure = self._calculate_estimated_time()
        
        # SMS metni oluştur
        sms_text = self._generate_sms_text(tahmini_sure)
        
        # SMS gönder (şimdilik log'a yaz - gerçek uygulamada SMS gateway kullanılır)
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"SMS GÖNDERİLDİ - Müşteri: {self.musteri_id.name}, Telefon: {self.musteri_id.phone}")
        _logger.info(f"SMS İçeriği: {sms_text}")
        
        # Gerçek SMS gönderme (SMS gateway entegrasyonu burada yapılır)
        self._send_real_sms(self.musteri_id.phone, sms_text)
    
    def _calculate_estimated_time(self):
        """Tahmini varış süresini hesapla"""
        # Basit hesaplama - gerçek uygulamada Google Maps API kullanılabilir
        # Şimdilik sabit değer döndürüyoruz
        return "15-20"
    
    def _generate_sms_text(self, tahmini_sure):
        """SMS metnini oluştur"""
        musteri_adi = self.musteri_id.name or "Değerli Müşterimiz"
        arac_adi = self.arac_id.name or "Teslimat Aracı"
        surucu_adi = self.surucu_id.name if self.surucu_id else "Sürücümüz"
        
        sms_text = f"""Merhaba {musteri_adi},
Teslimatınız yola çıktı! 
Tahmini varış süresi: {tahmini_sure} dakika
Araç: {arac_adi}
Sürücü: {surucu_adi}
İyi günler,
Teslimat Ekibi"""
        
        return sms_text
    
    def _send_planning_sms(self):
        """Teslimat planlandığında müşteriye SMS gönder"""
        if not self.musteri_id or not self.musteri_id.phone:
            return
        
        # SMS metni oluştur
        sms_text = self._generate_planning_sms_text()
        
        # SMS gönder (şimdilik log'a yaz)
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"PLANLAMA SMS GÖNDERİLDİ - Müşteri: {self.musteri_id.name}, Telefon: {self.musteri_id.phone}")
        _logger.info(f"PLANLAMA SMS İçeriği: {sms_text}")
        
        # Gerçek SMS gönderme
        self._send_real_sms(self.musteri_id.phone, sms_text)
    
    def _send_completion_sms(self):
        """Teslimat tamamlandığında müşteriye SMS gönder"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== _send_completion_sms ÇAĞRILDI ===")
        
        if not self.musteri_id or not self.musteri_id.phone:
            _logger.warning("SMS GÖNDERİLEMEDİ - Müşteri veya telefon yok!")
            return
        
        # SMS metni oluştur
        sms_text = self._generate_completion_sms_text()
        
        # SMS gönder (şimdilik log'a yaz)
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"TAMAMLAMA SMS GÖNDERİLDİ - Müşteri: {self.musteri_id.name}, Telefon: {self.musteri_id.phone}")
        _logger.info(f"TAMAMLAMA SMS İçeriği: {sms_text}")
        
        # Gerçek SMS gönderme
        self._send_real_sms(self.musteri_id.phone, sms_text)
    
    def _generate_planning_sms_text(self):
        """Teslimat planlama SMS metnini oluştur"""
        musteri_adi = self.musteri_id.name or "Değerli Müşterimiz"
        tarih = self.teslimat_tarihi.strftime("%d/%m/%Y") if self.teslimat_tarihi else "Belirtilen tarihte"
        
        sms_text = f"""Merhaba {musteri_adi},
Teslimatınız {tarih} tarihinde planlanmıştır.
Teslimat No: {self.name}
İyi günler,
Teslimat Ekibi"""
        
        return sms_text
    
    def _generate_completion_sms_text(self):
        """Teslimat tamamlama SMS metnini oluştur"""
        musteri_adi = self.musteri_id.name or "Değerli Müşterimiz"
        teslim_alan = self.teslim_alan_kisi or "Belirtilmemiş"
        teslim_tarihi = self.gercek_teslimat_saati.strftime("%d/%m/%Y %H:%M") if self.gercek_teslimat_saati else "Bugün"
        
        sms_text = f"""Merhaba {musteri_adi},
Teslimat ve kurulumunuz tamamlanmıştır.
Teslim Alan: {teslim_alan}
Teslim Tarihi: {teslim_tarihi}
Teslimat No: {self.name}
İyi günler,
Teslimat Ekibi"""
        
        return sms_text
    
    def _send_real_sms(self, phone_number, message):
        """Gerçek SMS gönderme (Netgsm entegrasyonu)"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"=== _send_real_sms BAŞLADI ===")
        _logger.info(f"Telefon: {phone_number}")
        _logger.info(f"Mesaj: {message[:100]}...")
        
        try:
            # Netgsm SMS gönderme
            sms_model = self.env['sms.sms']
            _logger.info(f"SMS Model: {sms_model}")
            
            # SMS oluştur
            sms_vals = {
                'number': phone_number,
                'body': message,
                'partner_id': self.musteri_id.id if self.musteri_id else False,
            }
            _logger.info(f"SMS Vals: {sms_vals}")
            
            sms = sms_model.create(sms_vals)
            _logger.info(f"SMS Oluşturuldu - ID: {sms.id}")
            
            # SMS'i gönder
            _logger.info("SMS.send() çağrılıyor...")
            sms.send()
            _logger.info("SMS.send() tamamlandı")
            
            # SMS durumunu kontrol et
            sms.refresh()
            _logger.info(f"SMS Durumu: {sms.state}")
            
            # Debug log
            _logger.info(f"✅ NETGSM SMS GÖNDERİLDİ - Telefon: {phone_number}")
            _logger.info(f"SMS ID: {sms.id}, Durum: {sms.state}")
            
        except Exception as e:
            # Hata durumunda log'a yaz
            _logger.error(f"❌ NETGSM SMS GÖNDERME HATASI - Telefon: {phone_number}")
            _logger.error(f"Hata: {str(e)}")
            _logger.error(f"Hata Tipi: {type(e)}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
