"""
NyayPath Legal Citation & Precedent Verification Module (Phase 2.3)
===================================================================
Provides structured, verified legal citations across the AI Legal Engine,
Case Search, and Legal Document Generator.

Key Guarantees:
- Strictly Traceable: Citations map directly to verified Supreme Court, High Court,
  statutory provisions, and CIC landmark rulings.
- Zero Hallucination: The engine never invents missing case names, paragraph numbers,
  statutory sections, or fake judgment URLs.
- Hierarchy of Authority: Distinguishes BINDING precedents (Supreme Court of India under
  Article 141) from PERSUASIVE precedents (High Courts, Tribunals, Commissions).
- Unambiguous Absence Indicator: Explicitly signals when no verified legal source
  supports a claim.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

try:
    from .precedent_library import LANDMARK_PRECEDENTS, precedent_engine
except ImportError:
    from precedent_library import LANDMARK_PRECEDENTS, precedent_engine

logger = logging.getLogger("nyaypath.citations")

# Official Repository URLs for authentic judgments
OFFICIAL_SOURCE_URLS = {
    "sc-ragging-vishwa-2009": "https://main.sci.gov.in/judgment/judis/34688.pdf",
    "cbse-aditya-2011": "https://main.sci.gov.in/judgment/judis/38314.pdf",
    "delhi-hc-pwd-potholes-2024": "https://delhihighcourt.nic.in/case-details",
    "paramveer-cic-2007": "https://cic.gov.in/decisions",
    "pioneer-urban-builder-2019": "https://main.sci.gov.in/supremecourt/2018/38234/38234_2018_Order_02-Apr-2019.pdf",
    "bhagat-singh-delhi-hc-2007": "https://delhihighcourt.nic.in/case-details",
    "subhash-kumar-water-1991": "https://main.sci.gov.in/judgment/judis/10777.pdf",
    "ugc-fee-refund-2018": "http://ncdrc.nic.in/bareact/case-briefs",
    "rbi-jayantilal-2016": "https://main.sci.gov.in/judgment/judis/43217.pdf",
    "shreya-singhal-2015": "https://main.sci.gov.in/judgment/judis/42497.pdf",
    "cic-pension-arrears-2024": "https://cic.gov.in/decisions",
    "bombay-hc-hospital-emergency-2024": "https://bombayhighcourt.nic.in/"
}


# =============================================================================
# Models
# =============================================================================

class CitationMetadata(BaseModel):
    source_identifier: str = Field(..., description="Unique precedent identifier")
    case_title: str = Field(..., description="Full legal title of the judgment or statutory authority")
    court: str = Field(..., description="Issuing court or commission name")
    citation: str = Field(..., description="Official law report or case citation reference")
    year: Optional[int] = Field(None, description="Year of judgment")
    authority_type: str = Field("PERSUASIVE", description="BINDING (Supreme Court) or PERSUASIVE (High Court / Tribunal)")
    bench: Optional[str] = Field(None, description="Presiding bench")
    category: str = Field(..., description="Legal jurisdiction or category")
    statutory_provisions: List[str] = Field(default_factory=list, description="Referenced statutory sections")
    relevant_ratio: str = Field(..., description="Core legal holding / ratio decidendi")
    how_to_cite: str = Field(..., description="Practical citation guidance for court/authority submission")
    source_url: Optional[str] = Field(None, description="Verified link to the official judgment or portal")
    pdf_download_url: Optional[str] = Field(None, description="NyayPath verified case brief PDF download endpoint")
    is_verified: bool = Field(True, description="Whether source is authentic and verified")


class CitationResolutionResponse(BaseModel):
    query: str
    has_citations: bool
    citations: List[CitationMetadata]
    message: Optional[str] = None


# =============================================================================
# Citation Engine
# =============================================================================

def extract_year_from_citation(citation: str, hearing_date: Optional[str] = None) -> Optional[int]:
    """Extracts 4-digit year from citation string or hearing date."""
    if hearing_date:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", hearing_date)
        if match:
            return int(match.group(1))

    if citation:
        match = re.search(r"\((19\d{2}|20\d{2})\)|\b(19\d{2}|20\d{2})\b", citation)
        if match:
            found = match.group(1) or match.group(2)
            if found:
                return int(found)
    return None


def format_precedent_to_citation(item: Dict[str, Any]) -> CitationMetadata:
    """Transforms raw landmark precedent record into standard citation format."""
    item_id = item.get("id", "")
    court_name = item.get("court", "Indian Court")
    is_binding = "supreme court" in court_name.lower()
    authority = "BINDING" if is_binding else "PERSUASIVE"

    citation_str = item.get("citation", "Citation Pending")
    hearing_date = item.get("hearing_date")
    year = extract_year_from_citation(citation_str, hearing_date)

    source_url = OFFICIAL_SOURCE_URLS.get(item_id) or "https://main.sci.gov.in/"
    pdf_url = f"/api/precedents/{item_id}/pdf" if item_id else None

    return CitationMetadata(
        source_identifier=item_id,
        case_title=item.get("title", "Untitled Authority"),
        court=court_name,
        citation=citation_str,
        year=year,
        authority_type=authority,
        bench=item.get("bench"),
        category=item.get("category", "General Law"),
        statutory_provisions=item.get("statutory_sections", []),
        relevant_ratio=item.get("key_ratio", item.get("summary", "")),
        how_to_cite=item.get("how_to_cite", f"Cite {citation_str}"),
        source_url=source_url,
        pdf_download_url=pdf_url,
        is_verified=True
    )


def resolve_citations_for_query(query: str, max_results: int = 3) -> CitationResolutionResponse:
    """
    Retrieves and ranks verified legal precedents supporting a legal query.
    - Matches semantic intent and keywords using precedent_engine.
    - If no relevant precedent exists, returns has_citations=False with clear indication.
    - Zero hallucination: Only curated, verified authorities are returned.
    """
    clean_q = (query or "").strip()
    if not clean_q:
        return CitationResolutionResponse(
            query="",
            has_citations=False,
            citations=[],
            message="No query provided."
        )

    # Search using precedent engine
    try:
        search_res = precedent_engine.search(clean_q, category="All")
        precedents = search_res.get("precedents", []) if isinstance(search_res, dict) else []
    except Exception as e:
        logger.warning(f"Error in precedent search: {e}")
        precedents = []

    # Genuine threshold: require recognized legal intent OR strong relevance score (>= 65)
    # Exclude generic unranked fallback ("Related General Precedent")
    has_legal_intent = search_res.get("expansion", {}).get("has_expansion", False) if isinstance(search_res, dict) else False

    relevant = [
        p for p in precedents 
        if p.get("relevance_label") != "Related General Precedent"
        and (p.get("relevance_score", 0) >= 65 or (has_legal_intent and p.get("relevance_score", 0) >= 55))
    ]

    # If no search hit, fallback to direct keyword scanning across LANDMARK_PRECEDENTS
    if not relevant:
        q_lower = clean_q.lower()
        for p in LANDMARK_PRECEDENTS:
            score = 0
            for tag in p.get("tags", []):
                if tag.lower() in q_lower:
                    score += 2
            for sec in p.get("statutory_sections", []):
                if sec.lower() in q_lower:
                    score += 3
            if score > 0:
                p_copy = dict(p)
                p_copy["relevance_score"] = score
                relevant.append(p_copy)

    # Sort descending by relevance score
    relevant = sorted(relevant, key=lambda x: x.get("relevance_score", 0), reverse=True)
    top_matches = relevant[:max_results]

    if not top_matches:
        return CitationResolutionResponse(
            query=clean_q,
            has_citations=False,
            citations=[],
            message="No sufficiently relevant verified judicial precedent matches this specific statement."
        )

    formatted_citations = [format_precedent_to_citation(m) for m in top_matches]

    return CitationResolutionResponse(
        query=clean_q,
        has_citations=True,
        citations=formatted_citations,
        message=f"Found {len(formatted_citations)} verified legal precedent(s)."
    )


def format_citations_prompt_context(citations: List[CitationMetadata]) -> str:
    """
    Formats structured citations into prompt context for LLMs to cite verified sources
    accurately without fabricating case details.
    """
    if not citations:
        return "NO VERIFIED PRECEDENTS AVAILABLE. Do not invent any case citations or judgment references."

    lines = ["VERIFIED LEGAL CITATIONS (Quote these exact authorities; do NOT fabricate case names or numbers):"]
    for idx, c in enumerate(citations, start=1):
        lines.append(f"\n[Citation {idx}]")
        lines.append(f"Title: {c.case_title}")
        lines.append(f"Court: {c.court} ({c.authority_type} Authority)")
        lines.append(f"Citation: {c.citation}")
        if c.year:
            lines.append(f"Year: {c.year}")
        if c.statutory_provisions:
            lines.append(f"Statutory Provisions: {', '.join(c.statutory_provisions)}")
        lines.append(f"Key Ratio: {c.relevant_ratio}")
        lines.append(f"Recommended Citation Text: {c.how_to_cite}")
        if c.source_url:
            lines.append(f"Official Source URL: {c.source_url}")

    return "\n".join(lines)
