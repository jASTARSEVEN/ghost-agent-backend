"""
Evaluation prompt builder for compliance evaluation.
Optimized using OpenAI GPT-4 prompting best practices.
"""


def build_compliance_evaluation_prompt(
    conversation_timeline: list[dict],
    conversation_metadata: dict,
    policy_rules: list[dict]
) -> str:
    """
    Build the evaluation prompt for LLM compliance analysis.
    
    Follows prompt engineering best practices:
    - Clear instructions with delimiters
    - Structured sections (rules, timeline, task)
    - ALL CAPS for critical requirements
    - Few-shot examples for complex scenarios
    - Explicit JSON output format
    
    Args:
        conversation_timeline: List of timeline entries from conversation processor
        conversation_metadata: Conversation metadata (duration, turns, etc.)
        policy_rules: List of policy rules to evaluate against
        
    Returns:
        Formatted system prompt for LLM evaluation
    """
    
    # Build sections
    rules_section = _build_rules_section(policy_rules)
    timeline_section = _build_timeline_section(conversation_timeline, conversation_metadata)
    task_section = _build_task_section()
    output_format_section = _build_output_format_section()
    examples_section = _build_examples_section()
    
    # Construct full prompt
    prompt = f"""You are an expert compliance auditor evaluating customer service conversations.

Your task is to analyze the conversation against company policy rules and identify compliance issues.

CRITICAL INSTRUCTIONS:
• Evaluate ONLY rules that apply to THIS specific conversation
• Focus on TIMING of actions - especially tool usage relative to dialogue
• Provide evidence by referencing EVENT IDs - DO NOT copy full transcript text
• Be strict with "critical" and "high" severity rules
• Consider context - what happened BEFORE each action

{rules_section}

{timeline_section}

{task_section}

{output_format_section}

{examples_section}

# FINAL INSTRUCTION
Analyze the conversation above and output ONLY the JSON response. Begin evaluation now."""
    
    return prompt


def _build_rules_section(policy_rules: list[dict]) -> str:
    """Build the policy rules section"""
    
    lines = ["# POLICY RULES TO EVALUATE"]
    lines.append("")
    lines.append("Evaluate the conversation against these rules:")
    lines.append("")
    
    for i, rule in enumerate(policy_rules, 1):
        rule_type = rule.get("rule_type", "do").upper()
        severity = rule.get("severity", "medium").upper()
        category = rule.get("category", "General")
        title = rule.get("title", "")
        description = rule.get("description", "")
        
        lines.append(f"## Rule {i} [ID: {rule.get('id')}] - {severity} SEVERITY")
        lines.append(f"**Category:** {category}")
        lines.append(f"**Type:** {rule_type}")
        lines.append(f"**Title:** {title}")
        lines.append(f"**Description:** {description}")
        lines.append("")
    
    return "\n".join(lines)


def _build_timeline_section(timeline: list[dict], metadata: dict) -> str:
    """Build the conversation timeline section"""
    
    lines = ["# CONVERSATION TIMELINE"]
    lines.append("")
    lines.append("## Conversation Metadata")
    lines.append(f"- Duration: {metadata.get('duration_seconds', 0)} seconds")
    lines.append(f"- Total turns: {metadata.get('total_turns', 0)}")
    lines.append(f"- Total tool calls: {metadata.get('total_tool_calls', 0)}")
    lines.append(f"- Started: {metadata.get('started_at', 'unknown')}")
    lines.append(f"- Ended: {metadata.get('ended_at', 'unknown')}")
    lines.append("")
    
    lines.append("## Chronological Event Flow")
    lines.append("")
    lines.append("IMPORTANT: Pay attention to EVENT IDs - use these to reference specific moments.")
    lines.append("TIMING MATTERS: Note when tools are used relative to customer statements.")
    lines.append("")
    
    for entry in timeline:
        event_id = entry.get("event_id")
        sequence = entry.get("sequence")
        timestamp = entry.get("timestamp", "").split("T")[1][:8] if "T" in entry.get("timestamp", "") else ""
        entry_type = entry.get("type")
        
        if entry_type == "dialogue":
            speaker = entry.get("speaker", "unknown").upper()
            text = entry.get("text", "")
            lines.append(f"[{timestamp}] SEQ {sequence} | EVENT_ID: {event_id}")
            lines.append(f"  {speaker}: {text}")
            lines.append("")
        
        elif entry_type == "tool_call":
            tool_name = entry.get("tool_name")
            tool_state = entry.get("tool_state")
            context = entry.get("context", {})
            
            lines.append(f"[{timestamp}] SEQ {sequence} | EVENT_ID: {event_id}")
            lines.append(f"  🔧 TOOL: {tool_name} ({tool_state})")
            
            # Show critical context
            if context.get("last_customer_statement"):
                lines.append(f"  └─ Context: Customer just said: \"{context['last_customer_statement'][:80]}...\"")
            if context.get("turns_since_last_customer") == 0:
                lines.append(f"  └─ ⚠️ TIMING NOTE: Tool called IMMEDIATELY after customer spoke")
            
            # Show tool result if available
            if tool_state == "success" and entry.get("tool_result"):
                lines.append(f"  └─ Result: {str(entry['tool_result'])[:100]}")
            
            lines.append("")
        
        elif entry_type == "lifecycle":
            lifecycle_event = entry.get("lifecycle_event", "unknown")
            lines.append(f"[{timestamp}] SEQ {sequence} | EVENT_ID: {event_id}")
            lines.append(f"  📞 LIFECYCLE: {lifecycle_event}")
            lines.append("")
    
    return "\n".join(lines)


