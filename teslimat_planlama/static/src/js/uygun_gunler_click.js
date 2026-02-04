odoo.define('teslimat_planlama.uygun_gunler_click', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');
    var Dialog = require('web.Dialog');

    ListRenderer.include({
        /**
         * Extracts the ID from a Many2one field value.
         * Handles various Many2one value formats returned by Odoo.
         *
         * @private
         * @param {*} value - Many2one field value (can be number, array, object, etc.)
         * @returns {number|null} The extracted ID or null if not found
         */
        _extractMany2oneId: function (value) {
            if (!value) {
                return null;
            }

            // Direct numeric ID
            if (typeof value === 'number') {
                return value;
            }

            // Array format: [id, name]
            if (Array.isArray(value) && value.length > 0) {
                return value[0];
            }

            // Object with res_id property
            if (value.res_id) {
                return value.res_id;
            }

            // Nested data object with id
            if (value.data && value.data.id) {
                return value.data.id;
            }

            // Object with id property
            if (typeof value === 'object' && value.id !== undefined) {
                return value.id;
            }

            return value;
        },

        /**
         * Parses date from various formats to YYYY-MM-DD string format.
         * Supports: tarih_str (DD.MM.YYYY format), Moment objects, Date objects, and string dates.
         *
         * @private
         * @param {Object} recordData - The record data object containing date fields
         * @returns {string|null} Formatted date string (YYYY-MM-DD) or null if parsing fails
         */
        _parseDateFromRecord: function (recordData) {
            var tarihValue = recordData.tarih || recordData.tarih_str;
            var tarih = null;

            // Parse from tarih_str field (format: "22.01.2026 Çar")
            if (recordData.tarih_str) {
                try {
                    var parts = recordData.tarih_str.split(' ')[0].split('.');
                    if (parts.length === 3) {
                        // Convert DD.MM.YYYY to YYYY-MM-DD
                        tarih = parts[2] + '-' + parts[1] + '-' + parts[0];
                    }
                } catch (error) {
                    console.error('Tarih parse hatası:', error);
                }
            }

            // Fallback to other date formats if tarih_str parsing failed
            if (!tarih && tarihValue) {
                try {
                    // Moment object
                    if (tarihValue._isAMomentObject || typeof tarihValue.format === 'function') {
                        tarih = tarihValue.format('YYYY-MM-DD');
                    }
                    // String date
                    else if (typeof tarihValue === 'string') {
                        tarih = tarihValue;
                    }
                    // JavaScript Date object
                    else if (tarihValue instanceof Date) {
                        tarih = tarihValue.toISOString().split('T')[0];
                    }
                    // Object with value property
                    else {
                        tarih = tarihValue.value || String(tarihValue);
                    }
                } catch (error) {
                    console.error('Tarih dönüştürme hatası:', error);
                }
            }

            return tarih;
        },

        /**
         * Finds the parent form controller for teslimat.ana.sayfa model.
         * Traverses up the widget tree to locate the parent form.
         *
         * @private
         * @returns {Object|null} Parent controller or null if not found
         */
        _findParentForm: function () {
            var parent = this.getParent();
            while (parent) {
                var model = parent.state && (parent.state.model || parent.state.resModel);
                if (model === 'teslimat.ana.sayfa' && parent.state && parent.state.data) {
                    return parent;
                }
                parent = parent.getParent && parent.getParent();
            }
            return null;
        },

        /**
         * Override _onRowClicked for custom behavior on teslimat.ana.sayfa.gun model.
         * When a row is clicked, creates a delivery document wizard with pre-filled values
         * from the selected date row and parent form (arac_id and ilce_id).
         *
         * @override
         * @private
         * @param {Event} ev - Click event object
         */
        _onRowClicked: function (ev) {
            // Apply custom logic only for teslimat.ana.sayfa.gun model
            if (this.state && this.state.model === 'teslimat.ana.sayfa.gun') {
                ev.preventDefault();
                ev.stopPropagation();

                var $row = $(ev.currentTarget);
                var rowId = $row.data('id');

                // Find the clicked record
                var record = _.find(this.state.data, function(r) {
                    return r.id === rowId;
                });

                if (!record || !record.data) {
                    return;
                }

                // Kapalı güne tıklanırsa wizard açma, uyarı göster
                if (record.data.arac_kapali_mi) {
                    Dialog.alert(this, 'Durum kapalı ise teslimat oluşturulamaz!');
                    return;
                }

                // Check remaining capacity
                var kalanKapasite = record.data.kalan_kapasite;
                if (kalanKapasite <= 0) {
                    Dialog.alert(this, 'Bu tarih için kapasite dolmuştur.');
                    return;
                }

                // Parse date from record
                var tarih = this._parseDateFromRecord(record.data);
                if (!tarih) {
                    Dialog.alert(this, 'Tarih bilgisi alınamadı.');
                    return;
                }

                // Find parent form (teslimat.ana.sayfa)
                var parentForm = this._findParentForm();
                if (!parentForm || !parentForm.state || !parentForm.state.data) {
                    Dialog.alert(this, 'Ana form bilgisi alınamadı.');
                    return;
                }

                // Ana Sayfa formundaki Araç ve İlçe (bazen state.data tek kayıt, bazen liste)
                var formData = parentForm.state.data;
                if (Array.isArray(formData) && formData.length > 0) {
                    formData = formData[0];
                }
                var aracField = formData.arac_id;
                var ilceField = formData.ilce_id;

                // Validate vehicle selection
                if (!aracField) {
                    Dialog.alert(this, 'Araç seçimi gereklidir.');
                    return;
                }

                // Extract IDs from Many2one fields (İlçe wizard'da otomatik atanacak)
                var aracId = this._extractMany2oneId(aracField);
                var ilceId = this._extractMany2oneId(ilceField);
                if (ilceId && typeof ilceId !== 'number') {
                    ilceId = parseInt(ilceId, 10) || null;
                }

                if (!aracId) {
                    Dialog.alert(this, 'Araç bilgisi alınamadı.');
                    return;
                }

                // Wizard context: tarih, araç ve Ana Sayfa'daki İlçe mutlaka geçirilir
                var context = {
                    default_teslimat_tarihi: tarih,
                    default_arac_id: aracId,
                    default_ilce_id: ilceId || false,
                };

                // Open teslimat belgesi wizard with pre-filled values
                this.do_action({
                    name: 'Teslimat Belgesi Oluştur',
                    type: 'ir.actions.act_window',
                    res_model: 'teslimat.belgesi.wizard',
                    view_mode: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: context,
                }, {
                    additional_context: context,
                });

                return;
            }

            // Default Odoo behavior for all other models
            this._super.apply(this, arguments);
        },
    });
});
