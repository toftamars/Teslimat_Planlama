odoo.define('teslimat_planlama.uygun_gunler_click', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        /**
         * One2many tree satırına tıklayınca action_teslimat_olustur çağır
         */
        _onRowClicked: function (ev) {
            // Eğer teslimat.ana.sayfa.gun modelinin tree view'ı ise
            if (this.state && this.state.model === 'teslimat.ana.sayfa.gun') {
                ev.preventDefault();
                ev.stopPropagation();

                var self = this;
                var $row = $(ev.currentTarget);
                var rowId = $row.data('id');

                // Record'u state'den bul
                var record = this.state.data.find(function(r) {
                    return r.id === rowId;
                });

                if (record && record.data) {
                    var tarih = record.data.tarih;
                    var kalan = record.data.kalan_kapasite;

                    // Kapasite yoksa işlem yapma
                    if (kalan <= 0) {
                        return;
                    }

                    // Parent context'ten arac_id ve ilce_id al
                    var parentRecord = this.getParent() && this.getParent().state;
                    if (parentRecord && parentRecord.data) {
                        var arac_id = parentRecord.data.arac_id && parentRecord.data.arac_id.res_id;
                        var ilce_id = parentRecord.data.ilce_id && parentRecord.data.ilce_id.res_id;

                        if (arac_id && ilce_id) {
                            // Wizard'ı aç
                            self.do_action({
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
                        }
                    }
                }
                return;
            }

            // Diğer modeller için normal davranış
            this._super.apply(this, arguments);
        },
    });
});
