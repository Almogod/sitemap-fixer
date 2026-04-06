# src/content/competitor_analyzer.py
"""
Analyzes competitor pages for a given keyword to build a rich content brief.
Fetches top competitor pages, extracts headings, keywords, word count,
LSI terms (including bigrams/trigrams), FAQ patterns, named entities,
search intent, and power words to create a comprehensive content brief.
"""

import httpx
from bs4 import BeautifulSoup
from collections import Counter
import re
import json
from src.content.content_brief import (
    ContentBrief,
    INTENT_INFORMATIONAL, INTENT_COMMERCIAL,
    INTENT_TRANSACTIONAL, INTENT_NAVIGATIONAL,
    STRUCTURE_GUIDE, STRUCTURE_LISTICLE, STRUCTURE_HOWTO,
    STRUCTURE_COMPARISON, STRUCTURE_DEEPDIVE,
    TONE_AUTHORITATIVE, TONE_CONVERSATIONAL,
    TONE_EDUCATIONAL, TONE_PERSUASIVE,
)
from src.content.stopwords import STOPWORDS, filter_stopwords_min_length
from src.utils.security import is_safe_url


# ── Power words — emotionally engaging words that boost CTR ──────────
POWER_WORDS = {
    "ultimate", "proven", "essential", "exclusive", "powerful",
    "revolutionary", "guaranteed", "secret", "breakthrough", "stunning",
    "insider", "effortless", "instantly", "remarkable", "critical",
    "surprising", "definitive", "comprehensive", "actionable", "must-know",
    "game-changing", "expert", "advanced", "complete", "crucial",
    "unbelievable", "mind-blowing", "life-changing", "epic", "legendary",
    "unstoppable", "foolproof", "brilliant", "jaw-dropping", "incredible",
    "savvy", "genius", "hack", "hacks", "masterclass", "blueprint",
    "dominate", "skyrocket", "transform", "supercharge", "turbocharge",
    "maximize", "optimize", "leverage", "amplify", "accelerate",
    "unlock", "unleash", "discover", "reveal", "expose",
}

# ── Intent signal patterns ───────────────────────────────────────────
_INFORMATIONAL_SIGNALS = {
    "how to", "what is", "what are", "guide", "tutorial",
    "tips", "learn", "understand", "explained", "definition",
    "difference between", "examples of", "introduction to",
    "basics", "beginner", "complete guide", "step by step",
}
_COMMERCIAL_SIGNALS = {
    "best", "top", "review", "reviews", "comparison", "compare",
    "vs", "versus", "alternative", "alternatives", "recommended",
    "ranking", "rated", "winner", "picks", "favorite",
}
_TRANSACTIONAL_SIGNALS = {
    "buy", "price", "pricing", "cost", "discount", "deal",
    "coupon", "order", "purchase", "cheap", "affordable",
    "free trial", "sign up", "subscribe", "download",
    "get started", "hire", "booking", "quote",
}

# ── Title templates by intent ────────────────────────────────────────
_TITLE_TEMPLATES = {
    INTENT_INFORMATIONAL: [
        "{keyword} — The Complete Guide ({year})",
        "How {keyword} Works: Everything You Need to Know",
        "{keyword} Explained: A Practical, No-Nonsense Guide",
        "The Ultimate Guide to {keyword} ({year} Edition)",
    ],
    INTENT_COMMERCIAL: [
        "Best {keyword} in {year} — Expert Picks & Reviews",
        "Top {keyword} Compared: Which One Actually Delivers?",
        "{keyword} Showdown: Honest Reviews & Rankings ({year})",
    ],
    INTENT_TRANSACTIONAL: [
        "Get {keyword} — Pricing, Plans & How to Start",
        "{keyword}: Features, Pricing & Where to Buy ({year})",
    ],
    INTENT_NAVIGATIONAL: [
        "{keyword} — Official Guide & Resources",
        "Everything About {keyword}: Features, Updates & More",
    ],
}

