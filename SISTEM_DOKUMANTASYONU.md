# 🚛 Teslimat Planlama Modülü - Sistem Dokümantasyonu

## 📋 İçindekiler
1. [İlçe-Gün Eşleştirmeleri](#ilçe-gün-eşleştirmeleri)
2. [Araç Tipleri ve Bilgileri](#araç-tipleri-ve-bilgileri)
3. [Sistem Kuralları](#sistem-kuralları)
4. [Sistem Nasıl Çalışır?](#sistem-nasıl-çalışır)

---

## 📅 İlçe-Gün Eşleştirmeleri

### **ANADOLU YAKASI İlçeleri ve Günleri**

#### **Pazartesi & Perşembe**
- **Maltepe** - Maksimum: 15 teslimat
- **Kartal** - Maksimum: 20 teslimat
- **Pendik** - Maksimum: 18 teslimat
- **Tuzla** - Maksimum: 12 teslimat

#### **Salı, Çarşamba & Cuma**
- **Üsküdar** - Maksimum: 25 teslimat
- **Kadıköy** - Maksimum: 30 teslimat
- **Ümraniye** - Maksimum: 28 teslimat
- **Ataşehir** - Maksimum: 22 teslimat

#### **Cumartesi**
- **Beykoz** - Maksimum: 12 teslimat
- **Çekmeköy** - Maksimum: 18 teslimat
- **Sancaktepe** - Maksimum: 15 teslimat
- **Sultanbeyli** - Maksimum: 15 teslimat
- **Şile** - Maksimum: 8 teslimat

### **AVRUPA YAKASI İlçeleri ve Günleri**

#### **Pazartesi & Cuma**
- **Şişli** - Maksimum: 20 teslimat
- **Beşiktaş** - Maksimum: 22 teslimat
- **Beyoğlu** - Maksimum: 25 teslimat
- **Kağıthane** - Maksimum: 18 teslimat

#### **Salı**
- **Sarıyer** - Maksimum: 20 teslimat
- **Eyüpsultan** - Maksimum: 20 teslimat
- **Sultangazi** - Maksimum: 18 teslimat
- **Gaziosmanpaşa** - Maksimum: 22 teslimat

#### **Çarşamba**
- **Bağcılar** - Maksimum: 25 teslimat
- **Bahçelievler** - Maksimum: 22 teslimat
- **Bakırköy** - Maksimum: 25 teslimat (Ayrıca Perşembe & Cumartesi)
- **Güngören** - Maksimum: 18 teslimat
- **Esenler** - Maksimum: 20 teslimat
- **Zeytinburnu** - Maksimum: 20 teslimat
- **Bayrampaşa** - Maksimum: 18 teslimat
- **Fatih** - Maksimum: 30 teslimat

#### **Perşembe & Cumartesi**
- **Büyükçekmece** - Maksimum: 25 teslimat
- **Silivri** - Maksimum: 15 teslimat
- **Çatalca** - Maksimum: 10 teslimat
- **Arnavutköy** - Maksimum: 15 teslimat
- **Bakırköy** - Maksimum: 25 teslimat (Ayrıca Çarşamba)

### **Özel Durumlar**
- **Pazar Günü**: Teslimat yapılmaz
- **Bakırköy**: Çarşamba, Perşembe ve Cumartesi olmak üzere 3 gün teslimat alır

---

## 🚗 Araç Tipleri ve Bilgileri

### **Araç Tipleri**

#### **1. Anadolu Yakası Araçları**
- **Tip Kodu**: `anadolu_yakasi`
- **Günlük Teslimat Limiti**: 25 teslimat (varsayılan)
- **Uygun İlçeler**: Sadece Anadolu Yakası ilçeleri
- **Örnek Araçlar**:
  - Anadolu Yakası Araç 1
  - Anadolu Yakası Araç 2

#### **2. Avrupa Yakası Araçları**
- **Tip Kodu**: `avrupa_yakasi`
- **Günlük Teslimat Limiti**: 25 teslimat (varsayılan)
- **Uygun İlçeler**: Sadece Avrupa Yakası ilçeleri
- **Örnek Araçlar**:
  - Avrupa Yakası Araç 1
  - Avrupa Yakası Araç 2

#### **3. Küçük Araç 1**
- **Tip Kodu**: `kucuk_arac_1`
- **Günlük Teslimat Limiti**: 15 teslimat (varsayılan)
- **Uygun İlçeler**: Her iki yakaya da gidebilir
- **Gün Kısıtı**: Yok (Tüm günler teslimat yapabilir)

#### **4. Küçük Araç 2**
- **Tip Kodu**: `kucuk_arac_2`
- **Günlük Teslimat Limiti**: 15 teslimat (varsayılan)
- **Uygun İlçeler**: Her iki yakaya da gidebilir
- **Gün Kısıtı**: Yok (Tüm günler teslimat yapabilir)

#### **5. Ek Araç**
- **Tip Kodu**: `ek_arac`
- **Günlük Teslimat Limiti**: 20 teslimat (varsayılan)
- **Uygun İlçeler**: Her iki yakaya da gidebilir
- **Gün Kısıtı**: Yok (Tüm günler teslimat yapabilir)

### **Araç Özellikleri**

#### **Kapasite Bilgileri**
- **Günlük Teslimat Limiti**: Her araç için maksimum günlük teslimat sayısı
- **Mevcut Kapasite**: Bugün için planlanmış teslimat sayısı
- **Kalan Kapasite**: `Günlük Limit - Mevcut Kapasite`

#### **Durum Bilgileri**
- **Aktif**: Araç teslimat yapabilir durumda mı?
- **Geçici Kapatma**: Belirli bir süre için araç kapatılmış mı?
- **Kapatma Sebebi**: Kapatma nedeni (bakım, tatil, vb.)
- **Kapatma Tarihleri**: Başlangıç ve bitiş tarihleri

---

## ⚙️ Sistem Kuralları

### **1. Araç-İlçe Uyumluluk Kuralları**

#### **Yaka Bazlı Kısıtlama**
- ✅ **Anadolu Yakası Araç** → Sadece **Anadolu Yakası** ilçelerine gidebilir
- ✅ **Avrupa Yakası Araç** → Sadece **Avrupa Yakası** ilçelerine gidebilir
- ✅ **Küçük Araç 1, Küçük Araç 2, Ek Araç** → **Her iki yakaya** da gidebilir

#### **İlçe Yaka Belirleme**
- İlçe adına göre otomatik olarak yaka tipi belirlenir:
  - **Anadolu Yakası**: Maltepe, Kartal, Pendik, Tuzla, Üsküdar, Kadıköy, Ümraniye, Ataşehir, Sancaktepe, Çekmeköy, Beykoz, Şile, Sultanbeyli
  - **Avrupa Yakası**: Beyoğlu, Şişli, Beşiktaş, Kağıthane, Sarıyer, Bakırköy, Bahçelievler, Güngören, Esenler, Bağcılar, Eyüpsultan, Gaziosmanpaşa, Küçükçekmece, Avcılar, Başakşehir, Sultangazi, Arnavutköy, Fatih, Zeytinburnu, Bayrampaşa, Esenyurt, Beylikdüzü, Silivri, Çatalca, Büyükçekmece

### **2. İlçe-Gün Eşleştirme Kuralları**

#### **Gün Bazlı Kısıtlama**
- Her ilçe için belirli günlerde teslimat yapılabilir
- İlçe-gün eşleştirmeleri kod içinde hardcoded olarak tanımlıdır
- Küçük araçlar için gün kısıtı **YOKTUR** (Tüm günler teslimat yapabilir)
- Yaka bazlı araçlar için ilçe-gün eşleştirmesine **UYULMALIDIR**

#### **Pazar Günü Kuralı**
- ⛔ **Pazar günü teslimat yapılmaz**
- Sistem pazar günü için teslimat tarihi önermez

### **3. Kapasite Kuralları**

#### **Gün Bazlı Kapasite**
- Her gün için maksimum teslimat kapasitesi: **50 teslimat** (varsayılan)
- İlçe-gün bazında özel kapasiteler tanımlanabilir

#### **Araç Bazlı Kapasite**
- Her araç için günlük teslimat limiti vardır
- Sistem kapasite aşımını otomatik kontrol eder

#### **Kapasite Hesaplama**
```
Kalan Kapasite = Maksimum Kapasite - Mevcut Teslimat Sayısı
```

### **4. Geçici Kapatma Kuralları**

#### **Araç Kapatma**
- Araçlar belirli tarih aralığı için kapatılabilir
- Kapatma sebebi girilmelidir
- Süresiz kapatma seçeneği vardır

#### **Gün Kapatma**
- Belirli günler geçici olarak kapatılabilir
- Kapatma tarih aralığı veya süresiz olabilir
- Kapatılan günler için teslimat tarihi önerilmez

---

## 🔄 Sistem Nasıl Çalışır?

### **1. Ana Sayfa - Kapasite Sorgulama**

#### **Adım 1: Araç ve İlçe Seçimi**
- Kullanıcı bir araç seçer
- Küçük araç değilse, ilçe seçimi zorunludur

#### **Adım 2: Uygunluk Kontrolü**
Sistem şu kontrolleri yapar:

1. **Araç-İlçe Uyumluluğu**
   - Yaka bazlı araç ise → İlçe yakası kontrol edilir
   - Küçük araç ise → Her ilçeye gidebilir ✅

2. **İlçe-Gün Uyumluluğu**
   - Küçük araç ise → Gün kısıtı yok ✅
   - Yaka bazlı araç ise → İlçe-gün eşleştirmesi kontrol edilir

#### **Adım 3: Tarih Listesi Hesaplama**
Sistem sonraki 30 günü kontrol eder:

1. **Gün Uygunluğu Kontrolü**
   - Seçilen ilçe o gün teslimat alıyor mu?
   - Gün aktif mi?
   - Gün geçici olarak kapatılmış mı?
   - Kapatma tarihleri içinde mi?

2. **Kapasite Kontrolü**
   - Günlük genel kapasite dolu mu?
   - İlçe-gün bazlı kapasite dolu mu?
   - Araç kapasitesi yeterli mi?

3. **Durum Belirleme**
   - **🟢 Boş**: `Kalan Kapasite > 5` ve `Doluluk Oranı < 50%`
   - **🟡 Dolu Yakın**: `Kalan Kapasite ≤ 5` veya `50% ≤ Doluluk Oranı < 90%`
   - **🔴 Dolu**: `Kalan Kapasite = 0` veya `Doluluk Oranı ≥ 90%`

#### **Adım 4: Sonuçların Gösterilmesi**
- **Tarih Bazlı Kapasite**: Her tarih için detaylı bilgi
- **İlçe Kapasitesi**: Toplam/kullanılan/kalan kapasite
- **Uygun Araçlar**: Seçilen ilçeye uygun diğer araçlar

### **2. Teslimat Belgesi Oluşturma**

#### **Otomatik Dolum**
- Transfer no girildiğinde:
  - Transfer belgesi bulunur
  - Müşteri bilgisi otomatik gelir
  - Ürün ve miktar bilgileri otomatik gelir

#### **Validasyon Kontrolleri**
1. **Transfer Durumu**: İptal ve taslak transferler için uyarı
2. **Mükerrer Kontrol**: Aynı transfer için daha önce teslimat oluşturulmuş mu?
3. **Kapasite Kontrolü**: Seçilen tarih için yeterli kapasite var mı?

### **3. Akıllı Planlama**

#### **Kapasite Bazlı Öneriler**
- Sistem mevcut kapasiteyi analiz eder
- En uygun tarihleri önerir
- Araç-ilçe uyumluluğunu kontrol eder

#### **Rota Optimizasyonu**
- Aynı ilçeye giden teslimatlar gruplanır
- Araç kapasitesi dikkate alınır
- Müsait tarihler öncelikli olarak önerilir

### **4. Sistem Kurulumu**

#### **Otomatik Kurulum Adımları**
1. **Günler Oluşturulur**: Haftanın 7 günü (Pazar hariç aktif)
2. **İlçeler Oluşturulur**: İstanbul'un 39 ilçesi
3. **Gün-İlçe Eşleştirmeleri**: Yukarıdaki tabloya göre
4. **Araçlar Oluşturulur**: 7 varsayılan araç (2 Anadolu, 2 Avrupa, 2 Küçük, 1 Ek)

#### **Manuel Yapılandırma**
- Kapasiteler ayarlanabilir
- Yeni araçlar eklenebilir
- Geçici kapatmalar yapılabilir
- Özel gün-ilçe eşleştirmeleri eklenebilir

---

## 📊 Özet Tablolar

### **İlçe-Gün Eşleştirme Özeti**

| Gün | Anadolu Yakası İlçeleri | Avrupa Yakası İlçeleri | Toplam |
|-----|------------------------|------------------------|--------|
| Pazartesi | 4 ilçe | 4 ilçe | 8 ilçe |
| Salı | 4 ilçe | 4 ilçe | 8 ilçe |
| Çarşamba | 4 ilçe | 8 ilçe | 12 ilçe |
| Perşembe | 4 ilçe | 5 ilçe | 9 ilçe |
| Cuma | 4 ilçe | 3 ilçe | 7 ilçe |
| Cumartesi | 5 ilçe | 4 ilçe | 9 ilçe |
| Pazar | ❌ Teslimat yok | ❌ Teslimat yok | 0 ilçe |

### **Araç Tipi Özeti**

| Araç Tipi | Günlük Limit | İlçe Kısıtı | Gün Kısıtı |
|-----------|-------------|-------------|------------|
| Anadolu Yakası | 25 | Sadece Anadolu | Var |
| Avrupa Yakası | 25 | Sadece Avrupa | Var |
| Küçük Araç 1 | 15 | Her iki yaka | Yok |
| Küçük Araç 2 | 15 | Her iki yaka | Yok |
| Ek Araç | 20 | Her iki yaka | Yok |

---

## 🔍 Teknik Detaylar

### **Veri Modelleri**

#### **teslimat.gun**
- Haftanın günlerini tanımlar
- Gün kodu ve sequence bilgisi içerir
- Günlük maksimum teslimat kapasitesi tanımlıdır

#### **teslimat.ilce**
- İlçe bilgilerini tutar
- Yaka tipi otomatik hesaplanır
- Konum bilgileri (enlem/boylam) saklanabilir

#### **teslimat.gun.ilce**
- Gün-İlçe eşleştirmelerini tutar
- İlçe-gün bazlı özel kapasiteler tanımlanabilir
- Tarih bazlı teslimat sayıları takip edilir

#### **teslimat.arac**
- Araç bilgilerini tutar
- Araç tipine göre uygun ilçeler Many2many ile ilişkilendirilir
- Günlük teslimat limiti ve mevcut kapasite takip edilir

### **Hesaplama Metodları**

#### **`_compute_ilce_uygunluk()`**
- Araç-İlçe uyumluluğunu kontrol eder
- Yaka bazlı kuralları uygular
- Küçük araçlar için özel kontrol yapar

#### **`_compute_tarih_listesi()`**
- Sonraki 30 günü analiz eder
- Her tarih için uygunluk kontrolü yapar
- Kapasite durumunu hesaplar
- Durum ikonları ve metinleri oluşturur

#### **`check_availability()`**
- Belirli bir tarih için müsaitlik kontrolü
- 5 farklı kontrol yapar:
  1. Gün aktif mi?
  2. Geçici kapatılmış mı?
  3. Kapatma tarihleri geçerli mi?
  4. İlçe-gün eşleşmesi var mı?
  5. Kapasite yeterli mi?

---

## 📝 Notlar

- Sistem kod içinde hardcoded ilçe-gün eşleştirmeleri kullanır
- Yaka bazlı kurallar otomatik olarak uygulanır
- Küçük araçlar tüm kısıtlamalardan muaf tutulur
- Kapasite kontrolü gerçek zamanlı olarak yapılır
- Geçici kapatmalar sistem tarafından otomatik dikkate alınır

