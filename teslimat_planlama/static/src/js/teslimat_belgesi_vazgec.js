/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

/**
 * teslimat.belgesi form görünümünde "Vazgeç" (Discard) butonuna basıldığında
 * Teslimat Belgeleri liste ekranına yönlendirir.
 */
patch(FormController.prototype, {
    async discard() {
        const resModel =
            this.model?.root?.resModel ||
            this.props?.resModel ||
            "";

        if (resModel === "teslimat.belgesi") {
            await super.discard(...arguments);
            await this.env.services.action.doAction(
                "teslimat_planlama.action_teslimat_belgesi",
                { clearBreadcrumbs: true }
            );
        } else {
            return super.discard(...arguments);
        }
    },
});
