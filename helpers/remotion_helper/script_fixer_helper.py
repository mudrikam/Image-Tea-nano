"""Script Fixer helper — extracted from vibe_code_actions_widget.py"""

import re
import json


_COMMON_RULES_AND_FORMAT = """
IMPORTANT: You are a strict background processing system, not a conversational agent or companion. NEVER output greetings, conversational text, summaries, or explanations. You MUST wrap your SEARCH/REPLACE blocks (and the CONTEXT block if continuation is required) in a single markdown code block like ```typescript\n<<<SEARCH...\n>>>REPLACE\n```. Do NOT provide any text outside the codeblock.

SEARCH/REPLACE FORMAT:
<<<SEARCH
exact lines from the original script that need to change (include full line, with indentation)
===
replacement lines (the corrected code)
>>>REPLACE

You can output MULTIPLE SEARCH/REPLACE blocks. Each block will be applied GLOBALLY (all matching occurrences) and in the order you provide.

RULES:
1. MINIMAL changes — only modify lines that are broken or requested to be updated
2. SEARCH must be EXACT (same whitespace/indentation as in original). If unsure, include more context lines.
3. Do NOT import Composition or registerRoot — handled externally
4. Do NOT use functions not in 'remotion' core. Valid: useCurrentFrame, useVideoConfig, interpolate, spring, Easing, Audio, Img, Video, AbsoluteFill, Sequence, useCurrentScale
5. interpolate() outputRange: numbers only, never strings
6. interpolate() inputRange: strictly increasing numbers
7. spring() returns number, not object
8. All inline styles: camelCase (backgroundColor not background-color)
9. If error says "X is not a function", remove that import and rewrite affected code
10. For FPS‑independent timing, use `fps` multiplier: e.g., `fps * 2` for 2 seconds

EXAMPLE 1 — Single change:
<<<SEARCH
import { useCurrentFrame, useVideoConfig, interpolate, spring, cameraZoom } from 'remotion';
===
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
>>>REPLACE

EXAMPLE 2 — Multiple changes (provide all blocks):
<<<SEARCH
  const camera = cameraZoom({ frame, fps, zoom: interpolate(frame, [0, 120], [1, 1.2]) });
===
  const zoom = interpolate(frame, [0, fps * 2], [1, 1.2], { extrapolateRight: 'clamp' });
>>>REPLACE

<<<SEARCH
  style={{ background-color: 'white' }}
===
  style={{ backgroundColor: 'white' }}
>>>REPLACE

TIPS:
- If the same pattern appears multiple times, include only ONE SEARCH block; the system will replace ALL occurrences globally.
- If different patterns need different fixes, output SEPARATE blocks for each pattern.
- Ensure each SEARCH block uniquely identifies the code you want to change (include enough surrounding lines if needed).

LONG FIXES / CONTINUATION:
If your required fixes are too long and you risk hitting the token limit, you can request to continue your fixes in the next turn. 
To prevent infinite loops, you MUST declare your total planned steps and outline them. End your response EXACTLY with this block:
<<<CONTEXT
[Step X of Y]
PLAN:
- Step 1: <describe task>
- Step 2: <describe task>
- Step ...
COMPLETED: <brief description of what you fixed so far>
NEXT: <what you plan to fix in the next turn>
===
<<<TOOL_CALL_RESPONSE

CRITICAL RULES FOR CONTINUATION:
1. ONLY append the <<<CONTEXT block if you ACTUALLY need another turn (i.e., X is less than Y). 
2. If you use <<<TOOL_CALL_RESPONSE, you MUST STOP GENERATING TEXT IMMEDIATELY! Do NOT simulate the next turn, do NOT output more SEARCH blocks after it. Wait for the system callback.
3. If you are on the FINAL planned step (X equals Y) or if the whole instruction is completed, DO NOT output the <<<CONTEXT block! Just end your message normally after the >>>REPLACE block so the loop can stop."""

SCRIPT_REFINE_SYSTEM = f"""You are a Remotion TypeScript/React code refiner. The user gives you an existing script and a refinement instruction. Apply the change using SEARCH/REPLACE blocks.
{_COMMON_RULES_AND_FORMAT}"""

SCRIPT_FIX_SYSTEM = f"""You are a Remotion TypeScript/React error fixer. Fix the script based on the error given.
{_COMMON_RULES_AND_FORMAT}"""


