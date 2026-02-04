odoo.define('teslimat_planlama.teslimat_belgesi_vazgec', function (require) {
    "use strict";

    var FormController = require('web.FormController');

    FormController.include({
        _onDiscard: function () {
            var self = this;
            var result = this._super.apply(this, arguments);
            if ((this.modelName || (this.state && this.state.model)) === 'teslimat.belgesi') {
                var openList = function () {
                    self.trigger_up('do_action', {
                        action: 'teslimat_planlama.action_teslimat_belgesi',
                        options: { clear_breadcrumbs: true },
                    });
                };
                if (result && typeof result.then === 'function') {
                    result.then(openList);
                } else {
                    openList();
                }
            }
            return result;
        },
    });
});
