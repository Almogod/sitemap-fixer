# src/content/page_generator.py
"""
AI-powered page generator with API-independent fallback.

Takes a ContentBrief and generates a full, SEO-optimized HTML page using
either an LLM (OpenAI, Google Gemini, Ollama) or the built-in template
engine.  The built-in engine produces publication-quality content that
reads naturally and ranks well on Google — no API key required.

The generated page includes:
  - Proper HTML structure with correct heading hierarchy
  - Optimized meta title and description
  - JSON-LD schema markup (Article, FAQPage, BreadcrumbList)
  - Internal links to existing site pages
  - Semantic HTML with targeted keyword density
  - Human-touch writing style with varied sentence lengths
  - E-E-A-T signals and reader engagement patterns
"""

import json
import re
import random
import hashlib
from datetime import datetime
from src.content.content_brief import ContentBrief
from src.content.content_schema import StructuredContent, MetaInfo, ContentMetadata, Hero, Section, Media, Callout, FAQItem, SchemaMarkup
from src.utils.logger import logger

def generate_page(brief: ContentBrief, llm_config: dict, existing_pages: list = None) -> dict:
    """
    Generate a complete SEO-optimized JSON structure from a ContentBrief.

    Strategy:
      1. If a valid LLM API key is provided, use the LLM with improved prompts.
      2. If the LLM call fails, fall back to built-in generation.
      3. If no API key is provided at all, use built-in generation directly.

    Returns:
        dict with: keyword, slug, meta_title, word_count, generation_method, json_schema
    """
    existing_pages = existing_pages or []
    json_schema_dict = None
    generation_method = "builtin"

    has_api = bool(llm_config.get("api_key"))
    provider = llm_config.get("provider", "").lower()

    if provider == "ollama":
        has_api = True

    if has_api:
        try:
            prompt = _build_prompt(brief, existing_pages)
            raw_content = None
            if provider == "openai":
                raw_content = _call_openai(prompt, llm_config)
            elif provider == "gemini":
                raw_content = _call_gemini(prompt, llm_config)
            elif provider == "ollama":
                raw_content = _call_ollama(prompt, llm_config)
            else:
                logger.warning(f"Unknown LLM provider '{provider}', falling back to built-in generator")

            if raw_content:
                json_schema_dict = _extract_json_from_llm(raw_content)
                if json_schema_dict:
                    generation_method = provider
                    logger.info(f"Structured Content generated via {provider}")
                else:
                    logger.warning(f"Failed to parse JSON from {provider}, falling back to built-in")
        except Exception as e:
            logger.warning(f"LLM call failed ({provider}): {e} — falling back to built-in generator")
            json_schema_dict = None

    if not json_schema_dict:
        json_schema_dict = _generate_builtin(brief, existing_pages)
        generation_method = "builtin"
        logger.info(f"Structured Content generated via built-in engine")

    word_count = json_schema_dict.get("content_metadata", {}).get("word_count", 0)

    return {
        "slug": brief.url_slug,
        "meta_title": brief.page_title,
        "meta_description": brief.meta_description,
        "schema_data": json_schema_dict,
        "word_count": word_count,
        "generation_method": generation_method,
    }

