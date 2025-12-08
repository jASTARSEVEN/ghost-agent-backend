"""
Simplified evaluation prompt builder for compliance evaluation.
Optimized for token efficiency while maintaining accuracy.
"""


def build_compliance_evaluation_prompt(
    conversation_data: dict,
    policy_rules: list[dict]
) -> str:
    """
    Build efficient evaluation prompt for LLM compliance analysis.
    
    Optimized for:
    - Token efficiency (~55% reduction)
    - Clear, concise instructions
    - Focus on essential information only
    
    Args:
        conversation_data: Processed conversation with dialogue and tools
        policy_rules: List of policy rules to evaluate against
        
    Returns:
        Formatted system prompt for LLM evaluation
    """
    
    dialogue = conversation_data.get("dialogue", [])
    tools_used = conversation_data.get("tools_used", [])
    metadata = conversation_data.get("metadata", {})
    
    # Build sections
    rules_section = _build_rules_section(policy_rules)
    transcript_section = _build_transcript_section(dialogue, metadata)
    tools_section = _build_tools_section(tools_used)
    
    # Construct prompt
    prompt = f"""You are a compliance auditor evaluating a customer service conversation.

# POLICY RULES
{rules_section}

# CONVERSATION TRANSCRIPT
Duration: {metadata.get('duration_seconds', 0)}s | Turns: {len(dialogue)}

{transcript_section}

# TOOLS USED
{tools_section}

# EVALUATION TASK
For each rule, determine:
1. Does it apply to this conversation?
2. Did the CSR follow it? (check dialogue + tools)
3. Identify violations with specific event_id

Key compliance checks:
• Identity verification BEFORE account access tools
• Required disclosures made before actions
• Professional communication maintained
• Proper tool usage sequence

# OUTPUT FORMAT (JSON only)
{{
  "overall_score": <0-100 integer>,
  "compliance_status": "<compliant|partially_compliant|non_compliant>",
  "compliance_findings": [
    {{
      "event_id": "<event_id from dialogue or tools>",
      "annotations": [
        {{
          "status": "<compliant|violated|warning>",
          "severity": "<critical|high|medium|low>",
          "rule_id": <rule_id>,
          "rule_title": "<rule title>",
          "rule_category": "<category>",
          "message": "<concise UI message>",
          "confidence": <0.0-1.0>,
          "details": "<explanation>",
          "recommendation": "<what should have been done (for violations)>",
          "context": {{
            "related_event_ids": ["<id>"],
            "tool_name": "<if tool-related>",
            "expected_action": "<what was expected>"
          }}
        }}
      ]
    }}
  ],
  "violations_summary": {{
    "total_violations": <count>,
    "total_warnings": <count>,
    "total_compliant": <count>,
    "by_severity": {{"critical": <count>, "high": <count>, "medium": <count>, "low": <count>}}
  }},
  "applicable_rules_summary": [
    {{
      "rule_id": <id>,
      "rule_title": "<title>",
      "category": "<category>",
      "severity": "<severity>",
      "result": "<compliant|violated|warning|not_applicable>",
      "event_count": <count>,
      "reason": "<if not_applicable>"
    }}
  ],
  "summary": "<natural language overall assessment>"
}}

Analyze the conversation and return JSON only."""
    
    return prompt


def _build_rules_section(rules: list[dict]) -> str:
    """Build compact rules section"""
    lines = []
    
    for rule in rules:
        rule_id = rule.get("id")
        severity = rule.get("severity", "medium").upper()
        category = rule.get("category", "General")
        title = rule.get("title", "")
        
        lines.append(f"[{rule_id}] {severity} | {category}: {title}")
    
    return "\n".join(lines)


def _build_transcript_section(dialogue: list[dict], metadata: dict) -> str:
    """Build compact transcript section"""
    if not dialogue:
        return "(No dialogue captured)"
    
    lines = []
    for turn in dialogue:
        timestamp = turn.get("timestamp", "")
        speaker = turn.get("speaker", "unknown").upper()
        text = turn.get("text", "")
        event_id = turn.get("event_id", "")
        
        # Format: [time] SPEAKER: text | ID: event_id
        lines.append(f"[{timestamp}] {speaker}: {text}")
        lines.append(f"  └─ ID: {event_id}")
    
    return "\n".join(lines)


def _build_tools_section(tools: list[dict]) -> str:
    """Build compact tools section"""
    if not tools:
        return "(No tools used)"
    
    lines = []
    for tool in tools:
        tool_name = tool.get("tool_name", "unknown")
        timestamp = tool.get("timestamp", "")
        event_id = tool.get("event_id", "")
        
        lines.append(f"[{timestamp}] 🔧 {tool_name} | ID: {event_id}")
    
    return "\n".join(lines)
