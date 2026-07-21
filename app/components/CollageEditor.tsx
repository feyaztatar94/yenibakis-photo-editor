"use client";

import { ChangeEvent, DragEvent, KeyboardEvent, PointerEvent, useEffect, useRef, useState } from "react";
import { canvasBlob, download, formatBytes, loadImage, seoName, SiteFooter, ToolHeader } from "./ImageEditor";

const WIDTH = 1280;
const HEIGHT = 720;
type Slot = { file: File; url: string } | null;
type Control = { scale: number; x: number; y: number };

function drawSlot(context: CanvasRenderingContext2D, image: HTMLImageElement, side: 0 | 1, control: Control, divider: number) {
  const leftWidth = WIDTH * divider;
  const slotWidth = side === 0 ? leftWidth : WIDTH - leftWidth;
  const fit = Math.max(slotWidth / image.naturalWidth, HEIGHT / image.naturalHeight);
  const scale = fit * control.scale;
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  const slotX = side === 0 ? 0 : leftWidth;
  const x = slotX + (slotWidth - width) / 2 + control.x;
  const y = (HEIGHT - height) / 2 + control.y;
  context.save();
  context.beginPath(); context.rect(slotX, 0, slotWidth, HEIGHT); context.clip();
  context.drawImage(image, x, y, width, height);
  context.restore();
}

