import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.content.engine import analyze_site_content

def test_heuristic_grounding():
    print("Testing Heuristic Grounding (AI Failure Fallback)...")
    
    # Mock pages for QCecuring
    mock_pages = [
        {"url": "https://qcecuring.com/", "title": "QCecuring | Certificate Lifecycle Management", "meta_description": "We specialize in Machine Identity Management and PKI solutions for enterprises."},
        {"url": "https://qcecuring.com/product/clm", "title": "Certificate Lifecycle Management Solutions", "meta_description": "Automate SSL/TLS lifecycle."},
        {"url": "https://qcecuring.com/product/pki", "title": "PKI as a Service | QCecuring Technologies", "meta_description": "Scalable enterprise PKI."},
    ]
    
    # Analyze with NO API (triggers fallback)
    res = analyze_site_content(mock_pages, "qcecuring.com", llm_config={})
    
    # Verify results are mined from Title/Meta
    print(f"Detected Niche: {res['niche']}")
    print(f"Detected Mission: {res['mission']}")
    
    assert "Certificate" in res['niche'] or "Management" in res['niche']
    assert "Machine Identity" in res['mission']
    assert res['discovery_method'] == "heuristic_grounding"
    print("✓ Heuristic Grounding Passed (Metadata mined successfully)")

def test_json_repair():
    print("\nTesting JSON Repair Engine...")
    from src.content.page_generator import _extract_json_from_llm
    
    broken_json = """
    Here is the analysis in JSON format:
    ```json
    {
        "niche": "Cybersecurity",
        "primary_purpose": "Security automation",
        "trailing_comma": "breaks standard parsers",
    }
    ```
    I hope this helps!
    """
    
    parsed = _extract_json_from_llm(broken_json)
    assert parsed is not None
    assert parsed["niche"] == "Cybersecurity"
    assert "trailing_comma" in parsed
    print("✓ JSON Repair Passed (Trailing comma fixed)")

if __name__ == "__main__":
    try:
        test_heuristic_grounding()
        test_json_repair()
        print("\nAll HEURISTIC FIXES Verified!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
