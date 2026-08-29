from __future__ import annotations

import html
import io
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

PAGES = {
    "home": "https://polariswellbeing.com/",
    "about": "https://polariswellbeing.com/about-us/",
    "team": "https://polariswellbeing.com/who-we-are/",
    "braingym": "https://polariswellbeing.com/the-braingym/",
    "qeeg": "https://polariswellbeing.com/qeeg/",
    "neurofeedback": "https://polariswellbeing.com/neurofeedback/",
    "consultation": "https://polariswellbeing.com/initial-wellbeing-consultation/",
    "contact": "https://polariswellbeing.com/contact/",
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/126 Safari/537.36 PolarisMigration/1.0",
    "Accept-Language": "en-GB,en;q=0.9",
})

BAD_WORDS = {
    "logo", "icon", "favicon", "emoji", "spinner", "arrow", "whatsapp", "facebook",
    "instagram", "linkedin", "google", "certificate", "badge", "pattern", "shape",
    "background", "placeholder", "cropped-polaris-logo", "site-icon", "avatar",
}

@dataclass
class Candidate:
    url: str
    page: str
    alt: str
    position: int
    width: int = 0
    height: int = 0
    entropy: float = 0.0
    faces: int = 0
    score: float = -9999.0


def largest_from_srcset(value: str) -> str | None:
    best_url = None
    best_width = -1
    for item in (value or "").split(","):
        bits = item.strip().split()
        if not bits:
            continue
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except ValueError:
                width = 0
        if width >= best_width:
            best_url, best_width = bits[0], width
    return best_url


def normalise_url(raw: str | None, base: str) -> str | None:
    if not raw or raw.startswith(("data:", "blob:", "javascript:")):
        return None
    url = urljoin(base, raw.strip())
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if "polariswellbeing.com" not in parsed.netloc:
        return None
    return url


def collect() -> tuple[list[Candidate], dict[str, str], dict[str, str]]:
    candidates: list[Candidate] = []
    html_by_page: dict[str, str] = {}
    links: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()

    for page_name, page_url in PAGES.items():
        response = SESSION.get(page_url, timeout=45)
        response.raise_for_status()
        html_by_page[page_name] = response.text
        soup = BeautifulSoup(response.text, "lxml")

        for anchor in soup.find_all("a", href=True):
            href = urljoin(page_url, anchor["href"])
            low = href.lower()
            if "whatsapp" in low or "wa.me" in low:
                links.setdefault("whatsapp", href)
            elif href.startswith("tel:"):
                links.setdefault("phone", href)
            elif href.startswith("mailto:"):
                links.setdefault("email", href)
            elif any(word in low for word in ("simplybook", "book-now", "booking")):
                links.setdefault("booking", href)

        position = 0
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            url = normalise_url(og["content"], page_url)
            if url and (url, page_name) not in seen:
                candidates.append(Candidate(url, page_name, "Open Graph image", position))
                seen.add((url, page_name))
                position += 1

        for img in soup.find_all("img"):
            src = largest_from_srcset(img.get("srcset", "")) or largest_from_srcset(img.get("data-srcset", ""))
            src = src or img.get("data-lazy-src") or img.get("data-src") or img.get("src")
            url = normalise_url(src, page_url)
            if not url or (url, page_name) in seen:
                continue
            alt = " ".join(filter(None, [img.get("alt", ""), " ".join(img.get("class") or [])]))
            candidates.append(Candidate(url, page_name, alt.strip(), position))
            seen.add((url, page_name))
            position += 1

        for element in soup.find_all(style=True):
            for match in re.findall(r"url\([\"']?([^\"')]+)", element.get("style", "")):
                url = normalise_url(match, page_url)
                if not url or (url, page_name) in seen:
                    continue
                candidates.append(Candidate(url, page_name, "Inline background image", position))
                seen.add((url, page_name))
                position += 1

    links.setdefault("phone", "tel:+35699908292")
    links.setdefault("whatsapp", "https://wa.me/35699908292")
    links.setdefault("email", "mailto:info@polariswellbeing.com")
    links.setdefault("booking", "mailto:info@polariswellbeing.com?subject=Initial%20Wellbeing%20Consultation")
    return candidates, html_by_page, links


