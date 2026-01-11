#!/usr/bin/env python3
"""
Araç-İlçe Eşleştirmelerini Düzelt

Bu script tüm araçların ilçe eşleştirmelerini yeniden hesaplar.
Odoo shell ile çalıştırılmalıdır:

python3 odoo-bin shell -c /path/to/odoo.conf -d database_name < fix_arac_ilce_eslesmesi.py
"""

# Tüm araçları al
araclar = env['teslimat.arac'].search([])
print(f"Toplam {len(araclar)} araç bulundu.")

for arac in araclar:
    print(f"\n{'='*60}")
    print(f"Araç: {arac.name} (Tip: {arac.arac_tipi})")
    print(f"Mevcut uygun ilçe sayısı: {len(arac.uygun_ilceler)}")
    
    # Uygun ilçeleri yeniden hesapla
    arac._update_uygun_ilceler()
    
    print(f"Güncellenen uygun ilçe sayısı: {len(arac.uygun_ilceler)}")
    if arac.uygun_ilceler:
        print(f"İlk 5 uygun ilçe: {', '.join(arac.uygun_ilceler[:5].mapped('name'))}")

# Değişiklikleri kaydet
env.cr.commit()
print(f"\n{'='*60}")
print("✓ Tüm araç-ilçe eşleştirmeleri güncellendi!")
print("✓ Değişiklikler veritabanına kaydedildi.")
