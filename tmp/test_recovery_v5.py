import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.crawler_engine.frontier import URLFrontier, SQLiteURLFrontier, is_internal_domain
from src.content.engine import analyze_site_content

def test_unified_domain_matching():
    print("Testing Unified Domain Matching (v5 Proof)...")
    
    # 1. Base Logic
    assert is_internal_domain("www.qcecuring.com", "qcecuring.com") == True
    assert is_internal_domain("qcecuring.com", "www.qcecuring.com") == True
    assert is_internal_domain("google.com", "qcecuring.com") == False
    print("✓ Shared Domain Helper Passed")

    # 2. In-Memory Frontier
    mem_f = URLFrontier(base_domain="qcecuring.com")
    mem_f.add("https://www.qcecuring.com/about")
    assert mem_f.size() == 1
    print("✓ Standard Frontier (Memory) Accepts 'www' Passed")

    # 3. SQLite Frontier
    sql_f = SQLiteURLFrontier(base_domain="qcecuring.com")
    sql_f.add("https://www.qcecuring.com/products")
    assert sql_f.size() == 1
    print("✓ Enterprise Frontier (SQLite) Accepts 'www' Passed")

def test_regex_restoration():
    print("\nTesting Title Regex Restoration (v5 Regex Proof)...")
    import re
    t = "Cryptographic Operations | QCecuring Technologies"
    # The fix: escaped pipe
    clean_t = re.sub(r'\|.*$', '', t).strip() 
    print(f"Original: {t}")
    print(f"Cleaned: {clean_t}")
    assert clean_t == "Cryptographic Operations"
    
    # Verify the miner uses it
    mock_pages = [
        {"url": "https://qcecuring.com/", "meta": {"title": "Cryptographic Operations | QCecuring"}},
        {"url": "https://qcecuring.com/clm", "meta": {"title": "Certificate Lifecycle Management | PKI"}}
    ]
    res = analyze_site_content(mock_pages, "qcecuring.com", llm_config={})
    print(f"Mined Niche: {res['niche']}")
    assert "Cryptographic" in res['niche']
    assert "Certificate" in res['niche']
    print("✓ Heuristic Mining Restoration Passed")

if __name__ == "__main__":
    try:
        test_unified_domain_matching()
        test_regex_restoration()
        print("\nAll v5 RECOVERY FIXES Verified!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
