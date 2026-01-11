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

                var recordId = $(ev.currentTarget).data('id');
                if (recordId) {
                    this._rpc({
                        model: 'teslimat.ana.sayfa.gun',
                        method: 'action_teslimat_olustur',
                        args: [[recordId]],
                    }).then(function (action) {
                        if (action) {
                            this.do_action(action);
                        }
                    }.bind(this));
                }
                return;
            }

            // Diğer modeller için normal davranış
            this._super.apply(this, arguments);
        },
    });
});
