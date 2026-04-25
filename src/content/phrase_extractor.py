# src/content/phrase_extractor.py
"""
Intelligent Compound Phrase Extractor.
Identifies semantically meaningful multi-word phrases (collocations) like
"tls handshake", "machine learning", "load balancer" — instead of breaking
them into isolated words like "tls" + "handshake".

Uses Pointwise Mutual Information (PMI) scoring to detect statistically
significant word pairings, combined with a domain-aware technical phrase
dictionary for instant recognition of known compounds.
"""

import re
import math
from collections import Counter
from typing import List, Set, Tuple
from src.content.stopwords import STOPWORDS
from src.utils.logger import logger

# ══════════════════════════════════════════════════════════════════════
# KNOWN TECHNICAL COMPOUND PHRASES
# These are always kept together regardless of PMI score.
# ══════════════════════════════════════════════════════════════════════

KNOWN_COMPOUNDS: Set[str] = {
    # Networking & Security
    "tls handshake", "ssl certificate", "dns lookup", "dns resolution",
    "load balancer", "load balancing", "reverse proxy", "api gateway",
    "rate limiting", "rate limit", "ip address", "mac address",
    "tcp connection", "udp packet", "http request", "http response",
    "web socket", "web server", "web application", "web scraping",
    "cross origin", "cors policy", "csrf token", "xss attack",
    "sql injection", "brute force", "man middle", "zero day",
    "denial service", "distributed denial", "public key", "private key",
    "access control", "two factor", "multi factor", "single sign",
    "oauth token", "jwt token", "bearer token", "api key",
    
    # Cloud & DevOps
    "cloud computing", "cloud native", "cloud storage", "cloud native infrastructure",
    "virtual machine", "container orchestration", "service mesh",
    "continuous integration", "continuous deployment", "continuous delivery",
    "infrastructure code", "version control", "source control",
    "blue green", "canary deployment", "rolling update",
    "auto scaling", "horizontal scaling", "vertical scaling",
    "fault tolerance", "high availability", "disaster recovery",
    "load testing", "stress testing", "performance testing",
    
    # AI & ML
    "machine learning", "deep learning", "neural network",
    "machine learning models", "deep learning models",
    "natural language", "language processing", "language model",
    "large language", "computer vision", "image recognition",
    "sentiment analysis", "named entity", "entity recognition",
    "transfer learning", "reinforcement learning", "supervised learning",
    "unsupervised learning", "gradient descent", "back propagation",
    "feature extraction", "feature engineering", "data pipeline",
    "training data", "test data", "validation data",
    "model training", "model inference", "model deployment",
    
    # SEO & Marketing
    "search engine", "search optimization", "keyword research",
    "keyword density", "link building", "content marketing",
    "social media", "email marketing", "conversion rate",
    "bounce rate", "click through", "organic traffic",
    "paid search", "meta description", "title tag",
    "schema markup", "structured data", "rich snippet",
    "core vitals", "page speed", "mobile first",
    "user experience", "user interface", "user engagement",
    "landing page", "call action", "lead generation",
    
    # Software Engineering
    "design pattern", "design patterns", "data structure",
    "data structures", "unit test", "unit testing",
    "integration test", "integration testing", "end end",
    "code review", "pull request", "merge request",
    "tech debt", "technical debt", "refactoring code",
    "open source", "closed source", "version control",
    "agile methodology", "scrum master", "sprint planning",
    "micro services", "microservices architecture", "event driven",
    "message queue", "task queue", "job scheduler",
    "database migration", "schema migration", "object relational",
    "rest api", "graphql api", "grpc service",
    
    # Business & Strategy
    "business model", "business intelligence", "business analysis",
    "market research", "competitive analysis", "swot analysis",
    "value proposition", "unique selling", "target audience",
    "customer journey", "customer experience", "customer retention",
    "revenue model", "profit margin", "cash flow",
    "supply chain", "quality assurance", "project management",
    "risk management", "change management", "stakeholder management",
    "key performance", "return investment", "total cost",
}