# ── Meta description templates ────────────────────────────────────────
_META_TEMPLATES = {
    INTENT_INFORMATIONAL: "Discover everything about {keyword}. This in-depth guide covers {supporting} — with actionable insights you can apply today.",
    INTENT_COMMERCIAL: "Looking for the best {keyword}? We compared {supporting} so you don't have to. See our expert picks for {year}.",
    INTENT_TRANSACTIONAL: "Ready to get started with {keyword}? Compare pricing, features, and {supporting}. Find the right fit for your needs.",
    INTENT_NAVIGATIONAL: "Your go-to resource for {keyword}. Learn about {supporting} and get the most up-to-date information.",
}

# ── CTA templates by intent ──────────────────────────────────────────
_CTA_TEMPLATES = {
    INTENT_INFORMATIONAL: [
        "Keep reading to learn the exact steps.",
        "Bookmark this guide — you'll want to come back to it.",
        "Share this with someone who needs it.",
    ],
    INTENT_COMMERCIAL: [
        "See which option came out on top.",
        "Check our detailed comparison table below.",
        "Read our final verdict before you decide.",
    ],
    INTENT_TRANSACTIONAL: [
        "Get started now — it only takes 2 minutes.",
        "Claim your free trial today.",
        "See pricing and plans.",
    ],
    INTENT_NAVIGATIONAL: [
        "Explore the full feature set.",
        "Visit the official page for the latest updates.",
    ],
}


