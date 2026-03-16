import httpx
import asyncio
import random
from src.utils.logger import logger

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

async def fetch(client, url, retries=3, backoff_factor=1.5):
    """
    Fetches a URL with retry logic, timeout handling, and header rotation.
    """
    last_error = None
    for attempt in range(retries):
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            response = await client.get(url, headers=headers, follow_redirects=True)
            
            return {
                "url": url,
                "status": response.status_code,
                "html": response.text,
                "headers": dict(response.headers),
                "redirect_history": [str(r.url) for r in response.history]
            }
            
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_error = str(e)
            if attempt < retries - 1:
                sleep_time = (backoff_factor ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(sleep_time)
            continue
        except Exception as e:
            return {"url": url, "status": 0, "html": "", "error": str(e)}
            
    return {"url": url, "status": 0, "html": "", "error": f"Failed after {retries} retries. Last error: {last_error}"}
