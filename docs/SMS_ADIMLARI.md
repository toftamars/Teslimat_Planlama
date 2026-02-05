# Teslimat Planlama – SMS Adımları

Tüm SMS’ler **Odoo sms modülü** (`sms.sms`) ile gönderilir. Alıcı: müşteri telefonu (manuel telefon veya müşteri kaydındaki telefon).

---

## SMS geçici olarak devre dışı

Şu an tüm SMS servisleri **kapalı**. Gönderim yapılmaz; uygulama hata vermez, sadece log’a “SMS devre dışı” yazar.

- **Kontrol:** Sistem parametresi `teslimat_planlama.sms_disabled` = `True` ise SMS gönderilmez.
- **Kod:** `models/sms_helper.py` içinde `SMSHelper.send_sms()` bu parametreye bakıyor.

### SMS’i tekrar nasıl aktif ederim?

1. **Ayarlar → Teknik → Parametreler → Sistem Parametreleri** menüsüne gidin.
2. **Anahtar** ile ara: `teslimat_planlama.sms_disabled`
3. İki seçenek:
   - **Parametreyi silin** (kaydı sil) → parametre yoksa SMS **açık** sayılır, gönderim yapılır.
   - **Veya** kaydı düzenleyip **Değer** alanını `False` veya boş yapıp kaydedin → SMS tekrar **açık** olur.

Kaydettiğiniz anda yeni işlemlerde SMS tekrar gönderilir; sunucuyu yeniden başlatmanız gerekmez.

---

## 1. Teslimat planlandı (belge oluşturuldu)

- **Ne zaman:** Teslimat Belgesi Oluştur wizard’ında “Teslimat Belgesi Oluştur” tıklandığında.
- **Metin:** Teslimat No, Tarih, Araç. “Teslimatınız planlanmıştır.”
- **Kod:** `teslimat_belgesi_wizard._create_teslimat_belgesi()` → `teslimat.send_teslimat_sms()`

---

## 2. Yolda (1. SMS)

- **Ne zaman:** Teslimat belgesi formunda “Yolda” butonuna basıldığında.
- **Metin:** “Ekiplerimiz ürün teslimatı ve kurulum için adresinize doğru yola çıkmıştır. Teslimat No: …”
- **Kod:** `teslimat_belgesi_actions.action_yolda_yap()` → `send_sms_yolda()`

---

## 3. Teslimat tamamlandı (2. SMS)

- **Ne zaman:** Teslimatı Tamamla wizard’ında “Tamamla” tıklandığında.
- **Metin:** “Ürün teslimatınız ve kurulumunuz tamamlanmıştır. Bizi tercih ettiğiniz için teşekkür ederiz. Teslimat No: …”
- **Kod:** `teslimat_tamamlama_wizard.action_teslimat_tamamla()` → `teslimat.write(vals)` → `teslimat.send_sms_tamamlandi()`

---

## Teknik

- **Gönderim:** `models/sms_helper.py` → `SMSHelper.send_sms(env, partner, message, record_name, phone_override)` → `env['sms.sms'].sudo().create()` + `.send()`.
- **Telefon:** Önce manuel telefon, yoksa müşteri telefonu, yoksa müşteri kaydındaki mobile/phone.
- **Devre dışı:** `ir.config_parameter` anahtarı `teslimat_planlama.sms_disabled` = `True` (veya 1/yes) ise gönderim atlanır, `True` döner.