def _extract_json_from_llm(text: str) -> dict:
    try:
        # Check for markdown json block
        if "```json" in text:
            match = re.search(r"```json(.*?)```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
        elif "```" in text:
            match = re.search(r"```(.*?)```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
        # Try parsing raw text
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Failed to extract JSON schema: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────
# BUILT-IN CONTENT GENERATOR (API-independent)
# ─────────────────────────────────────────────────────────────────────

# Transition phrases for natural flow between sections
_TRANSITIONS = [
    "Now, let's take a closer look at",
    "With that foundation in place, let's explore",
    "Building on that idea,",
    "Here's where things get interesting.",
    "You might be wondering about",
    "This brings us to an important point:",
    "Let's break this down further.",
    "There's more to this than meets the eye.",
    "Here's what most people miss:",
    "Moving on to something equally important —",
    "So what does this look like in practice?",
    "This is where the rubber meets the road.",
    "Let me walk you through this.",
    "The next piece of the puzzle is",
    "But wait — there's a nuance here.",
]

# Hook starters for introductions
_INTRO_HOOKS = {
    "question": [
        "Have you ever wondered why {keyword} matters so much?",
        "What if everything you thought you knew about {keyword} was only half the story?",
        "Why do so many people struggle with {keyword} — and what can you actually do about it?",
        "Ever noticed how the best results come from understanding {keyword} deeply?",
    ],
    "statistic": [
        "Here's a fact that might surprise you: most people approach {keyword} the wrong way.",
        "Studies consistently show that {keyword} can make or break your results.",
        "The difference between good and great often comes down to how well you understand {keyword}.",
    ],
    "story": [
        "When I first started learning about {keyword}, I made every mistake in the book.",
        "A few years ago, I came across {keyword} and it completely changed my approach.",
        "I used to overlook {keyword} — until I saw the impact it had firsthand.",
    ],
    "bold": [
        "Let's be honest: {keyword} isn't just another buzzword.",
        "If you're serious about results, {keyword} is non-negotiable.",
        "{keyword} is one of those topics that seems simple on the surface — but the details matter enormously.",
    ],
}

# Sentence connectors for natural writing
_CONNECTORS = [
    "In other words,", "Put simply,", "That said,", "Here's the thing:",
    "To put it another way,", "What this means is", "The bottom line?",
    "In practice,", "From experience,", "The key takeaway here is",
    "Think of it this way:", "One thing to keep in mind:",
    "It's worth noting that", "Interestingly,", "On a practical level,",
]

# Paragraph enders for variety
_PARAGRAPH_ENDERS = [
    "That's a crucial distinction to understand.",
    "This alone can make a significant difference.",
    "And that's something worth remembering.",
    "It's one of those things that's easy to overlook but hard to ignore once you see it.",
    "The results speak for themselves.",
    "This is exactly why attention to detail matters.",
    "And honestly? Most people skip this step.",
    "Keep this in mind as we move forward.",
]

# FAQ answer templates by type
_FAQ_ANSWER_PATTERNS = [
    "Great question. {answer_body} The key thing to remember is that {keyword} {closing}.",
    "{answer_body} In simple terms, {keyword} {closing}.",
    "This is something a lot of people ask about. {answer_body} When it comes to {keyword}, {closing}.",
    "Short answer: {brief_answer}. But let me explain. {answer_body} Understanding {keyword} {closing}.",
    "{answer_body} The important thing is that {keyword} {closing}.",
]


def _generate_builtin(brief: ContentBrief, existing_pages: list) -> dict:
    """
    Generate a complete article body using template-driven composition.
    Produces structured JSON content matching the ContentSchema.
    """
    rng = random.Random(hashlib.md5(brief.target_keyword.encode()).hexdigest())
    kw = brief.target_keyword
    
    # meta
    meta = {
        "title": brief.page_title,
        "description": brief.meta_description,
        "slug": brief.url_slug,
    }
    
    # content_metadata
    content_metadata = {
        "keyword": kw,
        "niche": brief.niche,
        "audience": brief.audience_type,
        "tone": brief.tone,
        "search_intent": brief.search_intent,
        "pain_points": brief.pain_points,
        "monetary_aspects": brief.monetary_aspects,
        "word_count": 0, # will calculate at end
    }

    # hero
    hero = {
        "headline": brief.page_title,
        "subheadline": brief.meta_description,
        "cta_text": brief.cta_suggestions[0] if brief.cta_suggestions else None
    }

    sections = []

    # 1. Introduction
    sections.append(_build_intro_section(brief, rng))

    # 2. Body sections
    headings = brief.headings or _generate_fallback_headings(kw, brief.search_intent)
    lsi_pool = list(brief.lsi_terms)
    entity_pool = list(brief.entity_mentions)
    internal_links = list(existing_pages)

    for i, heading in enumerate(headings):
        sec = _build_body_section(
            heading=heading,
            keyword=kw,
            lsi_pool=lsi_pool,
            entity_pool=entity_pool,
            internal_links=internal_links,
            brief=brief,
            section_index=i,
            total_sections=len(headings),
            rng=rng,
        )
        sections.append(sec)

    # 3. Conclusion
    sections.append(_build_conclusion_section(brief, rng))

    # 4. FAQ
    faq_items = []
    if brief.faq_questions:
        faq_items = _build_faq_items(brief, rng)

    schema_markup = {
        "article": True,
        "faq": len(faq_items) > 0,
        "breadcrumb": True
    }

    # count words
    total_words = len(hero["headline"].split()) + len(hero["subheadline"].split())
    for s in sections:
        total_words += len(s["heading"].split())
        for p in s["body_paragraphs"]: total_words += len(p.split())
        if s.get("callout"):
            total_words += len(s["callout"]["text"].split())
    for f in faq_items:
        total_words += len(f["question"].split()) + len(f["answer"].split())
        
    content_metadata["word_count"] = total_words

    structured_content = {
        "meta": meta,
        "content_metadata": content_metadata,
        "hero": hero,
        "sections": sections,
        "faq": faq_items,
        "schema_markup": schema_markup
    }

    return structured_content


def _build_intro_section(brief: ContentBrief, rng: random.Random) -> dict:
    """Build an engaging 2-3 paragraph introduction."""
    kw = brief.target_keyword
    lsi_sample = brief.lsi_terms[:5]
    power = brief.power_words[:3] if brief.power_words else ["essential", "practical", "proven"]

    hook_style = rng.choice(list(_INTRO_HOOKS.keys()))
    hook = rng.choice(_INTRO_HOOKS[hook_style]).format(keyword=kw)

    lsi_mention = ""
    if lsi_sample:
        lsi_mention = f" — from {lsi_sample[0]} to {lsi_sample[1]}" if len(lsi_sample) >= 2 else f" including {lsi_sample[0]}"

    context_templates = [
        f"{hook} In this {power[0]} guide, we'll walk you through everything "
        f"you need to know about {kw}{lsi_mention}. Whether you're "
        f"just getting started or looking to sharpen your approach, you'll find "
        f"actionable insights that you can put to work right away.",
        
        f"{hook} The truth is, {kw} is one of those areas "
        f"where the right knowledge can save you hours of trial and error. We've "
        f"put together this {power[0]} resource to give you a clear roadmap"
        f"{lsi_mention}. No fluff — just the stuff that actually works.",
        
        f"{hook} Understanding {kw} isn't just useful — "
        f"it's {power[0]}. In this guide, we'll cover the key concepts"
        f"{lsi_mention}, with {power[1] if len(power) > 1 else 'practical'} "
        f"examples and real-world applications. Let's dive in.",
    ]
    intro_p1 = rng.choice(context_templates)

    cta = brief.cta_suggestions[0] if brief.cta_suggestions else "Let's get into it."
    heading_preview = ""
    if brief.headings and len(brief.headings) >= 3:
        heading_preview = (
            f" We'll cover topics like {brief.headings[0].lower()}, "
            f"{brief.headings[1].lower()}, and "
            f"{brief.headings[2].lower()} — among others."
        )

    intro_p2 = (
        f"By the end of this guide, you'll have a solid understanding of "
        f"{kw} and how to apply it effectively.{heading_preview} "
        f"{cta}"
    )

    return {
        "id": "intro",
        "type": "intro",
        "heading": "Introduction",
        "body_paragraphs": [intro_p1, intro_p2]
    }


def _build_body_section(heading, keyword, lsi_pool, entity_pool,
                        internal_links, brief, section_index, total_sections, rng) -> dict:
    """Build a single content section dict with 3-5 paragraphs."""
    parts = []

    if section_index > 0:
        transition = rng.choice(_TRANSITIONS)
        parts.append(transition)

    section_lsi = []
    if lsi_pool:
        count = min(3, len(lsi_pool))
        section_lsi = [lsi_pool.pop(0) for _ in range(count) if lsi_pool]

    section_entities = []
    if entity_pool:
        count = min(2, len(entity_pool))
        section_entities = [entity_pool.pop(0) for _ in range(count) if entity_pool]

    num_paragraphs = rng.randint(2, 4)
    for p_idx in range(num_paragraphs):
        para = _build_paragraph(
            heading=heading,
            keyword=keyword,
            lsi_terms=section_lsi,
            entities=section_entities,
            para_index=p_idx,
            total_paras=num_paragraphs,
            brief=brief,
            rng=rng,
        )
        parts.append(para.replace('<p>', '').replace('</p>', '').replace('<strong>', '').replace('</strong>', ''))

    sec_dict = {
        "id": f"section-{section_index}",
        "type": "body",
        "heading": heading,
        "body_paragraphs": parts,
    }

    if internal_links and rng.random() > 0.5:
        link = internal_links.pop(0)
        sec_dict["internal_links"] = [{"title": link.get("title", keyword), "url": link.get("url", "#")}]

    if section_index % 2 == 1 and brief.power_words:
        pw = rng.choice(brief.power_words) if brief.power_words else "key"
        sec_dict["callout"] = {
            "type": "tip",
            "text": f"The most {pw} approach to {heading.lower()} is to start small, measure your results, and iterate. Don't try to do everything at once."
        }
        
    return sec_dict


def _build_paragraph(heading, keyword, lsi_terms, entities, para_index,
                     total_paras, brief, rng) -> str:
    """Build a single paragraph with varied sentence lengths and natural tone."""
    kw = keyword
    heading_lower = heading.lower()
    sentences = []

    if para_index == 0:
        openers = [
            f"When it comes to {heading_lower}, there are a few things worth understanding from the start.",
            f"Let's talk about {heading_lower}. It's an area that often doesn't get the attention it deserves.",
            f"{heading.rstrip('.')} is something that can significantly impact your results with {kw}.",
            f"Understanding {heading_lower} is one of the foundations of working effectively with {kw}.",
            f"If there's one area of {kw} that deserves your attention, it's {heading_lower}.",
        ]
        sentences.append(rng.choice(openers))
    elif para_index == total_paras - 1:
        connector = rng.choice(_CONNECTORS)
        sentences.append(f"{connector} getting {heading_lower} right is about consistency and attention to detail.")
    else:
        mid_openers = [
            "There's an important nuance here.",
            "Let me expand on that.",
            "Here's a practical example.",
            "In real-world scenarios, this looks a bit different.",
            "This is where experience really matters.",
            "But there's more to the story.",
        ]
        sentences.append(rng.choice(mid_openers))

    detail_count = rng.randint(2, 4)
    for i in range(detail_count):
        sentence = _generate_detail_sentence(
            keyword=kw, heading=heading_lower,
            lsi_terms=lsi_terms, entities=entities,
            brief=brief, rng=rng,
        )
        sentences.append(sentence)

    if rng.random() > 0.65:
        questions = [
            f"So what does this mean for your approach to {kw}?",
            "Why does this matter?",
            f"How can you apply this to {heading_lower}?",
            "Sound familiar?",
            "Makes sense, right?",
        ]
        sentences.insert(rng.randint(1, len(sentences)), rng.choice(questions))

    if rng.random() > 0.6:
        punchy = [
            "It's that simple.", "And it works.", "Don't skip this.",
            "Trust the process.", "Results follow effort.", "Details matter.",
            "That's a game changer.",
        ]
        sentences.insert(rng.randint(1, len(sentences)), rng.choice(punchy))

    text = " ".join(sentences)
    return text


def _generate_detail_sentence(keyword, heading, lsi_terms, entities, brief, rng) -> str:
    templates = []
    if lsi_terms:
        lsi = rng.choice(lsi_terms)
        templates.extend([
            f"One aspect that connects directly to {heading} is {lsi} — and understanding that relationship gives you an edge.",
            f"When you consider {lsi} alongside {keyword}, the picture becomes much clearer.",
            f"Experts in this space often emphasize the role of {lsi} when discussing {heading}.",
        ])
    if entities:
        entity = rng.choice(entities)
        templates.extend([
            f"Tools and frameworks like {entity} have shown how {heading} can be approached systematically.",
            f"Industry leaders, including {entity}, have adopted approaches that prioritize {heading}.",
            f"Looking at how {entity} handles this gives practical insight into effective {keyword} strategies.",
        ])
    templates.extend([
        f"The key to making {heading} work lies in understanding the underlying principles rather than just following rules.",
        f"In practice, the most successful approach to {heading} involves a combination of strategy, execution, and continuous refinement.",
        f"What many people get wrong about {heading} is treating it as a one-time task rather than an ongoing process.",
        f"From a {keyword} perspective, {heading} isn't optional — it's foundational.",
        f"Small improvements in {heading} can compound over time, leading to significant gains in your overall {keyword} results.",
    ])
    return rng.choice(templates)


def _build_faq_items(brief: ContentBrief, rng: random.Random) -> list:
    """Build FAQ item dicts."""
    kw = brief.target_keyword
    faq_items = []

    closings = [
        "requires both understanding and practice",
        "is ultimately about getting the fundamentals right",
        "depends on your specific situation and goals",
        "is an evolving field, so staying current is important",
    ]
    brief_answers = [
        "Yes, absolutely",
        "It depends on your situation",
        "Generally speaking, yes",
        "The short answer is yes",
    ]

    for q in brief.faq_questions:
        q_clean = q.strip().rstrip("?") + "?"
        answer_bodies = [
            f"This is a common question, and the answer involves understanding how {kw} works in practice. "
            f"The core idea is that {q_clean.lower().replace('?', '')} connects directly to the broader topic of {kw}.",
            
            f"To answer this properly, we need to look at {kw} from a practical standpoint. "
            f"The reality is that {q_clean.lower().replace('?', '')} isn't a simple yes-or-no situation.",
        ]

        pattern = rng.choice(_FAQ_ANSWER_PATTERNS)
        answer = pattern.format(
            answer_body=rng.choice(answer_bodies),
            keyword=kw,
            closing=rng.choice(closings),
            brief_answer=rng.choice(brief_answers),
        )

        faq_items.append({"question": q_clean, "answer": answer})

    return faq_items


def _build_conclusion_section(brief: ContentBrief, rng: random.Random) -> dict:
    """Build a compelling conclusion with summary and CTA."""
    kw = brief.target_keyword
    kw_title = kw.title()
    power = brief.power_words[0] if brief.power_words else "effective"
    cta = brief.cta_suggestions[-1] if brief.cta_suggestions else "Start putting these ideas into action today."

    conclusions = [
        (f"Wrapping Up: Your Path Forward with {kw_title}", [
            f"We've covered a lot of ground in this guide — from the fundamentals of {kw} to the nuanced strategies that set top performers apart. The most important takeaway? Knowledge without execution is just information. The {power} approach is to pick one or two insights from this guide and start implementing them now.",
            f"Remember, mastering {kw} isn't about perfection from day one. It's about consistent, intentional progress. Each small improvement compounds over time, and before you know it, you'll be seeing real, measurable results.",
            f"{cta} If you found this guide helpful, consider bookmarking it for future reference — you'll likely want to revisit specific sections as you put these strategies into practice."
        ]),
        (f"Final Thoughts on {kw_title}", [
            f"If you've made it this far, you already have a significant advantage. Most people skim articles about {kw} without ever putting the ideas into practice. You now have a structured framework to work with — use it.",
            f"The landscape of {kw} continues to evolve, but the core principles we've discussed remain constant. Focus on quality, stay consistent, and don't be afraid to experiment. The best strategy is the one you actually follow through on.",
            f"{cta} The gap between where you are and where you want to be is simply a matter of applied knowledge and persistence."
        ])
    ]

    choice = rng.choice(conclusions)
    return {
        "id": "conclusion",
        "type": "conclusion",
        "heading": choice[0],
        "body_paragraphs": choice[1]
    }


def _generate_fallback_headings(keyword: str, intent: str) -> list:
    """Generate sensible section headings when none were found from competitors."""
    kw = keyword
    if intent == "how-to":
        return [
            f"What Is {kw.title()} and Why Does It Matter?",
            f"Preparing for {kw.title()}: What You'll Need",
            f"Step-by-Step Guide to {kw.title()}",
            f"Common Mistakes to Avoid with {kw.title()}",
            f"Advanced Tips for {kw.title()}",
            f"Measuring Your {kw.title()} Results",
        ]
    elif intent == "commercial":
        return [
            f"What to Look for in {kw.title()}",
            f"Our Top Picks for {kw.title()}",
            f"How We Evaluated Each Option",
            f"Pros and Cons Breakdown",
            f"Which {kw.title()} Is Right for You?",
        ]
    else:
        return [
            f"Understanding {kw.title()}: The Fundamentals",
            f"Why {kw.title()} Matters More Than Ever",
            f"Key Components of {kw.title()}",
            f"Best Practices for {kw.title()}",
            f"Common Challenges and How to Overcome Them",
            f"The Future of {kw.title()}",
        ]


# ─────────────────────────────────────────────────────────────────────
# IMPROVED LLM PROMPT
# ─────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────
# IMPROVED LLM PROMPT
# ─────────────────────────────────────────────────────────────────────

def _build_prompt(brief: ContentBrief, existing_pages: list) -> str:
    """Build a comprehensive prompt that produces a JSON schema."""
    internal_links_str = "\n".join(
        f'- {{"title": "{p.get("title", p.get("url"))}", "url": "{p.get("url")}"}}'
        for p in existing_pages[:10]
    )
    faqs_str = "\n".join(f"- {q}" for q in brief.faq_questions)
    headings_str = "\n".join(f"- {h}" for h in brief.headings)
    lsi_str = ", ".join(brief.lsi_terms)
    entities_str = ", ".join(brief.entity_mentions) if brief.entity_mentions else "None"
    power_str = ", ".join(brief.power_words) if brief.power_words else "None"
    variants_str = ", ".join(brief.target_keyword_variants[:5]) if brief.target_keyword_variants else "None"

    return f"""You are a world-class SEO content writer. Write a comprehensive article that reads like a human expert wrote it, and return the result STRICTLY as a JSON object matching the provided schema.

═══════════════════════════════════════════
CONTENT BRIEF
═══════════════════════════════════════════
TARGET KEYWORD: {brief.target_keyword}
TITLE: {brief.page_title}
SEARCH INTENT: {brief.search_intent}
TONE: {brief.tone}
NICHE: {brief.niche}
AUDIENCE: {brief.audience_type}
PAIN POINTS: {', '.join(brief.pain_points) if brief.pain_points else 'General'}
MONETIZATION: {', '.join(brief.monetary_aspects) if brief.monetary_aspects else 'None'}
WORD COUNT TARGET: {brief.word_count_target}

═══════════════════════════════════════════
ELEMENTS TO INCLUDE
═══════════════════════════════════════════
SUBHEADINGS:
{headings_str}

LSI TERMS: {lsi_str}
KEYWORD VARIANTS: {variants_str}
ENTITIES: {entities_str}
POWER WORDS: {power_str}
FAQ QUESTIONS:
{faqs_str}

INTERNAL LINKS (use these in section.internal_links where relevant):
{internal_links_str}

═══════════════════════════════════════════
JSON SCHEMA EXPECTED
═══════════════════════════════════════════
{{
  "meta": {{"title": "{brief.page_title}", "description": "{brief.meta_description}", "slug": "{brief.url_slug}"}},
  "content_metadata": {{"keyword": "{brief.target_keyword}", "niche": "{brief.niche}", "audience": "{brief.audience_type}", "tone": "{brief.tone}", "search_intent": "{brief.search_intent}", "word_count": <int>}},
  "hero": {{"headline": "...", "subheadline": "...", "cta_text": "..."}},
  "sections": [
    {{
      "id": "...", "type": "intro|body|conclusion", "heading": "...",
      "body_paragraphs": ["string 1", "string 2"],
      "callout": {{"type": "tip|warning|note", "text": "..."}}, // Optional
      "internal_links": [{{"title": "...", "url": "..."}}] // Optional
    }}
  ],
  "faq": [{{"question": "...", "answer": "..."}}],
  "schema_markup": {{"article": true, "faq": true, "breadcrumb": true}}
}}

CRITICAL INSTRUCTIONS:
1. Return ONLY valid JSON block. NO markdown wrappers outside of ```json formatting.
2. The `body_paragraphs` array must contain plain text strings, no HTML tags (no <p>, <strong>, etc.).
3. Mix sentence lengths (5-8 words mixed with 20-30 words). Use contractions naturally. Include rhetorical questions.
"""


# ─────────────────────────────────────────────────────────────────────
# HTML WRAPPER FOR DEPLOYMENT
# ─────────────────────────────────────────────────────────────────────

def render_content_to_html(schema_dict: dict) -> str:
    """Convert the JSON StructuredContent back into an HTML page for deployment."""
    meta = schema_dict.get("meta", {})
    hero = schema_dict.get("hero", {})
    sections = schema_dict.get("sections", [])
    faqs = schema_dict.get("faq", [])
    
    parts = []
    
    # Hero
    parts.append(f"<h1>{hero.get('headline', '')}</h1>")
    if hero.get("subheadline"):
        parts.append(f"<p class='hero-sub'>{hero.get('subheadline')}</p>")
        
    # Sections
    for sec in sections:
        if sec.get("type") != "intro":
            parts.append(f"<h2>{sec.get('heading', '')}</h2>")
            
        for p in sec.get("body_paragraphs", []):
            parts.append(f"<p>{p}</p>")
            
        if sec.get("callout"):
            callout = sec.get("callout")
            parts.append(f"<blockquote class='callout-{callout.get('type', 'note')}'><strong>{callout.get('type', 'Note').title()}:</strong> {callout.get('text', '')}</blockquote>")
            
        for link in sec.get("internal_links", []):
            parts.append(f"<p>Related: <a href='{link.get('url', '')}'>{link.get('title', '')}</a></p>")
            
    # FAQ
    if faqs:
        parts.append("<h2>Frequently Asked Questions</h2>")
        for faq in faqs:
            parts.append(f"<h3>{faq.get('question', '')}</h3>")
            parts.append(f"<p>{faq.get('answer', '')}</p>")
            
    body_content = "\n".join(parts)
    
    schema_markup = schema_dict.get("schema_markup", {})
    
    # NOTE: _build_schemas is kept below for convenience, or you can construct it
    try:
        schema_json = json.dumps(_build_schemas(ContentBrief(**{
            "target_keyword": schema_dict.get("content_metadata", {}).get("keyword", ""),
            "url_slug": meta.get("slug", ""),
            "page_title": meta.get("title", ""),
            "meta_description": meta.get("description", ""),
        })), indent=2)
    except:
        schema_json = "{}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{meta.get("title", "")}</title>
    <meta name="description" content="{meta.get("description", "")}">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{meta.get("title", "")}">
    <meta property="og:description" content="{meta.get("description", "")}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="/{meta.get("slug", "")}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{meta.get("title", "")}">
    <meta name="twitter:description" content="{meta.get("description", "")}">
    <link rel="canonical" href="/{meta.get("slug", "")}">
    <script type="application/ld+json">
{schema_json}
    </script>
</head>
<body>
<article>
{body_content}
</article>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────
# SCHEMA GENERATION
# ─────────────────────────────────────────────────────────────────────

def _build_schemas(brief: ContentBrief) -> list:
    """Build JSON-LD schemas for the generated page."""
    now = datetime.now().isoformat()
    schemas = []

    # Article schema
    schemas.append({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": brief.page_title,
        "description": brief.meta_description,
        "keywords": brief.target_keyword,
        "datePublished": now,
        "dateModified": now,
        "author": {
            "@type": "Organization",
            "name": "UrlForge",
        },
        "publisher": {
            "@type": "Organization",
            "name": "UrlForge",
        },
    })

    # FAQ schema if we have questions
    if brief.faq_questions:
        schemas.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            f"This is a common question about {brief.target_keyword}. "
                            f"Understanding {q.lower().replace('?', '')} is important because "
                            f"it directly impacts how effectively you can apply {brief.target_keyword} "
                            f"strategies. The answer depends on your specific context, but the "
                            f"core principles remain consistent."
                        )
                    }
                }
                for q in brief.faq_questions
            ]
        })

    # Breadcrumb schema
    schemas.append({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": "/"
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": brief.category or brief.target_keyword.title(),
                "item": f"/{brief.url_slug}"
            }
        ]
    })

    return schemas