def apply_search_replace(original: str, ai_response: str) -> str:
    """Apply SEARCH/REPLACE blocks from AI response to original script.

    Robust, model-agnostic parser:
    - Accepts multiple blocks in one response
    - Global replacement: each block replaces ALL matching occurrences
    - Whole-line matching: only matches complete lines (no partial line replaces)
    - Whitespace-tolerant: leading/trailing whitespace ignored for matching
    - Empty replacement = delete matching lines
    - Handles markdown code fences, missing newlines before closing tag

    Args:
        original: The original script content
        ai_response: AI's response containing SEARCH/REPLACE blocks

    Returns:
        Modified script if changes applied, else empty string.
    """
    # Preprocess: strip markdown code fences if AI wrapped response
    cleaned = ai_response.strip()
    cleaned = re.sub(r'^```+\w*\s*\n?', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```+\s*$', '', cleaned, flags=re.MULTILINE)

    # Parse SEARCH/REPLACE blocks.
    blocks = re.findall(
        r'<<<SEARCH\s*\n(.*?)\n===\s*\n(.*?)(?:\n>>>REPLACE|>>>REPLACE)',
        cleaned, re.DOTALL
    )
    if not blocks:
        return ''

    newline = '\r\n' if '\r\n' in original else '\n'
    result = original
    total_applied = 0
    block_num = 0

    for search_text, replace_text in blocks:
        block_num += 1
        search_clean = search_text.rstrip()
        replace_clean = replace_text.rstrip()

        if not search_clean:
            print(f'[Vibe Video] Block {block_num}: empty SEARCH, skipping')
            continue

        # Line-based global matching (safe, whole-line only)
        search_lines = search_clean.splitlines()
        replace_lines = replace_clean.splitlines()  # empty list -> deletion
        search_stripped = [line.strip() for line in search_lines]

        result_lines = result.splitlines()
        i = 0
        local_applied = 0

        while i <= len(result_lines) - len(search_lines):
            window = [result_lines[i + j].strip() for j in range(len(search_lines))]
            if window == search_stripped:
                # Replace the block
                result_lines[i:i + len(search_lines)] = replace_lines
                local_applied += 1
                # Advance cursor appropriately
                if replace_lines:
                    i += len(replace_lines)
                # else: deletion — stay at same index (next line shifts in)
            else:
                i += 1

        if local_applied > 0:
            total_applied += local_applied
            result = newline.join(result_lines)
            if len(replace_lines) == 0:
                print(f'[Vibe Video] Block {block_num}: deleted ({local_applied} occurrence(s))')
            else:
                print(f'[Vibe Video] Block {block_num}: replaced ({local_applied} occurrence(s))')
        else:
            print(f'[Vibe Video] Block {block_num}: no match found')

    if total_applied == 0:
        print('[Vibe Video] No SEARCH/REPLACE blocks matched')
        return ''

    # Preserve trailing newline if original had one
    if original.endswith('\r\n') and not result.endswith('\r\n'):
        result += '\r\n'
    elif original.endswith('\n') and not result.endswith('\n'):
        result += '\n'

    print(f'[Vibe Video] Total: {total_applied} change(s) applied across {block_num} block(s)')
    return result


def is_continuation_request(ai_response: str) -> tuple[bool, str | None]:
    """Detect if AI response includes a continuation request with context.

    Expected format (BOTH markers together):
        <<<CONTEXT
        <state to carry forward>
        ===
        <<<TOOL_CALL_RESPONSE

    Returns:
        (is_continuation, context_string)
    """
    if not ai_response:
        return False, None
        
    cleaned = ai_response.strip()
    # Both markers MUST be present together
    pattern = r'<<<CONTEXT\s*\n(.*?)\n===\s*\n<<<TOOL_CALL_RESPONSE\s*$'
    match = re.search(pattern, cleaned, re.DOTALL)
    if match:
        return True, match.group(1).rstrip()
    return False, None


def strip_continuation_block(ai_response: str) -> str:
    """Remove the continuation request block from AI response, keeping only actual fix content."""
    if not ai_response:
        return ""
        
    cleaned = ai_response.strip()
    result = re.sub(
        r'\n?<<<CONTEXT\s*\n.*?\n===\s*\n<<<TOOL_CALL_RESPONSE.*$',
        '',
        cleaned,
        flags=re.DOTALL
    )
    return result.strip()


def build_continuation_prompt(original_script: str, accumulated_changes: str, user_error_msg: str) -> str:
    """Build prompt for continuation call, including current script state and history."""
    prompt = f"""You are continuing a previous script fix session.
{_COMMON_RULES_AND_FORMAT}

CURRENT SCRIPT STATE:
```typescript
{original_script}
```

YOUR PREVIOUS PLAN & NOTES (Read this carefully to know your current step and what to do NEXT):
{accumulated_changes if accumulated_changes else '(none yet)'}

ORIGINAL ERROR/INSTRUCTION:
{user_error_msg}

TASK:
Analyze the current script and the original instruction/error. Execute your NEXT planned step.
You MUST output at least one <<<SEARCH ... === ... >>>REPLACE block containing the actual code changes for this step. Do NOT just reply with a CONTEXT block.
You MUST use the exact SAME SEARCH/REPLACE block format shown in the rules above. NEVER provide the full script as your answer. Only include blocks for code segments that still need fixing.

CRITICAL ROLE ENFORCEMENT:
You are a script modification engine. Do NOT output a final conversational wrap-up like "I have updated the script", "Here is the code", "Task is complete". Simply provide the SEARCH/REPLACE blocks. When the task is finished, emit NOTHING ELSE.

If you need to make many changes and need another turn, you can request continuation using the EXACT block format below at the end of your response:
<<<CONTEXT
[Step X of Y]
PLAN:
- Step 1: <describe task>
- Step 2: <describe task>
- Step ...
COMPLETED: <brief description of what you fixed so far>
NEXT: <what you plan to fix in the next turn>
===
<<<TOOL_CALL_RESPONSE

CRITICAL: 
- STOP GENERATING immediately after <<<TOOL_CALL_RESPONSE! Do NOT simulate the next turn yourself and do NOT output more code after this block.
- If you have reached the final step (Step Y of Y) and the fix is complete, do NOT include the <<<CONTEXT ... <<<TOOL_CALL_RESPONSE block at all. Simply output your last SEARCH/REPLACE blocks and finish your response."""
    return prompt


def extract_code_block(text: str) -> str:
    """Extract first code block (markdown ```) from text. Only return content from codeblock if present, else empty string."""
    match = re.search(r'```(?:\w*\n)?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ''


# ============================================================================
# TOOL-CALL INFRASTRUCTURE FOR TOKEN-EFFICIENT REFINEMENT
# ============================================================================

# JSON Schema definitions for tools (OpenAI/Gemini compatible format)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_lines",
            "description": "Read a specific range of lines from the script (maximum 150 lines per request). Use when you need to examine a specific code section.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed, inclusive)"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-indexed, inclusive). The range will be capped at 150 lines maximum."
                    }
                },
                "required": ["start_line", "end_line"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_function",
            "description": "Extract a specific function or component definition by name. Use to focus on a particular function's implementation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function or component to read (e.g., 'render', 'MyComponent')"
                    }
                },
                "required": ["function_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_imports",
            "description": "Get all import statements from the script. Use to check available modules and dependencies.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compact_session",
            "description": "Summarize accumulated context to reduce token usage for subsequent turns. Call when conversation history grows long. Provide a summary_prompt describing what to condense.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary_prompt": {
                        "type": "string",
                        "description": "Instructions for how to summarize the accumulated context (e.g., 'Summarize completed changes and remaining tasks')"
                    }
                },
                "required": ["summary_prompt"]
            }
        }
    }
]

# Tool call marker that AI appends to request tool use
TOOL_CALL_MARKER = "<<<TOOL_CALL_RESPONSE"

# System instructions for tool usage (appended to prompts when tools are supported)
TOOL_USAGE_INSTRUCTIONS = """

