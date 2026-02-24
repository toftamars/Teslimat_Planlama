# Teslimat Planlama

**Odoo 15** için teslimat planlaması, kapasite yönetimi ve rota takibi modülü.

---

## Modül Hakkında

Teslimat Planlama modülü, teslimat operasyonlarını planlamak, kapasiteyi kontrol etmek ve müşteriye otomatik bilgilendirme yapmak için geliştirilmiş kapsamlı bir Odoo uygulamasıdır. Araç–ilçe–tarih bazlı kapasite yönetimi, stok transfer entegrasyonu, SMS bildirimleri ve teslimat fotoğrafı özellikleriyle operasyonel süreçleri tek ekrandan yönetmenizi sağlar.

---

## Modül Ne İşe Yarar?

| Amaç | Açıklama |
|------|----------|
| **Kapasite kontrolü** | Her araç–ilçe–tarih kombinasyonu için maksimum teslimat sayısı tanımlanır; kapasite aşıldığında yeni teslimat oluşturulamaz. |
| **Transfer entegrasyonu** | Teslimat belgeleri stok transfer belgeleriyle bağlanır; ürünler transfer üzerinden yönetilir. Transfer belgesinden ilgili teslimatlar görüntülenebilir. |
| **Eşzamanlılık koruması** | Aynı slota iki kullanıcı aynı anda teslimat eklemeye çalışırsa biri anında uyarı alır (bekleme yok). |
| **Rol bazlı limitler** | Kullanıcılar günde en fazla 7 teslimat oluşturabilir; yöneticiler sınırsızdır. |
| **Müşteri bilgilendirme** | Teslimat planlandığında, yolda olduğunda ve tamamlandığında müşteriye otomatik SMS gönderilir. |
| **Teslimat kanıtı** | Teslimat tamamlanırken opsiyonel fotoğraf yüklenebilir; fotoğrafa tıklayarak büyütülebilir. |
| **Konum takibi** | Sürücüler teslimat belgesi için enlem–boylam ile konum güncelleyebilir (İstanbul koordinat validasyonu ile). |

---

## Özellikler

### Araç ve Kapasite Yönetimi
- Araç tanımları (kapasite, araç tipi)
- Günlük kapasite limitleri
- Araç geçici kapatma (bakım, arıza, kaza, yakıt sorunu, sürücü yok, diğer)

### İlçe–Gün Programı
- Dinamik yapılandırma ile ilçe bazlı teslimat günleri
- Her ilçe için hangi günlerde teslimat yapılacağı ve maksimum teslimat sayısı tanımlanır

### Teslimat Belgesi
- Oluşturma, düzenleme, takip
- Durum akışı: Taslak → Bekliyor → Hazır → Yolda → Teslim Edildi / İptal
- Müşteri, araç, ilçe, sürücü, teslimat tarihi
- Transfer belgesi ve ürün bağlama

### Kapasite Sorgulama
- Araç ve ilçe seçerek uygun günleri görüntüleme
- Boş / dolu kapasite gösterimi
- Uygun güne tıklayarak hızlı teslimat oluşturma

### Transfer Entegrasyonu
- Stok transfer belgeleri ile teslimat belgesi eşleştirme
- Transfer belgesinden ilgili teslimatları smart button ile görüntüleme

### SMS Bildirimleri
- **1. SMS (Planlandı):** Teslimat belgesi oluşturulduğunda müşteriye bilgi
- **2. SMS (Yolda):** "Yolda" butonuna basıldığında müşteriye yolda bilgisi
- **3. SMS (Tamamlandı):** Teslimat tamamlandığında teşekkür mesajı
- SMS geçici devre dışı bırakılabilir (`teslimat_planlama.sms_disabled` parametresi)

### Teslimat Fotoğrafı
- Teslimat tamamlanırken opsiyonel fotoğraf yükleme
- Tamamlanan teslimatlarda fotoğraf görüntüleme
- Fotoğrafa tıklayarak tam boyutta görüntüleme (zoom)