def analyze_competitors(competitor_urls: list, target_keyword: str, domain: str, 
                       site_profile_md: str = "", niche: str = "", 
                       audience_type: str = "General") -> ContentBrief:
    """
    Fetches competitor pages and builds a comprehensive content brief
    for a new page targeting `target_keyword`.
    """
    all_headings = []
    all_unigrams = []
    all_bigrams = []
    all_trigrams = []
    all_faqs = []
    all_entities = []
    all_power = []
    word_counts = []
    intent_signals = []

    for url in competitor_urls[:5]:
        try:
            page_data = _fetch_page(url)
            if not page_data:
                continue

            soup = BeautifulSoup(page_data, "lxml")
            text = soup.get_text(" ", strip=True)

            all_headings.extend(_extract_headings(soup))
            tokens = _tokenize(text)
            all_unigrams.extend(tokens)
            all_bigrams.extend(_extract_ngrams(tokens, 2))
            all_trigrams.extend(_extract_ngrams(tokens, 3))
            all_faqs.extend(_extract_faq_questions(soup))
            all_entities.extend(_extract_entities(text))
            all_power.extend(_extract_power_words(text))
            intent_signals.extend(_detect_intent_signals(text, soup))

            word_count = len(text.split())
            word_counts.append(word_count)

        except Exception:
            continue

    # ── Search intent detection ───────────────────────────────────────
    search_intent = _resolve_intent(target_keyword, intent_signals)

    # ── Content structure inference ───────────────────────────────────
    content_structure = _infer_structure(target_keyword, all_headings, search_intent)

    # ── Tone selection ────────────────────────────────────────────────
    tone = _select_tone(search_intent)

    # ── Build frequency-ranked headings (deduplicated) ────────────────
    heading_counter = Counter(h.lower().strip() for h in all_headings if len(h.strip()) > 5)
    # Remove exact duplicates, keep top by frequency
    seen_heading_cores = set()
    top_headings = []
    for h, _ in heading_counter.most_common(30):
        core = _heading_core(h)
        if core not in seen_heading_cores:
            seen_heading_cores.add(core)
            top_headings.append(h.title())
        if len(top_headings) >= 8:
            break

    # ── Build LSI keyword list (uni + bi + trigrams) ──────────────────
    keyword_tokens = set(target_keyword.lower().split())
    unigram_counter = Counter(all_unigrams)
    bigram_counter = Counter(all_bigrams)
    trigram_counter = Counter(all_trigrams)

    lsi_unigrams = [
        w for w, _ in unigram_counter.most_common(60)
        if w not in keyword_tokens and len(w) > 4
    ][:15]

    lsi_bigrams = [
        bg for bg, cnt in bigram_counter.most_common(40)
        if cnt >= 2 and not all(t in keyword_tokens for t in bg.split())
    ][:10]

    lsi_trigrams = [
        tg for tg, cnt in trigram_counter.most_common(30)
        if cnt >= 2 and not all(t in keyword_tokens for t in tg.split())
    ][:5]

    lsi_terms = lsi_bigrams + lsi_trigrams + lsi_unigrams
    # Deduplicate while preserving order
    seen_lsi = set()
    unique_lsi = []
    for t in lsi_terms:
        if t not in seen_lsi:
            seen_lsi.add(t)
            unique_lsi.append(t)
    lsi_terms = unique_lsi[:25]

    # ── Entity extraction ─────────────────────────────────────────────
    entity_counter = Counter(all_entities)
    entities = [e for e, cnt in entity_counter.most_common(15) if cnt >= 2]

    # ── Power words ───────────────────────────────────────────────────
    power_counter = Counter(all_power)
    power_words = [w for w, _ in power_counter.most_common(10)]

    # ── Keyword variants ──────────────────────────────────────────────
    keyword_variants = _generate_keyword_variants(target_keyword)

    # ── Determine target word count ───────────────────────────────────
    if word_counts:
        avg_wc = int(sum(word_counts) / len(word_counts))
        # Aim slightly above average competitor word count
        target_wc = int(avg_wc * 1.15)
    else:
        target_wc = 1500
    target_wc = max(target_wc, 1200)  # Never less than 1200
    target_wc = min(target_wc, 3000)  # Cap at 3000 for built-in generator

    # ── FAQ deduplication ─────────────────────────────────────────────
    faq_dedup = []
    faq_cores = set()
    for q in all_faqs:
        core = q.lower().strip().rstrip("?")
        if core not in faq_cores and len(core) > 10:
            faq_cores.add(core)
            faq_dedup.append(q)
    # If no FAQs found, generate sensible ones from the keyword
    if not faq_dedup:
        faq_dedup = _generate_default_faqs(target_keyword, search_intent)
    faq_dedup = faq_dedup[:8]

    # ── Build title and meta ──────────────────────────────────────────
    title = _generate_title(target_keyword, search_intent)
    meta = _generate_meta(target_keyword, lsi_terms, search_intent)
    slug = re.sub(r'[^a-z0-9]+', '-', target_keyword.lower()).strip('-')

    # ── CTAs ──────────────────────────────────────────────────────────
    cta_suggestions = _CTA_TEMPLATES.get(search_intent, _CTA_TEMPLATES[INTENT_INFORMATIONAL])

    return ContentBrief(
        target_keyword=target_keyword,
        url_slug=slug,
        page_title=title,
        meta_description=meta,
        word_count_target=target_wc,
        readability_target=8.0,
        search_intent=search_intent,
        content_structure=content_structure,
        tone=tone,
        headings=top_headings,
        lsi_terms=lsi_terms,
        target_keyword_variants=keyword_variants,
        entity_mentions=entities,
        power_words=power_words,
        faq_questions=faq_dedup,
        cta_suggestions=cta_suggestions,
        competitor_urls=competitor_urls[:5],
        schema_type="Article",
        site_profile_md=site_profile_md,
        niche=niche,
        audience_type=audience_type
    )


# ─────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────────

def _fetch_page(url: str) -> str | None:
    if not is_safe_url(url):
        return None

    try:
        r = httpx.get(
            url, timeout=12, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
        )
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _extract_headings(soup) -> list:
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 5:
            # Weight H2s more: add them twice
            headings.append(text)
            if tag.name == "h2":
                headings.append(text)
    return headings