export default function CollageEditor() {
  const [slots, setSlots] = useState<[Slot, Slot]>([null, null]);
  const [controls, setControls] = useState<[Control, Control]>([{ scale: 1, x: 0, y: 0 }, { scale: 1, x: 0, y: 0 }]);
  const [divider, setDivider] = useState(0.5);
  const [name, setName] = useState("haber-fotograf-kolaji");
  const [quality, setQuality] = useState(84);
  const [status, setStatus] = useState("Sol ve sağ alan için birer fotoğraf ekleyin.");
  const [estimatedSize, setEstimatedSize] = useState<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const canvasAreaRef = useRef<HTMLDivElement>(null);
  const dividerDragRef = useRef(false);
  const slotsRef = useRef<[Slot, Slot]>([null, null]);
  const drawVersionRef = useRef(0);

  useEffect(() => {
    const version = ++drawVersionRef.current;
    Promise.all(slots.map((slot) => slot ? loadImage(slot.url) : null)).then((images) => {
      if (version !== drawVersionRef.current) return;
      const buffer = document.createElement("canvas"); buffer.width = WIDTH; buffer.height = HEIGHT;
      const context = buffer.getContext("2d", { alpha: false }); if (!context) return;
      context.imageSmoothingEnabled = true; context.imageSmoothingQuality = "high";
      context.fillStyle = "#fff"; context.fillRect(0, 0, WIDTH, HEIGHT);
      images.forEach((image, index) => { if (image) drawSlot(context, image, index as 0 | 1, controls[index], divider); });
      const dividerX = WIDTH * divider;
      context.strokeStyle = "rgba(39,73,155,.22)"; context.lineWidth = 2; context.beginPath(); context.moveTo(dividerX, 0); context.lineTo(dividerX, HEIGHT); context.stroke();
      const canvas = canvasRef.current; if (!canvas || version !== drawVersionRef.current) return;
      canvas.width = WIDTH; canvas.height = HEIGHT;
      canvas.getContext("2d", { alpha: false })?.drawImage(buffer, 0, 0);
    });
  }, [slots, controls, divider]);

  useEffect(() => { slotsRef.current = slots; }, [slots]);
  useEffect(() => () => slotsRef.current.forEach((slot) => { if (slot) URL.revokeObjectURL(slot.url); }), []);

  useEffect(() => {
    if (!slots[0] || !slots[1] || !canvasRef.current) { setEstimatedSize(null); return; }
    let cancelled = false;
    const timer = window.setTimeout(() => canvasRef.current && canvasBlob(canvasRef.current, quality).then((blob) => { if (!cancelled) setEstimatedSize(blob.size); }), 260);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [slots, controls, quality, divider]);

  function choose(side: 0 | 1, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return;
    const url = URL.createObjectURL(file);
    setSlots((current) => {
      const next: [Slot, Slot] = [...current]; if (next[side]) URL.revokeObjectURL(next[side]!.url); next[side] = { file, url }; return next;
    });
    setStatus(`${side === 0 ? "Sol" : "Sağ"} fotoğraf eklendi.`); event.target.value = "";
  }
  function setFile(side: 0 | 1, file?: File) {
    if (!file || !file.type.startsWith("image/")) return setStatus("Geçerli bir fotoğraf bırakın.");
    const url = URL.createObjectURL(file);
    setSlots((current) => { const next: [Slot, Slot] = [...current]; if (next[side]) URL.revokeObjectURL(next[side]!.url); next[side] = { file, url }; return next; });
    setStatus(`${side === 0 ? "Sol" : "Sağ"} fotoğraf eklendi.`);
  }
  function drop(side: 0 | 1, event: DragEvent<HTMLDivElement>) { event.preventDefault(); setFile(side, event.dataTransfer.files[0]); }
  function update(side: 0 | 1, change: Partial<Control>) {
    setControls((current) => { const next: [Control, Control] = [{ ...current[0] }, { ...current[1] }]; next[side] = { ...next[side], ...change }; return next; });
  }
  function moveDivider(clientX: number) {
    const bounds = canvasAreaRef.current?.getBoundingClientRect();
    if (!bounds) return;
    setDivider(Math.min(0.8, Math.max(0.2, (clientX - bounds.left) / bounds.width)));
  }
  function dividerDown(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dividerDragRef.current = true;
    moveDivider(event.clientX);
  }
  function dividerMove(event: PointerEvent<HTMLDivElement>) {
    if (dividerDragRef.current) moveDivider(event.clientX);
  }
  function dividerUp() { dividerDragRef.current = false; }
  function dividerKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setDivider((current) => Math.min(0.8, Math.max(0.2, current + (event.key === "ArrowRight" ? 0.02 : -0.02))));
  }
  async function save() {
    if (!slots[0] || !slots[1]) return setStatus("Kolaj için iki fotoğrafı da ekleyin.");
    if (!name.trim()) return setStatus("SEO dosya adı girin.");
    if (!canvasRef.current) return;
    download(await canvasBlob(canvasRef.current, quality), `${seoName(name, "fotograf-kolaji")}-yenibakishaber.webp`);
    setStatus("Kolaj indirildi.");
  }
  function resetAll() {
    slots.forEach((slot) => { if (slot) URL.revokeObjectURL(slot.url); });
    setSlots([null, null]); setControls([{ scale: 1, x: 0, y: 0 }, { scale: 1, x: 0, y: 0 }]); setDivider(0.5); setName("haber-fotograf-kolaji"); setQuality(84); setEstimatedSize(null); setStatus("Tüm işlemler sıfırlandı.");
  }

  return <main className="app-shell">
    <ToolHeader active="collage" />
    <section className="tool-intro"><div><span className="eyebrow">FOTOĞRAF KOLAJI</span><h1>İki fotoğrafı tek haber görselinde birleştirin</h1><p>Sol ve sağ alana fotoğrafları sürükleyip bırakın. Ortadaki ayracı mouse ile sağa veya sola çekerek alan genişliklerini değiştirin; her fotoğrafı kendi alanının altındaki kontrollerle bağımsız düzenleyin.</p></div><button className="reset-all" onClick={resetAll}>↻ Tümünü sıfırla</button></section>
    <section className="collage-workspace">
      <section className="collage-stage panel">
        <div className="collage-canvas-area" ref={canvasAreaRef}><canvas ref={canvasRef} width={WIDTH} height={HEIGHT} /><div className="collage-drop-grid" style={{ gridTemplateColumns: `${divider}fr ${1 - divider}fr` }}><div onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(0, event)}><label>{slots[0] ? "Sol fotoğrafı değiştir" : "Sol fotoğrafı buraya bırak"}<input type="file" hidden accept="image/*" onChange={(event) => choose(0, event)} /></label></div><div onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(1, event)}><label>{slots[1] ? "Sağ fotoğrafı değiştir" : "Sağ fotoğrafı buraya bırak"}<input type="file" hidden accept="image/*" onChange={(event) => choose(1, event)} /></label></div></div><div className="collage-divider" style={{ left: `${divider * 100}%` }} role="separator" aria-label="Kolaj alanlarını böl" aria-orientation="vertical" aria-valuemin={20} aria-valuemax={80} aria-valuenow={Math.round(divider * 100)} tabIndex={0} onPointerDown={dividerDown} onPointerMove={dividerMove} onPointerUp={dividerUp} onPointerCancel={dividerUp} onKeyDown={dividerKeyDown}><span>↔</span></div></div>
        <div className="collage-split-status">Sol alan %{Math.round(divider * 100)} · Sağ alan %{Math.round((1 - divider) * 100)}</div>
        <div className="collage-control-grid" style={{ gridTemplateColumns: `${divider}fr ${1 - divider}fr` }}>{[0, 1].map((index) => { const side = index as 0 | 1; const control = controls[side]; return <fieldset key={side}><legend>{side === 0 ? "Sol fotoğraf ayarları" : "Sağ fotoğraf ayarları"}</legend>
          <label className="field"><span>Ölçek: %{Math.round(control.scale * 100)}</span><input type="range" min="100" max="250" value={control.scale * 100} onChange={(event) => update(side, { scale: Number(event.target.value) / 100 })} /></label>
          <label className="field"><span>Yatay konum</span><input type="range" min="-500" max="500" value={control.x} onChange={(event) => update(side, { x: Number(event.target.value) })} /></label>
          <label className="field"><span>Dikey konum</span><input type="range" min="-500" max="500" value={control.y} onChange={(event) => update(side, { y: Number(event.target.value) })} /></label>
        </fieldset>; })}</div>
      </section>
      <aside className="collage-settings panel">
        <div className="panel-heading"><b>Dosya ve dışa aktarma</b></div>
        <label className="field seo-field"><span>Dosya Adı</span><input value={name} onChange={(event) => setName(event.target.value)} /><small>İndirmede Türkçe karakterler ve boşluklar otomatik düzenlenir.</small></label>
        <label className="field"><span>WebP kalitesi: %{quality}</span><input type="range" min="40" max="100" value={quality} onChange={(event) => setQuality(Number(event.target.value))} /></label>
        <div className="size-estimate"><span>Tahmini boyut:</span><b>{estimatedSize ? formatBytes(estimatedSize) : "—"}</b></div>
        <div className="filename"><span>İndirilecek dosya</span><b>{seoName(name, "fotograf-kolaji")}-yenibakishaber.webp</b></div>
        <button className="primary-button collage-download" onClick={save}>Kolajı indir</button><p className="status">{status}</p>
      </aside>
    </section><SiteFooter />
  </main>;
}