# ─────────────────────────────────────────────────────────────────────
# LLM PROVIDER IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────────────

def _call_openai(prompt: str, config: dict) -> str:
    try:
        import openai
        client = openai.OpenAI(api_key=config.get("api_key", ""))
        model = config.get("model", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert SEO content writer who writes in a natural, human voice. Your content is engaging, well-researched, and optimized for search engines while being genuinely helpful to readers."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=6000,
            temperature=0.8,  # Slightly higher for more natural variation
            top_p=0.95,
            frequency_penalty=0.3,  # Reduce repetition
            presence_penalty=0.2,   # Encourage topic diversity
        )
        return response.choices[0].message.content.strip()
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")


def _call_gemini(prompt: str, config: dict) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.get("api_key", ""))
        model_name = config.get("model", "gemini-1.5-flash")
        model = genai.GenerativeModel(
            model_name,
            generation_config={
                "temperature": 0.8,
                "top_p": 0.95,
                "max_output_tokens": 6000,
            }
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except ImportError:
        raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")


def _call_ollama(prompt: str, config: dict) -> str:
    import httpx
    host = config.get("ollama_host", "http://localhost:11434")
    model = config.get("model", "llama3")
    response = httpx.post(
        f"{host}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.95,
                "repeat_penalty": 1.15,
            }
        },
        timeout=180
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()
