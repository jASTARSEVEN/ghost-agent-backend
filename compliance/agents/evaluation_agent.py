"""
Compliance evaluation agent using Azure OpenAI LLM.
Evaluates conversations against policy rules and identifies compliance issues.
"""
import json
import logging
from typing import Dict, List, Any
from datetime import datetime

from compliance.agents.openai_client import get_openai_client
from compliance.agent_prompts.evaluation_prompt import build_compliance_evaluation_prompt
from common.config import settings

logger = logging.getLogger(__name__)


class EvaluationAgent:
    """Agent for evaluating conversation compliance using Azure OpenAI LLM."""
    
    def __init__(self):
        """Initialize the evaluation agent."""
        self.openai_client = get_openai_client()
    
    async def evaluate_conversation(
        self,
        conversation_data: Dict[str, Any],
        policy_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate a conversation for compliance against policy rules.
        
        Args:
            conversation_data: Structured conversation from processor with timeline and metadata
            policy_rules: List of policy rules to evaluate against
            
        Returns:
            Evaluation result dictionary with compliance findings
            
        Raises:
            ValueError: If evaluation fails or returns invalid data
        """
        if not conversation_data:
            raise ValueError("Conversation data cannot be empty")
        
        if not policy_rules:
            raise ValueError("Policy rules cannot be empty")
        
        metadata = conversation_data.get("metadata", {})
        
        logger.info(
            f"Starting evaluation for conversation {conversation_data.get('conversation_id')} "
            f"against {len(policy_rules)} rules"
        )
        
        try:
            evaluation_prompt = build_compliance_evaluation_prompt(
                conversation_data=conversation_data,
                policy_rules=policy_rules
            )
            
            logger.info(f"Evaluation prompt built: {len(evaluation_prompt)} characters")
            
            start_time = datetime.now()
            
            response_text = await self.openai_client.generate_content_with_retry(
                prompt="Evaluate this conversation for compliance.",
                system_instruction=evaluation_prompt,
                temperature=0.2,  
                max_tokens=6000,  
                timeout=float(settings.EXTRACTION_TIMEOUT_PER_CHUNK or 60),
                use_json_mode=True,
                max_retries=3
            )
            
            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            logger.info(f"OpenAI evaluation completed in {processing_time_ms}ms")
           
            evaluation_result = self._parse_evaluation_response(response_text)
            
            evaluation_result["llm_metadata"] = {
                "model_used": settings.AZURE_DEPLOYMENT_NAME or "gpt-4o",
                "processing_time_ms": processing_time_ms,
                "prompt_length": len(evaluation_prompt),
                "response_length": len(response_text)
            }
            
            self._validate_evaluation(evaluation_result, policy_rules)
            
            logger.info(
                f"Evaluation complete: score={evaluation_result.get('overall_score')}, "
                f"violations={evaluation_result.get('violations_summary', {}).get('total_violations', 0)}"
            )
            
            return evaluation_result
            
        except Exception as e:
            logger.error(f"Failed to evaluate conversation: {str(e)}")
            raise ValueError(f"Compliance evaluation failed: {str(e)}")
    
    def _parse_evaluation_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response from OpenAI API.
        
        Args:
            response_text: Raw response text from OpenAI
            
        Returns:
            Parsed evaluation dictionary
            
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
            evaluation = json.loads(text)
            
            if not isinstance(evaluation, dict):
                raise ValueError("Evaluation response must be a JSON object")
            
            return evaluation
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            logger.error(f"Response text: {response_text[:500]}...")
            raise ValueError(f"Failed to parse evaluation JSON: {str(e)}")
    
    def _validate_evaluation(
        self,
        evaluation: Dict[str, Any],
        policy_rules: List[Dict[str, Any]]
    ) -> None:
        """
        Validate evaluation structure and content.
        
        Args:
            evaluation: Parsed evaluation dictionary
            policy_rules: Original policy rules for validation
            
        Raises:
            ValueError: If validation fails
        """
        required_fields = [
            "overall_score",
            "compliance_status",
            "summary",
            "compliance_findings",
            "violations_summary",
            "applicable_rules_summary"
        ]
        
        missing_fields = [f for f in required_fields if f not in evaluation]
        if missing_fields:
            raise ValueError(f"Missing required fields in evaluation: {missing_fields}")
        
        score = evaluation["overall_score"]
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            raise ValueError(f"overall_score must be between 0-100, got: {score}")
        
        valid_statuses = ["compliant", "partially_compliant", "non_compliant"]
        status = evaluation["compliance_status"]
        if status not in valid_statuses:
            raise ValueError(f"compliance_status must be one of {valid_statuses}, got: {status}")
        
        findings = evaluation["compliance_findings"]
        if not isinstance(findings, list):
            raise ValueError("compliance_findings must be an array")
        
        for finding in findings:
            if "event_id" not in finding:
                raise ValueError("Each finding must have an event_id")
            if "annotations" not in finding or not isinstance(finding["annotations"], list):
                raise ValueError("Each finding must have annotations array")
            
            for annotation in finding["annotations"]:
                required_annotation_fields = [
                    "status", "severity", "rule_id", "message", "confidence"
                ]
                missing = [f for f in required_annotation_fields if f not in annotation]
                if missing:
                    raise ValueError(f"Annotation missing fields: {missing}")
                
                confidence = annotation["confidence"]
                if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                    raise ValueError(f"confidence must be between 0-1, got: {confidence}")
        
        summary = evaluation["violations_summary"]
        if not isinstance(summary, dict):
            raise ValueError("violations_summary must be an object")
        
        required_summary_fields = ["total_violations", "total_warnings", "total_compliant", "by_severity"]
        missing = [f for f in required_summary_fields if f not in summary]
        if missing:
            raise ValueError(f"violations_summary missing fields: {missing}")
        
        logger.info("Evaluation structure validated successfully")

