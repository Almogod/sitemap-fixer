from src.modules import (
    sitemap, robots, meta, internal_links,
    crawl_budget, schema, image_seo, core_web_vitals, keyword_gap,
    page_speed, heading_structure, open_graph, canonical_advanced,
    broken_links, content_quality, mobile_seo, page_experience,
    structured_data_validator, hreflang
)

MODULE_REGISTRY = {
    # Original modules
    "sitemap":                    sitemap,
    "canonical":                  canonical_advanced,
    "robots":                     robots,
    "meta":                       meta,
    "internal_links":             internal_links,
    "crawl_budget":               crawl_budget,
    "schema":                     schema,
    "image_seo":                  image_seo,
    "core_web_vitals":            core_web_vitals,
    "keyword_gap":                keyword_gap,

    # New modules
    "page_speed":                 page_speed,
    "heading_structure":          heading_structure,
    "open_graph":                 open_graph,
    "canonical_advanced":         canonical_advanced,
    "broken_links":               broken_links,
    "content_quality":            content_quality,
    "mobile_seo":                 mobile_seo,
    "page_experience":            page_experience,
    "structured_data_validator":  structured_data_validator,
    "hreflang":                   hreflang,
}
