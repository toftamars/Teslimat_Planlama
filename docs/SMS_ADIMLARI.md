# Teslimat Planlama – SMS Adımları

Tüm SMS’ler **Odoo sms modülü** (`sms.sms`) ile gönderilir. Alıcı: müşteri telefonu (manuel telefon veya müşteri kaydındaki telefon).

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
