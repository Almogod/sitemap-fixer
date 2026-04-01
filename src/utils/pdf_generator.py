from fpdf import FPDF
import datetime
import os

class SEOReportPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 20)
        self.set_text_color(16, 185, 129) # Primary Theme Color
        self.cell(0, 10, 'UrlForge - Deep SEO Audit Report', ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C')

def clean_text(text: str) -> str:
    """Ensure text is compatible with standard PDF fonts."""
    if not text:
        return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_seo_pdf(report: dict, output_path: str):
    pdf = SEOReportPDF()
    pdf.add_page()
    
    # Determine what type of report this is
    is_plugin = "state" in report
    engine_result = report.get("engine_result", {}) if is_plugin else report.get("engine_result", report)
    
    pages_crawled = engine_result.get("pages", [])
    first_url = pages_crawled[0].get("url", "Unknown Target") if pages_crawled else "Unknown Target"
    site_url = report.get("site_url", first_url)
    seo_score = report.get("seo_score_after", report.get("seo_score_before", engine_result.get("seo_score", "N/A")))

    # Summary
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, 'Analysis Overview', ln=True)
    pdf.set_font('helvetica', '', 12)
    pdf.cell(0, 8, f'Site URL: {clean_text(site_url)}', ln=True)
    pdf.cell(0, 8, f'Final SEO Score: {seo_score}', ln=True)
    pdf.cell(0, 8, f'Pages Analyzed: {len(pages_crawled)}', ln=True)
    pdf.ln(5)

    # Suggested Actions
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, 'Actionable SEO Fixes', ln=True)
    pdf.ln(2)
    
    actions = report.get("suggested_actions") or engine_result.get("actions", [])
    if not actions:
        pdf.set_font('helvetica', 'I', 11)
        pdf.cell(0, 8, 'No manual fixes suggested or all perfect.', ln=True)
    else:
        for idx, action in enumerate(actions, 1):
            pdf.set_font('helvetica', 'B', 11)
            pdf.cell(0, 8, clean_text(f'{idx}. {action.get("type", "General").title()}'), ln=True)
            pdf.set_font('helvetica', '', 10)
            url_str = action.get("url", "Site-wide")
            # Truncate URL if too long
            if len(url_str) > 70:
                url_str = url_str[:67] + "..."
            pdf.multi_cell(0, 6, clean_text(f'Page: {url_str}'))
            
            desc = action.get("description", action.get("fix_type", "Apply SEO optimization"))
            pdf.multi_cell(0, 6, clean_text(f'Description: {desc}'))
            pdf.ln(2)

    # Generated Pages section (Plugin Only)
    pages_gen = report.get("pages_generated", [])
    if pages_gen:
        pdf.add_page()
        pdf.set_font('helvetica', 'B', 16)
        pdf.cell(0, 10, 'AI-Generated Content Briefs', ln=True)
        pdf.ln(2)
        
        for pg in pages_gen:
            pdf.set_font('helvetica', 'B', 12)
            pdf.cell(0, 8, clean_text(f"Keyword: {pg.get('keyword', '')}"), ln=True)
            
            schema = pg.get("schema_data", {})
            meta = schema.get("meta", {})
            
            title = pg.get('title', meta.get('title', ''))
            slug = pg.get('slug', meta.get('slug', ''))
            
            pdf.set_font('helvetica', '', 10)
            pdf.cell(0, 6, clean_text(f"Title: {title}"), ln=True)
            pdf.cell(0, 6, clean_text(f"Target Slug: /{slug}"), ln=True)
            pdf.cell(0, 6, clean_text(f"Word Count: {pg.get('word_count', 0)}"), ln=True)
            pdf.ln(4)

    pdf.output(output_path)
    return output_path
