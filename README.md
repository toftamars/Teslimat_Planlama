# Teslimat Planlama

İstanbul ilçe bazlı teslimat planlaması, kapasite yönetimi, SMS bilgilendirme ve rota desteği için **Odoo 15** modülü.

| | |
|---|---|
| **Sürüm** | 15.0.2.4.2 |
| **Odoo** | 15.0 |
| **Lisans** | LGPL-3 |
| **Yazar** | Alper Tofta |
| **Depo** | https://github.com/toftamars/Teslimat_Planlama |

---

## Modül Hakkında

Teslimat Planlama; stok transfer belgelerinden teslimat belgeleri üretir ve her teslimatı bir **araç**, bir **ilçe** ve bir **tarih** ile eşler. Hangi ilçeye haftanın hangi günü gidileceği (ilçe-gün programı), araçların ilçe uygunluğu (Anadolu/Avrupa yakası) ve günlük kapasite kuralları sistem tarafından otomatik zorlanır. Kapasite sorgulama ekranından önümüzdeki günlerin doluluk durumu görüntülenir ve oradan doğrudan teslimat oluşturulur; müşteriye süreç boyunca otomatik SMS gönderilir.

Tüm yapılandırma (ilçeler, günler, araçlar, program) modül içinden, kod değişikliği olmadan yönetilir.

---

## Ne İşe Yarar?

| Amaç | Açıklama |
|------|----------|
| **Kapasite kontrolü** | Her araç için **günlük toplam** teslimat limiti (varsayılan 7) zorlanır; limit aşıldığında yeni teslimat oluşturulamaz. |
| **Transfer entegrasyonu** | Teslimat belgeleri stok transferleriyle bağlanır; ürünler transferden kopyalanır. Transfer formundan ilgili teslimatlar smart-button ile görülür. |
| **Eşzamanlılık koruması** | Aynı araç-güne iki kullanıcı aynı anda teslimat eklemeye çalışırsa biri anında uyarı alır (PostgreSQL advisory lock, bekleme yok). |
| **Rol bazlı limit** | Kullanıcı günde en fazla 7 teslimat oluşturur; yönetici sınırsızdır. |
| **Müşteri bilgilendirme** | Teslimat planlandığında, yolda olduğunda ve tamamlandığında müşteriye otomatik SMS. |
| **Teslimat kanıtı** | Tamamlamada opsiyonel fotoğraf yüklenir; tıklayınca büyütülür. |

---

## Özellikler

- **Kapasite sorgulama ekranı** — araç + ilçe seçilince önümüzdeki ~30 günün uygunluğu, doluluğu ve araç-kapatma durumu listelenir; uygun günden tek tıkla teslimat oluşturulur.
- **Transfer → Teslimat akışı** — `stock.picking` belgesinden wizard ile teslimat üretilir; transfer ürünleri otomatik kopyalanır.
- **Araç ve kapasite yönetimi** — araç tipine göre (yaka bazlı / küçük araç / ek araç) ilçe uygunluğu otomatik eşleştirilir; araç başına günlük limit.
- **İlçe-gün programı** — haftanın hangi günü hangi ilçelere teslimat yapılacağı dinamik tablo ile yönetilir.
- **Araç kapatma** — araçlar belirli tarih aralıklarında (bakım/arıza/kaza/yakıt/sürücü yok/diğer) kapatılır; kapalı araca o tarihte teslimat engellenir.
- **SMS bilgilendirme** — 3 aşamada müşteriye SMS (planlandı / yolda / tamamlandı); best-effort (SMS hatası teslimatı bloklamaz), sistem parametresiyle kapatılabilir.
- **Teslimat tamamlama** — teslim alan kişi, not ve fotoğraf ile tamamlama wizard'ı; fotoğraf zoom.
- **Durum akışı** — Taslak → Bekliyor → Hazır → Yolda → Teslim Edildi / İptal.
- **Raporlama** — pivot/grafik dashboard'ları (Özet, Durum Analizi, Tarih/Araç Trend).

---

## İş Kuralları

### Günlük kapasite (araç bazlı)
Bir araç **bir günde toplam** en fazla `gunluk_teslimat_limiti` (varsayılan **7**) teslimat yapabilir. Bu limit **araç gününün tamamı** içindir — o gün programdaki tüm ilçeler **birlikte** sayılır. **İlçe başına ayrı tavan yoktur.** İptal edilen teslimatlar sayıma dahil değildir.

