"""Araç-İlçe Eşleştirme Senkronizasyon Wizard."""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class TeslimatAracIlceSyncWizard(models.TransientModel):
    """Araç-İlçe eşleştirmelerini senkronize et."""

    _name = "teslimat.arac.ilce.sync.wizard"
    _description = "Araç-İlçe Eşleştirme Senkronizasyonu"

    sonuc_mesaji = fields.Text(string="Sonuç", readonly=True)
    durum = fields.Selection(
        [("hazir", "Hazır"), ("tamamlandi", "Tamamlandı")],
        string="Durum",
        default="hazir",
    )

    def action_sync(self):
        """Tüm araçların ilçe eşleştirmelerini senkronize et."""
        self.ensure_one()

        araclar = self.env["teslimat.arac"].search([])
        guncellenen_sayisi = 0
        sonuc_detay = []

        sonuc_detay.append(f"Toplam {len(araclar)} araç bulundu.\n")
        sonuc_detay.append("=" * 60 + "\n")

        for arac in araclar:
            eski_ilce_sayisi = len(arac.uygun_ilceler)
            
            # Uygun ilçeleri yeniden hesapla
            arac._update_uygun_ilceler()
            
            yeni_ilce_sayisi = len(arac.uygun_ilceler)
            
            if eski_ilce_sayisi != yeni_ilce_sayisi:
                guncellenen_sayisi += 1
                sonuc_detay.append(
                    f"✓ {arac.name} ({arac.arac_tipi}): "
                    f"{eski_ilce_sayisi} → {yeni_ilce_sayisi} ilçe\n"
                )
                
                # İlk 5 ilçeyi göster
                if arac.uygun_ilceler:
                    ilk_ilceler = ', '.join(arac.uygun_ilceler[:5].mapped('name'))
                    sonuc_detay.append(f"  İlk 5 ilçe: {ilk_ilceler}\n")
            else:
                sonuc_detay.append(
                    f"- {arac.name} ({arac.arac_tipi}): "
                    f"Değişiklik yok ({yeni_ilce_sayisi} ilçe)\n"
                )

        sonuc_detay.append("=" * 60 + "\n")
        sonuc_detay.append(
            f"\n✓ İşlem tamamlandı!\n"
            f"✓ {guncellenen_sayisi} araç güncellendi.\n"
            f"✓ {len(araclar) - guncellenen_sayisi} araç zaten günceldi.\n"
        )

        self.write({
            "sonuc_mesaji": "".join(sonuc_detay),
            "durum": "tamamlandi",
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