def image_info(candidate: Candidate, cascade: cv2.CascadeClassifier) -> tuple[Candidate, Image.Image] | None:
    try:
        response = SESSION.get(candidate.url, timeout=35, headers={"Referer": PAGES[candidate.page]})
        response.raise_for_status()
        if len(response.content) > 18_000_000:
            return None
        im = Image.open(io.BytesIO(response.content))
        im = ImageOps.exif_transpose(im).convert("RGB")
        candidate.width, candidate.height = im.size
        if candidate.width < 320 or candidate.height < 220:
            return None
        candidate.entropy = round(im.convert("L").entropy(), 3)
        if candidate.entropy < 3.2:
            return None
        thumb = im.copy()
        thumb.thumbnail((900, 900), Image.Resampling.LANCZOS)
        arr = cv2.cvtColor(np.asarray(thumb), cv2.COLOR_RGB2GRAY)
        faces = cascade.detectMultiScale(arr, scaleFactor=1.12, minNeighbors=5, minSize=(42, 42))
        candidate.faces = len(faces)
        return candidate, im
    except Exception:
        return None


def text_blob(candidate: Candidate) -> str:
    return f"{candidate.url} {candidate.alt}".lower()


def visual_penalty(candidate: Candidate) -> float:
    blob = text_blob(candidate)
    return 400 if any(word in blob for word in BAD_WORDS) else 0


def score_hero(c: Candidate) -> float:
    if c.page not in {"home", "about"}:
        return -9999
    aspect = c.width / c.height
    if not 1.12 <= aspect <= 2.4:
        return -9999
    area = min((c.width * c.height) / 120000, 42)
    page = 34 if c.page == "home" else 24
    face = min(c.faces, 3) * 21
    early = max(0, 28 - c.position * 1.4)
    landscape = 16 if 1.35 <= aspect <= 1.9 else 5
    warm_words = sum(word in text_blob(c) for word in ("polaris", "wellbeing", "factory", "team", "people", "space", "home", "welcome")) * 6
    return area + page + face + early + landscape + warm_words - visual_penalty(c)


def score_space(c: Candidate, hero_url: str) -> float:
    if c.url == hero_url or c.page not in {"home", "about", "team"}:
        return -9999
    aspect = c.width / c.height
    if not 0.9 <= aspect <= 2.2:
        return -9999
    area = min((c.width * c.height) / 140000, 36)
    page = {"about": 28, "home": 22, "team": 16}[c.page]
    face = min(c.faces, 5) * 12
    words = sum(word in text_blob(c) for word in ("team", "polaris", "factory", "space", "interior", "reception", "wellbeing")) * 6
    return area + page + face + words - visual_penalty(c)


def score_braingym(c: Candidate) -> float:
    if c.page not in {"braingym", "qeeg", "neurofeedback"}:
        return -9999
    aspect = c.width / c.height
    if not 0.9 <= aspect <= 2.4:
        return -9999
    area = min((c.width * c.height) / 130000, 38)
    page = {"braingym": 30, "qeeg": 26, "neurofeedback": 24}[c.page]
    keywords = sum(word in text_blob(c) for word in ("brain", "qeeg", "eeg", "neuro", "feedback", "cap", "electrode")) * 10
    face = min(c.faces, 2) * 8
    return area + page + keywords + face - visual_penalty(c)


def save_image(im: Image.Image, name: str, max_width: int, quality: int = 82) -> str:
    if im.width > max_width:
        new_height = round(im.height * max_width / im.width)
        im = im.resize((max_width, new_height), Image.Resampling.LANCZOS)
    path = ASSETS / name
    im.save(path, "WEBP", quality=quality, method=6)
    return f"assets/{name}"


def save_logo(candidates: list[tuple[Candidate, Image.Image]]) -> tuple[str, bool]:
    logo_matches = [item for item in candidates if "polaris-logo" in text_blob(item[0]) or "cropped-polaris" in text_blob(item[0])]
    if not logo_matches:
        logo_matches = [item for item in candidates if "logo" in text_blob(item[0])]
    if not logo_matches:
        return "", False
    candidate, image = max(logo_matches, key=lambda item: item[0].width * item[0].height)
    rgba = Image.open(io.BytesIO(SESSION.get(candidate.url, timeout=30).content))
    rgba = ImageOps.exif_transpose(rgba)
    if rgba.width > 900:
        rgba.thumbnail((900, 900), Image.Resampling.LANCZOS)
    out = ASSETS / "polaris-logo.png"
    rgba.save(out, "PNG", optimize=True)
    return "assets/polaris-logo.png", rgba.width / max(rgba.height, 1) > 2.4


