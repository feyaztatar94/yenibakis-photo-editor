# cPanel production kurulumu

Bu uygulama fotoğrafları sunucuya yüklemez. Canvas, WebP kodlama ve indirme işlemleri kullanıcının tarayıcısında gerçekleşir; VPS yalnızca Next.js arayüzünü ve giriş oturumunu sunar.

## Gereksinimler

- Node.js 20 veya daha yeni sürüm
- `peditor.ybseo.com.tr` alt alan adı
- cPanel Application Manager veya Node.js Application

## Kurulum

1. Projeyi sunucuya aktarın ve `pnpm install --frozen-lockfile` çalıştırın.
2. Production build oluşturun: `pnpm build`.
3. Uygulama ortamına `EDITOR_USERNAME`, `EDITOR_PASSWORD` ve en az 32 karakterli `AUTH_SECRET` değişkenlerini ekleyin.
4. Başlatma komutu olarak `pnpm start` kullanın. cPanel tarafından verilen `PORT` değeri Next.js tarafından otomatik kullanılır.
5. Alt alan adını uygulamaya bağlayın ve HTTPS yönlendirmesini etkinleştirin.

`next.config.ts` sıkıştırma ve gereksiz `X-Powered-By` başlığının kaldırılması için ayarlanmıştır. Yapı, cPanel Node.js uygulamasında doğrudan `pnpm start` ile çalışır.

## Kaynak kullanımı

Fotoğraf dosyaları HTTP isteğiyle sunucuya gönderilmediği için yükleme klasörü, cron temizliği veya geçici dosya silme işlemi gerekmez. Sunucu yükü statik JavaScript/CSS aktarımı ve küçük giriş doğrulama istekleriyle sınırlıdır. CDN/cache kullanımı bant genişliğini daha da azaltır.