> Örnek: Bir araç aynı gün Kadıköy + Üsküdar'a atanmışsa, ikisinin **toplamı** 7'yi geçemez (her birine 7'şer değil).

Eşzamanlı aşımı engellemek için transaction-kapsamlı PostgreSQL advisory lock kullanılır: `pg_try_advisory_xact_lock(arac_id, gün)`.

### İlçe-gün eşleşmesi (program)
`teslimat.gun.ilce` kaydı "o gün o ilçeye gidiliyor mu" bilgisini tutar (evet/hayır). Programında olmayan bir günde bir ilçeye teslimat oluşturulamaz. *(Not: program bir **takvim eşleşmesidir**; ilçe başına sayı limiti tutmaz.)*

### Araç-ilçe uygunluğu
Araç tipine göre belirlenir:
- **Anadolu Yakası aracı** → yalnız Anadolu Yakası ilçeleri
- **Avrupa Yakası aracı** → yalnız Avrupa Yakası ilçeleri
- **Küçük araç / Ek araç** → tüm ilçeler

Teslimat kapısı, aracın `uygun_ilceler` listesine (yaka kuralından üretilen materialized liste) bakar.

### Kişisel günlük kota
Araç kapasitesinden **ayrı** olarak, **Kullanıcı** rolündeki kişi günde en fazla 7 teslimat **oluşturabilir** (kişisel anti-spam kotası). **Yönetici** bu kotadan muaftır.

---

## Roller ve Yetkiler

| Rol | Açıklama | Yetki |
|-----|----------|-------|
| **Kullanıcı** (`base.group_user`) | Standart iç kullanıcı | Teslimat oluşturur/düzenler (günde max 7), **silemez**; tanım kayıtlarını (ilçe/gün/araç) yalnız okur |
| **Teslimat Sürücüsü** (`group_teslimat_driver`) | Saha sürücüsü | Teslimat takibi, "Yolda" / "Tamamla", tamamlama wizard'ı |
| **Teslimat Yöneticisi** (`group_teslimat_manager`) | Operasyon yöneticisi | Sınırsız teslimat, tüm tanımlar, araç/gün kapatma, senkronizasyon, raporlama; teslim-edilmiş hariç silebilir |
| **Süper Yönetici** (`group_teslimat_super_manager`) | | Koşulsuz silme dahil |

> **Erişim modeli:** Satır düzeyi (record-rule) izolasyon **bilinçli olarak yoktur** — tüm iç kullanıcılar tüm teslimatları görebilir. Bu, projenin kabul edilmiş kararıdır.

---

## Mimari

Modül, sorumlulukları ayrı dosyalara bölünmüş **mixin desenini** kullanır.

**Modeller (`models/`):**
- `teslimat.ilce` — ilçeler (İstanbul; yaka tipi otomatik hesaplanır)
- `teslimat.gun` — haftanın günleri
- `teslimat.gun.ilce` — ilçe-gün programı (eşleşme tablosu)
- `teslimat.arac` — araçlar, günlük limit, uygun ilçeler
- `teslimat.arac.kapatma` — araç kapatma kayıtları (tarih aralıklı, chatter'lı)
- `teslimat.belgesi` — ana teslimat belgesi (`mail.thread`)
  - `teslimat.belgesi.validators` — validasyon mixin'i (kapasite / araç-ilçe / araç-kapatma kapıları)
  - `teslimat.belgesi.actions` — onchange + action + SMS mixin'i
- `teslimat.belgesi.urun` — teslimat ürün satırları
- `teslimat.ana.sayfa` / `teslimat.ana.sayfa.gun` — kapasite sorgu ekranı (geçici / TransientModel)
- `res.partner`, `stock.picking` — devralma (inherit, smart-button)

**Yardımcılar:** `teslimat_constants.py` (tek kaynak sabitler — `DAILY_DELIVERY_LIMIT` vb.), `teslimat_utils.py` (saf yardımcı fonksiyonlar), `data/turkey_data.py` (İstanbul ilçeleri + haftalık program **tek kaynağı**).

**Wizard'lar (`wizards/`):** teslimat oluşturma, gün kapatma, araç kapatma, teslimat tamamlama.

---

## Gereksinimler ve Kurulum

**Bağımlılıklar:** `base`, `contacts`, `stock`, `mail`, `analytic`, `sms`
*(Muhasebe yerine hafif `analytic` modülüne bağlıdır — yalnız `account.analytic.account` kullanılır.)*

```bash
# Modülü addons yoluna kopyalayın, ardından:
odoo -d <veritabanı> -i teslimat_planlama
```

1. Modülü Odoo `addons` dizinine ekleyin, Odoo'yu yeniden başlatın.
2. **Uygulamalar**'dan **Teslimat Planlama**'yı yükleyin.
3. Kullanıcılara **Teslimat Sürücüsü** veya **Teslimat Yöneticisi** grubunu atayın.

Kurulumda `post_init_hook` çalışır: İstanbul ilçelerini yükler ve varsayılan haftalık programı uygular. Güncellemede (`-u teslimat_planlama`) `migrations/15.0.2.4.2/` altındaki pre-migration, kaldırılmış eski modellerin metadata'sını savepoint-korumalı şekilde temizler. Manifest sürümü ile migration klasörü birebir eşleşir.

---

## Nasıl Kullanılır?

Menü: **Teslimat**
- **📊 Kapasite Sorgulama** — araç + ilçe seç → uygun günleri gör → günden teslimat oluştur.
- **📄 Teslimat Belgeleri** — tüm teslimatlar; durum butonları (Yolda / Tamamla / İptal / Yol Tarifi).
- **🚗 Araçlar** — araç tanımları, günlük limit, "İlçe Eşleştirmesini Güncelle" / "Tüm Araç-İlçe Senkronizasyonu" (yönetici).
- **🔧 Araç Kapatma** — araç kapatma kayıtları.
- **📅 İlçe-Gün Programı** — haftalık program tablosu.
- **Raporlama** — Özet Dashboard, Durum Analizi, Tarih/Araç Trend (yönetici).

**Tipik akış:** Stok transferi hazırla → Kapasite Sorgulama'dan uygun gün/araç bul → teslimat belgesi oluştur (ürünler transferden kopyalanır, müşteriye SMS gider) → araç yola çıkınca **Yolda** → teslim olunca fotoğraf/not ile **Tamamla**.

---

## SMS Yapılandırması

SMS, Odoo'nun yerleşik `sms` modülü üzerinden gönderilir. Sistem parametresiyle geçici olarak kapatılabilir:

1. **Ayarlar → Teknik → Parametreler → Sistem Parametreleri**
2. `teslimat_planlama.sms_disabled` parametresini bulun.
3. SMS'i kapatmak için değerini `True`, açmak için `False` yapın (veya parametreyi silin).

Detaylı adımlar: [`docs/SMS_ADIMLARI.md`](docs/SMS_ADIMLARI.md).

---

## Teknik Notlar

- **Hedef:** Odoo 15.0 (yalnız). Diğer sürümlerde test edilmemiştir.
- **Performans:** Kapasite alanları `store=True` + günlük cron ile "bugüne" göre tazelenir; kapasite sorgu ekranı araç-kapatmayı toplu sorguyla okur (N+1 önlenir).
- **PII:** Telefon numaraları sunucu loglarında ve kalıcı chatter kayıtlarında son 4 hane gösterilecek şekilde maskelenir (`***1234`); form alanlarında tam görünür (sürücü arayabilsin diye).
- **Frontend:** `web.assets_backend` altında 3 JS (uygun gün tıklama, fotoğraf zoom, vazgeç).

---

## Bilinen Sınırlamalar

- **Dil:** Arayüz Türkçe. String'ler `_()` ile işaretli olsa da henüz çeviri katalogu (`i18n/*.pot`) üretilmemiştir → fiilen tek dil (TR).
- **Otomatik test yok:** Doğrulama elle (staging) yapılır — proje sahibinin bilinçli tercihi.
- **`uygun_ilceler` senkronizasyonu manueldir:** Yeni ilçe eklenince veya yaka değişince araçların uygun-ilçe listesi otomatik (cron'la) tazelenmez; yönetici "Senkronizasyon" düğmesiyle veya araç kaydını güncelleyerek tazeler.
- **Satır düzeyi izolasyon yok** (yukarıda belirtildiği gibi, kabul edilmiş karar).

---

## Lisans

LGPL-3

**Geliştirici:** Alper Tofta
