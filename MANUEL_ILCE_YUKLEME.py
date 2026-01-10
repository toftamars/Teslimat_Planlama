# Odoo Python Console'da çalıştırın:
env['teslimat.ilce'].create_istanbul_districts_simple()

# Sonra kontrol edin:
ilceler = env['teslimat.ilce'].search([])
print(f"Toplam ilçe sayısı: {len(ilceler)}")

# İstanbul ilçelerini göster:
istanbul_ilceleri = env['teslimat.ilce'].search([('state_id.name', 'ilike', 'istanbul')])
print(f"İstanbul ilçe sayısı: {len(istanbul_ilceleri)}")
for ilce in istanbul_ilceleri:
    print(f"- {ilce.name}")
