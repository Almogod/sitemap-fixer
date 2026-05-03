import httpx
import asyncio
import random
import time
from src.utils.logger import logger

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edge/123.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
]

ACCEPT_ENCODINGS = ["gzip, deflate, br", "gzip, deflate", "br"]

async def fetch(client, url, retries=5, backoff_factor=2.0, follow_redirects=True):
    """
    Highly robust fetcher with exponential backoff and 429 respect.
    """
    last_error = None
    for attempt in range(retries):
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": random.choice(ACCEPT_ENCODINGS),
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1"
            }
            
            t0 = time.time()
            async with client.stream("GET", url, headers=headers, follow_redirects=follow_redirects) as response:
                t1 = time.time()

                # Handle 429 Too Many Requests
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = 5
                    else:
                        wait_time = (backoff_factor ** attempt) + random.uniform(1, 5)
                    logger.warning(f"Rate limited (429) for {url}. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                # Handle 5xx errors (Temporary Server Issues)
                if response.status_code >= 500 and attempt < retries - 1:
                    wait_time = (backoff_factor ** attempt) + random.uniform(1, 3)
                    logger.warning(f"Server error ({response.status_code}) for {url}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                headers_dict = dict(response.headers)
                content_type = headers_dict.get("content-type", "").lower()
                is_text = any(t in content_type for t in ["text", "xml", "json", "javascript"])

                if is_text:
                    # Read full body only for text/HTML content
                    raw = await response.aread()
                    html_content = raw.decode(response.encoding or "utf-8", errors="replace")
                else:
                    # Binary (images, PDFs, etc.) — bail immediately, no body download
                    html_content = ""

                content_length = headers_dict.get("content-length", "0")

                return {
                    "url": url,
                    "final_url": str(response.url),
                    "status": response.status_code,
                    "html": html_content,
                    "headers": headers_dict,
                    "content_type": content_type.split(";")[0],
                    "content_length": int(content_length) if str(content_length).isdigit() else 0,
                    "response_time_ms": int((t1 - t0) * 1000),
                    "redirect_history": [
                        {"status": r.status_code, "url": str(r.url)}
                        for r in response.history
                    ],
                    "encoding": response.encoding
                }
            
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ReadTimeout) as e:
            last_error = str(type(e).__name__)
            if attempt < retries - 1:
                sleep_time = (backoff_factor ** attempt) + random.uniform(1, 3)
                logger.warning(f"Network error ({last_error}) for {url}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
            continue
        except Exception as e:
            logger.error(f"Critical fetch error for {url}: {e}")
            return {"url": url, "status": 0, "html": "", "content_type": "text/plain", "error": str(e)}
            
    return {"url": url, "status": 0, "html": "", "content_type": "text/plain", "error": f"Failed after {retries} retries. Last error: {last_error}"}
