"""
Policy extraction agent using Gemini LLM.
Extracts structured policy rules from compliance documents.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

from compliance.agents.gemini_client import get_gemini_client
from compliance.models import RuleType, Severity
from compliance.agent_prompts.extraction_prompt import build_policy_extraction_prompt

logger = logging.getLogger(__name__)


class ExtractionAgent:
    """Agent for extracting policy rules from compliance documents using Gemini LLM."""
    
    def __init__(self, prompt_file: Optional[str] = None):
        """
        Initialize the extraction agent.
        
        Args:
            prompt_file: Path to the system prompt file (deprecated - kept for backward compatibility)
        """
        self.gemini_client = get_gemini_client()
        # Note: We now use build_policy_extraction_prompt() function instead of loading from file
    
    async def extract_rules(self, document_text: str) -> list[dict]:
        """
        Extract policy rules from compliance document text.
        
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
        
        # Truncate if too long (Gemini has token limits)
        # Rough estimate: 1 token ≈ 4 characters, so 100k chars ≈ 25k tokens
        max_length = 100000
        if len(document_text) > max_length:
            logger.warning(f"Document text truncated from {len(document_text)} to {max_length} characters")
            document_text = document_text[:max_length] + "\n\n[Document truncated due to length...]"
        
        try:
            # Build the prompt with document text injected
            system_prompt = build_policy_extraction_prompt(document_text)
            
            # Call Gemini API - pass empty string as prompt since document is in system_prompt
            response_text = await self.gemini_client.generate_content(
                prompt="",  # Document text is already in system_prompt
                system_instruction=system_prompt,
                temperature=0.3,  # Lower temperature for more consistent extraction
                timeout=120.0  # 2 minutes timeout for large documents
            )
            
            # Parse JSON response
            rules = self._parse_response(response_text)
            
            # Validate and normalize rules
            validated_rules = self._validate_rules(rules)
            
            logger.info(f"Successfully extracted {len(validated_rules)} policy rules")
            return validated_rules
            
        except Exception as e:
            logger.error(f"Failed to extract rules: {str(e)}")
            raise ValueError(f"Policy extraction failed: {str(e)}")
    
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
        # Clean the response - remove markdown code blocks if present
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```
        
        if text.endswith("```"):
            text = text[:-3]  # Remove closing ```
        
        text = text.strip()
        
        try:
            data = json.loads(text)
            
            # Handle new format: {"policy_set_name": "...", "categories": [...]}
            if isinstance(data, dict) and "categories" in data:
                rules = []
                for category_obj in data["categories"]:
                    if isinstance(category_obj, dict) and "rules" in category_obj:
                        # Extract rules from this category
                        category_rules = category_obj["rules"]
                        if isinstance(category_rules, list):
                            rules.extend(category_rules)
                return rules
            
            # Handle legacy format: {"rules": [...]}
            elif isinstance(data, dict) and "rules" in data:
                rules = data["rules"]
            
            # Handle legacy format: [...] (array of rules)
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
            
            # Validate required fields
            required_fields = ["category", "rule_type", "title", "description", "severity"]
            missing_fields = [field for field in required_fields if field not in rule]
            if missing_fields:
                logger.warning(f"Skipping rule at index {i}: missing fields {missing_fields}")
                continue
            
            # Validate and normalize rule_type
            rule_type = rule["rule_type"].lower().strip()
            if rule_type not in ["do", "dont"]:
                logger.warning(f"Invalid rule_type '{rule_type}' at index {i}, defaulting to 'do'")
                rule_type = "do"
            
            # Validate and normalize severity
            severity = rule["severity"].lower().strip()
            valid_severities = ["info", "low", "medium", "high", "critical"]
            if severity not in valid_severities:
                logger.warning(f"Invalid severity '{severity}' at index {i}, defaulting to 'medium'")
                severity = "medium"
            
            # Normalize example_snippets
            example_snippets = rule.get("example_snippets", [])
            if not isinstance(example_snippets, list):
                example_snippets = []
            # Filter out empty snippets
            example_snippets = [s for s in example_snippets if s and isinstance(s, str) and s.strip()]
            
            # Truncate title if too long
            title = str(rule["title"]).strip()
            if len(title) > 100:
                title = title[:97] + "..."
            
            # Build validated rule
            validated_rule = {
                "category": str(rule["category"]).strip(),
                "rule_type": rule_type,
                "title": title,
                "description": str(rule["description"]).strip(),
                "severity": severity,
                "example_snippets": example_snippets[:5],  # Limit to 5 snippets
            }
            
            validated.append(validated_rule)
        
        if not validated:
            raise ValueError("No valid rules extracted from documents")
        
        return validated

