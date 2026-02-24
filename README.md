# Teslimat Planlama

Odoo 15 için teslimat planlaması ve rota yönetimi modülü.

## Modül Ne İşe Yarar?

Bu modül, teslimat operasyonlarını planlamak ve yönetmek için kullanılır. Araç kapasitelerini, ilçe bazlı teslimat günlerini ve müşteri teslimatlarını tek bir ekrandan takip etmenizi sağlar.

- **Kapasite kontrolü:** Her araç–ilçe–tarih kombinasyonu için maksimum teslimat sayısı tanımlanır; aşıldığında yeni teslimat oluşturulamaz.
- **Transfer entegrasyonu:** Teslimat belgeleri stok transfer belgeleriyle bağlanır; ürünler transfer üzerinden yönetilir.
- **Eşzamanlılık koruması:** Aynı slota iki kullanıcı aynı anda teslimat eklemeye çalışırsa, biri anında uyarı alır (bekleme yok).
- **Rol bazlı limitler:** Kullanıcılar günde en fazla 7 teslimat oluşturabilir; yöneticiler sınırsızdır.

## Nasıl Kullanılır?

### Tüm Kullanıcılar

1. **Kapasite Sorgulama** — Teslimat menüsünden "Kapasite Sorgulama"ya girin. Araç ve ilçe seçerek hangi günlerde boş kapasite olduğunu görün.
2. **Teslimat Belgeleri** — "Teslimat Belgeleri" menüsünden yeni teslimat oluşturun veya mevcut belgeleri düzenleyin. Müşteri, araç, ilçe ve teslimat tarihi seçin; sistem kapasiteyi otomatik kontrol eder.
3. **Transfer bağlama** — Teslimat belgesine stok transfer belgesi bağlayarak ürünleri teslimatla eşleştirin.

### Yöneticiler

1. **Araçlar** — Araç tanımlarını oluşturun, kapasite ve araç tipini ayarlayın.
2. **İlçe–Gün Programı** — Her ilçe için hangi günlerde teslimat yapılacağını ve günlük maksimum teslimat sayısını tanımlayın.
3. **Araç Kapatma** — Bakım veya arıza nedeniyle araçları geçici olarak kapatın.
4. **Raporlama** — Özet dashboard, durum analizi ve tarih/araç trend raporlarını inceleyin.

### Sürücüler

- Teslimat Belgeleri listesinden kendi atandıkları teslimatları görüntüleyebilir ve durum güncelleyebilir.

## Özellikler

- **Araç ve kapasite yönetimi** — Araç tanımları ve günlük kapasite limitleri
- **İlçe–gün eşleştirmeleri** — Dinamik yapılandırma ile ilçe bazlı teslimat günleri
- **Teslimat belgesi** — Oluşturma, takip ve durum yönetimi
- **Transfer entegrasyonu** — Stok transfer belgeleri ile entegrasyon
- **Kapasite sorgulama ve raporlama** — Slot bazlı kapasite kontrolü
- **Rol tabanlı erişim** — Kullanıcı, Sürücü ve Yönetici rolleri

### Roller

| Rol | Günlük teslimat limiti |
|-----|-------------------------|
| Kullanıcı | Max 7 |
| Yönetici | Sınırsız |
| Sürücü | Sürücü arayüzü ile teslimat takibi |

## Gereksinimler

- Odoo 15.0
- Bağımlılıklar: `base`, `contacts`, `stock`, `mail`, `account`, `sms`

## Kurulum

1. Modülü `addons` dizinine kopyalayın veya Odoo addons path'ine ekleyin.
2. Odoo'yu yeniden başlatın.
3. Uygulamalar menüsünden **Teslimat Planlama** modülünü yükleyin.

## Lisans

LGPL-3

---

**Geliştirici:** Alper Tofta