def _extract_faq_questions(soup) -> list:
    questions = []

    # 1. <dt>/<dd> pattern
    for dt in soup.find_all("dt"):
        text = dt.get_text(strip=True)
        if text and len(text) > 10:
            questions.append(text if text.endswith("?") else text + "?")

    # 2. Headings ending in ?
    for h in soup.find_all(["h2", "h3", "h4"]):
        text = h.get_text(strip=True)
        if text.endswith("?") and len(text) > 10:
            questions.append(text)

    # 3. <details>/<summary> accordion pattern
    for summary in soup.find_all("summary"):
        text = summary.get_text(strip=True)
        if text and len(text) > 10:
            questions.append(text if text.endswith("?") else text + "?")

    # 4. FAQ schema in JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") == "FAQPage":
                for entity in data.get("mainEntity", []):
                    name = entity.get("name", "")
                    if name and len(name) > 10:
                        questions.append(name)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "FAQPage":
                        for entity in item.get("mainEntity", []):
                            name = entity.get("name", "")
                            if name and len(name) > 10:
                                questions.append(name)
        except (json.JSONDecodeError, TypeError):
            continue

    # 5. Paragraphs starting with question words followed by ?
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if (text.endswith("?") and len(text) > 15 and
            any(text.lower().startswith(qw) for qw in
                ["how ", "what ", "why ", "when ", "where ", "which ", "who ",
                 "can ", "does ", "do ", "is ", "are ", "should ", "will "])):
            questions.append(text)

    return questions


