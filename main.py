import argparse
from src.crawler import crawl
from src.extractor import extract_metadata
from src.normalizer import normalize
from src.filter import is_valid
from src.generator import generate_sitemap

def build_clean_urls(pages, fix_canonical=False):
    seen = set()
    clean = [] 
    
    for p in pages:
        meta = extract_metadata(p)

        if not is_valid(meta):
            continue

        chosen = meta["canonical"] if (fix_canonical and meta.get("canonical")) else meta["url"]
        normalized = normalize(chosen)

        if normalized in seen:
            continue

        seen.add(normalized)
        clean.append(normalized) 
        
    return clean 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sitemap Fixer Tool")

    parser.add_argument("domain", help="Website URL (e.g., https://example.com)")
    parser.add_argument("--limit", type=int, default=200, help="Max pages to crawl")
    parser.add_argument("--output", default="sitemap.xml", help="Output file name")
    parser.add_argument("--fix-canonical", action="store_true", help="Use canonical URLs")

    args = parser.parse_args()

    print(f"Crawling {args.domain}...")
    pages = crawl(args.domain, limit=args.limit)

    print("Processing...")
    clean_urls = build_clean_urls(pages, fix_canonical=args.fix_canonical)

    print("Generating sitemap...")
    generate_sitemap(clean_urls, filename=args.output)

    print(f"Done. Generated {args.output} with {len(clean_urls)} URLs")
