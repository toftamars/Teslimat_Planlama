odoo.define('teslimat_planlama.uygun_gunler_click', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');
    var Dialog = require('web.Dialog');

    ListRenderer.include({
        /**
         * Override _onRowClicked - sadece teslimat.ana.sayfa.gun için özel davranış
         */
        _onRowClicked: function (ev) {
            // Sadece teslimat.ana.sayfa.gun modeli için özel işlem
            if (this.state && this.state.model === 'teslimat.ana.sayfa.gun') {
                ev.preventDefault();
                ev.stopPropagation();

                var $row = $(ev.currentTarget);
                var rowId = $row.data('id');

                // Record'u bul
                var record = _.find(this.state.data, function(r) {
                    return r.id === rowId;
                });

                if (!record || !record.data) {
                    return;
                }

                console.log('Record data:', record.data);
                console.log('Record data keys:', Object.keys(record.data));

                var kalan = record.data.kalan_kapasite;
                if (kalan <= 0) {
                    Dialog.alert(this, 'Bu tarih için kapasite dolmuştur.');
                    return;
                }

                // Tarih değerini al - farklı field isimlerini dene
                var tarihValue = record.data.tarih || record.data.tarih_str;
                var tarih;

                console.log('Tarih value:', tarihValue);
                console.log('Tarih_str value:', record.data.tarih_str);

                // tarih_str'den tarihi parse et (format: "22.01.2026 Çar")
                if (record.data.tarih_str) {
                    var parts = record.data.tarih_str.split(' ')[0].split('.');
                    if (parts.length === 3) {
                        tarih = parts[2] + '-' + parts[1] + '-' + parts[0]; // YYYY-MM-DD
                    }
                }

                // Eğer tarih hala yoksa, record.data.tarih'i dene
                if (!tarih && tarihValue) {
                    if (tarihValue._isAMomentObject || typeof tarihValue.format === 'function') {
                        tarih = tarihValue.format('YYYY-MM-DD');
                    } else if (typeof tarihValue === 'string') {
                        tarih = tarihValue;
                    } else if (tarihValue instanceof Date) {
                        tarih = tarihValue.toISOString().split('T')[0];
                    } else {
                        tarih = tarihValue.value || String(tarihValue);
                    }
                }

                console.log('Final tarih:', tarih);

                // Parent'ı bul
                var parent = this.getParent();
                while (parent && !parent.state) {
                    parent = parent.getParent();
                }

                if (!parent || !parent.state || !parent.state.data) {
                    return;
                }

                var arac = parent.state.data.arac_id;
                var ilce = parent.state.data.ilce_id;

                console.log('Parent data:', parent.state.data);
                console.log('Araç raw:', arac);
                console.log('İlçe raw:', ilce);

                if (!arac) {
                    Dialog.alert(this, 'Araç seçimi gereklidir.');
                    return;
                }

                // Araç ID'sini al
                var arac_id = arac.res_id || (arac.data && arac.data.id) || arac;

                // İlçe ID'sini al (opsiyonel olabilir)
                var ilce_id = null;
                if (ilce) {
                    ilce_id = ilce.res_id || (ilce.data && ilce.data.id) || ilce;
                }

                console.log('Araç ID:', arac_id);
                console.log('İlçe ID:', ilce_id);

                if (!arac_id) {
                    return;
                }

                // Context oluştur
                var ctx = {
                    default_teslimat_tarihi: tarih,
                    default_arac_id: arac_id,
                };

                if (ilce_id) {
                    ctx.default_ilce_id = ilce_id;
                }

                console.log('Context:', ctx);

                // Wizard'ı aç - context'i farklı yollarla gönder
                this.do_action({
                    name: 'Teslimat Belgesi Oluştur',
                    type: 'ir.actions.act_window',
                    res_model: 'teslimat.belgesi.wizard',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: ctx,
                }, {
                    additional_context: ctx,
                });
                return;
            }

            // Diğer tüm modeller için normal Odoo davranışı
            this._super.apply(this, arguments);
        },
    });
});
