import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COOKIE_NAME, isValidSession } from "./auth.server";
import { SiteFooter, ToolHeader } from "./components/ImageEditor";

export const dynamic = "force-dynamic";

const tools = [
  { href: "/resizer", icon: "↔", eyebrow: "TOPLU İŞLEM", title: "Fotoğraf Boyutlandırma", description: "Çok sayıda fotoğrafı en-boy oranını bozmadan ortak genişliğe dönüştürün. Her dosyaya haber odaklı bir ad verip WebP olarak topluca indirin.", color: "blue" },
  { href: "/crop", icon: "⌗", eyebrow: "1280 × 720", title: "Fotoğraf Kırpma", description: "Fotoğrafı mouse ile sürükleyerek kadrajı belirleyin, ölçek çubuğuyla yakınlaştırın ve yayın ölçüsünde temiz bir haber görseli hazırlayın.", color: "orange" },
  { href: "/tamamlama", icon: "□", eyebrow: "BEYAZ ZEMİN", title: "Fotoğraf Tamamlama", description: "Dikey veya küçük fotoğrafları beyaz 1280×720 canvas üzerinde ortalayın. Görüntüyü bozmadan ölçekleyerek eksik alanları tamamlayın.", color: "green" },
  { href: "/kolaj", icon: "▥", eyebrow: "İKİLİ CANVAS", title: "Fotoğraf Kolajı", description: "İki fotoğrafı yan yana birleştirin. Sağ ve sol görselin ölçek ve konum ayarlarını bağımsız değiştirerek tek bir WebP oluşturun.", color: "purple" },
];

export default async function HomePage() {
  const store = await cookies();
  if (!(await isValidSession(store.get(COOKIE_NAME)?.value))) redirect("/login");
  return <main className="app-shell home-page">
    <ToolHeader />
    <section className="home-hero"><div><span className="eyebrow">YENİ BAKIŞ EDİTÖR ARAÇLARI</span><h1>Habere uygun görseller,<br /><em>birkaç dokunuşla hazır.</em></h1><p>Fotoğraflarınızı sunucuya yüklemeden, doğrudan tarayıcınızda hızlı ve güvenli biçimde düzenleyin. Kullanmak istediğiniz aracı seçerek başlayın.</p></div><div className="hero-badge"><b>4</b><span>pratik fotoğraf aracı</span><small>WebP · 1280×720 · Tarayıcıda işleme</small></div></section>
    <section className="tool-grid">{tools.map((tool) => <article className={`tool-card ${tool.color}`} key={tool.href}><div className="tool-card-icon">{tool.icon}</div><span>{tool.eyebrow}</span><h2>{tool.title}</h2><p>{tool.description}</p><a href={tool.href}>Araca Git <b>→</b></a></article>)}</section>
    <section className="privacy-banner"><div className="privacy-icon">✓</div><div><b>Fotoğraflarınız sunucuya gönderilmez</b><span>Tüm düzenleme, dönüştürme ve indirme işlemleri cihazınızdaki tarayıcı belleğinde gerçekleşir.</span></div></section>
    <SiteFooter />
  </main>;
}
