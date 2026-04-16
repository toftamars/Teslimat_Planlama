/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ImageField } from "@web/views/fields/image/image_field";
import { useRef, onMounted, onPatched } from "@odoo/owl";

/**
 * teslimat_fotografi alanı için tıklanınca büyük resim popup'ı açan patch.
 * Odoo 19 ImageField bileşeni üzerine uygulanır.
 */
patch(ImageField.prototype, {
    setup() {
        super.setup(...arguments);
        this.imageRef = useRef("image");

        const attachZoom = () => {
            if (this.props.name !== "teslimat_fotografi") return;
            const img = this.imageRef?.el || document.querySelector(`[name="${this.props.name}"] img`);
            if (!img) return;
            img.style.cursor = "pointer";
            img.title = "Fotoğrafa tıklayarak büyütebilirsiniz";
            img.onclick = (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                this._openZoomDialog(img.src, img.alt || "Teslimat Fotoğrafı");
            };
        };

        onMounted(attachZoom);
        onPatched(attachZoom);
    },

    /**
     * Resmi büyük modal içinde göster.
     * @param {string} src - Resim URL'si
     * @param {string} alt - Resim açıklaması
     */
    _openZoomDialog(src, alt) {
        if (!src) return;
        // Basit tam ekran overlay
        const overlay = document.createElement("div");
        Object.assign(overlay.style, {
            position: "fixed",
            top: "0",
            left: "0",
            width: "100vw",
            height: "100vh",
            backgroundColor: "rgba(0,0,0,0.85)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: "9999",
            cursor: "zoom-out",
        });

        const img = document.createElement("img");
        Object.assign(img.style, {
            maxWidth: "90vw",
            maxHeight: "90vh",
            borderRadius: "8px",
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            objectFit: "contain",
        });
        img.src = src;
        img.alt = alt;

        overlay.appendChild(img);
        overlay.addEventListener("click", () => document.body.removeChild(overlay));
        document.addEventListener("keydown", function closeOnEsc(e) {
            if (e.key === "Escape" && document.body.contains(overlay)) {
                document.body.removeChild(overlay);
                document.removeEventListener("keydown", closeOnEsc);
            }
        });
        document.body.appendChild(overlay);
    },
});
