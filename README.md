# Teslimat Planlama Modülü

## Odoo v15 Teslimat Planlama ve Rota Optimizasyonu Modülü

Bu modül, Odoo v15 için geliştirilmiş teslimat planlama ve rota optimizasyonu çözümüdür.

## Özellikler

### 🚚 Ana Modüller
- **Teslimat Planlama**: Genel teslimat planları oluşturma ve yönetimi
- **Teslimat Transfer**: Transfer belgeleri ile entegre teslimat işlemleri
- **Müşteri Yönetimi**: Teslimat tercihleri ve konum bilgileri
- **Stok Entegrasyonu**: Transfer belgeleri ile otomatik veri çekme

### 🔄 Transfer Belgesi Entegrasyonu
- Transfer no girildiğinde otomatik bilgi doldurma
- Kaynak ve hedef konum otomatik belirleme
- Ürün ve miktar bilgileri otomatik çekme
- Müşteri bilgileri otomatik doldurma
- Transfer belgesinden teslimat belgesi oluşturma

### 📍 Konum ve Rota Yönetimi
- Enlem/boylam koordinatları
- Teslimat bölgesi tanımlama
- Tahmini teslimat süreleri
- Tercih edilen teslimat günleri ve saatleri

### 📊 Durum Takibi
- Taslak → Onaylandı → Çalışıyor → Tamamlandı
- Transfer durumları: Bekliyor → Hazırlanıyor → Yolda → Tamamlandı
- Gerçek zamanlı durum güncellemeleri

## Kurulum

1. Modülü Odoo addons klasörüne kopyalayın
2. Odoo'yu yeniden başlatın
3. Uygulamalar menüsünden "Teslimat Planlama" modülünü yükleyin

## Kullanım

### Teslimat Planı Oluşturma
1. Teslimat Planlama → Planlamalar → Yeni
2. Plan adı ve tarih girin
3. Müşterileri ve ürünleri seçin
4. Transferler ekleyin

### Transfer Belgesi ile Çalışma
1. Transfer no alanına transfer belgesi numarasını girin
2. Bilgiler otomatik doldurulacak
3. Gerekirse düzenlemeler yapın
4. "Teslimat Belgesi Oluştur" butonuna tıklayın

## Bağımlılıklar

- Odoo v15
- contacts (Müşteri yönetimi)
- stock (Stok yönetimi)
- delivery (Teslimat yönetimi)
- sale (Satış yönetimi)

## Geliştirici

Bu modül Odoo v15 standartlarına uygun olarak geliştirilmiştir.

## Lisans

LGPL-3