def base_css() -> str:
    return r'''
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&display=swap');
:root{--ink:#14342d;--ink2:#2f4b44;--cream:#fbf8f1;--paper:#fffdf8;--sage:#e9eee8;--sage2:#d7e0d8;--plum:#75536b;--line:rgba(20,52,45,.18);--serif:'Source Serif 4',Georgia,serif;--sans:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--wrap:1180px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--cream);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.58;-webkit-font-smoothing:antialiased}body.has-mobile-cta{padding-bottom:calc(78px + env(safe-area-inset-bottom))}img{display:block;max-width:100%}a{color:inherit;text-decoration:none}button,a{touch-action:manipulation}.wrap{width:min(calc(100% - 40px),var(--wrap));margin:auto}.eyebrow{margin:0 0 13px;color:var(--plum);font-size:.75rem;font-weight:600;letter-spacing:.16em;text-transform:uppercase}.display{font-family:var(--serif);font-weight:400;letter-spacing:-.035em;line-height:.96}.intro{color:var(--ink2);font-size:1.08rem;line-height:1.62}.site-header{height:68px;background:rgba(251,248,241,.94);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:30;backdrop-filter:blur(12px)}.header-inner{height:100%;display:flex;align-items:center;justify-content:space-between;gap:16px}.brand{display:flex;align-items:center;min-width:0}.brand img{max-height:42px;max-width:188px;width:auto}.brand-text{font-family:var(--serif);font-size:1.32rem;white-space:nowrap}.desktop-nav{display:none}.menu-button{width:46px;height:46px;border:0;background:transparent;color:var(--ink);font:600 .77rem var(--sans);letter-spacing:.08em;text-transform:uppercase}.mobile-menu{position:fixed;inset:68px 0 0;background:var(--cream);z-index:29;padding:34px 20px 110px;opacity:0;visibility:hidden;transform:translateY(-10px);transition:.22s ease}.mobile-menu.is-open{opacity:1;visibility:visible;transform:none}.mobile-menu a{display:flex;justify-content:space-between;align-items:center;min-height:62px;border-bottom:1px solid var(--line);font-family:var(--serif);font-size:1.65rem}.mobile-menu .brain-link{color:var(--plum)}.hero{padding:46px 0 54px}.hero h1{font-size:clamp(3.05rem,13vw,4.65rem);max-width:780px;margin:0}.hero-copy{margin:25px 0 25px;max-width:590px;font-size:1.08rem;color:var(--ink2)}.button{display:inline-flex;align-items:center;justify-content:center;min-height:52px;padding:0 24px;background:var(--ink);color:white;border:1px solid var(--ink);font-weight:600;font-size:.92rem;border-radius:999px}.button:hover,.button:focus-visible{background:#214a40}.button.light{background:var(--paper);color:var(--ink)}.micro{display:block;margin-top:14px;color:var(--ink2);font-size:.78rem}.hero-image{margin-top:34px;height:292px;overflow:hidden;border-radius:3px}.hero-image img{width:100%;height:100%;object-fit:cover;object-position:center}.section{padding:66px 0;border-top:1px solid var(--line)}.section h2{font-size:clamp(2.35rem,10vw,4.2rem);margin:0 0 18px;max-width:810px}.service-list{margin-top:30px;border-top:1px solid var(--line)}.service-row{display:grid;grid-template-columns:1fr auto;gap:16px;padding:22px 0;border-bottom:1px solid var(--line);align-items:center}.service-row h3{font-family:var(--serif);font-weight:400;font-size:1.55rem;line-height:1.08;margin:0 0 6px}.service-row p{margin:0;color:var(--ink2);font-size:.89rem}.arrow{font-size:1.35rem;color:var(--plum)}.text-link{display:inline-flex;align-items:center;gap:9px;margin-top:25px;color:var(--plum);font-weight:600;font-size:.9rem}.steps{margin-top:29px}.step{display:grid;grid-template-columns:38px 1fr;gap:15px;padding:19px 0;border-top:1px solid var(--line)}.step:last-child{border-bottom:1px solid var(--line)}.step-number{font-size:.75rem;letter-spacing:.12em;color:var(--plum);padding-top:6px}.step h3{font-family:var(--serif);font-weight:400;font-size:1.45rem;margin:0 0 5px}.step p{margin:0;color:var(--ink2);font-size:.92rem}.why{background:var(--sage)}.why-grid{display:grid;gap:34px}.why-image{height:310px;overflow:hidden}.why-image img{width:100%;height:100%;object-fit:cover}.points{border-top:1px solid rgba(20,52,45,.25);margin-top:25px}.point{padding:18px 0;border-bottom:1px solid rgba(20,52,45,.25)}.point strong{display:block;font-family:var(--serif);font-size:1.28rem;font-weight:400;margin-bottom:3px}.point span{font-size:.88rem;color:var(--ink2)}.link-cluster{display:flex;flex-wrap:wrap;gap:10px 22px;margin-top:24px}.link-cluster a{font-size:.86rem;font-weight:600;color:var(--plum)}.final{padding:74px 0 88px;background:var(--ink);color:white}.final h2{font-size:clamp(2.7rem,12vw,4.7rem);margin:0 0 20px}.final p{color:rgba(255,255,255,.76);max-width:610px;margin:0 0 28px}.footer{padding:42px 0 108px;background:#0f2923;color:rgba(255,255,255,.72);font-size:.82rem}.footer-grid{display:grid;gap:26px}.footer-brand{font-family:var(--serif);font-size:1.55rem;color:white}.footer a{display:block;margin:7px 0}.preview-note{margin-top:26px;padding-top:20px;border-top:1px solid rgba(255,255,255,.14);font-size:.72rem}.mobile-cta{position:fixed;left:0;right:0;bottom:0;z-index:40;padding:10px 14px calc(10px + env(safe-area-inset-bottom));background:rgba(251,248,241,.94);border-top:1px solid var(--line);backdrop-filter:blur(14px)}.mobile-cta .button{width:100%}.page-hero{padding:50px 0 38px}.page-hero h1{font-size:clamp(3.1rem,13vw,5.7rem);margin:0 0 20px}.choice-list{border-top:1px solid var(--line);margin:25px 0 0}.choice{display:grid;grid-template-columns:34px 1fr auto;gap:12px;align-items:center;padding:21px 0;border-bottom:1px solid var(--line)}.choice small{color:var(--plum);letter-spacing:.12em}.choice h2{font-family:var(--serif);font-weight:400;font-size:1.55rem;line-height:1.08;margin:0 0 5px}.choice p{font-size:.86rem;color:var(--ink2);margin:0}.back-link{display:inline-flex;margin:22px 0 0;font-size:.84rem;font-weight:600;color:var(--plum)}.safety{margin-top:36px;padding:20px 0;border-top:1px solid var(--line);font-size:.78rem;color:var(--ink2)}
@media(min-width:780px){body.has-mobile-cta{padding-bottom:0}.wrap{width:min(calc(100% - 72px),var(--wrap))}.site-header{height:82px}.brand img{max-height:54px;max-width:235px}.menu-button,.mobile-menu,.mobile-cta{display:none}.desktop-nav{display:flex;align-items:center;gap:25px;font-size:.78rem;font-weight:600}.desktop-nav .brain-link{color:var(--plum)}.desktop-nav .button{min-height:44px;padding:0 18px}.hero{padding:78px 0 82px}.hero-grid{display:grid;grid-template-columns:minmax(0,.92fr) minmax(400px,.78fr);gap:62px;align-items:center}.hero h1{font-size:clamp(4.4rem,7.2vw,7.15rem)}.hero-copy{font-size:1.18rem}.hero-image{margin:0;height:620px}.section{padding:104px 0}.section h2{font-size:clamp(3.3rem,5.5vw,5rem)}.services-layout{display:grid;grid-template-columns:.72fr 1fr;gap:90px;align-items:start}.service-list{margin-top:0}.conversation-layout{display:grid;grid-template-columns:.8fr 1fr;gap:100px}.steps{margin-top:0}.why-grid{grid-template-columns:1fr 1fr;gap:86px;align-items:center}.why-image{height:610px}.final{padding:112px 0}.footer{padding-bottom:46px}.footer-grid{grid-template-columns:1.4fr repeat(3,1fr)}.page-hero{padding:88px 0 58px}.page-grid{display:grid;grid-template-columns:.78fr 1fr;gap:100px;align-items:start}.choice-list{margin-top:0}.choice{padding:25px 0}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
'''


