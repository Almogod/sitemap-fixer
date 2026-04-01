# src/content/content_schema.py

from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Media(BaseModel):
    type: str = Field(..., description="image, video, etc.")
    url: str
    alt: str
    caption: Optional[str] = None

class Callout(BaseModel):
    type: str = Field(..., description="tip, warning, or note")
    text: str

class Section(BaseModel):
    id: str
    type: str = Field(..., description="intro, body, faq, cta, comparison, testimony")
    heading: str
    body_paragraphs: List[str]
    bullet_points: Optional[List[str]] = None
    media: Optional[Media] = None
    callout: Optional[Callout] = None
    internal_links: Optional[List[Dict[str, str]]] = None

class FAQItem(BaseModel):
    question: str
    answer: str

class ContentMetadata(BaseModel):
    keyword: str
    niche: Optional[str] = None
    audience: Optional[str] = None
    tone: str
    search_intent: str
    pain_points: Optional[List[str]] = None
    monetary_aspects: Optional[List[str]] = None
    word_count: int
    keyword_density: Optional[float] = None
    readability_score: Optional[float] = None

class MetaInfo(BaseModel):
    title: str
    description: str
    slug: str
    canonical_url: Optional[str] = None
    og_image: Optional[str] = None

class Hero(BaseModel):
    headline: str
    subheadline: str
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None

class SchemaMarkup(BaseModel):
    article: bool = True
    faq: bool = False
    breadcrumb: bool = True

class StructuredContent(BaseModel):
    """
    The strictly typed schema for generated SEO content.
    Used for frontend rendering and backend storage instead of raw HTML.
    """
    meta: MetaInfo
    content_metadata: ContentMetadata
    hero: Hero
    sections: List[Section]
    faq: Optional[List[FAQItem]] = None
    schema_markup: SchemaMarkup

    def to_dict(self):
        return self.model_dump()
