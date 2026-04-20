"""Script Fixer helper — extracted from vibe_code_actions_widget.py"""

import re


_COMMON_RULES_AND_FORMAT = """
IMPORTANT: You are a strict background processing system, not a conversational agent or companion. NEVER output greetings, conversational text, summaries, or explanations. Output ONLY raw SEARCH/REPLACE blocks (and the CONTEXT block if continuation is required). Do NOT wrap in markdown code fences (```) or any other formatting.

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

    Expected format at end of response:
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
    """Extract first code block (markdown ```) from text."""
    match = re.search(r'```(?:\w*\n)?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    stripped = text.strip()
    if 'import' in stripped and ('React' in stripped or 'remotion' in stripped):
        return stripped
    return stripped
