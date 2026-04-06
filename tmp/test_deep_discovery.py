import os
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.content.engine import analyze_site_content

def test_deep_discovery():
    mock_pages = [
        {
            "url": "https://example.com/",
            "title": "Elite Dental Care - Painless Dentistry in Delhi",
            "meta_description": "We offer premium dental services including implants and whitening.",
            "headings": {"h1": ["Elite Dental Care"], "h2": ["Our Services"], "h3": []}
        },
        {
            "url": "https://example.com/services/implants",
            "title": "Dental Implants Delhi - Elite Dental Care",
            "meta_description": "Safe and permanent dental implants using titanium posts.",
            "headings": {"h1": ["Dental Implants"], "h2": ["Why Choose Us"], "h3": ["Process"]}
        },
        {
            "url": "https://example.com/about",
            "title": "About Elite Dental Care",
            "meta_description": "Our mission is to bring world-class dentistry to India.",
            "headings": {"h1": ["Our Story"], "h2": ["Our Mission"], "h3": []}
        }
    ]
    
    llm_config = {
        "provider": "openai",
        "api_key": "sk-dummy",
        "model": "gpt-4o-mini"
    }
    
    # Mock LLM response with the NEW UNIVERSAL JSON structure
    mock_json = {
      "niche": "Premium Dental Care",
      "primary_purpose": "Providing high-end dental treatments in Delhi",
      "mission": "To revolutionize dental health with painless technology.",
      "hierarchy_summary": "Core structure: /services for treatments, /about for mission, /research for papers.",
      "elaborate_services": [
        {"name": "Dental Implants", "detailed_description": "Permanent tooth replacement using robotic precision and titanium posts for lifelong stability."},
        {"name": "Teeth Whitening", "detailed_description": "Laser-based cosmetic enhancement that brightens smiles in under 60 minutes with zero sensitivity."}
      ],
      "found_faqs": ["Implants cost", "Painless surgery", "Healing time"],
      "authority_evidence": ["Delhi Times: Best Dentist 2024", "Paper: Robotic Implants in Modern Dentistry"],
      "target_audience": "Delhi residents seeking premium care",
      "tone": "authoritative"
    }
    
    import src.content.page_generator
    import json
    src.content.page_generator._call_openai = MagicMock(return_value=json.dumps(mock_json))
    
    result = analyze_site_content(mock_pages, "example.com", llm_config=llm_config)
    
    print("Universal Auditor v2 Result:")
    print(f"Discovery Method: {result.get('discovery_method')}")
    print(f"Hierarchy: {result.get('hierarchy')}")
    print(f"Found FAQs: {result.get('found_faqs')}")
    print(f"Authority: {result.get('authority')}")
    
    assert result.get('discovery_method') == 'universal_auditor_v2'
    assert len(result.get('authority')) == 2

if __name__ == "__main__":
    test_deep_discovery()
