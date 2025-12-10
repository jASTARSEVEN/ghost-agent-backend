"""
Policy extraction agent using Azure OpenAI LLM.
Extracts structured policy rules from compliance documents with intelligent chunking.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, List

from compliance.agents.openai_client import get_openai_client
from compliance.agents.text_chunker import get_text_chunker
from compliance.models import RuleType, Severity
from compliance.agent_prompts.extraction_prompt import build_policy_extraction_prompt
from common.config import settings

logger = logging.getLogger(__name__)


class ExtractionAgent:
    """Agent for extracting policy rules from compliance documents using Azure OpenAI LLM."""
    
    def __init__(self, prompt_file: Optional[str] = None):
        """
        Initialize the extraction agent.
        
        Args:
            prompt_file: Path to the system prompt file (deprecated - kept for backward compatibility)
        """
        self.openai_client = get_openai_client()
        self.text_chunker = get_text_chunker()
    
    async def extract_rules(self, document_text: str) -> list[dict]:
        """
        Extract policy rules from compliance document text with intelligent chunking.
        
        Automatically handles:
        - Small documents: Single API call
        - Large documents: Chunked into overlapping sections, processed in parallel
        - Result aggregation: Merges and deduplicates rules from all chunks
        
        Args:
            document_text: Cleaned and concatenated text from compliance documents
            
        Returns:
            List of extracted rule dictionaries with the following structure:
            {
                "category": str,
                "rule_type": "do" | "dont",
                "title": str,
                "description": str,
                "severity": "info" | "low" | "medium" | "high" | "critical",
                "example_snippets": list[str]
            }
            
        Raises:
            ValueError: If extraction fails or returns invalid data
        """
        if not document_text or not document_text.strip():
            raise ValueError("Document text cannot be empty")
        
        logger.info(f"Starting extraction for document with {len(document_text)} characters")
        
        try:
            # Check if we need to chunk the document
            if self.text_chunker.should_chunk(document_text):
                logger.info("Document is large - using chunked extraction with parallel processing")
                validated_rules = await self._extract_rules_chunked(document_text)
            else:
                logger.info("Document is small - using single extraction")
                validated_rules = await self._extract_rules_single(document_text)
            
            logger.info(f"Successfully extracted {len(validated_rules)} policy rules")
            return validated_rules
            
        except Exception as e:
            logger.error(f"Failed to extract rules: {str(e)}")
            raise ValueError(f"Policy extraction failed: {str(e)}")
    
    async def _extract_rules_single(self, document_text: str) -> list[dict]:
        """
        Extract rules from a single document (no chunking).
        
        Args:
            document_text: Document text to process
            
        Returns:
            List of validated rule dictionaries
        """
        system_prompt = build_policy_extraction_prompt(document_text)
        
        response_text = await self.openai_client.generate_content_with_retry(
            prompt="Extract all compliance rules from the provided policy documents.",
            system_instruction=system_prompt,
            temperature=0.3,  
            max_tokens=4000,  
            timeout=float(settings.EXTRACTION_TIMEOUT_PER_CHUNK),
            use_json_mode=True,  
            max_retries=3
        )
        
        
        rules = self._parse_response(response_text)
        
        validated_rules = self._validate_rules(rules)
        
        return validated_rules
    
    async def _extract_rules_chunked(self, document_text: str) -> list[dict]:
        """
        Extract rules from a large document using chunking and parallel processing.
        
        Args:
            document_text: Large document text to process
            
        Returns:
            List of validated and deduplicated rule dictionaries
        """
        chunks = self.text_chunker.chunk_text(document_text)
        logger.info(f"Split document into {len(chunks)} chunks for parallel processing")
        
        max_parallel = settings.EXTRACTION_MAX_PARALLEL
        chunk_results = []
        
        for i in range(0, len(chunks), max_parallel):
            batch = chunks[i:i + max_parallel]
            batch_indices = list(range(i, i + len(batch)))
            
            logger.info(f"Processing batch {i // max_parallel + 1}: chunks {batch_indices[0]}-{batch_indices[-1]}")
            
            tasks = [
                self._extract_rules_from_chunk(chunk_text, metadata, chunk_idx)
                for chunk_idx, (chunk_text, metadata) in zip(batch_indices, batch)
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for chunk_idx, result in zip(batch_indices, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Chunk {chunk_idx} failed: {str(result)}")
                elif result:
                    chunk_results.append(result)
        
        if not chunk_results:
            raise ValueError("All chunks failed to extract rules")
        
        logger.info(f"Successfully processed {len(chunk_results)} chunks")
        
        merged_rules = self.text_chunker.merge_chunk_results(chunk_results)
        
        return merged_rules
    
    async def _extract_rules_from_chunk(
        self, 
        chunk_text: str, 
        metadata: dict, 
        chunk_idx: int
    ) -> List[dict]:
        """
        Extract rules from a single chunk.
        
        Args:
            chunk_text: Text of the chunk
            metadata: Chunk metadata (index, position, etc.)
            chunk_idx: Index of the chunk
            
        Returns:
            List of validated rules from this chunk
        """
        try:
            logger.info(
                f"Processing chunk {chunk_idx} "
                f"({metadata['chunk_index'] + 1}/{metadata['total_chunks']}): "
                f"{len(chunk_text)} chars"
            )
            
            chunk_context = ""
            if metadata['total_chunks'] > 1:
                chunk_context = f"\n\nNOTE: This is chunk {metadata['chunk_index'] + 1} of {metadata['total_chunks']} from a larger document. Extract all rules from this section."
            
            system_prompt = build_policy_extraction_prompt(chunk_text + chunk_context)
            
            response_text = await self.openai_client.generate_content_with_retry(
                prompt="Extract all compliance rules from the provided policy document section.",
                system_instruction=system_prompt,
                temperature=0.3,
                max_tokens=4000,
                timeout=float(settings.EXTRACTION_TIMEOUT_PER_CHUNK),
                use_json_mode=True,
                max_retries=2  
            )
            
            rules = self._parse_response(response_text)
            
            validated_rules = self._validate_rules(rules)
            
            logger.info(f"Chunk {chunk_idx} extracted {len(validated_rules)} rules")
            return validated_rules
            
        except Exception as e:
            logger.error(f"Failed to extract rules from chunk {chunk_idx}: {str(e)}")
            raise
    
    def _parse_response(self, response_text: str) -> list[dict]:
        """
        Parse JSON response from Gemini API.
        Handles both the new format (with categories) and legacy formats.
        
        Args:
            response_text: Raw response text from Gemini
            
        Returns:
            List of rule dictionaries (flattened from categories if needed)
            
        Raises:
            ValueError: If JSON parsing fails
        """
        text = response_text.strip()
        
        if text.startswith("```json"):
            text = text[7:]  
        elif text.startswith("```"):
            text = text[3:]  
        
        if text.endswith("```"):
            text = text[:-3]  
        
        text = text.strip()
        
        try:
            data = json.loads(text)
            
            if isinstance(data, dict) and "categories" in data:
                rules = []
                for category_obj in data["categories"]:
                    if isinstance(category_obj, dict) and "rules" in category_obj:
                        category_rules = category_obj["rules"]
                        if isinstance(category_rules, list):
                            rules.extend(category_rules)
                return rules
            
            elif isinstance(data, dict) and "rules" in data:
                rules = data["rules"]
            
            elif isinstance(data, list):
                rules = data
            
            else:
                raise ValueError("Invalid response format: expected object with 'categories' or 'rules' array, or array of rules")
            
            if not isinstance(rules, list):
                raise ValueError("Rules must be an array")
            
            return rules
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            logger.error(f"Response text: {response_text[:500]}...")
            raise ValueError(f"Failed to parse JSON response: {str(e)}")
    
    def _validate_rules(self, rules: list[dict]) -> list[dict]:
        """
        Validate and normalize extracted rules.
        
        Args:
            rules: List of rule dictionaries from LLM
            
        Returns:
            List of validated and normalized rule dictionaries
            
        Raises:
            ValueError: If validation fails
        """
        validated = []
        
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                logger.warning(f"Skipping invalid rule at index {i}: not a dictionary")
                continue
            
            required_fields = ["category", "rule_type", "title", "description", "severity"]
            missing_fields = [field for field in required_fields if field not in rule]
            if missing_fields:
                logger.warning(f"Skipping rule at index {i}: missing fields {missing_fields}")
                continue
            
            rule_type = rule["rule_type"].lower().strip()
            if rule_type not in ["do", "dont"]:
                logger.warning(f"Invalid rule_type '{rule_type}' at index {i}, defaulting to 'do'")
                rule_type = "do"
            
            severity = rule["severity"].lower().strip()
            valid_severities = ["info", "low", "medium", "high", "critical"]
            if severity not in valid_severities:
                logger.warning(f"Invalid severity '{severity}' at index {i}, defaulting to 'medium'")
                severity = "medium"
            
            example_snippets = rule.get("example_snippets", [])
            if not isinstance(example_snippets, list):
                example_snippets = []
            example_snippets = [s for s in example_snippets if s and isinstance(s, str) and s.strip()]
            
            title = str(rule["title"]).strip()
            if len(title) > 100:
                title = title[:97] + "..."
            
            validated_rule = {
                "category": str(rule["category"]).strip(),
                "rule_type": rule_type,
                "title": title,
                "description": str(rule["description"]).strip(),
                "severity": severity,
                "example_snippets": example_snippets[:5],  
            }
            
            validated.append(validated_rule)
        
        if not validated:
            raise ValueError("No valid rules extracted from documents")
        
        return validated