### Konum Güncelleme
- Sürücüler teslimat belgesi için enlem–boylam ile konum güncelleyebilir
- İstanbul koordinat aralığı validasyonu

### Raporlama
- Özet dashboard (pivot, grafik)
- Durum analizi (pasta grafik)
- Tarih / araç trend raporları

---

## Roller ve Yetkiler

| Rol | Açıklama | Günlük teslimat limiti |
|-----|----------|-------------------------|
| **Kullanıcı** | Teslimat oluşturma, kapasite sorgulama, transfer bağlama | Max 7 |
| **Teslimat Sürücüsü** | Yolda / Tamamla butonları, konum güncelleme, teslimat takibi | Sürücü arayüzü |
| **Teslimat Yöneticisi** | Araçlar, ilçe–gün programı, araç kapatma, raporlama, sınırsız teslimat | Sınırsız |

---

## Nasıl Kullanılır?

### Tüm Kullanıcılar

1. **Kapasite Sorgulama**
   - Teslimat menüsünden **Kapasite Sorgulama**'ya girin.
   - Araç ve ilçe seçin.
   - Hangi günlerde boş kapasite olduğunu görün.
   - Uygun bir güne tıklayarak hızlı teslimat oluşturabilirsiniz.

2. **Teslimat Belgeleri**
   - **Teslimat Belgeleri** menüsünden yeni teslimat oluşturun veya mevcut belgeleri düzenleyin.
   - Müşteri, araç, ilçe ve teslimat tarihi seçin; sistem kapasiteyi otomatik kontrol eder.
   - Transfer belgesi bağlayarak ürünleri teslimatla eşleştirin.

3. **Transfer Bağlama**
   - Teslimat belgesinde **Transfer Belgesi** alanından stok transferini seçin.
   - Ürünler transfer üzerinden teslimat belgesine aktarılır.

### Sürücüler

1. **Yolda** — Teslimat belgesi formunda **Yolda** butonuna basın; müşteriye yolda SMS'i gönderilir.
2. **Konum Güncelle** — Konum güncelleme wizard'ı ile enlem–boylam girerek teslimat konumunu kaydedin.
3. **Teslimatı Tamamla** — Tamamlama wizard'ında opsiyonel fotoğraf ve not ekleyerek teslimatı tamamlayın; müşteriye tamamlandı SMS'i gönderilir.

### Yöneticiler

1. **Araçlar** — Araç tanımlarını oluşturun; kapasite ve araç tipini ayarlayın.
2. **İlçe–Gün Programı** — Her ilçe için teslimat günlerini ve günlük maksimum teslimat sayısını tanımlayın.
3. **Araç Kapatma** — Bakım veya arıza nedeniyle araçları geçici olarak kapatın.
4. **Raporlama** — Özet dashboard, durum analizi ve tarih/araç trend raporlarını inceleyin.

---

## Gereksinimler

- **Odoo:** 15.0
- **Bağımlılıklar:** `base`, `contacts`, `stock`, `mail`, `account`, `sms`

---

## Kurulum

1. Modülü Odoo `addons` dizinine kopyalayın veya addons path'ine ekleyin.
2. Odoo'yu yeniden başlatın.
3. Uygulamalar menüsünden **Teslimat Planlama** modülünü yükleyin.
4. Kullanıcılara **Teslimat Sürücüsü** veya **Teslimat Yöneticisi** gruplarını atayın.

---

## SMS Yapılandırması

SMS servisleri varsayılan olarak **devre dışı** olabilir. Aktif etmek için:

1. **Ayarlar → Teknik → Parametreler → Sistem Parametreleri** menüsüne gidin.
2. `teslimat_planlama.sms_disabled` parametresini arayın.
3. Parametreyi silin veya değerini `False` yapın.

Detaylı SMS adımları için `docs/SMS_ADIMLARI.md` dosyasına bakın.

---

## Lisans

LGPL-3

---

**Geliştirici:** Alper Tofta