TOOL USAGE FOR CONTEXT RETRIEVAL:
You can request specific code sections using tool calls before making SEARCH/REPLACE changes. This helps you get exact context without receiving the full script every turn.

TOOLS AVAILABLE:
1. read_lines(start_line, end_line) — Get lines N through M (1-indexed). Each request is limited to 150 lines maximum. Use multiple focused requests if you need more context.
2. read_function(function_name) — Extract a function/component definition by name.
3. read_imports() — Get all import statements.
4. compact_session(summary_prompt) — Condense accumulated context to save tokens; you provide how to summarize.

BEST PRACTICES FOR TOOL USAGE:
- Keep read_lines requests to 100-150 lines maximum per call. If you need more context, make multiple plan for the next request.
- Request specific regions rather than large swaths. Use get_script_overview to understand structure first.
- Before requesting a large range, consider if read_function() would be more efficient for a specific component.
- If you find yourself needing many line ranges, use compact_session to summarize and reset context.

HOW TO CALL TOOLS:
At the end of your response, append a JSON object wrapped in ```json``` fences, followed by <<<TOOL_CALL_RESPONSE on its own line:

```json
{
  "tool_calls": [
    {"tool": "read_lines", "parameters": {"start_line": 1, "end_line": 100}},
    {"tool": "read_function", "parameters": {"function_name": "render"}}
  ]
}
<<<TOOL_CALL_RESPONSE
```