def brand_markup(logo_path: str, is_wordmark: bool) -> str:
    if logo_path:
        label = '<span class="brand-text">Polaris Wellbeing</span>' if not is_wordmark else ''
        return f'<span class="brand"><img src="{logo_path}" alt="Polaris Wellbeing">{label}</span>'
    return '<span class="brand brand-text">Polaris Wellbeing</span>'


def header(brand: str, contact_href: str = "talk-to-our-team.html") -> str:
    return f'''<header class="site-header"><div class="wrap header-inner"><a href="index.html" aria-label="Polaris Wellbeing home">{brand}</a><nav class="desktop-nav" aria-label="Main navigation"><a href="services.html">How We Can Help</a><a class="brain-link" href="braingym.html">BrainGym</a><a href="index.html#why">Our Approach</a><a href="https://polariswellbeing.com/who-we-are/" target="_blank" rel="noopener">Our Team</a><a href="https://polariswellbeing.com/about-us/" target="_blank" rel="noopener">About Polaris</a><a class="button" href="{contact_href}">Talk to our team</a></nav><button class="menu-button" type="button" aria-expanded="false" aria-controls="mobile-menu">Menu</button></div></header><nav class="mobile-menu" id="mobile-menu" aria-label="Mobile navigation"><a href="services.html">How We Can Help <span>→</span></a><a class="brain-link" href="braingym.html">BrainGym <span>→</span></a><a href="index.html#why">Our Approach <span>→</span></a><a href="https://polariswellbeing.com/who-we-are/">Our Team <span>→</span></a><a href="https://polariswellbeing.com/about-us/">About Polaris <span>→</span></a></nav>'''


