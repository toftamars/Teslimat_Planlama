# Teslimat Planlama Modülü

Odoo 15 için geliştirilmiş kapsamlı teslimat planlama ve yönetim modülü.

## 📋 Özellikler

- **Araç ve Kapasite Yönetimi**: Araçlar, kapasiteleri ve durumları dinamik olarak yönetilebilir
- **Dinamik İlçe-Gün Eşleştirmeleri**: İlçe-gün eşleştirmeleri modül içinden yöneticiler tarafından yönetilebilir (hardcoded değil)
- **Teslimat Belgesi Yönetimi**: Transfer belgelerinden otomatik teslimat belgesi oluşturma
- **Kapasite Sorgulama**: Gerçek zamanlı kapasite kontrolü ve tarih bazlı sorgulama
- **3 Farklı Rol**: Kullanıcı, Sürücü ve Yönetici rolleri ile yetkilendirme
- **Transfer Entegrasyonu**: Stock picking ile tam entegrasyon

## 🚀 Kurulum

1. Modülü Odoo addons dizinine kopyalayın
2. Odoo'yu yeniden başlatın
3. Uygulamalar menüsünden "Teslimat Planlama" modülünü yükleyin
4. Modül yüklendikten sonra otomatik olarak:
   - Günler oluşturulur (7 gün)
   - Varsayılan araçlar oluşturulur (7 araç)
   - İlçeler ve eşleştirmeler yapılandırılabilir

## 👥 Kullanıcı Rolleri

### Kullanıcı (User)
- Günlük maksimum **7 teslimat** oluşturabilir
- Teslimat belgelerini görüntüleyebilir ve düzenleyebilir
- Kapasite sorgulama yapabilir
- Ana sayfa üzerinden teslimat oluşturabilir

### Sürücü (Driver)
- Bugünkü teslimatlarını görüntüleyebilir
- Teslimat tamamlama işlemlerini yapabilir
- Konum güncelleme yapabilir
- Teslimat oluşturmaz

### Yönetici (Manager)
- Sınırsız teslimat oluşturabilir
- İlçe-gün eşleştirmelerini yönetebilir
- Araç kapasitelerini ayarlayabilir
- Araçları kapatabilir
- Tüm yapılandırma işlemlerini yapabilir

## ⚙️ Yapılandırma

### İlçe-Gün Eşleştirmeleri (Dinamik)

Modül içinden `Yapılandırma > Gün-İlçe Eşleştirmeleri` menüsünden:
- Yeni eşleştirmeler eklenebilir
- Mevcut eşleştirmeler düzenlenebilir
- Eşleştirmeler silinebilir
- Kapasite limitleri ayarlanabilir

**Not**: Varsayılan eşleştirmeler program kurulumu sırasında oluşturulur, sonrasında modülden değiştirilebilir.

### Araç Kapasiteleri

Araçlar için günlük teslimat limiti varsayılan olarak **7**'dir (user grubu için).
Yöneticiler bu limiti modül içinden değiştirebilir:
- `Yapılandırma > Teslimat Araçları` menüsünden
- Araç form view'ında "Günlük Teslimat Limiti" alanından

### Gün Kapasiteleri

Günlük maksimum teslimat kapasitesi varsayılan olarak **50**'dir.
Yöneticiler bu limiti modül içinden değiştirebilir:
- `Yapılandırma > Teslimat Günleri` menüsünden
- Gün form view'ında "Günlük Maksimum Teslimat" alanından

## 📖 Kullanım

### Teslimat Belgesi Oluşturma

#### Yöntem 1: Transfer Belgesinden
1. Stock > Transferler menüsünden bir transfer belgesi açın
2. Header'daki "🚛 Teslimat Oluştur" butonuna tıklayın
3. Wizard'da gerekli bilgileri doldurun
4. "Teslimat Belgesi Oluştur" butonuna tıklayın

