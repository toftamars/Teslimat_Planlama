# Google Maps API — Trafik Rota Sıralama

Teslimat Planlama modülündeki **trafik sıralaması** (Odoo `sira_no` güncelleme) **Google Routes API — Compute Route Matrix (Pro)** kullanır. Ücretsiz URL ile açılan **Yol Tarifi** / **Rota Optimizasyonu** haritaları API anahtarı **gerektirmez**; yalnızca otomatik sıralama gerektirir.

> **Distance Matrix API (Legacy):** Mart 2025 itibarıyla legacy statüde. Yeni kurulumlarda **Routes API** kullanın.

---

## Nereden alınır?

1. [Google Cloud Console](https://console.cloud.google.com/) → proje oluşturun veya seçin.
2. **APIs & Services → Library** → **Routes API** etkinleştirin.
3. **APIs & Services → Credentials** → **Create credentials → API key**.
4. Anahtarı kısıtlayın:
   - Application restrictions: IP (Odoo sunucu IP’si) önerilir
   - API restrictions: yalnızca **Routes API**
5. **Billing** hesabı bağlayın (kredi kartı). Ücretsiz kota sonrası kullandıkça ödeme.

Resmi fiyat listesi: [Google Maps Platform Pricing](https://developers.google.com/maps/billing-and-pricing/pricing)

---

## Odoo’ya tanımlama

**Ayarlar → Teknik → Parametreler → Sistem Parametreleri**

| Anahtar | Açıklama |
|---------|----------|
| `teslimat_planlama.google_maps_api_key` | Google API anahtarı |
| `teslimat_planlama.rota_baslangic_adres` | Depo/çıkış adresi (varsayılan: İstanbul, Türkiye) |

Modül kurulumunda boş anahtar kaydı oluşturulur (`maps_parameter_data.xml`). Anahtar girilene kadar trafik cron’u sessizce atlanır.

---

## Maliyet (Compute Route Matrix **Pro** — trafik duyarlı)

**Faturalama birimi:** *element* = `origins × destinations`

Her sıralama: `(N teslimat + 1 depo)²` element  
Örnek: 7 teslimat → 8×8 = **64 element / sıralama**

| Aylık ücretsiz (Pro) | Sonrası fiyat |
|----------------------|---------------|
| **5.000 element** | **10 USD / 1.000 element** |

### Tahmini aylık maliyet (22 iş günü)

| Senaryo | Sıralama/gün | Element/ay | Ücretsiz sonrası | Tahmini maliyet |
|---------|--------------|------------|------------------|-----------------|
| 3 araç × 5 teslimat (6²=36) | 3 | ~2.376 | 0 | **0 USD** |
| 5 araç × 7 teslimat (8²=64) | 5 | ~7.040 | ~2.040 | **~21 USD/ay** |
| 10 araç × 7 teslimat | 10 | ~14.080 | ~9.080 | **~91 USD/ay** |
| Manuel 5 ek sıralama/gün (aynı 5 araç) | 10 | ~14.080 | ~9.080 | **~91 USD/ay** |

Cron günde **1 kez** (05:30) + liste aksiyonu **🚦 Trafik Sırasına Göre Sırala** + rota öncesi otomatik sıralama ek API çağrısı yapabilir — sık manuel kullanım maliyeti artırır.

**Essentials** SKU (trafiksiz): 10.000 ücretsiz element, 5 USD/1.000 — daha ucuz ama **anlık trafik yok**.

---

## Modülde otomatik sıralama nasıl çalışır?

1. **Cron (05:30):** Bugünkü **Hazır/Yolda** teslimatlar araç bazında sıralanır → `sira_no` yazılır.
2. **Liste aksiyonu:** 🚦 Trafik Sırasına Göre Sırala (aynı araç + aynı gün seçimi).
3. **Rota Optimizasyonu:** Aynı araç+gün seçiminde önce trafik sıralaması, sonra Google Maps açılır.
4. **Liste görünümü:** `sira_no` kolonu, varsayılan sıralama `sira_no`.

Algoritma: depodan başlayan açık TSP (tüm duraklar ziyaret, dönüş yok); brute-force (max 7 teslimat = 5040 permütasyon).

---

## Sorun giderme

| Belirti | Kontrol |
|---------|---------|
| Cron çalışmıyor | API key boş mu? Odoo log: `Trafik rota cron: API anahtarı yok` |
| HTTP 403 | Routes API etkin mi? Faturalandırma açık mı? |
| Adres bulunamadı | `prepare_maps_destination` çıktısını Google Maps’te manuel deneyin |
| Sıra değişmedi | Seçim aynı araç + aynı gün mü? Durum Hazır/Yolda mı? |
