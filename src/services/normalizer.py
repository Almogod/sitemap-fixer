import re
from urllib.parse import urlparse, urlunparse, quote, unquote

def normalize(url, force_https=True, remove_www=False):
    """
    Standardizes a URL by:
    - Forcing https (optional)
    - Lowercasing the hostname
    - Stripping default ports
    - Removing fragments and query parameters
    - Canonicalizing www. (optional)
    - Normalizing encoded paths and collapsing double slashes
    - Stripping trailing slashes
    """
    if not url:
        return ""
        
    parsed = urlparse(url.strip())
    
    # Force scheme
    scheme = parsed.scheme.lower() or "https"
    if force_https:
        scheme = "https"
        
    # Lowercase netloc and strip default ports
    netloc = parsed.netloc.lower()
    if ":" in netloc:
        host, port = netloc.rsplit(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host
            
    # WWW canonicalization
    if remove_www and netloc.startswith("www."):
        netloc = netloc[4:]
        
    # Path normalization
    path = parsed.path
    if not path:
        path = "/"
        
    # Collapse double slashes
    path = re.sub(r'/{2,}', '/', path)
    
    # Strip trailing slash (unless it's just /)
    if len(path) > 1:
        path = path.rstrip("/")
        
    # Encoded path normalization (ensure consistent % encoding)
    path = quote(unquote(path), safe="/%")
    
    return urlunparse((
        scheme,
        netloc,
        path,
        "", # query
        "", # params
        ""  # fragment
    ))