The system will execute these tools and send you the results in the next turn. Then you can proceed with SEARCH/REPLACE.
IMPORTANT: If you call tools, DO NOT output SEARCH/REPLACE blocks in the same response. Wait for tool results first.
"""


def get_script_overview(script_content: str, max_lines: int = 30) -> str:
    """Generate a compressed overview of the script (function list + import summary).
    
    Used to send a minimal initial context instead of the full script, saving tokens.
    """
    lines = script_content.splitlines()
    
    # Collect import lines
    imports = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            imports.append(line)
    
    # Collect function/component definitions
    definitions = []
    pattern = r'^(?:export\s+)?(?:const|function)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:=|\(|<)'
    for i, line in enumerate(lines, 1):
        m = re.match(pattern, line.strip())
        if m:
            definitions.append(f"  Line {i}: {m.group(1)}")
    
    # Collect key variable declarations that might hold strings (like text color)
    key_vars = []
    var_pattern = r'^\s*(?:const|let)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*='
    for i, line in enumerate(lines, 1):
        m = re.match(var_pattern, line.strip())
        if m:
            var_name = m.group(1)
            # Only include variables that look like style-related or text-related
            style_related = any(keyword in var_name.lower() for keyword in ['color', 'text', 'style', 'bg', 'background', 'fill', 'stroke'])
            if style_related and i <= 200:  # Only first 200 lines to avoid noise
                key_vars.append(f"  Line {i}: {var_name} = {line.split('=')[1].strip()[:50]}")
    
    overview_parts = []
    overview_parts.append(f"Script Overview ({len(lines)} lines total):")
    
    if imports:
        overview_parts.append(f"\nImports ({len(imports)} lines):")
        for imp in imports[:10]:  # limit to first 10
            overview_parts.append(f"  {imp}")
        if len(imports) > 10:
            overview_parts.append(f"  ... and {len(imports) - 10} more imports")
    
    if definitions:
        overview_parts.append(f"\nFunction/Component definitions ({len(definitions)}):")
        for d in definitions[:15]:
            overview_parts.append(f"  {d}")
        if len(definitions) > 15:
            overview_parts.append(f"  ... and {len(definitions) - 15} more")
    
    if key_vars:
        overview_parts.append(f"\nKey style/text variables:")
        for v in key_vars[:10]:
            overview_parts.append(f"  {v}")
    
    return '\n'.join(overview_parts)


def parse_tool_calls(ai_response: str) -> list[dict] | None:
    """Extract tool calls from AI response.
    
    Expected format (marker mandatory at end):
    ```json
    { "tool_calls": [...] }
    <<<TOOL_CALL_RESPONSE
    ```
    The closing ``` fence is optional; any text before the JSON block is ignored.
    Returns list of tool call dicts or None if no valid calls found.
    """
    if not ai_response:
        return None
    
    cleaned = ai_response.strip()
    
    # Must end with the marker
    if not re.search(r'\n?<<<TOOL_CALL_RESPONSE\s*$', cleaned):
        return None
    
    # Remove marker
    without_marker = re.sub(r'\n?<<<TOOL_CALL_RESPONSE\s*$', '', cleaned).strip()
    
    # Try to extract JSON from inside ```json ... ``` fences (if present)
    json_match = re.search(r'```json\s*(.*?)\s*```', without_marker, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # No fences — find outermost JSON object by locating first '{' and last '}'
        start = without_marker.find('{')
        end = without_marker.rfind('}')
        if start == -1 or end == -1 or start > end:
            return None
        json_str = without_marker[start:end+1].strip()
    
    if not json_str:
        return None
    
    try:
        data = json.loads(json_str)
        tool_calls = data.get('tool_calls', [])
        if isinstance(tool_calls, list) and tool_calls:
            return tool_calls
    except json.JSONDecodeError as e:
        print(f"[Vibe Video] JSON parse error in tool calls: {e}")
    
    return None


def execute_tool_call(tool_name: str, params: dict, full_script: str, accumulated_context: str = "") -> tuple[str, str]:
    """Execute a single tool call and return (result_text, updated_context).
    
    Args:
        tool_name: Name of the tool to execute
        params: Parameters for the tool
        full_script: The complete current script content
        accumulated_context: Existing accumulated context (for compact_session updates)
    
    Returns:
        (tool_result_text, new_accumulated_context)
    """
    lines = full_script.splitlines()
    result = ""
    
    if tool_name == "read_lines":
        req_start = params.get("start_line", 1)
        req_end = params.get("end_line", req_start)
        total_lines = len(lines)

        # Validate types
        try:
            req_start = int(req_start)
            req_end = int(req_end)
        except (ValueError, TypeError):
            result = f"[Error] Invalid line numbers: start={req_start}, end={req_end}"
            return result, accumulated_context

        # Enforce maximum range limit (150 lines) to encourage focused requests
        MAX_LINES_PER_REQUEST = 150
        requested_count = req_end - req_start + 1
        if requested_count > MAX_LINES_PER_REQUEST:
            result = (f"[Warning] Requested {requested_count} lines ({req_start}-{req_end}) exceeds maximum "
                      f"of {MAX_LINES_PER_REQUEST}. Reducing to {MAX_LINES_PER_REQUEST} lines.")
            req_end = req_start + MAX_LINES_PER_REQUEST - 1

        # Completely out of range?
        if req_start > total_lines or req_start < 1:
            result = (f"[Warning] Requested lines {req_start}-{req_end} are outside script bounds "
                      f"(script has {total_lines} lines). Returning last 50 lines instead.")
            # Give last 50 lines as fallback
            start = max(1, total_lines - 49)
            end = total_lines
            selected = lines[start-1:end]
            result += "\n" + '\n'.join(selected)
            return result, accumulated_context

        # Normal clamping
        start = max(1, min(req_start, total_lines))
        end = max(start, min(req_end, total_lines))
        selected = lines[start-1:end]
        result = f"Lines {start}-{end} (of {total_lines}):\n" + '\n'.join(selected)

        # Note adjustments if any
        if start != req_start or end != req_end or requested_count > MAX_LINES_PER_REQUEST:
            result += f"\n[Note: requested {req_start}-{req_end}, adjusted to {start}-{end}]"

        return result, accumulated_context
        
    elif tool_name == "read_function":
        func_name = params.get("function_name", "").strip()
        if not func_name:
            result = "Error: function_name parameter required."
            return result, accumulated_context
        
        # Find function start: match `function Name(` or `const Name =` (including optional export)
        patterns = [
            rf'^(?:export\s+)?function\s+{re.escape(func_name)}\s*\(',
            rf'^(?:export\s+)?const\s+{re.escape(func_name)}\s*=',
            rf'^(?:export\s+)?let\s+{re.escape(func_name)}\s*=',
            rf'^(?:export\s+)?class\s+{re.escape(func_name)}\b',
        ]
        start_idx = None
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            for pat in patterns:
                if re.match(pat, line_stripped):
                    start_idx = i
                    break
            if start_idx is not None:
                break
        
        if start_idx is None:
            result = f"Function '{func_name}' not found."
            return result, accumulated_context
        
        # Find end using brace counting (handles multi-line bodies)
        brace_count = 0
        end_idx = None
        for i in range(start_idx, len(lines)):
            for ch in lines[i]:
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
            if brace_count == 0 and i > start_idx:
                end_idx = i + 1  # include the closing line
                break
        if end_idx is None:
            end_idx = len(lines)
        
        selected = lines[start_idx:end_idx]
        result = f"Function '{func_name}' (lines {start_idx+1}-{end_idx}):\n" + '\n'.join(selected)
        return result, accumulated_context
        

    elif tool_name == "read_imports":
        imports = [line for line in lines if line.strip().startswith(('import ', 'from '))]
        result = "Import statements:\n" + '\n'.join(imports) if imports else "No imports found."
        
    elif tool_name == "compact_session":
        summary_prompt = params.get("summary_prompt", "Summarize current progress")
        # We don't call AI here — that would be recursive. Instead, just note the request.
        # The AI will handle summarization on its next turn using this prompt.
        result = f"[compact_session requested: {summary_prompt}]"
        # Update accumulated_context with note that compaction was requested
        # The actual compaction will be done by AI on subsequent turn using the summary_prompt as guidance
        return result, accumulated_context + f"\n[Session compaction requested: {summary_prompt}]"
    
    else:
        result = f"Unknown tool: {tool_name}"
    
    return result, accumulated_context


def build_tool_aware_initial_prompt(script_content: str, instruction: str) -> str:
    """Build initial prompt for refinement using tool-aware instructions and compressed script."""
    overview = get_script_overview(script_content)
    prompt = f"""You are a Remotion TypeScript/React code refiner with access to tools for retrieving code context.
{_COMMON_RULES_AND_FORMAT}
{TOOL_USAGE_INSTRUCTIONS}

CURRENT SCRIPT OVERVIEW (full script NOT provided — use tools to read sections):
{overview}

USER INSTRUCTION:
{instruction}

TASK:
Examine the script overview to understand structure. Use the available tools (read_lines, read_function, read_imports) to retrieve the code sections you need. After receiving tool results, output your SEARCH/REPLACE blocks to apply the changes.

IMPORTANT:
- Use tools proactively if the instruction is vague; do not guess code.
- Output SEARCH/REPLACE blocks wrapped in ```typescript``` fences.
- If you need another turn, use the CONTEXT/TOOL_CALL_RESPONSE block at the end."""
    return prompt


def build_tool_aware_continuation_prompt(original_script: str, accumulated_changes: str, user_error_msg: str, tool_results: list[str] = None, after_tool_call: bool = False) -> str:
    """Build continuation prompt without full script — AI must use tools to read sections.
    
    Args:
        after_tool_call: If True, AI has already received tool results and MUST NOT request more tools.
    """
    overview = get_script_overview(original_script)
    tool_results_section = ""
    if tool_results:
        tool_results_section = "\n\nTOOL RESULTS (from your previous context requests):\n"
        for i, res in enumerate(tool_results, 1):
            tool_results_section += f"--- Tool Result {i} ---\n{res}\n"
    
    # Determine task instructions based on state
    if after_tool_call:
        task_instructions = """TASK:
You have received the requested code sections below. DO NOT request any more tools.
USE THE PROVIDED CODE SECTIONS to write your SEARCH/REPLACE blocks. Ensure EXACT line matching including indentation.

If you need another turn after this, use the CONTEXT/TOOL_CALL_RESPONSE block.

CRITICAL:
- DO NOT call any more tools in this turn. You already have the context you requested.
- SEARCH blocks MUST match the provided code EXACTLY (including whitespace).
- Output SEARCH/REPLACE blocks wrapped in ```typescript``` code fences.
- If this is your final step, just end after SEARCH/REPLACE without any CONTEXT block."""
    else:
        task_instructions = """TASK:
Execute your NEXT planned step. Use tools (read_lines, read_function, read_imports) to retrieve any code sections you need. After receiving tool results, output your SEARCH/REPLACE blocks. If you need another turn after this, use the CONTEXT/TOOL_CALL_RESPONSE block.

CRITICAL:
- If you call tools, DO NOT output SEARCH/REPLACE in this same response — wait for tool results.
- When ready to apply changes, output SEARCH/REPLACE blocks wrapped in ```typescript``` code fences.
- If this is your final step, just end after SEARCH/REPLACE without any CONTEXT block."""
    
    prompt = f"""You are continuing a previous script refinement session (with tool support).
{_COMMON_RULES_AND_FORMAT}
{TOOL_USAGE_INSTRUCTIONS}

CURRENT SCRIPT OVERVIEW (full script NOT included — use tools to read any section):
{overview}

YOUR PREVIOUS PLAN & NOTES:
{accumulated_changes if accumulated_changes else '(none yet)'}

{tool_results_section}
ORIGINAL INSTRUCTION:
{user_error_msg}

{task_instructions}
"""
    return prompt