def footer() -> str:
    return '''<footer class="footer"><div class="wrap"><div class="footer-grid"><div><div class="footer-brand">Polaris Wellbeing</div><p>A welcoming place for thoughtful care, conversation and specialist support.</p></div><div><strong>Explore</strong><a href="services.html">How We Can Help</a><a href="braingym.html">BrainGym</a><a href="index.html#why">Our Approach</a></div><div><strong>Visit</strong><a href="https://polariswellbeing.com/contact/" target="_blank" rel="noopener">Location & hours</a><a href="talk-to-our-team.html">Talk to our team</a></div><div><strong>Information</strong><a href="https://polariswellbeing.com/privacy-policy/" target="_blank" rel="noopener">Privacy</a></div></div><div class="preview-note">Private design preview · Content and links remain under review · Please do not submit sensitive health information.</div></div></footer>'''


def common_script() -> str:
    return '''<script>const menuButton=document.querySelector('.menu-button');const mobileMenu=document.querySelector('.mobile-menu');if(menuButton&&mobileMenu){menuButton.addEventListener('click',()=>{const open=menuButton.getAttribute('aria-expanded')==='true';menuButton.setAttribute('aria-expanded',String(!open));menuButton.textContent=open?'Menu':'Close';mobileMenu.classList.toggle('is-open',!open);document.body.style.overflow=open?'':'hidden'});mobileMenu.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{menuButton.setAttribute('aria-expanded','false');menuButton.textContent='Menu';mobileMenu.classList.remove('is-open');document.body.style.overflow=''}));}document.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',e=>{const target=document.querySelector(a.getAttribute('href'));if(target){e.preventDefault();target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}}));</script>'''