def _build_task_section() -> str:
    """Build the evaluation task instructions"""
    
    return """# EVALUATION TASK

For EACH rule that applies to this conversation:

1. **Determine if rule applies**
   - Some rules may not be relevant to this conversation type
   - Mark as "not_applicable" if rule doesn't apply
   - Provide brief reason why

2. **Evaluate compliance** (if applicable)
   - Status: "compliant" | "violated" | "warning" | "unclear"
   - "compliant" = Rule was followed correctly
   - "violated" = Rule was clearly broken
   - "warning" = Rule was partially followed or could be improved
   - "unclear" = Insufficient information to determine

3. **Provide evidence**
   - Reference EVENT IDs where rule was followed/violated
   - For violations: Show what SHOULD have happened
   - For tool-related rules: Check TIMING relative to dialogue
   - Include brief reasoning

4. **Calculate confidence**
   - 0.0 to 1.0 scale
   - Higher confidence for clear-cut cases
   - Lower confidence for subjective judgments

5. **Make recommendations** (for violations/warnings only)
   - What agent should have done differently
   - Be specific and actionable

## Special Focus Areas

### Identity Verification Rules
- Did agent verify identity BEFORE accessing account?
- Look for verification requests (account number, phone, security questions)
- Check timing: verification request → customer provides info → tool used

### Required Disclosures
- Were disclosures made BEFORE taking action?
- Look for phrases like "this will...", "you'll lose...", "refund policy..."
- Check timing: disclosure → customer acknowledgment → action tool

### Retention Attempts (for cancellations)
- Was retention attempted BEFORE processing cancellation?
- Look for offers, alternatives, discounts mentioned
- Check timing: retention offer → customer response → cancellation tool

### Communication Standards
- Greeting, empathy, professionalism
- These are usually softer judgments - use "warning" for minor issues"""


def _build_output_format_section() -> str:
    """Build the output format specification"""
    
    return """# OUTPUT FORMAT

Return ONLY this JSON structure (no additional text):

{
  "overall_score": <integer 0-100>,
  "compliance_status": "<compliant|partially_compliant|non_compliant>",
  "summary": "<brief natural language summary>",
  "compliance_findings": [
    {
      "event_id": "<event_id where rule applies>",
      "annotations": [
        {
          "status": "<compliant|violated|warning>",
          "severity": "<critical|high|medium|low>",
          "rule_id": <rule_id>,
          "rule_title": "<rule title>",
          "rule_category": "<category>",
          "message": "<concise message for UI>",
          "confidence": <0.0-1.0>,
          "details": "<explanation of finding>",
          "recommendation": "<what should have been done (if violation/warning)>",
          "context": {
            "related_event_ids": ["<event_id>", ...],
            "tool_name": "<if tool-related>",
            "expected_action": "<what was expected>"
          }
        }
      ]
    }
  ],
  "violations_summary": {
    "total_violations": <count>,
    "total_warnings": <count>,
    "total_compliant": <count>,
    "by_severity": {
      "critical": <count>,
      "high": <count>,
      "medium": <count>,
      "low": <count>
    }
  },
  "applicable_rules_summary": [
    {
      "rule_id": <rule_id>,
      "result": "<compliant|violated|warning|not_applicable>",
      "reason": "<brief reason if not_applicable>"
    }
  ]
}

## Output Guidelines

1. **overall_score**: Calculate as percentage of compliant rules
   - Weight by severity: critical=40pts, high=30pts, medium=20pts, low=10pts
   - Violations reduce score, warnings reduce by half

2. **compliance_status**:
   - "compliant" = score >= 90 AND no critical/high violations
   - "non_compliant" = score < 70 OR any critical violations
   - "partially_compliant" = everything else

3. **compliance_findings**: Include ONLY events with annotations
   - Do NOT include every event in timeline
   - Only events where rules were checked
   
4. **message**: Short UI-friendly message
   - "✓" prefix for compliant
   - "⚠️" prefix for warnings
   - "⚠️ CRITICAL:" or "⚠️ HIGH:" for violations

5. **annotations**: Group by event_id
   - Multiple rules can apply to same event
   - Each rule gets separate annotation"""


