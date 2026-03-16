import os
import gzip
import httpx
from datetime import datetime
from xml.sax.saxutils import escape
from src.utils.logger import logger

MAX_URLS_PER_SITEMAP = 50000

def stream_sitemap(pages, filename, use_gzip=True):
    """
    Streams sitemap to disk to handle large sites with minimal memory.
    Supports Gzip compression.
    """
    target_filename = f"{filename}.gz" if use_gzip else filename
    
    # We use 'wt' (write text) mode with gzip.open for convenience
    with (gzip.open(target_filename, 'wt', encoding='utf-8') if use_gzip else open(target_filename, 'w', encoding='utf-8')) as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" ')
        f.write('xmlns:xhtml="http://www.w3.org/1999/xhtml" ')
        f.write('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" ')
        f.write('xmlns:video="http://www.google.com/schemas/sitemap-video/1.1" ')
        f.write('xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n')
        
        for page in pages:
            f.write('  <url>\n')
            f.write(f'    <loc>{escape(page["url"])}</loc>\n')
            
            # Use actual lastmod if provided, else current date
            lastmod = page.get("lastmod") or datetime.utcnow().date().isoformat()
            f.write(f'    <lastmod>{lastmod}</lastmod>\n')
            
            # Changefreq and Priority
            if page.get("changefreq"):
                f.write(f'    <changefreq>{escape(page["changefreq"])}</changefreq>\n')
            if page.get("priority"):
                f.write(f'    <priority>{escape(str(page["priority"]))}</priority>\n')
            
            # Hreflang
            for hr in page.get("hreflangs", []):
                f.write(f'    <xhtml:link rel="{escape(hr.get("rel", "alternate"))}" hreflang="{escape(hr["hreflang"])}" href="{escape(hr["href"])}"/>\n')
                
            # Images
            for img in page.get("images", []):
                f.write('    <image:image>\n')
                f.write(f'      <image:loc>{escape(img["loc"])}</image:loc>\n')
                if img.get("title"):
                    f.write(f'      <image:title>{escape(img["title"])}</image:title>\n')
                f.write('    </image:image>\n')
                
            # Videos
            for vid in page.get("videos", []):
                f.write('    <video:video>\n')
                f.write(f'      <video:content_loc>{escape(vid["content_loc"])}</video:content_loc>\n')
                f.write(f'      <video:title>{escape(vid.get("title", "Video"))}</video:title>\n')
                f.write(f'      <video:thumbnail_loc>{escape(page["url"])}</video:thumbnail_loc>\n')
                f.write(f'      <video:description>{escape(vid.get("description", "Video on page"))}</video:description>\n')
                f.write('    </video:video>\n')
                
            f.write('  </url>\n')
            
        f.write('</urlset>')
    return target_filename

def generate_sitemaps(pages_iterator, base_url, output_prefix="sitemap", use_gzip=True, ping=True):
    """
    Enterprise-grade sitemap generator.
    Handles streaming input, Gzip, and search engine pings.
    """
    sitemap_files = []
    chunk_index = 1
    current_chunk = []
    
    for page in pages_iterator:
        current_chunk.append(page)
        if len(current_chunk) >= MAX_URLS_PER_SITEMAP:
            filename = f"{output_prefix}_{chunk_index}.xml"
            actual_file = stream_sitemap(current_chunk, filename, use_gzip)
            sitemap_files.append(actual_file)
            current_chunk = []
            chunk_index += 1
            
    if current_chunk:
        filename = f"{output_prefix}_{chunk_index}.xml"
        actual_file = stream_sitemap(current_chunk, filename, use_gzip)
        sitemap_files.append(actual_file)
        
    final_files = sitemap_files
    if len(sitemap_files) > 1:
        index_file = f"{output_prefix}_index.xml{'.gz' if use_gzip else ''}"
        create_sitemap_index(sitemap_files, base_url, index_file, use_gzip)
        final_files = [index_file] + sitemap_files
        
    if ping:
        primary_sitemap = final_files[0]
        ping_search_engines(f"{base_url.rstrip('/')}/{primary_sitemap}")
        
    return final_files

def create_sitemap_index(sitemap_files, base_url, filename, use_gzip=True):
    with (gzip.open(filename, 'wt', encoding='utf-8') if use_gzip else open(filename, 'w', encoding='utf-8')) as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for sf in sitemap_files:
            f.write('  <sitemap>\n')
            f.write(f'    <loc>{base_url.rstrip("/")}/{sf}</loc>\n')
            f.write(f'    <lastmod>{datetime.utcnow().date().isoformat()}</lastmod>\n')
            f.write('  </sitemap>\n')
        f.write('</sitemapindex>')

def ping_search_engines(sitemap_url):
    """Pings Google and Bing with the new sitemap URL."""
    engines = [
        f"https://www.google.com/ping?sitemap={sitemap_url}",
        f"https://www.bing.com/ping?sitemap={sitemap_url}"
    ]
    with httpx.Client() as client:
        for url in engines:
            try:
                resp = client.get(url)
                logger.info(f"Pinged {url}: {resp.status_code}")
            except Exception as e:
                logger.warning(f"Failed to ping {url}: {e}")
