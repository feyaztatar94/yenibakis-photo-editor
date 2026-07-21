"use client";

import { ChangeEvent, DragEvent, PointerEvent, useEffect, useRef, useState } from "react";

const OUTPUT_WIDTH = 1280;
const OUTPUT_HEIGHT = 720;
const ACCEPTED_IMAGE = /\.(jpe?g|png|webp|avif)$/i;

export type Tool = "resize" | "crop" | "complete";
type ImageItem = { id: string; file: File; url: string; width: number; height: number };
type Transform = { x: number; y: number; scale: number };

export function seoName(value: string, fallback = "gorsel") {
  const safe = value.replace(/\.[^.]+$/, "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("tr-TR").replace(/ı/g, "i").replace(/ğ/g, "g").replace(/ü/g, "u")
    .replace(/ş/g, "s").replace(/ö/g, "o").replace(/ç/g, "c").replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "").replace(/(?:-yenibakishaber)+$/g, "").slice(0, 90);
  return safe || fallback;
}

export function formatBytes(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(2)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function loadImage(url: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Görsel okunamadı."));
    image.src = url;
  });
}

export function canvasBlob(canvas: HTMLCanvasElement, quality: number) {
  return new Promise<Blob>((resolve, reject) => canvas.toBlob(
    (blob) => blob ? resolve(blob) : reject(new Error("WebP oluşturulamadı.")), "image/webp", quality / 100,
  ));
}

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function drawCanvas(canvas: HTMLCanvasElement, image: HTMLImageElement, tool: Tool, transform: Transform) {
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) return;
  canvas.width = OUTPUT_WIDTH;
  canvas.height = OUTPUT_HEIGHT;
  context.fillStyle = tool === "complete" ? "#fff" : "#15171b";
  context.fillRect(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT);
  const fit = tool === "crop"
    ? Math.max(OUTPUT_WIDTH / image.naturalWidth, OUTPUT_HEIGHT / image.naturalHeight)
    : OUTPUT_HEIGHT / image.naturalHeight;
  const scale = fit * transform.scale;
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  let x = (OUTPUT_WIDTH - width) / 2 + transform.x;
  let y = (OUTPUT_HEIGHT - height) / 2 + transform.y;
  if (tool === "crop") {
    x = Math.min(0, Math.max(OUTPUT_WIDTH - width, x));
    y = Math.min(0, Math.max(OUTPUT_HEIGHT - height, y));
  }
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(image, x, y, width, height);
}

async function render(item: ImageItem, tool: Tool, transform: Transform, resizeWidth: number, quality: number) {
  const image = await loadImage(item.url);
  const canvas = document.createElement("canvas");
  if (tool === "resize") {
    canvas.width = resizeWidth;
    canvas.height = Math.max(1, Math.round(image.naturalHeight / image.naturalWidth * resizeWidth));
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("Canvas kullanılamıyor.");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
  } else {
    drawCanvas(canvas, image, tool, transform);
  }
  return canvasBlob(canvas, quality);
}

export function ToolHeader({ active }: { active?: Tool | "collage" }) {
  return <header className="topbar">
    <a className="brand" href="/">
      <span className="brand-logo-window"><img src="/yenibakis-logo-transparent.png" alt="Yeni Bakış" /></span>
      <span>yenibakishaber.com editörleri<br />için hazırlanan <b>Online Photo Editor</b></span>
    </a>
    <nav className="tool-nav" aria-label="Görsel araçları">
      <a className={active === "resize" ? "is-active" : ""} href="/resizer">Boyutlandırma</a>
      <a className={active === "crop" ? "is-active" : ""} href="/crop">Kırpma</a>
      <a className={active === "complete" ? "is-active" : ""} href="/tamamlama">Tamamlama</a>
      <a className={active === "collage" ? "is-active" : ""} href="/kolaj">Kolaj</a>
    </nav>
    <div className="topbar-actions"><a className="xpanel-button" href="https://www.yenibakishaber.com/xpanel" target="_blank" rel="noreferrer">XPanel</a><a className="home-button" href="https://www.yenibakishaber.com/" target="_blank" rel="noreferrer">Yeni Bakış<br />Anasayfa</a><form action="/api/logout" method="post"><button className="logout-button">Çıkış</button></form></div>
  </header>;
}

