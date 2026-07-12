# YBSEO İçerik Botu

VPS üzerinde yerel Ollama/Qwen modeliyle SEO kaynaklarını araştıran, özgün Türkçe içerik hazırlayan, kalite kontrollerinden geçiren ve WordPress REST API üzerinden yayımlayan otomasyon.

## Kaynaklar

- Moz Blog
- BlogSEO
- Ahrefs Blog
- Search Engine Land

Kaynak metinler doğrudan çevrilmez veya kopyalanmaz. Bot çok kaynaklı araştırma yapar, Türkçe ve YBSEO'ya özgü bir anlatım üretir ve kaynak bağlantılarını yazının sonunda gösterir.

## Güvenlik ve kalite

- En az iki araştırma kaynağı
- Benzer anahtar kelimeli kaynak yazıların eşleştirilmesi
- Kaynak makale gövdelerinin çok kaynaklı Türkçe sentezi
- En az 1.500 kelime
- Otomatik genişletme ve bölüm bazlı zenginleştirme
- H2 bölüm ve kaynak bağlantısı kontrolleri
- Başarısız içeriklerin yayımlanmaması
- Üç ardışık hatada üç günlük devre kesici
- Telegram ve e-posta bildirimleri
- VPS izleme veritabanına aşama ve ölçüm kaydı

## Kurulum

`config.example.env` dosyasını `config.env` olarak kopyalayın ve gizli değerleri yalnızca sunucuda tanımlayın. `config.env`, Telegram anahtarları ve çalışma verileri git tarafından dışlanır.

İlk denemeler `DRY_RUN=true` ile yapılmalıdır. Kalite testi doğrulandıktan sonra `DRY_RUN=false` ve systemd timer etkinleştirilir.
