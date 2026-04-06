import json
import heapq
import time
from src.config import config
from collections import deque
from urllib.parse import urlparse, urlunparse

def ensure_scheme(url: str, default_scheme: str = "https") -> str:
    """Ensure the URL has a scheme (defaulting to https)."""
    if not url:
        return url
    
    # Handle cases like "example.com" or "example.com/path"
    parsed = urlparse(url)
    if not parsed.scheme:
        # If there's no scheme, we assume the first part until "/" or ":" is the netloc
        # unless it starts with "/" (relative path)
        if url.startswith(("//", "/")):
            return f"{default_scheme}:{url}" if url.startswith("//") else url
        
        # Check if the URL has a dot in the first segment (heuristic for domain)
        parts = url.split("/", 1)
        if "." in parts[0]:
            return f"{default_scheme}://{url}"
            
    return url

def is_internal_domain(netloc, base_domain):
    """Returns True if netloc matches base_domain, ignoring 'www.' prefix."""
    if not netloc or not base_domain: return False
    def norm(d): return d.lower().replace("www.", "", 1)
    return norm(netloc) == norm(base_domain)


class URLFrontier:
    def __init__(self, base_domain=None):
        self.queue = [] # Heap for priority queue
        self.visited = set()
        self.base_domain = None
        self.base_path = ""
        self.counter = 0 # To ensure stable sort for same priority
        
        if base_domain:
            normalized = ensure_scheme(base_domain)
            parsed = urlparse(normalized)
            self.base_domain = parsed.netloc
            path = parsed.path
            if path and path != "/":
                self.base_path = path

    def add(self, url, depth=0, force_add=False, priority=0):
        if not url:
            return
        
        url = ensure_scheme(url)
        
        # Domain locking: only add if same domain (unless force_add is true for external validation)
        if self.base_domain and not force_add:
            parsed = urlparse(url)
            # FIX: Use shared 'www-agnostic' check
            if parsed.netloc and not is_internal_domain(parsed.netloc, self.base_domain):
                return
            if self.base_path and not parsed.path.startswith(self.base_path) and parsed.path != self.base_path:
                return

        if url not in self.visited:
            self.counter += 1
            # heapq is a min-heap, so we use -priority for a max-priority queue
            heapq.heappush(self.queue, (-priority, self.counter, {"url": url, "depth": depth}))
            self.visited.add(url)

    def get(self):
        if self.queue:
            prio, count, item = heapq.heappop(self.queue)
            return item
        return None

    def size(self):
        return len(self.queue)

    def peek(self):
        if self.queue:
            return self.queue[0][2].get("url")
        return None

class SQLiteURLFrontier:
    """Enterprise-grade frontier using SQLite for large local crawls without RAM explosion."""
    def __init__(self, base_domain=None, db_path=None):
        import sqlite3
        import tempfile
        import threading
        import os
        if not db_path:
            fd, db_path = tempfile.mkstemp(suffix=".sqlite")
            os.close(fd)
        self.db_path = db_path
        self._local = threading.local()
        
        self.base_domain = None
        self.base_path = ""
        if base_domain:
            normalized = ensure_scheme(base_domain)
            parsed = urlparse(normalized)
            self.base_domain = parsed.netloc
            path = parsed.path
            if path and path != "/":
                self.base_path = path

        conn = self._get_conn()
        conn.execute("CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, url TEXT, depth INTEGER, priority INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_visited ON visited(url)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prio ON queue(priority DESC, id ASC)")
        conn.commit()

    def _get_conn(self):
        import sqlite3
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-64000") # 64MB cache
        return self._local.conn

    def add(self, url, depth=0, force_add=False, priority=0):
        if not url:
            return
        
        url = ensure_scheme(url)
        
        if self.base_domain and not force_add:
            parsed = urlparse(url)
            # FIX: Use shared 'www-agnostic' check
            if parsed.netloc and not is_internal_domain(parsed.netloc, self.base_domain):
                return
            
            if self.base_path and not parsed.path.startswith(self.base_path) and parsed.path != self.base_path:
                return

        conn = self._get_conn()
        try:
            # Atomic: Only insert if not visited
            conn.execute("INSERT OR IGNORE INTO visited (url) VALUES (?)", (url,))
            if conn.total_changes > 0:
                conn.execute("INSERT INTO queue (url, depth, priority) VALUES (?, ?, ?)", (url, depth, priority))
                conn.commit()
        except Exception as e:
            logger.debug(f"SQLite add conflict for {url}: {e}")

    def get(self):
        conn = self._get_conn()
        try:
            res = conn.execute("SELECT id, url, depth FROM queue ORDER BY priority DESC, id ASC LIMIT 1").fetchone()
            if res:
                id, url, depth = res
                conn.execute("DELETE FROM queue WHERE id = ?", (id,))
                conn.commit()
                return {"url": url, "depth": depth}
        except Exception as e:
            logger.error(f"SQLite get error: {e}")
        return None

    def size(self):
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]

    def peek(self):
        conn = self._get_conn()
        res = conn.execute("SELECT url FROM queue ORDER BY priority DESC, id ASC LIMIT 1").fetchone()
        return res[0] if res else None