# ── PMI Scoring Parameters ─────────────────────────────────────────
MIN_PMI_SCORE = 2.5        # Lowered from 3.0 — capture more collocations
MIN_BIGRAM_FREQ = 2        # Minimum times a bigram must appear
MIN_WORD_LENGTH = 2        # Minimum word length (allow "tls", "api", etc.)


def extract_meaningful_phrases(text: str, max_phrases: int = 40) -> List[str]:
    """
    Main entry point. Extracts semantically meaningful phrases from text.
    
    Strategy:
    1. Scan for known compound phrases first (instant recognition)
    2. Build PMI-scored bigrams for unknown collocations  
    3. Extend to trigrams where significant
    4. Merge isolated words only if they don't belong to a phrase
    
    Returns a ranked list of meaningful phrases.
    """
    if not text:
        return []
    
    text_lower = text.lower()
    
    # ── Phase 1: Known compound detection ─────────────────────────────
    found_compounds = []
    for compound in KNOWN_COMPOUNDS:
        if compound in text_lower:
            found_compounds.append(compound)
    
    # ── Phase 2: Tokenize for statistical analysis ────────────────────
    # Use a permissive regex: any word with 2+ alphanumeric characters
    raw_tokens = re.findall(r'\b[a-z][a-z0-9]{1,}\b', text_lower)
    
    # Keep tokens that are NOT stopwords, OR are known technical abbreviations
    tokens = [
        t for t in raw_tokens 
        if t not in STOPWORDS or _is_technical_abbreviation(t)
    ]
    
    # If we have very few tokens, also extract from URL/path fragments and titles
    if len(tokens) < 10:
        # Try extracting from raw text more aggressively
        extra_tokens = re.findall(r'\b[a-z]{2,}\b', text_lower)
        extra_tokens = [
            t for t in extra_tokens 
            if t not in STOPWORDS and len(t) >= 3
        ]
        tokens = list(dict.fromkeys(tokens + extra_tokens))  # Deduplicate, preserve order
    
    if len(tokens) < 3:
        # Even with very few tokens, return whatever we have
        result = list(set(found_compounds))
        # Add any non-stopword tokens as individual keywords
        for t in tokens:
            if t not in STOPWORDS and len(t) >= 3 and not _is_noise_word(t):
                result.append(t)
        return result[:max_phrases]
    
    # ── Phase 3: PMI-scored bigram discovery ──────────────────────────
    unigram_counts = Counter(tokens)
    total_tokens = len(tokens)
    
    bigram_list = []
    for i in range(len(tokens) - 1):
        w1, w2 = tokens[i], tokens[i + 1]
        # Skip if both are stopwords
        if w1 in STOPWORDS and w2 in STOPWORDS:
            continue
        bigram_list.append(f"{w1} {w2}")
    
    bigram_counts = Counter(bigram_list)
    
    pmi_scored_bigrams = []
    for bigram, freq in bigram_counts.items():
        if freq < MIN_BIGRAM_FREQ:
            continue
        w1, w2 = bigram.split()
        
        # PMI = log2(P(w1,w2) / (P(w1) * P(w2)))
        p_bigram = freq / max(total_tokens - 1, 1)
        p_w1 = unigram_counts[w1] / total_tokens
        p_w2 = unigram_counts[w2] / total_tokens
        
        denominator = p_w1 * p_w2
        if denominator > 0:
            pmi = math.log2(p_bigram / denominator)
        else:
            pmi = 0
        
        if pmi >= MIN_PMI_SCORE:
            pmi_scored_bigrams.append((bigram, pmi, freq))
    
    # Sort by PMI * frequency for robust ranking
    pmi_scored_bigrams.sort(key=lambda x: x[1] * math.log(1 + x[2]), reverse=True)
    
    # ── Phase 4: Trigram extension ────────────────────────────────────
    trigram_list = []
    for i in range(len(tokens) - 2):
        w1, w2, w3 = tokens[i], tokens[i + 1], tokens[i + 2]
        if sum(1 for w in [w1, w2, w3] if w in STOPWORDS) <= 1:
            trigram_list.append(f"{w1} {w2} {w3}")
    
    trigram_counts = Counter(trigram_list)
    significant_trigrams = [
        (tg, cnt) for tg, cnt in trigram_counts.items() if cnt >= 2
    ]
    significant_trigrams.sort(key=lambda x: x[1], reverse=True)
    
    # ── Phase 5: Merge and deduplicate ────────────────────────────────
    all_phrases = set(found_compounds)
    
    # Add PMI bigrams
    for bigram, pmi, freq in pmi_scored_bigrams[:25]:
        all_phrases.add(bigram)
    
    # Add significant trigrams
    for trigram, cnt in significant_trigrams[:10]:
        all_phrases.add(trigram)
    
    # ── Phase 6: Add high-value unigrams NOT covered by phrases ──────
    phrase_words = set()
    for phrase in all_phrases:
        phrase_words.update(phrase.split())
    
    # Add unigrams that aren't already part of a discovered phrase
    for word, count in unigram_counts.most_common(80):
        if word in phrase_words:
            continue
        if word in STOPWORDS:
            continue
        if len(word) < 3:
            continue
        if len(word) == 3 and not _is_technical_abbreviation(word):
            continue
        if _is_noise_word(word):
            continue
        all_phrases.add(word)
        if len(all_phrases) >= max_phrases:
            break
    
    # ── Phase 7: Final ranking by relevance ───────────────────────────
    ranked = _rank_phrases(list(all_phrases), text_lower, unigram_counts, total_tokens)
    
    return ranked[:max_phrases]