def document(title: str, body: str, description: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex,nofollow"><meta name="description" content="{html.escape(description)}"><meta name="theme-color" content="#fbf8f1"><title>{html.escape(title)}</title><style>{base_css()}</style></head><body class="has-mobile-cta">{body}{common_script()}</body></html>'''


def build_home(brand: str, hero: str, space: str, brain: str) -> str:
    body = header(brand)
    body += f'''<main><section class="hero"><div class="wrap hero-grid"><div><p class="eyebrow">Welcome to Polaris Wellbeing</p><h1 class="display">Your life is connected. Your care should be too.</h1><p class="hero-copy">Come in, take a seat. Polaris is a welcoming place to talk things through, explore what could help and find the right support — with therapy, BrainGym and specialist care all under one roof.</p><a class="button" href="talk-to-our-team.html">Talk to our team</a><span class="micro">Initial Wellbeing Consultation within 48 hours of booking.</span></div><figure class="hero-image"><img src="{hero}" alt="A welcoming moment at Polaris Wellbeing"></figure></div></section>
<section class="section" id="services"><div class="wrap services-layout"><div><p class="eyebrow">What brings you here?</p><h2 class="display">Support shaped around real life.</h2><p class="intro">You may know exactly what you’re looking for, or simply want to explore. Either is a good place to start.</p></div><div class="service-list"><a class="service-row" href="services.html#therapy"><div><h3>Therapy & emotional wellbeing</h3><p>Space to talk, understand and move forward.</p></div><span class="arrow">→</span></a><a class="service-row" href="services.html#young-people"><div><h3>Children, young people & families</h3><p>Support shaped around growing minds and family life.</p></div><span class="arrow">→</span></a><a class="service-row" href="services.html#specialist"><div><h3>Assessments & specialist care</h3><p>Clearer understanding from the right professional perspective.</p></div><span class="arrow">→</span></a><a class="service-row" href="braingym.html"><div><h3>BrainGym</h3><p>qEEG brain mapping and neurofeedback within the wider Polaris team.</p></div><span class="arrow">→</span></a><a class="text-link" href="services.html">See everything we offer <span>→</span></a></div></div></section>
<section class="section"><div class="wrap conversation-layout"><div><p class="eyebrow">Your first conversation</p><h2 class="display">Let’s begin with a conversation.</h2><p class="intro">No long intake process. No need to choose a service before you speak to us.</p><a class="text-link" href="talk-to-our-team.html">Talk to our team <span>→</span></a></div><div class="steps"><div class="step"><span class="step-number">01</span><div><h3>Tell us what brings you here</h3><p>Share as much or as little as feels comfortable.</p></div></div><div class="step"><span class="step-number">02</span><div><h3>Meet with a wellbeing specialist</h3><p>Your Initial Wellbeing Consultation takes place within 48 hours of booking.</p></div></div><div class="step"><span class="step-number">03</span><div><h3>Agree the next step together</h3><p>We help you find the professional or combination of support that fits.</p></div></div></div></div></section>
<section class="section why" id="why"><div class="wrap why-grid"><figure class="why-image"><img src="{space}" alt="The welcoming environment and people at Polaris Wellbeing"></figure><div><p class="eyebrow">Why Polaris feels different</p><h2 class="display">Professional care, without the clinical atmosphere.</h2><p class="intro">Polaris brings different kinds of expertise together in one welcoming place. You meet people, not departments.</p><div class="points"><div class="point"><strong>A team that talks to each other</strong><span>Your care does not need to be split between disconnected services.</span></div><div class="point"><strong>More than one perspective</strong><span>Different professionals can contribute when that genuinely adds value.</span></div><div class="point"><strong>BrainGym under the same roof</strong><span>qEEG and neurofeedback add a specialist capability to the wider team.</span></div><div class="point"><strong>A space designed to feel human</strong><span>Warm, calm and personal — not like entering a clinical system.</span></div></div><div class="link-cluster"><a href="index.html#why">Our approach →</a><a href="https://polariswellbeing.com/who-we-are/" target="_blank" rel="noopener">Meet the team →</a><a href="https://polariswellbeing.com/about-us/" target="_blank" rel="noopener">About Polaris →</a><a href="braingym.html">Explore BrainGym →</a></div></div></div></section>
<section class="final"><div class="wrap"><p class="eyebrow" style="color:#d9bccf">You’re welcome here</p><h2 class="display">Come and have a conversation.</h2><p>You can arrive knowing exactly what you need, or simply knowing you’d like to talk. Either way, we’ll meet you there.</p><a class="button light" href="talk-to-our-team.html">Talk to our team</a></div></section></main>'''
    body += footer()
    body += '<div class="mobile-cta"><a class="button" href="talk-to-our-team.html">Talk to our team</a></div>'
    return document("Polaris Wellbeing · Live Preview v0.3", body, "A welcoming place for therapy, BrainGym and specialist wellbeing support in Malta.")


def build_contact(brand: str, links: dict[str, str]) -> str:
    email_href = links["email"]
    if "?" not in email_href:
        email_href += "?subject=Message%20for%20Polaris%20Wellbeing"
    body = header(brand, "talk-to-our-team.html")
    body += f'''<main><section class="page-hero"><div class="wrap page-grid"><div><a class="back-link" href="index.html">← Back to Polaris</a><p class="eyebrow" style="margin-top:35px">Talk to our team</p><h1 class="display">How would you like to talk?</h1><p class="intro">Choose what feels easiest. You don’t need to prepare anything or know which service to ask for.</p></div><div class="choice-list"><a class="choice" href="{html.escape(links['booking'], quote=True)}"><small>01</small><div><h2>Initial Consultation</h2><p>A focused first conversation, available within 48 hours of booking.</p></div><span class="arrow">→</span></a><a class="choice" href="{html.escape(links['whatsapp'], quote=True)}"><small>02</small><div><h2>WhatsApp us</h2><p>Message the client care team directly.</p></div><span class="arrow">→</span></a><a class="choice" href="{html.escape(links['phone'], quote=True)}"><small>03</small><div><h2>Call us</h2><p>Speak with the team during reception hours.</p></div><span class="arrow">→</span></a><a class="choice" href="{html.escape(email_href, quote=True)}"><small>04</small><div><h2>Send a message</h2><p>Tell us briefly what you’re looking for and how to reach you.</p></div><span class="arrow">→</span></a><div class="safety">Polaris Wellbeing is not an emergency service. Do not use these routes for urgent or life-threatening situations. The production site will include verified Malta urgent-support information.</div></div></div></section></main>'''
    body += footer()
    return document("Talk to our team · Polaris Wellbeing", body, "Choose the easiest way to start a conversation with Polaris Wellbeing.")


def build_services(brand: str) -> str:
    sections = [
        ("therapy", "Therapy & emotional wellbeing", "Psychology, psychotherapy, counselling, couples and family work, trauma-informed support and other therapeutic approaches."),
        ("young-people", "Children, young people & families", "Psychological, developmental, communication and family support shaped around children, adolescents and the people around them."),
        ("specialist", "Assessments & specialist care", "Psychological, developmental, neurodiversity, psychiatric, occupational and other specialist perspectives available through the team."),
        ("coaching", "Coaching, confidence & performance", "Practical, goal-focused support for work, life transitions, confidence, resilience and personal development."),
        ("body", "Body & physical wellbeing", "Physical, lifestyle and complementary wellbeing services that can sit alongside the wider Polaris approach."),
        ("organisations", "Groups, programmes & organisations", "Workshops, groups, professional programmes and support for organisations and their people."),
    ]
    rows = ''.join(f'<article class="service-row" id="{sid}"><div><h3>{title}</h3><p>{copy}</p></div><a class="arrow" href="talk-to-our-team.html" aria-label="Talk to our team about {title}">→</a></article>' for sid, title, copy in sections)
    body = header(brand)
    body += f'''<main><section class="page-hero"><div class="wrap page-grid"><div><a class="back-link" href="index.html">← Back to home</a><p class="eyebrow" style="margin-top:35px">How we can help</p><h1 class="display">Support for the person, not just the label.</h1><p class="intro">Polaris brings a broad team together, while keeping the first step simple. Explore the main areas below, or talk to us and let us guide you.</p><a class="button" href="talk-to-our-team.html">Talk to our team</a></div><div class="service-list" style="margin-top:0">{rows}<a class="service-row" href="braingym.html"><div><h3>BrainGym</h3><p>qEEG brain mapping and neurofeedback within the wider Polaris team.</p></div><span class="arrow">→</span></a></div></div></section></main>'''
    body += footer() + '<div class="mobile-cta"><a class="button" href="talk-to-our-team.html">Talk to our team</a></div>'
    return document("How We Can Help · Polaris Wellbeing", body, "Explore therapy, family support, assessments, BrainGym and specialist wellbeing care at Polaris.")


def build_braingym(brand: str, brain_image: str) -> str:
    body = header(brand)
    body += f'''<main><section class="page-hero"><div class="wrap"><a class="back-link" href="index.html">← Back to home</a><div class="hero-grid" style="margin-top:38px"><div><p class="eyebrow">BrainGym at Polaris</p><h1 class="display">Another way to understand and work with the brain.</h1><p class="hero-copy">BrainGym brings qEEG brain mapping and EEG-based neurofeedback into the wider Polaris team. It offers an additional perspective when it is relevant to you, without reducing the person to a scan or a set of numbers.</p><a class="button" href="talk-to-our-team.html">Talk to our team</a></div><figure class="hero-image"><img src="{brain_image}" alt="BrainGym equipment and care at Polaris Wellbeing"></figure></div></div></section><section class="section"><div class="wrap services-layout"><div><p class="eyebrow">The two core services</p><h2 class="display">Measurement and feedback, in context.</h2><p class="intro">BrainGym sits alongside conversation, history, goals and professional judgement. It does not replace them.</p></div><div class="service-list"><a class="service-row" href="https://polariswellbeing.com/qeeg/" target="_blank" rel="noopener"><div><h3>qEEG Brain Mapping</h3><p>Recording and quantitative analysis of patterns in scalp electrical activity.</p></div><span class="arrow">→</span></a><a class="service-row" href="https://polariswellbeing.com/neurofeedback/" target="_blank" rel="noopener"><div><h3>Neurofeedback</h3><p>Real-time EEG-derived feedback used during training for self-regulation.</p></div><span class="arrow">→</span></a><a class="text-link" href="talk-to-our-team.html">Ask us about BrainGym <span>→</span></a></div></div></section></main>'''
    body += footer() + '<div class="mobile-cta"><a class="button" href="talk-to-our-team.html">Talk to our team</a></div>'
    return document("BrainGym · Polaris Wellbeing", body, "Explore qEEG brain mapping and neurofeedback within the wider Polaris Wellbeing team.")


def main() -> None:
    candidates, _, links = collect()
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    analysed: list[tuple[Candidate, Image.Image]] = []
    for candidate in candidates:
        result = image_info(candidate, cascade)
        if result:
            analysed.append(result)

    logo_path, is_wordmark = save_logo(analysed)
    brand = brand_markup(logo_path, is_wordmark)

    hero_candidates = []
    for c, im in analysed:
        c.score = score_hero(c)
        if c.score > -9000:
            hero_candidates.append((c, im))
    if not hero_candidates:
        raise RuntimeError("No suitable hero image found")
    hero_c, hero_im = max(hero_candidates, key=lambda item: item[0].score)

    space_candidates = []
    for c, im in analysed:
        c.score = score_space(c, hero_c.url)
        if c.score > -9000:
            space_candidates.append((c, im))
    space_c, space_im = max(space_candidates, key=lambda item: item[0].score)

    brain_candidates = []
    for c, im in analysed:
        c.score = score_braingym(c)
        if c.score > -9000:
            brain_candidates.append((c, im))
    brain_c, brain_im = max(brain_candidates, key=lambda item: item[0].score)

    hero_path = save_image(hero_im, "polaris-hero.webp", 1800, 84)
    space_path = save_image(space_im, "polaris-space.webp", 1500, 82)
    brain_path = save_image(brain_im, "polaris-braingym.webp", 1600, 83)

    (ROOT / "index.html").write_text(build_home(brand, hero_path, space_path, brain_path), encoding="utf-8")
    (ROOT / "talk-to-our-team.html").write_text(build_contact(brand, links), encoding="utf-8")
    (ROOT / "services.html").write_text(build_services(brand), encoding="utf-8")
    (ROOT / "braingym.html").write_text(build_braingym(brand, brain_path), encoding="utf-8")

    provenance = {
        "version": "0.3",
        "source": "https://polariswellbeing.com/",
        "selected": {
            "logo": logo_path,
            "hero": asdict(hero_c),
            "space": asdict(space_c),
            "braingym": asdict(brain_c),
        },
        "contact_links": links,
        "candidate_count": len(candidates),
        "analysed_count": len(analysed),
    }
    (ASSETS / "source-provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(provenance, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
