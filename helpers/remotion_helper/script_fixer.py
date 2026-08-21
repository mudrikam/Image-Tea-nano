"""Multi-Response Tool: Handles AI continuation requests when responses are too long.

This helper manages the scenario where an AI needs multiple turns to deliver all
SEARCH/REPLACE blocks due to token limits. The AI signals continuation by ending
its response with a special block:

    <<<CONTEXT
    <state to carry forward>
    ===
    <<<TOOL_CALL_RESPONSE

The system detects this and automatically calls the AI again with the accumulated
context, allowing the AI to "remember" previous fixes and continue applying more.
"""

import json
import re
from typing import Optional, Tuple
from PySide6.QtCore import QThread, Signal
from helpers.remotion_helper.script_fixer_helper import (
    SCRIPT_FIX_SYSTEM,
    apply_search_replace,
    build_continuation_prompt,
    extract_code_block,
    is_continuation_request,
    strip_continuation_block,
)


class ScriptFixWorker(QThread):
    """Worker that performs AI-assisted script fixing with multi-turn support."""
    finished = Signal(bool, str)  # (success, fixed_script or error)
    progress = Signal(str)        # Progress messages

    MAX_RETRIES = 3

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        service: str,
        model: str,
        script_content: str,
        error_msg: str,
        parent=None
    ):
        super().__init__(parent)
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.script_content = script_content
        self.error_msg = error_msg

    def _call_ai(self, prompt: str) -> str:
        """Call the configured AI provider with the given prompt."""
        import os
        import json
        svc = (self.service or '').lower()
        endpoint = (self.endpoint or '').strip()
        if endpoint:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            return CustomEndpointHelper.call_endpoint(
                self.api_key, endpoint, svc, self.model, prompt, timeout=120
            )
        elif svc == 'gemini':
            import google.genai as genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=[prompt]
            )
            return response.text
        elif svc in ('openai', 'openrouter', 'maia', 'blackbox'):
            from openai import OpenAI
            config_path = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.abspath(__file__)
                            )
                        )
                    )
                ),
                'configs', 'ai_config.json'
            )
            with open(config_path, 'r', encoding='utf-8') as f:
                ai_config = json.load(f)
            base_url = ai_config['provider_endpoints'][svc]
            client = OpenAI(api_key=self.api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            from helpers.ai_helper.openai_stream_helper import extract_response_text
            return extract_response_text(response)
        elif svc == 'groq':
            from groq import Groq
            client = Groq(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            from helpers.ai_helper.openai_stream_helper import extract_response_text
            return extract_response_text(response)
        else:
            raise ValueError(f"Unsupported service: {svc}")

    def run(self):
        """Main worker loop with multi-turn continuation support."""
        try:
            current_script = self.script_content
            accumulated_summary = ""
            attempt = 0

            while attempt < self.MAX_RETRIES:
                attempt += 1
                self.progress.emit(
                    f'Attempt {attempt}/{self.MAX_RETRIES}: Analyzing error and generating fix...'
                )

                # Build prompt (first attempt vs continuation)
                if attempt == 1:
                    prompt = (
                        SCRIPT_FIX_SYSTEM
                        + "\n\nSCRIPT TO FIX:\n" + current_script
                        + "\n\nERROR:\n" + self.error_msg
                    )
                else:
                    prompt = build_continuation_prompt(
                        original_script=current_script,
                        accumulated_changes=accumulated_summary,
                        user_error_msg=self.error_msg
                    )

                # Call AI
                print(f"[Vibe Video] Raw AI Request (Attempt {attempt}):\n{'-'*40}\n{prompt}\n{'-'*40}")
                ai_response = self._call_ai(prompt)

                print(f"[Vibe Video] Raw AI Response (Attempt {attempt}):\n{'-'*40}\n{ai_response}\n{'-'*40}")

                # Check if AI requests continuation (tool call response)
                is_continuation, context = is_continuation_request(ai_response)

                # Strip continuation block to get actual fix content
                fix_content = strip_continuation_block(ai_response)

                # Apply SEARCH/REPLACE blocks from this response
                patched = apply_search_replace(current_script, fix_content)

                if patched:
                    self.progress.emit(
                        f'Successfully applied code enhancements via blocks (Attempt {attempt}).'
                    )
                    # Update state for next turn if continuation requested
                    current_script = patched
                    accumulated_summary += (
                        f"\n[Attempt {attempt}] Applied {len(re.findall(r'<<<SEARCH', fix_content))} block(s).\n"
                    )

                    if is_continuation:
                        # AI wants to continue — loop again
                        self.progress.emit(
                            'AI requested continuation. Proceeding with additional fixes...'
                        )
                        # Append context to accumulated summary for next prompt
                        if context:
                            accumulated_summary += f"AI context: {context}\n"
                        # Continue to next iteration (re-call AI)
                        continue
                    else:
                        # No continuation needed — done
                        self.finished.emit(True, patched)
                        return
                else:
                    # No blocks applied — check if it was trying to patch
                    if ai_response and '<<<SEARCH' not in ai_response:
                        # try fallback (full code extraction)
                        code = extract_code_block(ai_response)
                        if code and ('import' in code or 'export' in code):
                            self.progress.emit(
                                f'Applied complete script overwrite (Fallback used in Attempt {attempt}).'
                            )
                            self.finished.emit(True, code)
                            return
                    else:
                        print(f'[Vibe Video] Attempt {attempt} provided SEARCH/REPLACE blocks but failed to apply. Skipping fallback.')

                    # No usable fix; retry if continuation requested, else fail
                    if is_continuation:
                        self.progress.emit(
                            'AI requested continuation to try an alternative fix approach...'
                        )
                        if context:
                            accumulated_summary += f"AI context: {context}\n"
                        continue

                    self.progress.emit(
                        f'No valid fix format applied in attempt {attempt}, retrying...'
                    )
                    # Loop automatically continues to next attempt

            # Max retries reached
            self.progress.emit(f'Fix failed after maximum retries ({self.MAX_RETRIES}).')
            self.finished.emit(False, '')
            self.finished.emit(False, 'Max retries exceeded')

        except Exception as e:
            self.progress.emit(f'Critical error during fix: {str(e)}')
            self.finished.emit(False, str(e))


# Re-export for backwards compatibility (old imports)
__all__ = ['ScriptFixWorker']
