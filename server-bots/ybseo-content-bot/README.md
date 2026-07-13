# YBSEO İçerik Botu

VPS üzerinde çalışan, SEO kaynaklarını araştıran ve kullanıcının gönderdiği nihai Türkçe yazıyı kontrollü biçimde WordPress HTML yapısına dönüştüren Telegram editör botu.

## Kaynaklar

- Moz Blog
- BlogSEO
- Ahrefs Blog
- Search Engine Land

Bot benzer konudaki kaynakları paket halinde Telegram'a gönderir. Nihai yazıyı kullanıcı hazırlar; yerel Qwen modeli yalnızca SEO alanlarını, H2/H3 yapısını, paragrafları, listeleri ve izin verilen bağlantıları düzenler. Kullanıcının metnine yeni iddia, sayı, kaynak veya örnek eklemesi yasaktır.

## Telegram akışı

1. `/konu` ile eşleşen kaynak yazıları alın.
2. `/yazi` yazıp nihai metni mesaj, `.txt`, `.md`, `.html` veya `.docx` olarak gönderin.
3. İsterseniz görselleri gönderin; ilk görsel kapak olur.
4. En az `MIN_WORDS` (varsayılan 1.500) kelimelik metni `/bitir` ile SEO/HTML önizlemesine dönüştürün. Tam önizleme Telegram'a ve e-postaya gelir.
5. `/duzelt talimat` ile yalnızca belirttiğiniz değişikliği yaptırın.
6. `/taslak`, `/yayinla` veya `/zamanla GG.AA.YYYY SS:DD` komutlarından birini kullanın.

Kritik kalite sorunu bulunan bir yazı doğrudan yayımlanamaz veya zamanlanamaz; WordPress taslağı olarak kaydedilebilir.

## Güvenlik ve kalite

- Yalnızca yapılandırılmış Telegram sohbet kimliğinden komut kabulü
- Yeni bilgi ve URL üretimini engelleyen editör sistem promptu
- İzinli HTML etiketleri ve bağlantılar için deterministik kontrol
- Model metni fazla kısaltır veya uzatırsa işlemi durdurma
- Kritik kalite sorununda doğrudan yayın ve zamanlama engeli
- Yayın için mutlaka açık `/yayinla` veya `/zamanla` komutu
- Telegram ve tam HTML ekli e-posta önizlemesi
- VPS izleme veritabanına hata ve servis durumu kaydı

## Kurulum

`config.example.env` dosyasını `config.env` olarak kopyalayın ve gizli değerleri yalnızca sunucuda tanımlayın. `config.env`, Telegram anahtarları ve çalışma verileri git tarafından dışlanır.

Kalıcı servis `ybseo-telegram-bot.service` dosyasıdır. Eski otomatik içerik üretim timer'ı bu iş akışında etkinleştirilmemelidir.
