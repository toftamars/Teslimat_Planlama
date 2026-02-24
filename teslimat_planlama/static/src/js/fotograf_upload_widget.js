/**
 * Fotoğraf yükleme widget'ı - İki buton: Fotoğraf Çek (kamera) ve Galeriden Seç.
 * Android 14/15 Chrome'da kamera seçeneği için capture attribute kullanır.
 * iOS ve Android'de tutarlı davranış sağlar.
 */
odoo.define('teslimat_planlama.fotograf_upload_widget', function (require) {
    "use strict";

    var FieldBinaryImage = require('web.basic_fields').FieldBinaryImage;
    var fieldRegistry = require('web.field_registry');

    var FieldBinaryImageCameraGallery = FieldBinaryImage.extend({
        /**
         * Render sonrası: Tek butonu iki butonla değiştir (Fotoğraf Çek + Galeriden Seç)
         */
        _render: function () {
            var result = this._super.apply(this, arguments);

            if (this.mode === 'edit') {
                this._replaceUploadButtons();
            }

            return result;
        },

        /**
         * Varsayılan yükleme butonunu iki butonla değiştir
         */
        _replaceUploadButtons: function () {
            var $buttons = this.$('.o_select_file_button');
            var $originalInput = this.$('.o_input_file').first();

            if (!$buttons.length || !$originalInput.length) {
                return;
            }

            // Orijinal butonu gizle
            $buttons.hide();

            // İki yeni file input: biri capture ile (kamera), biri capture olmadan (galeri)
            var $inputCamera = $('<input>', {
                type: 'file',
                class: 'o_input_file o_input_file_camera',
                accept: 'image/*',
                capture: 'environment',
                style: 'display:none;'
            });
            var $inputGallery = $('<input>', {
                type: 'file',
                class: 'o_input_file o_input_file_gallery',
                accept: 'image/*',
                style: 'display:none;'
            });

            // Change event - parent'ın delegated handler'ı (change .o_input_file) tetiklenir

            // İki buton
            var $btnCamera = $('<button>', {
                type: 'button',
                class: 'btn btn-primary o_select_file_button o_file_camera_btn',
                html: '<i class="fa fa-camera"/> Fotoğraf Çek'
            });
            var $btnGallery = $('<button>', {
                type: 'button',
                class: 'btn btn-secondary o_select_file_button o_file_gallery_btn',
                html: '<i class="fa fa-folder-open-o"/> Galeriden Seç'
            });

            $btnCamera.on('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                $inputCamera.click();
            });
            $btnGallery.on('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                $inputGallery.click();
            });

            // Butonları orijinal butonun yanına ekle
            var $btnContainer = $buttons.first().parent();
            $btnContainer.append($btnCamera).append(' ').append($btnGallery).append($inputCamera).append($inputGallery);
        },
    });

    fieldRegistry.add('image_camera_gallery', FieldBinaryImageCameraGallery);

    return FieldBinaryImageCameraGallery;
});
