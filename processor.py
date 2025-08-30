import re
from typing import List, Dict, Any
from logger_config import get_logger

logger = get_logger(__name__)

class DocumentProcessor:
    """Handles document chunking and prompt preparation for LLM processing"""

    def __init__(self, max_section_length: int = 6000):
        # Bump default limit to allow larger sections
        self.max_section_length = max_section_length

    def create_sections(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create manageable sections for LLM processing without oversplitting.
        
        Instead of splitting by every heading/paragraph, we chunk the document
        into larger sections that roughly fit into token limits.
        """
        try:
            text = content["text"].strip()
            if not text:
                return []

            # If the document is already within size, keep as one section
            if len(text) <= self.max_section_length:
                logger.info("Document fits in a single section")
                return [{
                    "text": text,
                    "heading": "Full Document",
                    "number": None,
                    "section_number": 0
                }]

            # Otherwise, chunk by length while preserving paragraph boundaries
            sections = self._chunk_text(text)
            logger.info(f"Document split into {len(sections)} large sections")
            return sections

        except Exception as e:
            logger.error(f"Section creation error: {str(e)}")
            raise

    def _chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Split text into large contiguous chunks instead of micro-sections"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        sections, current_text = [], ""
        section_count = 0

        for para in paragraphs:
            # If adding the paragraph would exceed max, start a new section
            if len(current_text) + len(para) > self.max_section_length and current_text:
                sections.append({
                    "text": current_text.strip(),
                    "heading": f"Document Section {section_count+1}",
                    "number": None,
                    "section_number": section_count
                })
                current_text = para + "\n\n"
                section_count += 1
            else:
                current_text += para + "\n\n"

        # Add final section
        if current_text.strip():
            sections.append({
                "text": current_text.strip(),
                "heading": f"Document Section {section_count+1}",
                "number": None,
                "section_number": section_count
            })

        return sections

    def create_plain_english_prompt(self, section: Dict[str, Any]) -> str:
        heading = section.get("heading", "Document Section")
        text = section["text"]
        return f"""Convert the following legal text into plain English that anyone can understand. 
Keep all important information and meaning, but use simple words and clear sentences.

Section: {heading}

Legal Text:
{text}

Plain English Version:"""

    def create_summary_prompt(self, section: Dict[str, Any]) -> str:
        heading = section.get("heading", "Document Section")
        text = section["text"]
        return f"""Summarize the following legal text into clear, concise bullet points. 
Preserve all legal meaning and important details.

Section: {heading}

Legal Text:
{text}

Bullet-Point Summary:"""

    def validate_output(self, original_sections: List[Dict], processed_output: str) -> Dict[str, Any]:
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }

        # Simple sanity checks
        if "[TRUNCATED]" in processed_output or "[INCOMPLETE]" in processed_output:
            validation_result["warnings"].append("Output may be truncated")

        if len(processed_output) < 50:
            validation_result["errors"].append("Output suspiciously short")
            validation_result["is_valid"] = False

        return validation_result
