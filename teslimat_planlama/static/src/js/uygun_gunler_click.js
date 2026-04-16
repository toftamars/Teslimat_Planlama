/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

/**
 * teslimat.ana.sayfa.gun modeline ait liste satırlarına özel tıklama davranışı ekler.
 * Bir satıra tıklandığında tarih, araç ve ilçe bilgileriyle teslimat belgesi wizard'ı açılır.
 */
patch(ListRenderer.prototype, {
    /**
     * Satır tıklama olayını işler.
     * Sadece teslimat.ana.sayfa.gun modeli için özel davranış gösterir.
     */
    async onClickRecord(record) {
        const resModel = this.props.list?.resModel || this.props.list?.model?.resModel;

        if (resModel !== "teslimat.ana.sayfa.gun") {
            return super.onClickRecord(...arguments);
        }

        // Kapalı araç kontrolü
        if (record.data.arac_kapali_mi) {
            this.env.services.notification.add(
                "Durum kapalı ise teslimat oluşturulamaz!",
                { type: "warning" }
            );
            return;
        }

        // Kapasite kontrolü
        const kalanKapasite = record.data.kalan_kapasite;
        if (kalanKapasite <= 0) {
            this.env.services.notification.add(
                "Bu tarih için kapasite dolmuştur.",
                { type: "warning" }
            );
            return;
        }

        // Tarih: tarih_str alanından (DD.MM.YYYY Gün formatı) veya doğrudan tarih alanından al
        let tarih = null;
        const tarihStr = record.data.tarih_str || "";
        if (tarihStr) {
            const parts = tarihStr.split(" ")[0].split(".");
            if (parts.length === 3) {
                tarih = `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
        }
        if (!tarih && record.data.tarih) {
            tarih = record.data.tarih;
        }
        if (!tarih) {
            this.env.services.notification.add(
                "Tarih bilgisi alınamadı.",
                { type: "danger" }
            );
            return;
        }

        // Ana Sayfa kaydının res_id'sini bul (üst view'dan)
        let anaSayfaResId = null;
        try {
            const parentModel = this.props.list?.model;
            if (parentModel?.root?.resId) {
                anaSayfaResId = parentModel.root.resId;
            }
        } catch (_) {}

        // Araç ve ilçe: parent (ana sayfa) kaydından al
        let aracId = null;
        let ilceId = null;
        try {
            const parentRecord = this.props.list?.model?.root;
            if (parentRecord?.data) {
                const aracField = parentRecord.data.arac_id;
                const ilceField = parentRecord.data.ilce_id;
                aracId = Array.isArray(aracField) ? aracField[0] : (aracField?.id ?? aracField);
                ilceId = Array.isArray(ilceField) ? ilceField[0] : (ilceField?.id ?? ilceField ?? false);
            }
        } catch (_) {}

        if (!aracId) {
            this.env.services.notification.add(
                "Araç bilgisi alınamadı. Lütfen araç seçin.",
                { type: "warning" }
            );
            return;
        }

        const context = {
            default_teslimat_tarihi: tarih,
            default_arac_id: aracId,
            default_ilce_id: ilceId || false,
            default_ana_sayfa_res_id: anaSayfaResId || false,
        };

        await this.env.services.action.doAction({
            name: "Teslimat Belgesi Oluştur",
            type: "ir.actions.act_window",
            res_model: "teslimat.belgesi.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context,
        });
    },
});
