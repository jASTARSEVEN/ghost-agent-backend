"""
Smart text chunking utility for processing large documents.
Splits documents intelligently while preserving context and structure.
"""
import re
import logging
from typing import List, Tuple
from common.config import settings

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Intelligent text chunker that splits documents while preserving context.
    
    Features:
    - Section-aware splitting (respects document structure)
    - Context overlap between chunks
    - Configurable chunk sizes
    - Preserves sentence boundaries
    """
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        Initialize the text chunker.
        
        Args:
            chunk_size: Maximum characters per chunk (defaults to settings.EXTRACTION_CHUNK_SIZE)
            chunk_overlap: Overlap between chunks in characters (defaults to settings.EXTRACTION_CHUNK_OVERLAP)
        """
        self.chunk_size = chunk_size or settings.EXTRACTION_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.EXTRACTION_CHUNK_OVERLAP
        
        logger.info(f"TextChunker initialized: chunk_size={self.chunk_size}, overlap={self.chunk_overlap}")
    
    def should_chunk(self, text: str) -> bool:
        """
        Determine if text needs to be chunked.
        
        Args:
            text: Input text
            
        Returns:
            True if text exceeds chunk size threshold
        """
        # Use 80% of chunk_size as threshold to account for variation
        threshold = int(self.chunk_size * 0.8)
        return len(text) > threshold
    
    def chunk_text(self, text: str) -> List[Tuple[str, dict]]:
        """
        Split text into overlapping chunks with metadata.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of tuples: (chunk_text, metadata_dict)
            where metadata contains: chunk_index, total_chunks, start_pos, end_pos
        """
        if not text or not text.strip():
            return []
        
        # If text is small enough, return as single chunk
        if not self.should_chunk(text):
            return [(text, {
                "chunk_index": 0,
                "total_chunks": 1,
                "start_pos": 0,
                "end_pos": len(text),
                "is_single_chunk": True
            })]
        
        logger.info(f"Chunking text of length {len(text)} characters")
        
        # Split text into chunks
        chunks = []
        start_pos = 0
        chunk_index = 0
        
        while start_pos < len(text):
            # Calculate end position for this chunk
            end_pos = min(start_pos + self.chunk_size, len(text))
            
            # If not at the end, try to break at a natural boundary
            if end_pos < len(text):
                end_pos = self._find_break_point(text, start_pos, end_pos)
            
            # Extract chunk
            chunk_text = text[start_pos:end_pos]
            
            # Add chunk with metadata
            chunks.append((chunk_text, {
                "chunk_index": chunk_index,
                "total_chunks": -1,  # Will be updated after
                "start_pos": start_pos,
                "end_pos": end_pos,
                "is_single_chunk": False
            }))
            
            chunk_index += 1
            
            # Move to next chunk with overlap
            # For the last chunk, we're done
            if end_pos >= len(text):
                break
            
            # Calculate next start position (with overlap)
            start_pos = end_pos - self.chunk_overlap
            
            # Make sure we're making progress
            if start_pos <= chunks[-1][1]["start_pos"]:
                start_pos = end_pos
        
        # Update total_chunks in all metadata
        total_chunks = len(chunks)
        for i, (chunk_text, metadata) in enumerate(chunks):
            metadata["total_chunks"] = total_chunks
        
        logger.info(f"Split into {total_chunks} chunks")
        return chunks
    
    def _find_break_point(self, text: str, start: int, preferred_end: int) -> int:
        """
        Find a natural break point for chunking (paragraph, sentence, or word boundary).
        
        Args:
            text: Full text
            start: Start position of chunk
            preferred_end: Preferred end position
            
        Returns:
            Adjusted end position at natural boundary
        """
        # Look back from preferred_end to find a good break point
        search_window = min(500, preferred_end - start)  # Look back up to 500 chars
        search_start = preferred_end - search_window
        
        # Priority 1: Double newline (paragraph break)
        para_breaks = [m.end() for m in re.finditer(r'\n\s*\n', text[search_start:preferred_end])]
        if para_breaks:
            return search_start + para_breaks[-1]
        
        # Priority 2: Single newline (line break)
        line_breaks = [m.end() for m in re.finditer(r'\n', text[search_start:preferred_end])]
        if line_breaks:
            return search_start + line_breaks[-1]
        
        # Priority 3: Sentence boundary (., !, ?)
        sentence_breaks = [m.end() for m in re.finditer(r'[.!?]\s+', text[search_start:preferred_end])]
        if sentence_breaks:
            return search_start + sentence_breaks[-1]
        
        # Priority 4: Word boundary
        word_breaks = [m.end() for m in re.finditer(r'\s+', text[search_start:preferred_end])]
        if word_breaks:
            return search_start + word_breaks[-1]
        
        # Fallback: use preferred_end
        return preferred_end
    
    def merge_chunk_results(self, chunk_results: List[list]) -> list:
        """
        Merge and deduplicate rules from multiple chunks.
        
        Args:
            chunk_results: List of rule lists from different chunks
            
        Returns:
            Merged and deduplicated list of rules
        """
        if not chunk_results:
            return []
        
        # If only one chunk, return as-is
        if len(chunk_results) == 1:
            return chunk_results[0]
        
        # Merge all rules
        all_rules = []
        for rules in chunk_results:
            if rules:
                all_rules.extend(rules)
        
        if not all_rules:
            return []
        
        logger.info(f"Merging {len(all_rules)} rules from {len(chunk_results)} chunks")
        
        # Deduplicate based on similarity
        deduplicated = self._deduplicate_rules(all_rules)
        
        logger.info(f"After deduplication: {len(deduplicated)} unique rules")
        return deduplicated
    
    def _deduplicate_rules(self, rules: list) -> list:
        """
        Remove duplicate or very similar rules.
        
        Args:
            rules: List of rule dictionaries
            
        Returns:
            Deduplicated list of rules
        """
        if not rules:
            return []
        
        unique_rules = []
        seen_signatures = set()
        
        for rule in rules:
            # Create a signature for the rule
            signature = self._rule_signature(rule)
            
            # Check if we've seen a very similar rule
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_rules.append(rule)
            else:
                logger.debug(f"Skipping duplicate rule: {rule.get('title', 'unknown')}")
        
        return unique_rules
    
    def _rule_signature(self, rule: dict) -> str:
        """
        Create a signature for a rule to detect duplicates.
        
        Args:
            rule: Rule dictionary
            
        Returns:
            Signature string
        """
        # Normalize title and create signature
        title = rule.get("title", "").lower().strip()
        category = rule.get("category", "").lower().strip()
        rule_type = rule.get("rule_type", "").lower().strip()
        
        # Remove common punctuation and extra spaces
        title = re.sub(r'[^\w\s]', '', title)
        title = re.sub(r'\s+', ' ', title)
        
        # Create signature from key components
        signature = f"{category}|{rule_type}|{title}"
        
        return signature
    
    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of token count.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count (1 token ≈ 4 characters)
        """
        return len(text) // 4


# Global chunker instance
_chunker: TextChunker = None


def get_text_chunker() -> TextChunker:
    """
    Get or create the global text chunker instance.
    
    Returns:
        TextChunker instance
    """
    global _chunker
    if _chunker is None:
        _chunker = TextChunker()
    return _chunker