def extract_phrases_from_pages(pages: list, max_phrases: int = 50) -> List[str]:
    """
    Extract meaningful phrases from multiple crawled pages.
    Combines text from all pages for better statistical signal.
    Enhanced to extract from titles, meta descriptions, headings, URLs,
    and body text — weighted by SEO importance.
    """
    from bs4 import BeautifulSoup
    
    all_text_parts = []
    high_value_parts = []  # Titles, metas, headings — weighted higher
    url_parts = []
    
    for p in pages:
        html = p.get("html", "")
        url = p.get("url", "")
        
        # Extract keywords from URL path segments
        if url:
            from urllib.parse import urlparse
            path = urlparse(url).path
            # Convert path to words: /my-cool-page/ -> "my cool page"
            path_words = re.sub(r'[^a-zA-Z0-9]', ' ', path).strip()
            if path_words and len(path_words) > 2:
                url_parts.append(path_words)
        
        if html:
            soup = BeautifulSoup(html, "lxml")
            
            # Extract headings (H1-H3) as high-value signals
            for tag in soup.find_all(["h1", "h2", "h3"]):
                heading_text = tag.get_text(strip=True)
                if heading_text and len(heading_text) > 3:
                    high_value_parts.append(heading_text)
            
            # Extract title tag
            title_tag = soup.find("title")
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                if title_text:
                    high_value_parts.append(title_text)
            
            # Extract meta description
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                high_value_parts.append(meta_tag["content"])
            
            # Extract meta keywords if present
            meta_kw = soup.find("meta", attrs={"name": "keywords"})
            if meta_kw and meta_kw.get("content"):
                high_value_parts.append(meta_kw["content"])
            
            # Extract body text
            for s in soup(["script", "style", "noscript", "svg", "form", "button", "iframe"]):
                s.decompose()
            body_text = soup.get_text(" ", strip=True)[:10000]
            all_text_parts.append(body_text)
        
        # Also use pre-extracted title/meta fields if available
        title = p.get("title", "")
        meta = p.get("meta_description", "")
        if title:
            high_value_parts.append(title)
        if meta:
            high_value_parts.append(meta)
    
    # Weight: high-value parts 5x, URL parts 3x, body text 1x
    combined = " ".join(high_value_parts * 5 + url_parts * 3 + all_text_parts)
    
    if not combined.strip():
        logger.warning("No text content found in any pages for keyword extraction")
        # Last resort: extract from URLs only
        if url_parts:
            combined = " ".join(url_parts * 5)
        else:
            return []
    
    return extract_meaningful_phrases(combined, max_phrases)