export function SiteFooter() {
  return <footer className="site-footer"><img src="/yenibakis-logo-transparent.png" alt="Yeni Bakış" /><span>Online Image Editör, Feyaz Tatar tarafından yenibakishaber.com editörleri için hazırlanmıştır.</span></footer>;
}

export default function ImageEditor({ tool }: { tool: Tool }) {
  const [items, setItems] = useState<ImageItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [transforms, setTransforms] = useState<Record<string, Transform>>({});
  const [quality, setQuality] = useState(84);
  const [resizeWidth, setResizeWidth] = useState(1280);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Görsel ekleyerek başlayın.");
  const [estimatedSize, setEstimatedSize] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragRef = useRef<{ px: number; py: number; x: number; y: number } | null>(null);
  const itemsRef = useRef<ImageItem[]>([]);
  const active = items.find((item) => item.id === activeId) ?? items[0];
  const transform = active ? transforms[active.id] ?? { x: 0, y: 0, scale: 1 } : { x: 0, y: 0, scale: 1 };

  useEffect(() => {
    if (!active || tool === "resize" || !canvasRef.current) return;
    let cancelled = false;
    loadImage(active.url).then((image) => { if (!cancelled && canvasRef.current) drawCanvas(canvasRef.current, image, tool, transform); });
    return () => { cancelled = true; };
  }, [active, tool, transform]);

  useEffect(() => {
    if (!active) { setEstimatedSize(null); return; }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      render(active, tool, transform, resizeWidth, quality).then((blob) => { if (!cancelled) setEstimatedSize(blob.size); }).catch(() => { if (!cancelled) setEstimatedSize(null); });
    }, 220);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [active, tool, transform, resizeWidth, quality]);

  useEffect(() => { itemsRef.current = items; }, [items]);
  useEffect(() => () => itemsRef.current.forEach((item) => URL.revokeObjectURL(item.url)), []);

  function updateTransform(change: Partial<Transform>) {
    if (!active) return;
    setTransforms((current) => ({ ...current, [active.id]: { ...transform, ...change } }));
  }

  async function addFiles(files: File[]) {
    const valid = files.filter((file) => file.type.startsWith("image/") || ACCEPTED_IMAGE.test(file.name));
    if (!valid.length) return setStatus("JPG, PNG, WebP veya AVIF formatında bir görsel seçin.");
    const additions = await Promise.all(valid.map(async (file) => {
      const url = URL.createObjectURL(file);
      const image = await loadImage(url);
      return { id: crypto.randomUUID(), file, url, width: image.naturalWidth, height: image.naturalHeight };
    }));
    setItems((current) => [...current, ...additions]);
    setNames((current) => ({ ...current, ...Object.fromEntries(additions.map((item) => [item.id, seoName(item.file.name)])) }));
    setTransforms((current) => ({ ...current, ...Object.fromEntries(additions.map((item) => [item.id, { x: 0, y: 0, scale: 1 }])) }));
    setActiveId((current) => current ?? additions[0].id);
    setStatus(`${additions.length} görsel eklendi. SEO dosya adlarını kontrol edin.`);
  }

  function chooseFiles(event: ChangeEvent<HTMLInputElement>) { void addFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }
  function dropFiles(event: DragEvent) { event.preventDefault(); void addFiles(Array.from(event.dataTransfer.files)); }
  function removeItem(id: string) {
    setItems((current) => {
      const removed = current.find((item) => item.id === id); if (removed) URL.revokeObjectURL(removed.url);
      const next = current.filter((item) => item.id !== id);
      setActiveId((selected) => selected === id ? next[0]?.id ?? null : selected);
      return next;
    });
  }
  function resetAll() {
    items.forEach((item) => URL.revokeObjectURL(item.url));
    setItems([]); setActiveId(null); setNames({}); setTransforms({}); setResizeWidth(1280); setQuality(84); setEstimatedSize(null);
    if (fileInput.current) fileInput.current.value = "";
    setStatus("Tüm işlemler sıfırlandı.");
  }

  function pointerDown(event: PointerEvent<HTMLCanvasElement>) {
    if (tool === "resize") return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { px: event.clientX, py: event.clientY, x: transform.x, y: transform.y };
  }
  function pointerMove(event: PointerEvent<HTMLCanvasElement>) {
    if (!dragRef.current || !canvasRef.current || tool === "resize") return;
    const bounds = canvasRef.current.getBoundingClientRect();
    const ratioX = OUTPUT_WIDTH / bounds.width;
    const ratioY = OUTPUT_HEIGHT / bounds.height;
    updateTransform({
      x: dragRef.current.x + (event.clientX - dragRef.current.px) * ratioX,
      y: dragRef.current.y + (event.clientY - dragRef.current.py) * ratioY,
    });
  }
  function pointerUp() { dragRef.current = null; }

  function outputName(item: ImageItem) { return `${seoName(names[item.id] ?? item.file.name)}-yenibakishaber.webp`; }
  async function saveOne() {
    if (!active || !names[active.id]?.trim()) return setStatus("İndirmeden önce SEO dosya adı girin.");
    setBusy(true); setStatus("WebP hazırlanıyor…");
    try { download(await render(active, tool, transform, resizeWidth, quality), outputName(active)); setStatus("Görsel indirildi."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Görsel işlenemedi."); }
    finally { setBusy(false); }
  }
  async function saveAll() {
    if (!items.length || items.some((item) => !names[item.id]?.trim())) return setStatus("Tüm görseller için SEO dosya adı girin.");
    setBusy(true);
    try {
      for (let index = 0; index < items.length; index += 1) {
        const item = items[index]; setStatus(`${index + 1}/${items.length} hazırlanıyor…`);
        download(await render(item, tool, transforms[item.id] ?? { x: 0, y: 0, scale: 1 }, resizeWidth, quality), outputName(item));
        await new Promise((resolve) => window.setTimeout(resolve, 180));
      }
      setStatus("Tüm görseller indirildi.");
    } catch { setStatus("Toplu işlem tamamlanamadı."); } finally { setBusy(false); }
  }

  const intro = tool === "resize"
    ? ["TOPLU BOYUTLANDIRMA", "Fotoğrafları tek ölçüyle boyutlandırın", "İstediğiniz kadar fotoğraf ekleyin; en-boy oranını bozmadan ortak genişliğe dönüştürün, her dosyanın haberle ilişkili adını düzenleyin ve WebP olarak tek tek ya da topluca indirin."]
    : tool === "crop"
      ? ["16:9 KIRPMA", "Kadrajı mouse ile belirleyin", "Fotoğrafı canvas üzerinde mouse ile sürükleyerek haberin odak noktasını seçin; ölçek çubuğuyla yakınlaştırın ve ekranda gördüğünüz kadrajı tam 1280×720 WebP olarak indirin."]
      : ["FOTOĞRAF TAMAMLAMA", "Fotoğrafı beyaz 1280×720 zemine yerleştirin", "Fotoğrafı oranını bozmadan beyaz 1280×720 canvasın merkezine yerleştirin. Mouse ile sürükleyerek konumlandırın, ölçek çubuğuyla büyütüp küçültün; boş kalan alanlar temiz beyaz zemin olarak korunur."];

  return <main className="app-shell">
    <ToolHeader active={tool} />
    <section className="tool-intro"><div><span className="eyebrow">{intro[0]}</span><h1>{intro[1]}</h1><p>{intro[2]}</p></div><button className="reset-all" onClick={resetAll}>↻ Tümünü sıfırla</button></section>
    <section className="workspace">
      <aside className="queue panel">
        <div className="panel-heading"><b>Görseller</b><span>{items.length}</span></div>
        <button className="add-button" onClick={() => fileInput.current?.click()}>+ Görsel ekle</button>
        <input ref={fileInput} hidden type="file" accept="image/jpeg,image/png,image/webp,image/avif" multiple onChange={chooseFiles} />
        <div className="queue-list">{items.map((item) => <div className={`queue-item ${item.id === active?.id ? "is-active" : ""}`} key={item.id}>
          <button onClick={() => setActiveId(item.id)}><img src={item.url} alt="" /><span><b>{names[item.id] || item.file.name}</b><small>{item.width}×{item.height}</small></span></button>
          <button className="remove" aria-label="Görseli kaldır" onClick={() => removeItem(item.id)}>×</button>
        </div>)}</div>
      </aside>

      <section className="editor panel" onDragOver={(event) => event.preventDefault()} onDrop={dropFiles}>
        {active ? tool === "resize"
          ? <img className="resize-preview" src={active.url} alt={active.file.name} />
          : <div className="canvas-wrap is-draggable"><canvas ref={canvasRef} width={OUTPUT_WIDTH} height={OUTPUT_HEIGHT} aria-label={tool === "crop" ? "Kırpma önizlemesi" : "Tamamlama önizlemesi"} data-offset-x={Math.round(transform.x)} data-offset-y={Math.round(transform.y)} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} /></div>
          : <button className="dropzone" onClick={() => fileInput.current?.click()}><b>Görselleri buraya bırakın</b><span>veya bilgisayarınızdan seçin</span></button>}
        <footer>{active ? `${active.file.name} · ${active.width}×${active.height}` : "JPG, PNG, WebP ve AVIF"}</footer>
      </section>

      <aside className="settings panel">
        <div className="panel-heading"><b>Dosya ve dışa aktarma</b></div>
        {tool === "resize" && <label className="field"><span>Ortak genişlik</span><div className="pixel-input"><input type="number" min="100" max="10000" value={resizeWidth} onChange={(event) => setResizeWidth(Math.min(10000, Math.max(100, Number(event.target.value) || 100)))} /><b>px</b></div></label>}
        {tool !== "resize" && <><div className="fixed-size"><span>Çıktı ölçüsü</span><b>1280 × 720 px</b></div><label className="field"><span>Ölçek: %{Math.round(transform.scale * 100)}</span><input type="range" min={tool === "complete" ? 40 : 100} max="250" value={Math.round(transform.scale * 100)} onChange={(event) => updateTransform({ scale: Number(event.target.value) / 100 })} /></label><button className="reset-button" onClick={() => updateTransform({ x: 0, y: 0, scale: 1 })}>{tool === "crop" ? "Kadrajı ortala" : "Fotoğrafı ortala"}</button></>}
        <label className="field seo-field"><span>Dosya Adı</span><input type="text" value={active ? names[active.id] ?? "" : ""} disabled={!active} placeholder="örnek-haber-fotografi" onChange={(event) => active && setNames((current) => ({ ...current, [active.id]: event.target.value }))} /><small>Haberi açıklayan kelimeler kullanın. Türkçe karakterler ve boşluklar indirmede otomatik düzeltilir.</small></label>
        <label className="field"><span>WebP kalitesi: %{quality}</span><input type="range" min="40" max="100" value={quality} onChange={(event) => setQuality(Number(event.target.value))} /></label>
        <div className="size-estimate"><span>Tahmini boyut:</span><b>{estimatedSize ? formatBytes(estimatedSize) : "—"}</b></div>
        <div className="filename"><span>İndirilecek dosya</span><b>{active ? outputName(active) : "seo-dosya-adi-yenibakishaber.webp"}</b></div>
        <div className="actions"><button className="primary-button" disabled={!active || busy} onClick={saveOne}>Seçili görseli indir</button><button className="secondary-button" disabled={!items.length || busy} onClick={saveAll}>Tümünü ayrı ayrı indir</button></div>
        <p className="status" aria-live="polite">{status}</p>
      </aside>
    </section><SiteFooter />
  </main>;
}
