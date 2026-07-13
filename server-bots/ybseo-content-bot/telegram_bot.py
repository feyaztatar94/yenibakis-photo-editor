from __future__ import annotations

import html
import json
import os
import re
import smtplib
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from docx import Document
from dotenv import dotenv_values

import bot

BASE = Path("/opt/ybseo-content-bot")
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
STATE_FILE = DATA / "telegram-state.json"
PROMPT_FILE = BASE / "EDITOR_PROMPT.md"
TG = dotenv_values(os.getenv("TELEGRAM_CONFIG", str(BASE / "telegram.env")))
TOKEN = TG["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT = int(TG["TELEGRAM_CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"


def default_state() -> dict:
    return {"mode": "idle", "article_parts": [], "source_urls": [], "photos": [], "topic": None, "formatted": None, "next_topic": None, "last_update": 0}


def load_state() -> dict:
    if not STATE_FILE.exists(): return default_state()
    return {**default_state(), **json.loads(STATE_FILE.read_text(encoding="utf-8"))}


def save_state(state: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_workflow(state: dict, keep_schedule: bool = True) -> None:
    last_update = state.get("last_update", 0)
    next_topic = state.get("next_topic") if keep_schedule else None
    state.clear()
    state.update(default_state())
    state["last_update"] = last_update
    state["next_topic"] = next_topic


def api(method: str, **kwargs):
    response = requests.post(f"{API}/{method}", timeout=70, **kwargs)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"): raise RuntimeError(payload)
    return payload.get("result")


def send(text: str) -> None:
    for start in range(0, len(text), 3900):
        api("sendMessage", data={"chat_id": ALLOWED_CHAT, "text": text[start:start + 3900], "disable_web_page_preview": True})


def send_document(path: Path, caption: str) -> None:
    with path.open("rb") as handle:
        api("sendDocument", data={"chat_id": ALLOWED_CHAT, "caption": caption[:900]}, files={"document": (path.name, handle)})


def send_preview_email(article: dict, summary: str, page: str) -> None:
    values = dotenv_values(os.getenv("SMTP_CONFIG", "/opt/automations/yenibakis_bulten/.env"))
    recipient = os.getenv("EMAIL_TO", "")
    if not recipient or not values.get("SMTP_HOST"):
        return
    mail = EmailMessage()
    mail["Subject"] = f"YBSEO yazı önizlemesi: {article.get('title')}"
    mail["From"] = values.get("EMAIL_FROM") or values.get("SMTP_USERNAME")
    mail["To"] = recipient
    mail.set_content(summary + "\n\nYazının tam HTML önizlemesi bu e-postaya eklenmiştir.")
    mail.add_attachment(page.encode("utf-8"), maintype="text", subtype="html", filename=f"{article.get('slug', 'ybseo-onizleme')}.html")
    with smtplib.SMTP(values["SMTP_HOST"], int(values.get("SMTP_PORT", "587")), timeout=30) as smtp:
        smtp.starttls()
        smtp.login(values["SMTP_USERNAME"], values["SMTP_PASSWORD"])
        smtp.send_message(mail)


def topic_pack(state: dict) -> None:
    send("🔎 YBSEO kaynakları taranıyor ve benzer yazılar eşleştiriliyor...")
    posts = bot.existing_posts(); candidates = []
    for source in bot.SOURCES: candidates.extend(bot.parse_feed(source) or bot.scrape_index(source))
    topic = bot.choose_topic(candidates, posts, set())
    topic_keys = bot.keywords(topic["title"])
    ranked = sorted(candidates, key=lambda x: len(topic_keys & bot.keywords(x["title"])), reverse=True)
    research = [topic]
    for item in ranked:
        if item["url"] == topic["url"] or item["source"] in {x["source"] for x in research}:
            continue
        if topic_keys & bot.keywords(item["title"]):
            research.append(item)
        if len(research) == 4:
            break
    if len(research) < 2: raise RuntimeError("Eşleşen en az iki kaynak bulunamadı")
    state["topic"] = {"title": topic["title"], "sources": [{"source": x["source"], "title": x["title"], "url": x["url"]} for x in research]}
    state["source_urls"] = [x["url"] for x in research]
    state["next_topic"] = (datetime.now() + timedelta(days=4)).isoformat()
    save_state(state)
    lines = [f"📚 Yeni konu paketi\n\nÖnerilen konu:\n{topic['title']}\n", "Eşleşen kaynaklar:"]
    lines += [f"• {x['source']}: {x['title']}\n{x['url']}" for x in research]
    lines += ["", "Yazıyı hazırladıktan sonra /yazi komutunu gönderin. Metni mesajlar halinde veya .txt/.docx dosyası olarak iletebilirsiniz."]
    send("\n".join(lines))


def download_file(file_id: str, name: str) -> Path:
    info = api("getFile", data={"file_id": file_id})
    response = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{info['file_path']}", timeout=60)
    response.raise_for_status()
    content = response.content
    UPLOADS.mkdir(parents=True, exist_ok=True)
    path = UPLOADS / re.sub(r"[^a-zA-Z0-9._-]", "-", name)
    path.write_bytes(content); return path


def document_text(message: dict) -> str:
    doc = message["document"]
    path = download_file(doc["file_id"], doc.get("file_name", "article.txt"))
    suffix = path.suffix.lower()
    if suffix in (".txt", ".html", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        return "\n\n".join(p.text for p in Document(path).paragraphs if p.text.strip())
    raise ValueError("Yalnızca .txt, .md, .html veya .docx metin dosyası kabul edilir")


def format_article(state: dict) -> None:
    raw = "\n\n".join(state["article_parts"]).strip()
    word_count = len(re.findall(r"\b\w+\b", BeautifulSoup(raw, "html.parser").get_text(" ")))
    if word_count < bot.MIN_WORDS:
        raise ValueError(f"Yazı çok kısa ({word_count} kelime); en az {bot.MIN_WORDS} kelimelik nihai metin gönderin")
    internal = bot.existing_posts()[:30]
    user = f"""Aşağıdaki metni YBSEO için WordPress'e uygun hale getir.
Metni yeniden yazma, yeni bilgi veya kaynak üretme, anlamı koru. Doğru H2/H3 hiyerarşisi ve SEO alanları oluştur. Kritik sorun varsa ready_to_publish=false döndür.

KULLANICININ YAZISI:\n{raw}

KULLANICININ VERDİĞİ KAYNAKLAR:\n{chr(10).join(state['source_urls']) or 'Yok'}

MEVCUT YBSEO DAHİLİ BAĞLANTILARI:\n{chr(10).join(f"{x['title']['rendered']}: {x['link']}" for x in internal)}
"""
    send("🧭 Yazı, SEO ve WordPress HTML yapısına dönüştürülüyor. Bu işlem birkaç dakika sürebilir.")
    formatted = bot.ollama_json([{"role": "system", "content": PROMPT_FILE.read_text(encoding="utf-8")}, {"role": "user", "content": user}], 3600)
    validate_formatted(formatted, raw, state)
    state["formatted"] = formatted; state["mode"] = "review"; save_state(state)
    preview(state)


def validate_formatted(article: dict, raw: str, state: dict) -> None:
    required = {"title", "seo_title", "slug", "meta_description", "focus_keyword", "excerpt", "content_html", "quality_report", "ready_to_publish"}
    missing = required.difference(article)
    if missing:
        raise ValueError("Eksik çıktı alanları: " + ", ".join(sorted(missing)))
    soup = BeautifulSoup(article["content_html"], "html.parser")
    allowed_tags = {"p", "h2", "h3", "ul", "ol", "li", "strong", "em", "a", "br"}
    forbidden = sorted({tag.name for tag in soup.find_all(True) if tag.name not in allowed_tags})
    if forbidden:
        raise ValueError("İzin verilmeyen HTML etiketi: " + ", ".join(forbidden))
    if not soup.find("h2"):
        raise ValueError("Yazıda H2 ara başlığı bulunmuyor")
    for tag in soup.find_all(True):
        allowed_attrs = {"href", "rel", "target"} if tag.name == "a" else set()
        unexpected = set(tag.attrs).difference(allowed_attrs)
        if unexpected:
            raise ValueError(f"{tag.name} etiketinde izin verilmeyen özellik: {', '.join(sorted(unexpected))}")
    raw_words = len(re.findall(r"\b\w+\b", BeautifulSoup(raw, "html.parser").get_text(" ")))
    output_words = len(re.findall(r"\b\w+\b", soup.get_text(" ")))
    if output_words < raw_words * 0.75 or output_words > raw_words * 1.35:
        raise ValueError(f"Editör metin hacmini fazla değiştirdi ({raw_words} → {output_words} kelime)")
    allowed_urls = set(state.get("source_urls", []))
    allowed_urls.update(x.get("link") for x in bot.existing_posts()[:30])
    allowed_urls.discard(None)
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.startswith(("#", "/")):
            continue
        if href not in allowed_urls:
            raise ValueError(f"Model izin verilmeyen bir bağlantı ekledi: {urlparse(href).netloc or href}")
    report = article.get("quality_report") or {}
    if report.get("critical_issues"):
        article["ready_to_publish"] = False


def preview(state: dict) -> None:
    article = state.get("formatted")
    if not article: raise ValueError("Henüz biçimlendirilmiş yazı yok")
    report = article.get("quality_report", {})
    summary = f"📝 SEO önizlemesi hazır\n\nBaşlık: {article.get('title')}\nSEO başlığı: {article.get('seo_title')}\nURL: /{article.get('slug')}/\nAnahtar kelime: {article.get('focus_keyword')}\nYayıma hazır: {'Evet' if article.get('ready_to_publish') else 'Hayır'}\n\nUyarılar:\n" + "\n".join(f"• {x}" for x in report.get("warnings", []) + report.get("critical_issues", []))
    send(summary + "\n\nKomutlar: /taslak, /yayinla, /zamanla GG.AA.YYYY SS:DD, /duzelt talimat, /iptal")
    page = f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{html.escape(article.get("title", ""))}</title><style>body{{font:18px/1.7 system-ui;max-width:900px;margin:40px auto;padding:20px}}h1,h2,h3{{line-height:1.25}}</style></head><body><h1>{html.escape(article.get("title", ""))}</h1>{article.get("content_html", "")}</body></html>'
    path = DATA / "telegram-preview.html"; path.write_text(page, encoding="utf-8"); send_document(path, "YBSEO yayın önizlemesi")
    send_preview_email(article, summary, page)


def upload_image(path: Path, alt: str) -> dict:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    response = bot.wp_post("POST", "media", data=path.read_bytes(), headers={"Content-Type": mime, "Content-Disposition": f'attachment; filename="{path.name}"'}).json()
    bot.wp_post("POST", f"media/{response['id']}", json={"alt_text": alt})
    return response


def publish(state: dict, status: str, date: str | None = None) -> dict:
    article = state.get("formatted")
    if not article: raise ValueError("Yayımlanacak biçimlendirilmiş yazı yok")
    if status != "draft" and not article.get("ready_to_publish"):
        raise ValueError("Kalite raporu yazıyı yayıma hazır bulmadı. /duzelt ile sorunları giderin veya yalnız /taslak kullanın")
    media = []
    for item in state.get("photos", []): media.append(upload_image(Path(item), article.get("focus_keyword", "YBSEO görseli")))
    if not media:
        media.append(bot.wp_post("POST", "media", data=bot.cover(article["title"]), headers={"Content-Type": "image/webp", "Content-Disposition": f'attachment; filename="{article["slug"]}.webp"'}).json())
    content = article["content_html"]
    if len(media) > 1:
        content += "<h2>İlgili Görseller</h2>" + "".join(f'<figure><img src="{x["source_url"]}" alt="{html.escape(article.get("focus_keyword", ""))}"></figure>' for x in media[1:])
    payload = {"title": article["title"], "slug": article["slug"], "excerpt": article["excerpt"], "content": content, "status": status, "featured_media": media[0]["id"]}
    if date: payload["date"] = date
    result = bot.wp_post("POST", "posts", json=payload).json()
    send(f"✅ WordPress işlemi tamamlandı\nDurum: {status}\n{result.get('link')}")
    reset_workflow(state); save_state(state); return result


def command(message: dict, state: dict) -> None:
    text = message.get("text", "").strip(); cmd = text.split()[0].lower() if text.startswith("/") else ""
    if cmd in ("/start", "/yardim"):
        send("YBSEO editör botu hazır.\n\n/konu — kaynak paketi\n/yazi — yazı toplama\n/bitir — biçimlendir\n/onizle — önizleme\n/taslak — WordPress taslağı\n/yayinla — yayımla\n/zamanla GG.AA.YYYY SS:DD\n/iptal — işlemi sil\n/durum — durum")
    elif cmd == "/konu": reset_workflow(state); topic_pack(state)
    elif cmd == "/yazi":
        state["mode"] = "collecting"; state["article_parts"] = []; state["photos"] = []; state["formatted"] = None
        save_state(state); send("Metni mesajlar halinde veya .txt/.docx dosyası olarak gönderin. Tamamlanınca /bitir yazın.")
    elif cmd == "/bitir": format_article(state)
    elif cmd == "/onizle": preview(state)
    elif cmd == "/iptal": reset_workflow(state); save_state(state); send("İşlem iptal edildi.")
    elif cmd == "/durum": send(f"Durum: {state['mode']}\nKonu: {(state.get('topic') or {}).get('title','-')}\nMetin parçaları: {len(state['article_parts'])}\nGörsel: {len(state['photos'])}")
    elif cmd == "/taslak": publish(state, "draft")
    elif cmd == "/yayinla": publish(state, "publish")
    elif cmd == "/zamanla":
        value = text[len(cmd):].strip(); when = datetime.strptime(value, "%d.%m.%Y %H:%M")
        publish(state, "future", when.strftime("%Y-%m-%dT%H:%M:%S"))
    elif cmd == "/duzelt":
        if not state.get("formatted"): raise ValueError("Önce yazıyı /bitir ile biçimlendirin")
        instruction = text[len(cmd):].strip()
        if not instruction: raise ValueError("/duzelt komutundan sonra değişiklik talimatını yazın")
        user = f"Mevcut JSON'u yalnız şu talimata göre düzelt; yeni bilgi ekleme ve aynı JSON şemasını koru. Talimat: {instruction}\nJSON: {json.dumps(state['formatted'], ensure_ascii=False)}"
        revised = bot.ollama_json([{"role": "system", "content": PROMPT_FILE.read_text(encoding="utf-8")}, {"role": "user", "content": user}], 3600)
        validate_formatted(revised, "\n\n".join(state["article_parts"]), state)
        state["formatted"] = revised; save_state(state); preview(state)
    elif message.get("document") and state["mode"] == "collecting":
        state["article_parts"].append(document_text(message)); save_state(state); send("Dosya metne eklendi. Başka parça gönderebilir veya /bitir yazabilirsiniz.")
    elif message.get("photo"):
        item = message["photo"][-1]; path = download_file(item["file_id"], f"photo-{int(time.time())}.jpg")
        state["photos"].append(str(path)); save_state(state); send("Görsel kaydedildi. İlk görsel kapak olarak kullanılacak.")
    elif state["mode"] == "collecting" and text:
        state["article_parts"].append(text); save_state(state); send(f"Metin parçası eklendi ({len(state['article_parts'])}). Tamamlanınca /bitir yazın.")
    else: send("Komut anlaşılmadı. /yardim yazabilirsiniz.")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True); state = load_state(); offset = int(state.get("last_update", 0))
    bot.track("ok", "Telegram editör servisi başladı", stage="telegram_editor")
    if not state.get("next_topic"):
        try: topic_pack(state)
        except Exception as exc: bot.log(f"İlk konu paketi hazırlanamadı: {exc}")
    while True:
        try:
            updates = api("getUpdates", data={"offset": offset, "timeout": 25, "allowed_updates": json.dumps(["message"])})
            for update in updates:
                offset = update["update_id"] + 1; state["last_update"] = offset; save_state(state)
                message = update.get("message", {})
                if message.get("chat", {}).get("id") != ALLOWED_CHAT: continue
                try: command(message, state)
                except Exception as exc: send(f"❌ İşlem tamamlanamadı\n{type(exc).__name__}: {exc}"); bot.track("error", str(exc), stage="telegram_command")
            if state.get("next_topic") and datetime.now() >= datetime.fromisoformat(state["next_topic"]): topic_pack(state)
        except Exception as exc:
            bot.log(f"Telegram döngüsü: {exc}"); time.sleep(10)


if __name__ == "__main__": main()
