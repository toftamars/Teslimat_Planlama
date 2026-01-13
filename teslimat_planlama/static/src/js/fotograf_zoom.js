odoo.define('teslimat_planlama.fotograf_zoom', function (require) {
    "use strict";

    var FormRenderer = require('web.FormRenderer');
    var Dialog = require('web.Dialog');

    FormRenderer.include({
        /**
         * Image field'a tıklanınca modal popup aç
         */
        _onImageClick: function (ev) {
            var $target = $(ev.currentTarget);
            var $img = $target.find('img');
            
            // Sadece teslimat_fotografi field'ı için
            if (!$target.closest('[name="teslimat_fotografi"]').length) {
                return this._super.apply(this, arguments);
            }

            ev.preventDefault();
            ev.stopPropagation();

            if (!$img.length || !$img.attr('src')) {
                return;
            }

            var imgSrc = $img.attr('src');
            var imgAlt = $img.attr('alt') || 'Teslimat Fotoğrafı';

            // Modal dialog oluştur
            var dialog = new Dialog(this, {
                title: imgAlt,
                size: 'large',
                $content: $('<div class="text-center" style="padding: 20px;">')
                    .append($('<img>')
                        .attr('src', imgSrc)
                        .attr('alt', imgAlt)
                        .css({
                            'max-width': '100%',
                            'max-height': '80vh',
                            'height': 'auto',
                            'width': 'auto',
                            'cursor': 'zoom-out',
                            'border-radius': '8px',
                            'box-shadow': '0 4px 8px rgba(0,0,0,0.2)'
                        })
                    ),
                buttons: [
                    {
                        text: 'Kapat',
                        classes: 'btn-secondary',
                        close: true
                    }
                ]
            });

            dialog.open();

            // Modal içindeki resme tıklanınca kapat
            dialog.$content.find('img').on('click', function() {
                dialog.close();
            });
        },

        /**
         * Image field render edildiğinde click event ekle
         */
        _renderField: function (node) {
            var result = this._super.apply(this, arguments);
            
            if (node.tag === 'field' && node.attrs.widget === 'image') {
                var fieldName = node.attrs.name;
                
                // Sadece teslimat_fotografi için
                if (fieldName === 'teslimat_fotografi') {
                    var self = this;
                    this.$el.find('[name="' + fieldName + '"]').each(function() {
                        var $field = $(this);
                        var $img = $field.find('img');
                        
                        if ($img.length) {
                            // Cursor pointer yap
                            $img.css('cursor', 'pointer');
                            $img.attr('title', 'Fotoğrafa tıklayarak büyütebilirsiniz');
                            
                            // Click event ekle
                            $img.off('click.zoom').on('click.zoom', function(ev) {
                                ev.preventDefault();
                                ev.stopPropagation();
                                self._onImageClick(ev);
                            });
                        }
                    });
                }
            }
            
            return result;
        }
    });
});