def group_related_keywords(keywords: List[str]) -> List[str]:
    """
    Post-process a list of individual keywords to merge related ones.
    Greedily merges keywords into the longest known compounds.
    """
    if not keywords: return []
    
    # Sort compounds by length (descending) to match longest first
    sorted_compounds = sorted(list(KNOWN_COMPOUNDS), key=lambda x: len(x.split()), reverse=True)
    
    result = []
    keywords_lower = [kw.lower() for kw in keywords]
    consumed = set()
    
    # 1. Look for compounds in the pool of keywords
    for compound in sorted_compounds:
        parts = compound.split()
        if len(parts) < 2: continue
        
        # Find indices of all parts in our keyword list
        indices = []
        temp_consumed = set()
        for part in parts:
            found = False
            for idx, kw in enumerate(keywords_lower):
                if kw == part and idx not in consumed and idx not in temp_consumed:
                    indices.append(idx)
                    temp_consumed.add(idx)
                    found = True
                    break
            if not found: break
            
        if len(indices) == len(parts):
            # All parts found! Merge them.
            result.append(compound)
            consumed.update(indices)
            
    # 2. Add remaining unmerged keywords
    for i, kw in enumerate(keywords):
        if i not in consumed:
            result.append(kw)
            
    return result


# ─────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────────

def _is_technical_abbreviation(word: str) -> bool:
    """Check if a short word is a known technical abbreviation."""
    known_abbrevs = {
        "api", "cdn", "ssl", "tls", "dns", "tcp", "udp", "http", "ssh",
        "ftp", "sql", "css", "dom", "jwt", "rpc", "sdk", "cli", "gui",
        "ide", "orm", "mvp", "crm", "erp", "seo", "sem", "ppc", "roi",
        "kpi", "sla", "aws", "gcp", "iam", "vpc", "ecs", "eks", "rds",
        "ci", "cd", "ml", "ai", "nlp", "llm", "rag", "gpu", "cpu",
        "ram", "ssd", "hdd", "url", "uri", "xml", "csv", "pdf", "web", "app",
        "iot", "vpn", "cms", "cdn", "b2b", "b2c", "saas", "paas", "iaas",
        "devops", "defi", "nft", "dao", "dapp",
    }
    return word.lower() in known_abbrevs


def _is_noise_word(word: str) -> bool:
    """Returns True if the word is likely noise/gibberish."""
    if len(word) < 3:
        return True
    # No vowels and not a known abbreviation
    if not any(v in word for v in "aeiouy") and not _is_technical_abbreviation(word):
        return True
    # Excessive character repetition
    if len(word) > 4 and any(word.count(c) > len(word) / 2 for c in set(word)):
        return True
    # Very low vowel ratio for longer words (noise filter)
    if len(word) > 8:
        vowels = sum(1 for c in word if c in "aeiouy")
        if vowels / len(word) < 0.10:
            return True
    # Pure digits or hex-like strings
    if word.isdigit():
        return True
    if re.match(r'^[0-9a-f]+$', word) and len(word) > 6:
        return True
    return False


def _rank_phrases(phrases: List[str], full_text: str, 
                  unigram_counts: Counter, total_tokens: int) -> List[str]:
    """
    Rank phrases by a composite score:
    - Known compound bonus (+5)
    - Multi-word bonus (+2 per word)
    - Frequency in text
    - Technical abbreviation bonus
    """
    scored = []
    for phrase in phrases:
        score = 0.0
        words = phrase.split()
        
        # Known compound bonus
        if phrase in KNOWN_COMPOUNDS:
            score += 5.0
        
        # Multi-word bonus (compounds are more valuable)
        if len(words) > 1:
            score += 2.0 * len(words)
        
        # Frequency score
        freq = full_text.count(phrase)
        score += math.log(1 + freq) * 1.5
        
        # Technical abbreviation bonus
        if any(_is_technical_abbreviation(w) for w in words):
            score += 3.0
        
        # Length bonus for meaningful single words (penalize very short)
        if len(words) == 1 and len(phrase) >= 6:
            score += 1.0
        
        scored.append((phrase, score))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return [phrase for phrase, _ in scored]
