import os
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.content.engine import analyze_site_content

def test_ai_discovery():
    mock_pages = [
        {
            "url": "https://example.com/",
            "title": "Elite Dental Care - Best Dentist in Delhi",
            "meta_description": "We provide premium dental services including teeth whitening, implants, and orthodontics in the heart of Delhi.",
            "headings": ["Elite Dental Care", "Our Services", "Book an Appointment"]
        },
        {
            "url": "https://example.com/about",
            "title": "About Us - Elite Dental Care",
            "meta_description": "Our mission is to provide painless dentistry with world-class technology.",
            "headings": ["Our Mission", "Meet the Doctors"]
        }
    ]
    
    # Mock llm_config
    # We will check if it calls the right provider
    llm_config = {
        "provider": "openai",
        "api_key": "sk-dummy", # dummy key to trigger the block
        "model": "gpt-4o-mini"
    }
    
    # Mock the LLM call to avoid actual API costs/errors during logic test
    import src.content.page_generator
    src.content.page_generator._call_openai = MagicMock(return_value="""
    {
      "niche": "Premium Dentistry",
      "tone": "authoritative",
      "mission": "To provide world-class, painless dental care using advanced technology in Delhi.",
      "services": ["Teeth Whitening", "Dental Implants", "Orthodontics", "Painless Dentistry"],
      "audience": "Patients seeking premium dental care in Delhi",
      "topics": ["Dentistry", "Oral Health", "Cosmetic Surgery"]
    }
    """)
    
    result = analyze_site_content(mock_pages, "example.com", llm_config=llm_config)
    
    print("AI Discovery Result:")
    print(f"Niche: {result.get('niche')}")
    print(f"Services: {result.get('services')}")
    print(f"Discovery Method: {result.get('discovery_method')}")
    
    assert result.get('discovery_method') == 'ai_first'
    assert "Teeth Whitening" in result.get('services')

if __name__ == "__main__":
    test_ai_discovery()
