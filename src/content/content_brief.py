# src/content/content_brief.py
"""
Data model for a content brief — the comprehensive spec given to the page
generator.  Captures everything needed to produce a high-ranking, human-
quality piece of content without requiring an external API.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Search-intent taxonomy ────────────────────────────────────────────
INTENT_INFORMATIONAL = "informational"   # how-to, guide, what-is
INTENT_COMMERCIAL    = "commercial"      # best-X, top-X, reviews
INTENT_TRANSACTIONAL = "transactional"   # buy, pricing, sign-up
INTENT_NAVIGATIONAL  = "navigational"    # brand + feature

# ── Content structure archetypes ──────────────────────────────────────
STRUCTURE_GUIDE      = "guide"
STRUCTURE_LISTICLE   = "listicle"
STRUCTURE_HOWTO      = "how-to"
STRUCTURE_COMPARISON = "comparison"
STRUCTURE_DEEPDIVE   = "deep-dive"

# ── Tone presets ──────────────────────────────────────────────────────
TONE_AUTHORITATIVE    = "authoritative"
TONE_CONVERSATIONAL   = "conversational"
TONE_EDUCATIONAL      = "educational"
TONE_PERSUASIVE       = "persuasive"


@dataclass
class ContentBrief:
    # ── Core identifiers ──────────────────────────────────────────────
    target_keyword: str
    url_slug: str
    page_title: str
    meta_description: str

    # ── Content dimensions ────────────────────────────────────────────
    word_count_target: int = 1500
    readability_target: float = 8.0   # Flesch-Kincaid grade level

    # ── Search intent & structure ─────────────────────────────────────
    search_intent: str = INTENT_INFORMATIONAL
    content_structure: str = STRUCTURE_GUIDE
    tone: str = TONE_CONVERSATIONAL

    # ── Semantic enrichment ───────────────────────────────────────────
    headings: List[str] = field(default_factory=list)
    lsi_terms: List[str] = field(default_factory=list)
    target_keyword_variants: List[str] = field(default_factory=list)
    entity_mentions: List[str] = field(default_factory=list)
    power_words: List[str] = field(default_factory=list)

    # ── User-engagement helpers ───────────────────────────────────────
    faq_questions: List[str] = field(default_factory=list)
    cta_suggestions: List[str] = field(default_factory=list)

    # ── Linking & competitors ─────────────────────────────────────────
    internal_links: List[dict] = field(default_factory=list)
    competitor_urls: List[str] = field(default_factory=list)

    # ── Schema / categorization ───────────────────────────────────────
    schema_type: str = "Article"
    category: Optional[str] = None

    # ── Structured JSON Schema attributes ─────────────────────────────
    niche: str = ""
    audience_type: str = "General Audience"
    pain_points: List[str] = field(default_factory=list)
    monetary_aspects: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_keyword": self.target_keyword,
            "url_slug": self.url_slug,
            "page_title": self.page_title,
            "meta_description": self.meta_description,
            "word_count_target": self.word_count_target,
            "readability_target": self.readability_target,
            "search_intent": self.search_intent,
            "content_structure": self.content_structure,
            "tone": self.tone,
            "headings": self.headings,
            "lsi_terms": self.lsi_terms,
            "target_keyword_variants": self.target_keyword_variants,
            "entity_mentions": self.entity_mentions,
            "power_words": self.power_words,
            "faq_questions": self.faq_questions,
            "cta_suggestions": self.cta_suggestions,
            "internal_links": self.internal_links,
            "competitor_urls": self.competitor_urls,
            "schema_type": self.schema_type,
            "category": self.category,
            "niche": self.niche,
            "audience_type": self.audience_type,
            "pain_points": self.pain_points,
            "monetary_aspects": self.monetary_aspects,
        }