def _build_examples_section() -> str:
    """Build few-shot examples section"""
    
    return """# EXAMPLES

## Example 1: Identity Verification Violation

Input:
```
[10:00:15] CUSTOMER: I want to cancel my account
[10:00:17] TOOL: lookup_account (loading) | EVENT_ID: evt-123
  Context: Customer just said: "I want to cancel my account"
  TIMING NOTE: Tool called IMMEDIATELY after customer spoke
```

Rule: "Verify customer identity before accessing account" (critical)

Output:
```json
{
  "event_id": "evt-123",
  "annotations": [{
    "status": "violated",
    "severity": "critical",
    "rule_id": 12,
    "rule_title": "Verify customer identity before accessing account",
    "message": "⚠️ CRITICAL: Account accessed without verification",
    "confidence": 0.95,
    "details": "Agent used lookup_account tool immediately after customer request without requesting account number, phone verification, or security questions.",
    "recommendation": "Agent should have asked: 'May I have your account number to verify your identity?'",
    "context": {
      "related_event_ids": [],
      "tool_name": "lookup_account",
      "expected_action": "Request verification first"
    }
  }]
}
```

## Example 2: Proper Retention Sequence

Input:
```
[10:03:00] AGENT: Would you like our economy plan at 50% off? | EVENT_ID: evt-200
[10:03:15] CUSTOMER: No thanks, I've decided to cancel
[10:03:20] TOOL: process_cancellation (success) | EVENT_ID: evt-201
  Context: Customer just said: "No thanks, I've decided to cancel"
```

Rule: "Offer retention options before cancellation" (high)

Output:
```json
{
  "event_id": "evt-200",
  "annotations": [{
    "status": "compliant",
    "severity": "high",
    "rule_id": 13,
    "rule_title": "Offer retention options before cancellation",
    "message": "✓ Retention option offered before cancellation",
    "confidence": 0.92,
    "details": "Agent offered discounted plan before processing cancellation. Customer declined, then cancellation was processed. Proper sequence followed.",
    "context": {
      "related_event_ids": ["evt-201"],
      "expected_action": "Offer retention before cancellation"
    }
  }]
}
```

## Example 3: Communication Warning

Input:
```
[10:00:22] AGENT: I found your account. Let me cancel that. | EVENT_ID: evt-150
```

Rule: "Express empathy for cancellation requests" (medium)

Output:
```json
{
  "event_id": "evt-150",
  "annotations": [{
    "status": "warning",
    "severity": "medium",
    "rule_id": 16,
    "rule_title": "Express empathy for cancellation requests",
    "message": "⚠ Could show more empathy",
    "confidence": 0.75,
    "details": "While not a violation, agent proceeded directly to action without acknowledging customer's decision with empathy.",
    "recommendation": "Consider: 'I'm sorry to hear you want to cancel. Let me help you with that.'",
    "context": {
      "expected_action": "Acknowledge with empathy before proceeding"
    }
  }]
}
```"""


def format_conversation_for_prompt(conversation_data: dict) -> dict:
    """
    Extract and format conversation data for prompt building.
    
    Args:
        conversation_data: Output from conversation processor
        
    Returns:
        Dictionary with timeline and metadata ready for prompt
    """
    return {
        "timeline": conversation_data.get("timeline", []),
        "metadata": conversation_data.get("metadata", {})
    }