#### Yöntem 2: Ana Sayfadan
1. Teslimat > Ana Sayfa menüsünü açın
2. Araç ve ilçe seçin (küçük araçlar için ilçe seçimi opsiyonel)
3. "Yenile" butonuna tıklayın
4. Tarih listesinden bir tarih seçin
5. "Teslimat Oluştur" butonuna tıklayın
6. Wizard'da transfer no girin ve "Teslimat Belgesi Oluştur" butonuna tıklayın

### Kapasite Kontrolü

1. Teslimat > Ana Sayfa menüsünü açın
2. Araç ve ilçe seçin
3. "Yenile" butonuna tıklayın
4. Tarih Bazlı Kapasite sekmesinde:
   - Her tarih için teslimat sayısı
   - Toplam kapasite
   - Kalan kapasite
   - Durum (Boş, Dolu Yakın, Dolu)

### İlçe-Gün Eşleştirmeleri Yönetimi (Yöneticiler)

1. Teslimat > Yapılandırma > Gün-İlçe Eşleştirmeleri menüsünü açın
2. Yeni eşleştirme eklemek için "Yeni Oluştur" butonuna tıklayın
3. Gün, İlçe ve Tarih seçin
4. Maksimum teslimat sayısını belirleyin
5. Kaydedin

**Not**: Eşleştirmeler tarih bazlı olabilir. Aynı gün ve ilçe için birden fazla eşleştirme (farklı tarihler için) oluşturulabilir.

## 🔧 Teknik Detaylar

### Modül Yapısı

```
teslimat_planlama/
├── models/           # Odoo modelleri
├── wizards/          # Wizard/transient modeller
├── views/            # XML view tanımları
├── security/         # Security ve access rights
├── data/             # Data ve sequences
└── static/           # Statik dosyalar (ikonlar)
```

### Önemli Modeller

- `teslimat.sehir`: Şehir yönetimi
- `teslimat.ilce`: İlçe yönetimi (yaka tipi otomatik hesaplanır)
- `teslimat.gun`: Gün yönetimi
- `teslimat.gun.ilce`: Dinamik ilçe-gün eşleştirmeleri
- `teslimat.arac`: Araç yönetimi
- `teslimat.belgesi`: Teslimat belgeleri
- `teslimat.planlama`: Teslimat planlamaları

### Bağımlılıklar

- `base`: Temel Odoo modülü
- `contacts`: İletişim yönetimi
- `stock`: Stok ve transfer yönetimi
- `mail`: Mesajlaşma ve aktivite takibi

## 📝 Notlar

- **Dinamik Yapılandırma**: Tüm yapılandırmalar modül içinden yapılabilir, kod içinde hardcoded değildir
- **Kapasite Limitleri**: Tüm kapasite değerleri database'de tutulur ve modülden değiştirilebilir
- **User Grubu Limiti**: User grubu günlük maksimum 7 teslimat oluşturabilir (kodda `DAILY_DELIVERY_LIMIT = 7`)
- **Manager Grubu**: Manager grubu sınırsız teslimat oluşturabilir

## 🐛 Sorun Giderme

### "Günlük teslimat limiti aşıldı" Hatası
- User grubu günlük maksimum 7 teslimat oluşturabilir
- Çözüm: Yönetici yetkisi gereklidir veya ertesi gün tekrar deneyin

### İlçe-Gün Eşleştirmesi Bulunamadı
- Yöneticiler `Yapılandırma > Gün-İlçe Eşleştirmeleri` menüsünden yeni eşleştirme ekleyebilir
- Varsayılan eşleştirmeler program kurulumu sırasında oluşturulmalıdır

### Araç Kapasitesi Dolu
- Araç kapasitesi dolu ise yeni teslimat oluşturulamaz
- Çözüm: Farklı bir araç seçin veya yöneticiler kapasiteyi artırabilir

## 📞 Destek

Teknik sorularınız için lütfen geliştirici ekibiyle iletişime geçin.

## 📄 Lisans

LGPL-3

---

**Versiyon**: 15.0.2.0.0
**Son Güncelleme**: 2024
