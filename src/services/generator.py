from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime
import math


MAX_URLS_PER_SITEMAP = 50000


def chunk_urls(urls, chunk_size):
    for i in range(0, len(urls), chunk_size):
        yield urls[i:i + chunk_size]


def create_sitemap(urls, filename):
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    for url in urls:
        url_el = SubElement(urlset, "url")

        loc = SubElement(url_el, "loc")
        loc.text = url

        lastmod = SubElement(url_el, "lastmod")
        lastmod.text = datetime.utcnow().date().isoformat()

    tree = ElementTree(urlset)
    tree.write(filename, encoding="utf-8", xml_declaration=True)


def create_sitemap_index(sitemap_files, base_url, filename="sitemap_index.xml"):
    sitemapindex = Element("sitemapindex", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    for file in sitemap_files:
        sitemap = SubElement(sitemapindex, "sitemap")

        loc = SubElement(sitemap, "loc")
        loc.text = f"{base_url.rstrip('/')}/{file}"

        lastmod = SubElement(sitemap, "lastmod")
        lastmod.text = datetime.utcnow().date().isoformat()

    tree = ElementTree(sitemapindex)
    tree.write(filename, encoding="utf-8", xml_declaration=True)


def generate_sitemaps(urls, base_url, output_prefix="sitemap"):
    total = len(urls)

    if total <= MAX_URLS_PER_SITEMAP:
        filename = f"{output_prefix}.xml"
        create_sitemap(urls, filename)
        return [filename]

    sitemap_files = []
    chunks = list(chunk_urls(urls, MAX_URLS_PER_SITEMAP))

    for i, chunk in enumerate(chunks, start=1):
        filename = f"{output_prefix}_{i}.xml"
        create_sitemap(chunk, filename)
        sitemap_files.append(filename)

    create_sitemap_index(sitemap_files, base_url)

    return sitemap_files