def _tokenize(text: str) -> list:
    """Tokenize text into cleaned, filtered single words."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 3 and t not in STOPWORDS]


def _extract_ngrams(tokens: list, n: int) -> list:
    """Extract n-grams from a token list, filtering out stop-heavy ngrams."""
    ngrams = []
    for i in range(len(tokens) - n + 1):
        gram_tokens = tokens[i:i + n]
        # Skip if more than half the tokens are very short
        if sum(1 for t in gram_tokens if len(t) <= 3) > n // 2:
            continue
        ngrams.append(" ".join(gram_tokens))
    return ngrams


def _extract_entities(text: str) -> list:
    """
    Extract potential named entities — capitalized multi-word phrases.
    Not perfect NER, but catches brand names, tool names, concepts.
    """
    entities = []
    # Find sequences of 2-4 capitalized words
    pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
    for match in re.finditer(pattern, text):
        entity = match.group(1)
        # Filter out common sentence starters and noise
        if entity.split()[0].lower() not in {"the", "this", "that", "when", "where", "how", "what", "why", "if", "but", "and", "for"}:
            entities.append(entity)
    return entities


def _extract_power_words(text: str) -> list:
    """Find power words present in the text."""
    text_lower = text.lower()
    found = []
    for pw in POWER_WORDS:
        if pw in text_lower:
            found.append(pw)
    return found


def _detect_intent_signals(text: str, soup) -> list:
    """Detect search intent signals from page text and structure."""
    signals = []
    text_lower = text.lower()

    for sig in _INFORMATIONAL_SIGNALS:
        if sig in text_lower:
            signals.append(INTENT_INFORMATIONAL)
    for sig in _COMMERCIAL_SIGNALS:
        if sig in text_lower:
            signals.append(INTENT_COMMERCIAL)
    for sig in _TRANSACTIONAL_SIGNALS:
        if sig in text_lower:
            signals.append(INTENT_TRANSACTIONAL)

    # Check for comparison tables -> commercial
    if soup.find("table"):
        signals.append(INTENT_COMMERCIAL)

    # Check for pricing elements -> transactional
    for cls in ["pricing", "price", "plan", "plans"]:
        if soup.find(class_=re.compile(cls, re.I)):
            signals.append(INTENT_TRANSACTIONAL)

    return signals


def _resolve_intent(keyword: str, signals: list) -> str:
    """Resolve the most likely search intent from keyword text + accumulated signals."""
    kw_lower = keyword.lower()

    # Direct keyword-level detection takes priority
    for sig in _TRANSACTIONAL_SIGNALS:
        if sig in kw_lower:
            return INTENT_TRANSACTIONAL
    for sig in _COMMERCIAL_SIGNALS:
        if sig in kw_lower:
            return INTENT_COMMERCIAL
    for sig in _INFORMATIONAL_SIGNALS:
        if sig in kw_lower:
            return INTENT_INFORMATIONAL

    # Fall back to competitor page signal voting
    if signals:
        counter = Counter(signals)
        return counter.most_common(1)[0][0]

    return INTENT_INFORMATIONAL  # Default


def _infer_structure(keyword: str, headings: list, intent: str) -> str:
    """Infer the best content structure based on keyword and intent."""
    kw_lower = keyword.lower()
    headings_text = " ".join(h.lower() for h in headings)

    if "how to" in kw_lower or "step" in headings_text:
        return STRUCTURE_HOWTO
    if intent == INTENT_COMMERCIAL or "vs" in kw_lower or "compare" in kw_lower:
        return STRUCTURE_COMPARISON
    if any(w in kw_lower for w in ["best", "top", "list"]):
        return STRUCTURE_LISTICLE
    if any(w in headings_text for w in ["deep dive", "in-depth", "anatomy", "breakdown"]):
        return STRUCTURE_DEEPDIVE

    return STRUCTURE_GUIDE


def _select_tone(intent: str) -> str:
    """Pick the best content tone for the resolved search intent."""
    return {
        INTENT_INFORMATIONAL: TONE_EDUCATIONAL,
        INTENT_COMMERCIAL: TONE_AUTHORITATIVE,
        INTENT_TRANSACTIONAL: TONE_PERSUASIVE,
        INTENT_NAVIGATIONAL: TONE_CONVERSATIONAL,
    }.get(intent, TONE_CONVERSATIONAL)


def _heading_core(heading: str) -> str:
    """Normalize a heading to a 'core' form for deduplication."""
    h = heading.lower().strip()
    h = re.sub(r"[^a-z0-9\s]", "", h)
    tokens = [t for t in h.split() if len(t) > 3 and t not in STOPWORDS]
    return " ".join(sorted(tokens))


def _generate_keyword_variants(keyword: str) -> list:
    """Generate plural, question-form, and long-tail variants of the keyword."""
    kw = keyword.strip()
    variants = []

    # Plural/singular toggle
    if kw.endswith("s"):
        variants.append(kw[:-1])  # Remove trailing s
    else:
        variants.append(kw + "s")  # Add s

    # Question forms
    variants.append(f"what is {kw}")
    variants.append(f"how to {kw}")
    variants.append(f"best {kw}")
    variants.append(f"why {kw}")
    variants.append(f"{kw} guide")
    variants.append(f"{kw} tips")
    variants.append(f"{kw} examples")
    variants.append(f"{kw} for beginners")

    return variants


def _generate_default_faqs(keyword: str, intent: str) -> list:
    """Generate sensible FAQ questions when none were found in competitor pages."""
    kw = keyword.strip()
    faqs = [
        f"What is {kw}?",
        f"Why is {kw} important?",
        f"How does {kw} work?",
        f"What are the benefits of {kw}?",
        f"How do I get started with {kw}?",
    ]
    if intent == INTENT_COMMERCIAL:
        faqs.extend([
            f"What is the best {kw}?",
            f"How do I choose the right {kw}?",
        ])
    elif intent == INTENT_TRANSACTIONAL:
        faqs.extend([
            f"How much does {kw} cost?",
            f"Where can I buy {kw}?",
        ])
    return faqs


def _generate_title(keyword: str, intent: str) -> str:
    """Generate a click-worthy, intent-aligned title."""
    import datetime
    year = datetime.datetime.now().year
    templates = _TITLE_TEMPLATES.get(intent, _TITLE_TEMPLATES[INTENT_INFORMATIONAL])
    # Pick the first template (most common/safest)
    title = templates[0].format(keyword=keyword.title(), year=year)
    # Ensure ≤ 60 chars for SEO
    if len(title) > 60:
        title = title[:57] + "..."
    return title


def _generate_meta(keyword: str, lsi_terms: list, intent: str) -> str:
    """Generate a compelling, benefit-driven meta description."""
    import datetime
    year = datetime.datetime.now().year
    supporting = ", ".join(lsi_terms[:3]) if lsi_terms else keyword
    template = _META_TEMPLATES.get(intent, _META_TEMPLATES[INTENT_INFORMATIONAL])
    meta = template.format(keyword=keyword, supporting=supporting, year=year)
    # Ensure ≤ 155 chars for SEO
    return meta[:155]
