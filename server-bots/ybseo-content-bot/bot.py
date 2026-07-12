from __future__ import annotations

import html
import io
import json
import os
import random
import re
import smtplib
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from PIL import Image, ImageDraw, ImageFont

WP_URL = os.getenv("WP_URL", "https://ybseo.com.tr").rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_PASSWORD = os.environ["WP_APP_PASSWORD"]
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
MIN_DAYS = int(os.getenv("MIN_DAYS", "3"))
MAX_DAYS = int(os.getenv("MAX_DAYS", "5"))
MIN_WORDS = int(os.getenv("MIN_WORDS", "650"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/ybseo-content-bot/data"))
STATE_FILE = DATA_DIR / "state.json"
PREVIEW_FILE = DATA_DIR / "latest-preview.json"
LOCK_FILE = DATA_DIR / "run.lock"
STATUS_DIR = Path(os.getenv("STATUS_DIR", "/root/automation_status"))
MONITOR_DB = Path(os.getenv("MONITOR_DB", "/root/monitor/monitor.db"))
AUTH = (WP_USER, WP_PASSWORD)
UA = "YBSEOContentBot/1.0 (+https://ybseo.com.tr/)"

SOURCES = [
    {"name": "Moz", "url": "https://moz.com/blog", "feed": "https://moz.com/blog/feed"},
    {"name": "BlogSEO", "url": "https://www.blogseo.io/blog", "feed": None},
    {"name": "Ahrefs", "url": "https://ahrefs.com/blog/", "feed": "https://ahrefs.com/blog/feed/"},
    {"name": "Search Engine Land", "url": "https://searchengineland.com/", "feed": "https://searchengineland.com/feed"},
]
RUN = {"stage": "starting", "started": time.time(), "topic": None, "words": 0, "sources": 0, "attempts": 0}


def log(message: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def track(status: str, message: str, **meta) -> None:
    RUN.update(meta)
    payload = {**RUN, **meta, "elapsed_seconds": round(time.time() - RUN["started"], 1)}
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    (STATUS_DIR / "ybseo-content-bot.json").write_text(json.dumps({"bot": "ybseo-content-bot", "status": status, "message": message, "timestamp": datetime.now().isoformat(timespec="seconds"), "meta": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    MONITOR_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(MONITOR_DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, bot_name TEXT NOT NULL, ts TEXT NOT NULL, status TEXT NOT NULL, message TEXT, meta_json TEXT)")
        conn.execute("INSERT INTO events (bot_name, ts, status, message, meta_json) VALUES (?, ?, ?, ?, ?)", ("ybseo-content-bot", datetime.now().isoformat(timespec="seconds"), status, message, json.dumps(payload, ensure_ascii=False)))
    log(f"{status.upper()} [{RUN['stage']}]: {message}")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"used_urls": [], "last_publish": None, "next_publish": None}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(value: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    value = unicodedata.normalize("NFKD", value.translate(table)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:90]


def request(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": UA, **kwargs.pop("headers", {})}
    response = requests.get(url, headers=headers, timeout=30, **kwargs)
    response.raise_for_status()
    return response


def parse_feed(source: dict) -> list[dict]:
    if not source["feed"]:
        return []
    try:
        soup = BeautifulSoup(request(source["feed"]).content, "xml")
        results = []
        for item in soup.find_all("item")[:20]:
            link = item.find("link")
            title = item.find("title")
            desc = item.find("description")
            if link and title:
                results.append({"source": source["name"], "url": link.get_text(strip=True), "title": title.get_text(" ", strip=True), "summary": BeautifulSoup(desc.get_text() if desc else "", "html.parser").get_text(" ", strip=True)[:500]})
        return results
    except Exception as exc:
        log(f"Feed okunamadı ({source['name']}): {exc}")
        return []


def scrape_index(source: dict) -> list[dict]:
    try:
        soup = BeautifulSoup(request(source["url"]).text, "html.parser")
        host = urlparse(source["url"]).netloc
        found, seen = [], set()
        for anchor in soup.select("a[href]"):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            url = urljoin(source["url"], anchor.get("href", ""))
            if urlparse(url).netloc != host or len(title) < 28 or url in seen:
                continue
            if any(x in url.lower() for x in ("/author/", "/category/", "/tag/", "#")):
                continue
            seen.add(url)
            found.append({"source": source["name"], "url": url, "title": title[:180], "summary": ""})
            if len(found) >= 20:
                break
        return found
    except Exception as exc:
        log(f"Dizin okunamadı ({source['name']}): {exc}")
        return []


def existing_posts() -> list[dict]:
    response = request(f"{WP_URL}/wp-json/wp/v2/posts?per_page=100&_fields=id,link,slug,title")
    return response.json()


def choose_topic(candidates: list[dict], posts: list[dict], used: set[str]) -> dict:
    existing = " ".join(BeautifulSoup(p["title"]["rendered"], "html.parser").get_text() for p in posts).lower()
    blocked = ("jobs", "podcast", "webinar", "event", "pricing", "discount", "release notes")
    scored = []
    for item in candidates:
        if item["url"] in used or any(word in item["title"].lower() for word in blocked):
            continue
        words = [w for w in slugify(item["title"]).split("-") if len(w) > 4]
        overlap = sum(1 for word in words if word in existing)
        item["score"] = len(set(words)) - overlap * 2 + random.random()
        scored.append(item)
    if not scored:
        raise RuntimeError("Uygun yeni konu bulunamadı")
    return max(scored, key=lambda x: x["score"])


def article_text(url: str) -> str:
    soup = BeautifulSoup(request(url).text, "html.parser")
    for tag in soup.select("script,style,nav,footer,header,form,aside"):
        tag.decompose()
    root = soup.select_one("article") or soup.select_one("main") or soup
    chunks = [" ".join(x.get_text(" ", strip=True).split()) for x in root.select("h1,h2,h3,p,li")]
    return "\n".join(x for x in chunks if len(x) > 35)[:9000]


def related_research(topic: dict, candidates: list[dict]) -> list[dict]:
    keys = set(slugify(topic["title"]).split("-"))
    ranked = sorted(candidates, key=lambda x: len(keys & set(slugify(x["title"]).split("-"))), reverse=True)
    selected = [topic]
    for item in ranked:
        if item["url"] != topic["url"] and item["source"] not in {x["source"] for x in selected}:
            selected.append(item)
        if len(selected) == 3:
            break
    research = []
    for item in selected:
        try:
            research.append({**item, "text": article_text(item["url"])[:3500]})
        except Exception as exc:
            log(f"Makale okunamadı ({item['url']}): {exc}")
    return research


def ollama_json(messages: list[dict], predict: int) -> dict:
    response = requests.post(f"{OLLAMA_URL}/api/chat", json={"model": OLLAMA_MODEL, "messages": messages, "format": "json", "stream": False, "keep_alive": "15m", "options": {"temperature": 0.25, "num_ctx": 8192, "num_predict": predict}}, timeout=1200)
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def ollama_text(prompt: str, predict: int = 700) -> str:
    response = requests.post(f"{OLLAMA_URL}/api/chat", json={"model": OLLAMA_MODEL, "messages": [{"role": "system", "content": "Sen deneyimli bir Türk SEO editörüsün. Yalnızca istenen HTML bölümünü üret."}, {"role": "user", "content": prompt}], "stream": False, "keep_alive": "15m", "options": {"temperature": 0.25, "num_ctx": 4096, "num_predict": predict}}, timeout=600)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def add_section(article: dict, heading: str, instruction: str) -> dict:
    existing = BeautifulSoup(article.get("content_html", ""), "html.parser").get_text(" ")[:1800]
    prompt = f"""'{article['title']}' başlıklı SEO yazısına yeni bir bölüm yaz.
Başlık tam olarak: {heading}
Amaç: {instruction}
180-260 Türkçe kelime kullan. <h2>, <h3>, <p>, <ul> ve <li> dışında etiket kullanma.
Mevcut yazıyı tekrarlama, doğrulanmamış sayı veya iddia uydurma. Kaynaklar bölümü ekleme.

MEVCUT METİNDEN ÖZET:
{existing}"""
    fragment = ollama_text(prompt)
    if not fragment.lower().startswith("<h2"):
        fragment = f"<h2>{html.escape(heading)}</h2>" + fragment
    marker = re.search(r"<h2[^>]*>\s*Kaynaklar\s*</h2>", article["content_html"], flags=re.I)
    if marker:
        article["content_html"] = article["content_html"][:marker.start()] + fragment + article["content_html"][marker.start():]
    else:
        article["content_html"] += fragment
    return article


def generate_article(topic: dict, research: list[dict], posts: list[dict]) -> dict:
    sources = "\n\n".join(f"KAYNAK: {x['source']}\nURL: {x['url']}\nBAŞLIK: {x['title']}\nMETİN:\n{x['text']}" for x in research)
    internal = "\n".join(f"- {BeautifulSoup(p['title']['rendered'], 'html.parser').get_text()}: {p['link']}" for p in posts[:12])
    prompt = f"""YBSEO adlı Türk SEO ajansı için özgün, öğretici ve profesyonel bir blog yazısı hazırla.
Konu fikri: {topic['title']}

Kurallar:
- Kaynak cümlelerini çevirmeden veya kopyalamadan bilgileri sentezle.
- En az {MIN_WORDS}, en fazla 1000 Türkçe kelime kullan. Kısa özet üretme; her ana bölümü somut örneklerle açıkla.
- Türkiye'deki işletme, WordPress veya haber sitesi bağlamında somut öneriler ekle.
- H1 kullanma. İçerikte H2 ve gerektiğinde H3, paragraflar, maddeler ve bir kontrol listesi kullan.
- Doğrulanamayan sayı, tarih, alıntı veya başarı vaadi uydurma.
- 2-4 uygun dahili bağlantıyı doğal bağlamda HTML bağlantısı olarak ekle.
- Son bölüm H2 başlıklı 'Kaynaklar' olsun ve araştırma URL'lerini bağlantı olarak listele.
- JSON dışında hiçbir şey yazma.

JSON şeması:
{{"title":"...","slug":"...","excerpt":"140-160 karakter","meta_description":"140-160 karakter","content_html":"<h2>...</h2>...","image_alt":"..."}}

ARAŞTIRMA:
{sources}

MEVCUT YBSEO YAZILARI:
{internal}"""
    RUN["stage"] = "generation"; RUN["attempts"] = 1
    track("running", "İlk yazı üretimi başladı")
    article = ollama_json([{"role": "system", "content": "Sen deneyimli bir Türk SEO editörüsün. Yalnızca geçerli JSON üret."}, {"role": "user", "content": prompt}], 2400)
    RUN["words"] = article_word_count(article)
    if article_word_count(article) < MIN_WORDS:
        RUN["stage"] = "expansion"; RUN["attempts"] = 2
        track("running", f"İlk sürüm {RUN['words']} kelime; otomatik genişletme başladı", words=RUN["words"])
        expand = f"""Aşağıdaki Türkçe SEO yazısı yalnızca {article_word_count(article)} kelime ve fazla kısa.
JSON yapısını aynen koruyarak content_html alanını en az {MIN_WORDS}, en fazla 1000 kelimeye genişlet.
Her H2 altında ayrıntılı açıklama, uygulanabilir adımlar ve örnek ekle. Yeni olgu, sayı veya kaynak uydurma.
Mevcut kaynak bağlantılarını ve dahili bağlantıları koru. Yalnızca geçerli JSON döndür.

{json.dumps(article, ensure_ascii=False)}"""
        article = ollama_json([{"role": "system", "content": "Sen deneyimli bir Türk SEO editörüsün. Yalnızca geçerli JSON üret."}, {"role": "user", "content": expand}], 2600)
        RUN["words"] = article_word_count(article)
    enrichment = [
        ("Uygulama Adımları", "Okurun konuyu kendi sitesinde uygulayabilmesi için sıralı ve somut adımlar ver."),
        ("Yaygın Hatalar ve Kontrol Listesi", "Yaygın yanlışları açıkla ve uygulanabilir bir kontrol listesi sun."),
        ("WordPress ve Haber Siteleri İçin Öneriler", "Konuyu Türkiye'deki WordPress ve haber sitelerine uyarlayan pratik öneriler ver."),
    ]
    for heading, instruction in enrichment:
        if article_word_count(article) >= MIN_WORDS:
            break
        RUN["stage"] = "section_enrichment"; RUN["attempts"] += 1
        track("running", f"Metin {article_word_count(article)} kelime; '{heading}' bölümü ekleniyor", words=article_word_count(article))
        article = add_section(article, heading, instruction)
        RUN["words"] = article_word_count(article)
    return article


def article_word_count(article: dict) -> int:
    text = BeautifulSoup(article.get("content_html", ""), "html.parser").get_text(" ")
    return len(re.findall(r"\b[\wçğıöşüÇĞİÖŞÜ]+\b", text))


def validate(article: dict, research: list[dict]) -> None:
    required = ("title", "slug", "excerpt", "meta_description", "content_html", "image_alt")
    if any(not article.get(k) for k in required):
        raise ValueError("Eksik içerik alanı")
    words = article_word_count(article)
    if words < MIN_WORDS:
        raise ValueError(f"Yazı kısa: {words} kelime")
    if article["content_html"].lower().count("<h2") < 4:
        raise ValueError("Yetersiz bölüm sayısı")
    if not all(x["url"] in article["content_html"] for x in research):
        raise ValueError("Kaynak bağlantıları eksik")
    article["slug"] = slugify(article["slug"] or article["title"])


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def cover(title: str) -> bytes:
    image = Image.new("RGB", (1280, 720), "#071a2e")
    draw = ImageDraw.Draw(image)
    for y in range(720):
        draw.line((0, y, 1280, y), fill=(7 + y // 40, 26 + y // 22, 46 + y // 14))
    draw.rounded_rectangle((70, 68, 1210, 652), radius=34, fill="#0d2944", outline="#2cc5a7", width=3)
    draw.text((115, 112), "YBSEO  •  SEO REHBERİ", font=font(28, True), fill="#2cc5a7")
    words, lines, line = title.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font(55, True)) > 1010:
            lines.append(line); line = word
        else: line = trial
    if line: lines.append(line)
    y = 220
    for text in lines[:4]:
        draw.text((115, y), text, font=font(55, True), fill="white"); y += 74
    draw.text((115, 590), "ybseo.com.tr", font=font(25), fill="#a9bed0")
    output = io.BytesIO(); image.save(output, "WEBP", quality=88, method=6)
    return output.getvalue()


def wp_post(method: str, path: str, **kwargs) -> requests.Response:
    response = requests.request(method, f"{WP_URL}/wp-json/wp/v2/{path}", auth=AUTH, timeout=90, **kwargs)
    response.raise_for_status(); return response


def publish(article: dict) -> dict:
    media = wp_post("POST", "media", data=cover(article["title"]), headers={"Content-Type": "image/webp", "Content-Disposition": f'attachment; filename="{article["slug"]}.webp"'}).json()
    wp_post("POST", f"media/{media['id']}", json={"alt_text": article["image_alt"], "title": article["title"]})
    categories = request(f"{WP_URL}/wp-json/wp/v2/categories?search=SEO&_fields=id,name").json()
    payload = {"title": article["title"], "slug": article["slug"], "excerpt": article["excerpt"], "content": article["content_html"], "status": "publish", "featured_media": media["id"]}
    if categories: payload["categories"] = [categories[0]["id"]]
    return wp_post("POST", "posts", json=payload).json()


def telegram(message: str) -> None:
    values = dotenv_values(os.getenv("TELEGRAM_CONFIG", "/opt/ybseo-content-bot/telegram.env"))
    token, chat = values.get("TELEGRAM_BOT_TOKEN"), values.get("TELEGRAM_CHAT_ID")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": message, "disable_web_page_preview": False}, timeout=30).raise_for_status()


def email_notify(subject: str, message: str) -> None:
    values = dotenv_values(os.getenv("SMTP_CONFIG", "/opt/automations/yenibakis_bulten/.env"))
    recipient = os.getenv("EMAIL_TO", "")
    if not recipient or not values.get("SMTP_HOST"):
        return
    mail = EmailMessage()
    mail["Subject"] = subject
    mail["From"] = values.get("EMAIL_FROM") or values.get("SMTP_USERNAME")
    mail["To"] = recipient
    mail.set_content(message)
    with smtplib.SMTP(values["SMTP_HOST"], int(values.get("SMTP_PORT", "587")), timeout=30) as smtp:
        smtp.starttls()
        smtp.login(values["SMTP_USERNAME"], values["SMTP_PASSWORD"])
        smtp.send_message(mail)


def notify(subject: str, message: str) -> None:
    errors = []
    for sender in (lambda: telegram(message), lambda: email_notify(subject, message)):
        try: sender()
        except Exception as exc: errors.append(str(exc))
    if errors: log("Bildirim uyarısı: " + " | ".join(errors))


def due(state: dict) -> bool:
    if os.getenv("FORCE_RUN") == "1": return True
    if not state.get("next_publish"): return True
    return datetime.now(timezone.utc) >= datetime.fromisoformat(state["next_publish"])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists() and time.time() - LOCK_FILE.stat().st_mtime < 7200:
        log("Başka bir çalışma sürüyor"); return
    LOCK_FILE.write_text(str(os.getpid()))
    try:
        track("running", "Çalışma başladı", stage="schedule_check")
        state = load_state()
        if not due(state): track("idle", f"Sıradaki yayın tarihi: {state['next_publish']}", stage="waiting"); return
        RUN["stage"] = "source_scan"; track("running", "Kaynak taraması başladı")
        posts = existing_posts(); candidates = []
        for source in SOURCES: candidates.extend(parse_feed(source) or scrape_index(source))
        topic = choose_topic(candidates, posts, set(state.get("used_urls", [])))
        RUN["topic"] = topic["title"]; RUN["stage"] = "topic_selected"
        track("running", f"Konu seçildi: {topic['title']} ({topic['source']})", candidates=len(candidates))
        research = related_research(topic, candidates)
        RUN["sources"] = len(research)
        if len(research) < 2: raise RuntimeError("En az iki kaynak okunamadı")
        article = generate_article(topic, research, posts)
        (DATA_DIR / "latest-attempt.json").write_text(json.dumps({"topic": topic, "research": research, "article": article, "metrics": RUN}, ensure_ascii=False, indent=2), encoding="utf-8")
        validate(article, research)
        RUN["words"] = article_word_count(article); RUN["stage"] = "quality_passed"
        PREVIEW_FILE.write_text(json.dumps({"topic": topic, "research": research, "article": article}, ensure_ascii=False, indent=2), encoding="utf-8")
        if DRY_RUN:
            track("ok", f"Yayınsız test başarılı: {article['title']} ({RUN['words']} kelime)"); return
        RUN["stage"] = "wordpress_publish"; track("running", "WordPress yayını başladı")
        result = publish(article)
        state["used_urls"] = (state.get("used_urls", []) + [x["url"] for x in research])[-500:]
        state["last_publish"] = datetime.now(timezone.utc).isoformat()
        state["next_publish"] = (datetime.now(timezone.utc) + timedelta(days=random.randint(MIN_DAYS, MAX_DAYS))).isoformat()
        state["consecutive_failures"] = 0
        state["last_error"] = None
        save_state(state); notify("YBSEO yazısı yayımlandı", f"✅ YBSEO yazısı yayımlandı\n{result['title']['rendered']}\n{result['link']}")
        track("ok", f"Yayımlandı: {result['link']}", stage="published", link=result["link"])
    except Exception as exc:
        diagnostics = f"Aşama: {RUN['stage']}\nKonu: {RUN.get('topic') or '-'}\nKaynak: {RUN['sources']}\nDeneme: {RUN['attempts']}\nKelime: {RUN['words']}\nSüre: {round(time.time()-RUN['started'])} sn"
        state = load_state()
        failures = int(state.get("consecutive_failures", 0)) + 1
        state["consecutive_failures"] = failures
        state["last_error"] = {"at": datetime.now(timezone.utc).isoformat(), "type": type(exc).__name__, "message": str(exc), "stage": RUN["stage"], "metrics": RUN}
        if failures >= 3:
            state["next_publish"] = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
            diagnostics += "\nDevre kesici: 3 ardışık hata nedeniyle 3 gün duraklatıldı."
        else:
            state["next_publish"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        save_state(state)
        track("error", f"{type(exc).__name__}: {exc}")
        try: notify("YBSEO içerik botu hatası", f"❌ YBSEO içerik botu hata verdi\n{type(exc).__name__}: {exc}\n\n{diagnostics}")
        except Exception: pass
        raise
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
