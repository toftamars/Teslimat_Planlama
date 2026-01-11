odoo.define('teslimat_planlama.uygun_gunler_click', function (require) {
    "use strict";

    var core = require('web.core');
    var ListRenderer = require('web.ListRenderer');
    var Dialog = require('web.Dialog');

    ListRenderer.include({
        events: _.extend({}, ListRenderer.prototype.events, {
            'click tbody tr': '_onTeslimatRowClick',
        }),

        _onTeslimatRowClick: function (ev) {
            // Sadece teslimat.ana.sayfa.gun modeli için
            if (!this.state || this.state.model !== 'teslimat.ana.sayfa.gun') {
                return;
            }

            // Button tıklaması ise engelleme
            if ($(ev.target).closest('button').length) {
                return;
            }

            ev.preventDefault();
            ev.stopPropagation();

            var self = this;
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

            var tarih = record.data.tarih;

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

            var arac_id = arac.res_id || arac.data && arac.data.id;
            var ilce_id = ilce.res_id || ilce.data && ilce.data.id;

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
        },
    });
});
