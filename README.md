# Yeni Bakış Görsel Atölyesi

Haber görsellerini tarayıcı içinde toplu boyutlandıran veya 1280×720 kırpan Next.js uygulaması. Görseller sunucuya yüklenmez.

## Kurulum

```bash
npm install
cp .env.example .env.local
npm run dev
```

`.env.local` içindeki kullanıcı adı, şifre ve en az 32 karakterlik `AUTH_SECRET` değerini değiştirin. Ardından `http://localhost:3000/login` adresini açın.

Bu yerel kopyadaki giriş bilgileri: kullanıcı adı `editör`, şifre `feyaztatar94`.

## Araçlar

- `/resizer`: En-boy oranını koruyarak ortak genişliğe toplu dönüştürme
- `/crop`: Yatay/dikey kadrajı seçerek sabit 16:9 oranında 1280×720 kırpma
- `/tamamlama`: Fotoğrafı merkezleyerek beyaz 1280×720 zemine yerleştirme
- `/kolaj`: İki fotoğrafı ayrı ölçek ve eksen kontrolleriyle 1280×720 kolajda birleştirme
- WebP kalite ayarı ve SEO uyumlu dosya adı
- Tekli veya ayrı dosyalar halinde toplu indirme

Uygulama production ortamında `peditor.ybseo.com.tr` alan adı arkasında çalıştırılacak şekilde hazırlanmıştır. VPS dağıtımında Node.js process manager ve HTTPS reverse proxy yapılandırması ayrıca yapılmalıdır.

cPanel kurulum ayrıntıları için `CPANEL_DEPLOYMENT.md` dosyasına bakın.

Not: Tarayıcılar güvenlik nedeniyle çoklu indirmeler için ayrıca izin isteyebilir.
