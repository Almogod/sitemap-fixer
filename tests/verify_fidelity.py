# tests/verify_fidelity.py
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from tests.mock_site_data import QCE_PAGES
from src.content.engine import analyze_site_content, generate_markdown_site_profile, run_content_engine
from src.content.faq_generator import generate_site_faqs
from src.content.page_generator import generate_page

def test_fidelity_audit():
    print("--- 🔎 Starting URLForge Fidelity Verification ---")
    domain = "www.qcecuring.com"
    llm_config = {"provider": "builtin", "api_key": ""} # Force Heuristic fallback
    
    # 1. Site Analysis Verification
    print(f"\n[PHASE 1] Strategic DNA Analysis for {domain}...")
    context = analyze_site_content(QCE_PAGES, domain, llm_config)
    niche = context.get("niche", "")
    mission = context.get("mission", "")
    
    print(f"Detected Niche: {niche}")
    # ASSERT: Should NOT be 'General Authority'
    if "General" in niche or "Authority" == niche:
        print("❌ FAIL: Niche identification is too generic.")
    elif "Curing" in niche or "Concrete" in niche:
        print("✅ PASS: Niche correctly identified as Concrete/Curing.")
    else:
        print(f"⚠️ WARN: Niche identified as '{niche}'.")

    # 2. Markdown Profile Verification
    print("\n[PHASE 2] Markdown DNA Report Generation...")
    report_md = generate_markdown_site_profile(context)
    print("--- SAMPLE REPORT START ---")
    print(report_md[:400] + "...")
    print("--- SAMPLE REPORT END ---")
    
    # 3. FAQ Synthesis Verification
    print("\n[PHASE 3] FAQ Synthesis Performance...")
    keywords = ["concrete curing", "thermal blankets", "maturity sensors"]
    faqs = generate_site_faqs(keywords, domain, llm_config, site_context=context)
    
    if len(faqs) > 0:
        print(f"✅ PASS: Generated {len(faqs)} specialized FAQs.")
        sample_q = faqs[0].question
        sample_a = faqs[0].answer
        print(f"Sample Q: {sample_q}")
        print(f"Sample A: {sample_a}")
        
        # ASSERT: Answer should mention QCE or niche-specific terms
        if domain in sample_a or "concrete" in sample_a.lower():
            print("✅ PASS: Answer is correctly grounded in site context.")
        else:
            print("❌ FAIL: FAQ answer is generic.")
    else:
        print("❌ FAIL: No FAQs generated.")

    # 4. Page Generation Verification
    print("\n[PHASE 4] Zero-AI Page Generation Test...")
    from src.content.content_brief import ContentBrief
    brief = ContentBrief(
        target_keyword="concrete curing thermal blankets",
        url_slug="thermal-blanket-optimization",
        page_title="Expert Guide to Curing Thermal Blankets",
        meta_description="How to optimize R-value for concrete curing.",
        niche=niche,
        site_profile_md=report_md,
        services=context.get("services", []),
        tone="Authoritative",
        competitor_urls=[]
    )
    
    page = generate_page(brief, llm_config)
    method = page.get("generation_method")
    schema = page.get("schema_data", {})
    sections = schema.get("sections", [])
    
    print(f"Generation Method: {method}")
    if method == "dna_synthesis":
        print("✅ PASS: Correctly fell back to high-fidelity DNA synthesis.")
    
    # ASSERT: Content quality
    if len(sections) >= 2:
        print(f"✅ PASS: Generated {len(sections)} technical sections.")
        body_text = " ".join([" ".join(s.get("body_paragraphs", [])) for s in sections])
        
        # Check for AI Tropes
        tropes = ["Unlock", "Transform", "Navigate", "Delve", "Landscape"]
        found_tropes = [t for t in tropes if t in body_text]
        if found_tropes:
            print(f"❌ FAIL: AI Tropes found: {found_tropes}")
        else:
            print("✅ PASS: Zero AI-isms detected in body text.")
            
        # Check for Branding
        if domain in body_text:
            print("✅ PASS: Content is correctly branded (Zero-Generic).")
        else:
            print("❌ FAIL: Content lacks site-specific branding.")

if __name__ == "__main__":
    test_fidelity_audit()
