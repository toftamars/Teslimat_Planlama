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

                var kalan = record.data.kalan_kapasite;
                if (kalan <= 0) {
                    Dialog.alert(this, 'Bu tarih için kapasite dolmuştur.');
                    return;
                }

                // Tarih değerini al - moment objesi veya string olabilir
                var tarihValue = record.data.tarih;
                var tarih;

                if (tarihValue) {
                    // Moment objesi ise string'e çevir
                    if (tarihValue._isAMomentObject || typeof tarihValue.format === 'function') {
                        tarih = tarihValue.format('YYYY-MM-DD');
                    } else if (typeof tarihValue === 'string') {
                        tarih = tarihValue;
                    } else if (tarihValue instanceof Date) {
                        tarih = tarihValue.toISOString().split('T')[0];
                    } else {
                        // Objeden value al
                        tarih = tarihValue.value || tarihValue;
                    }
                }

                console.log('Tıklanan satır tarihi:', tarih, 'Raw:', tarihValue);

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

                if (!arac || !ilce) {
                    Dialog.alert(this, 'Araç ve ilçe seçimi gereklidir.');
                    return;
                }

                var arac_id = arac.res_id || (arac.data && arac.data.id);
                var ilce_id = ilce.res_id || (ilce.data && ilce.data.id);

                if (!arac_id || !ilce_id) {
                    return;
                }

                // Wizard'ı aç
                this.do_action({
                    name: 'Teslimat Belgesi Oluştur',
                    type: 'ir.actions.act_window',
                    res_model: 'teslimat.belgesi.wizard',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: {
                        default_teslimat_tarihi: tarih,
                        default_arac_id: arac_id,
                        default_ilce_id: ilce_id,
                    },
                });
                return;
            }

            // Diğer tüm modeller için normal Odoo davranışı
            this._super.apply(this, arguments);
        },
    });
});
