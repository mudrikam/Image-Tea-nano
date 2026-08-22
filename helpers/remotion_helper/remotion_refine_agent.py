"""Stateful adapter around the original Remotion refinement protocol."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from helpers.remotion_helper.script_fixer_helper import (
    apply_search_replace,
    build_tool_aware_continuation_prompt,
    build_tool_aware_initial_prompt,
    execute_tool_call,
    extract_code_block,
    is_continuation_request,
    parse_tool_calls,
    strip_continuation_block,
)


@dataclass
class AgentStep:
    kind: str
    message: str
    turn: int = 0
    attempt: int = 0


@dataclass
class AgentResult:
    success: bool
    script: str
    message: str
    steps: list[AgentStep] = field(default_factory=list)


class RemotionRefineAgent:
    """Single-pass refinement session using the original tool-aware protocol."""

    MAX_TURNS = 10
    MAX_TOOL_CALLS = 12
    MAX_RESPONSE_CHARS = 180_000
    MAX_BLOCK_RETRIES = 1

    def __init__(self, call_ai, script: str, instruction: str, emit_step=None):
        self.call_ai = call_ai
        self.script = script
        self.instruction = instruction.strip()
        self.emit_step = emit_step
        self.steps: list[AgentStep] = []
        self._pending_failed: list[tuple[list[str], list[str]]] = []
        self._failed_retries = 0

    def run(self) -> AgentResult:
        if not self.script.strip():
            return self._finish(False, self.script, 'Current script is empty.')

        current_script = self.script
        applied_any_change = False
        carryover = ''
        collected_tool_results = []
        prompt = build_tool_aware_initial_prompt(current_script, self.instruction)

        for turn in range(1, self.MAX_TURNS + 1):
            self._step('turn', f'Turn {turn}: preparing refinement.', turn)
            summary = carryover
            carryover = ''
            continuation = False
            continuation_context = None

            self._step('request', f'Turn {turn}: contacting AI.', turn, 1)
            try:
                response = self.call_ai(prompt) or ''
            except Exception as exc:
                self._step('error', f'Turn {turn}: AI request failed: {exc}', turn, 1)
                return self._finish(False, current_script, f'AI request failed: {exc}')

            if len(response) > self.MAX_RESPONSE_CHARS:
                self._step('reject', f'Turn {turn}: AI response exceeded the safe size limit.', turn, 1)
                return self._finish(False, current_script, 'AI response exceeded the safe size limit.')

            tool_calls = parse_tool_calls(response) or self._parse_legacy_tool_calls(response)
            if tool_calls:
                tool_results = []
                for call in tool_calls[:self.MAX_TOOL_CALLS]:
                    name = call.get('tool') or call.get('name') if isinstance(call, dict) else ''
                    params = call.get('parameters') or call.get('arguments') or {} if isinstance(call, dict) else {}
                    result, summary = execute_tool_call(name, params, current_script, summary)
                    tool_results.append(f'[Tool: {name}]\n{result}')
                collected_tool_results.extend(tool_results)
                # Tool calls gather context; continue the session for follow-up edits.
                prompt = build_tool_aware_continuation_prompt(
                    current_script,
                    summary,
                    f'User instruction: {self.instruction}',
                    tool_results=collected_tool_results,
                    # Permit further inspection or an immediate patch.
                    after_tool_call=False,
                )
                self._step('tools', f'Turn {turn}: supplied {len(tool_results)} context block(s); continuing the same refinement.', turn, 1)
                continue

            # Preserve the full response so multiple SEARCH/REPLACE blocks and
            # out-of-fence CONTEXT metadata are not lost.
            continuation, continuation_context = is_continuation_request(response)
            content = strip_continuation_block(response)
            content = content if '<<<SEARCH' in content else (extract_code_block(content) or content)

            # Continuation-only responses are valid; request the next edit.
            if continuation and '<<<SEARCH' not in content:
                prompt = build_tool_aware_continuation_prompt(
                    current_script,
                    continuation_context or '',
                    f'User instruction: {self.instruction}',
                    tool_results=collected_tool_results,
                    after_tool_call=False,
                )
                self._step('continuation', f'Turn {turn}: continuation state received; requesting next edit.', turn, 1)
                continue

            patched = self._apply_atomic_search_replace(current_script, content)
            failed = list(getattr(self, '_pending_failed', []))

            if patched:
                current_script = patched
                applied_any_change = True
                self._step('apply', f'Turn {turn}: SEARCH/REPLACE applied.', turn, 1)

            if failed:
                self._pending_failed = []
                changes = '\n'.join(
                    '- intended change:\n' + '\n'.join('    ' + l for l in repl)
                    for repl, _search in failed[:10]
                )
                note = (
                    'Some SEARCH/REPLACE blocks were not applied because their SEARCH '
                    'anchors were not found in the current file (an earlier block may '
                    'have already changed that code). Re-issue corrected blocks for '
                    'these intended changes, anchoring on lines that exist in the '
                    'current file shown below:\n' + changes
                )
                if self._failed_retries < self.MAX_BLOCK_RETRIES:
                    # Re-issue corrected blocks once. Without this bound the loop
                    # would re-request forever (a conflict where an earlier block
                    # already changed a line a later block anchors on), burning
                    # every turn and exhausting the session.
                    self._failed_retries += 1
                    prompt = build_tool_aware_continuation_prompt(
                        current_script,
                        note,
                        f'User instruction: {self.instruction}',
                        tool_results=collected_tool_results,
                        after_tool_call=False,
                    )
                    self._step('protocol', f'Turn {turn}: some blocks did not match; requesting corrected patches.', turn, 1)
                    continue
                # Retries exhausted: stop instead of looping through every turn.
                if patched:
                    # Keep the changes that did apply; the preview/compiler is the
                    # source of truth for the rest.
                    self._step('protocol', f'Turn {turn}: some blocks still did not match; keeping applied changes.', turn, 1)
                else:
                    # Nothing applied this turn and the corrected blocks still did
                    # not match. End the pass rather than re-prompting forever.
                    self._step('protocol', f'Turn {turn}: blocks still did not match; stopping the pass.', turn, 1)
                    if applied_any_change:
                        self.script = current_script
                        return self._finish(True, current_script, 'Refinement completed with partial changes.')
                    return self._finish(False, current_script, 'AI returned SEARCH/REPLACE blocks that did not match the current file.')

            if not patched:
                fallback = self._full_file_fallback(response)
                if fallback:
                    # Preview/compiler validates full-file output; accept it here.
                    current_script = fallback
                    applied_any_change = True
                    self._step('apply', f'Turn {turn}: full-file candidate accepted; preview will validate it.', turn, 1)
                else:
                    # Prose planning text is not a failed edit; request the structured response.
                    prompt = build_tool_aware_continuation_prompt(
                        current_script,
                        (
                            f'Previous AI response (not yet an edit):\n{response}\n\n'
                            'The previous response contained no executable tool call or valid patch. '
                            'Continue the same instruction now.'
                        ),
                        f'User instruction: {self.instruction}',
                        tool_results=collected_tool_results,
                        after_tool_call=False,
                    )
                    self._step(
                        'protocol',
                        f'Turn {turn}: AI returned planning text; requesting the structured inspection or edit response.',
                        turn,
                        1,
                    )
                    continue

            self.script = current_script
            if continuation:
                carryover = continuation_context or ''
                prompt = build_tool_aware_continuation_prompt(
                    current_script,
                    carryover,
                    f'User instruction: {self.instruction}',
                    tool_results=collected_tool_results,
                    after_tool_call=True,
                )
                continue
            return self._finish(True, current_script, 'Refinement completed.')

        if applied_any_change:
            return self._finish(True, current_script, 'Refinement completed at the continuation limit.')
        return self._finish(False, current_script, 'AI did not return an executable tool call or SEARCH/REPLACE patch within the allowed refinement turns.')

    def _apply_atomic_search_replace(self, script, content):
        """Apply every SEARCH/REPLACE block whose anchor matches the source.

        Matching tolerates blank-line and trailing-whitespace differences. Blocks
        whose anchor is not found are recorded in ``self._pending_failed`` so the
        caller can request corrected patches; no-op blocks are skipped.
        """
        content = re.sub(r'^\s*```(?:typescript|tsx?|javascript)?\s*$', '', content, flags=re.MULTILINE | re.IGNORECASE)
        content = re.sub(r'^\s*```\s*$', '', content, flags=re.MULTILINE)
        blocks = self._parse_search_replace_blocks(content)
        if not blocks:
            return None

        candidate = script
        newline = '\r\n' if '\r\n' in script else '\n'
        applied_blocks = 0
        self._pending_failed = []
        for search_text, replace_text in blocks:
            norm_search = self._normalize_block(search_text)
            norm_replace = self._normalize_block(replace_text)
            if not norm_search:
                continue
            # Skip no-op blocks where search equals replace.
            if norm_search == norm_replace:
                continue
            matches = self._find_block_matches(candidate, norm_search)
            if not matches:
                replace_hint = [line for line in norm_replace if line.strip()][:3]
                search_hint = [line for line in norm_search if line.strip()][:3]
                if replace_hint or search_hint:
                    self._pending_failed.append((replace_hint, search_hint))
                continue
            source_lines = candidate.splitlines()
            prev_start = None
            for start, end in sorted(matches, reverse=True):
                # Skip overlapping spans when the anchor repeats.
                if prev_start is not None and start <= prev_start:
                    continue
                source_lines[start:end + 1] = norm_replace
                prev_start = start
            candidate = newline.join(source_lines)
            applied_blocks += 1
        return candidate if applied_blocks else None

    @staticmethod
    def _normalize_block(text):
        """Strip line-number metadata and trailing whitespace, then trim leading
        and trailing blank lines; keeps internal blank lines and indentation.
        """
        lines = (text or '').replace('\r\n', '\n').split('\n')
        lines = [RemotionRefineAgent._strip_line_metadata(line).rstrip() for line in lines]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    @staticmethod
    def _parse_search_replace_blocks(content):
        """Extract (search, replace) tuples tolerant of delimiter formatting."""
        pattern = re.compile(
            r'<<<[ \t]*SEARCH\b[^\n]*\r?\n'
            r'(.*?)'
            r'\r?\n=+(?:[ \t]*\r?\n|$)'
            r'(.*?)'
            r'(?:\r?\n>>>[ \t]*REPLACE\b|>>>[ \t]*REPLACE\b)',
            re.DOTALL | re.IGNORECASE,
        )
        return [(s, r) for s, r in pattern.findall(content or '')]

    def _find_block_matches(self, script, norm_search):
        """Return [(start, end)] spans matching ``norm_search``.

        Tries an exact line match first, then a blank-line-insensitive fallback.
        Inline comments (``// ...`` and ``/* ... */``, outside string literals)
        are ignored when comparing, so AI-authored SEARCH lines that include or
        omit trailing comments still match the source robustly.
        """
        src = [
            self._strip_comment(self._strip_line_metadata(line).rstrip())
            for line in script.splitlines()
        ]
        search = [self._strip_comment(line) for line in norm_search]
        n = len(search)
        if n:
            exact = [
                (i, i + n - 1)
                for i in range(len(src) - n + 1)
                if src[i:i + n] == search
            ]
            if exact:
                return exact
        if n == 1:
            # Single-line blocks: tolerate indentation/whitespace/comment
            # differences by matching the stripped line, applied to every match.
            target = search[0].strip()
            if not target:
                return []
            return [(i, i) for i, line in enumerate(src) if line.strip() == target]
        significant = [line.strip() for line in search if line.strip()]
        if len(significant) < 2:
            return []
        match = self._blank_insensitive_match(src, significant)
        return [match] if match is not None else []

    @staticmethod
    def _blank_insensitive_match(src, significant):
        """Find the first span whose non-blank lines equal ``significant`` in order."""
        sig_len = len(significant)
        for start in range(len(src)):
            if src[start].strip() != significant[0]:
                continue
            si = 0
            j = start
            while j < len(src) and si < sig_len:
                if src[j].strip() == '':
                    j += 1
                    continue
                if src[j].strip() == significant[si]:
                    si += 1
                    j += 1
                    continue
                break
            if si == sig_len:
                return start, j - 1
        return None

    @staticmethod
    def _line_metadata(line):
        match = re.match(r'^\s*(?:Line\s+)?(\d+):\s*(.*)$', line)
        return (int(match.group(1)), match.group(2)) if match else None

    @staticmethod
    def _strip_line_metadata(line):
        return re.sub(r'^\s*(?:Line\s+)?\d+:\s*', '', line)

    @staticmethod
    def _strip_comment(line):
        """Return ``line`` with trailing line/block comments removed.

        Comments inside string/template literals are preserved. Used only when
        matching SEARCH anchors against the source, never for the replacement,
        so AI-authored comments in either side do not break the match.
        """
        out = []
        in_str = None
        i = 0
        n = len(line)
        while i < n:
            c = line[i]
            if in_str:
                out.append(c)
                if c == '\\' and i + 1 < n:
                    out.append(line[i + 1])
                    i += 2
                    continue
                if c == in_str:
                    in_str = None
                i += 1
                continue
            if c in ('"', "'", '`'):
                in_str = c
                out.append(c)
                i += 1
                continue
            if c == '/' and i + 1 < n and line[i + 1] == '/':
                break
            if c == '/' and i + 1 < n and line[i + 1] == '*':
                i += 2
                while i < n - 1 and not (line[i] == '*' and line[i + 1] == '/'):
                    i += 1
                if i < n - 1:
                    i += 2
                continue
            out.append(c)
            i += 1
        return ''.join(out).rstrip()

    def _parse_legacy_tool_calls(self, response):
        if not response or 'tool_calls' not in response:
            return None
        return parse_tool_calls(response + '\n<<<TOOL_CALL_RESPONSE')

    def _full_file_fallback(self, response):
        if not response or '<<<SEARCH' in response:
            return ''
        match = re.search(r'```(?:tsx?|typescript|javascript)\s*\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match and ('import ' in match.group(1) or 'export ' in match.group(1)) else ''

    def _looks_like_renderable_remotion(self, script):
        return '<Composition' in script and ('from \'remotion\'' in script or 'from "remotion"' in script)

    def _validate_with_reason(self, script):
        if not script or 'export ' not in script:
            return False, 'missing export'
        if 'from \'remotion\'' not in script and 'from "remotion"' not in script:
            return False, 'missing Remotion import'
        delimiter_error = self._check_delimiters(script)
        if delimiter_error:
            return False, delimiter_error
        imports = self._imported_names(script)
        declarations = self._declared_names(script)
        missing_remotion = sorted(
            name for name in self._remotion_references(script)
            if name not in imports and name not in declarations
        )
        if missing_remotion:
            return False, 'missing Remotion imports: ' + ', '.join(missing_remotion)
        missing_constants = sorted(
            name for name in re.findall(r'\b(?:COLOR_[A-Z0-9_]+|FPS|DURATION)\b', script)
            if name not in declarations and name not in imports
        )
        if missing_constants:
            return False, 'undefined constants: ' + ', '.join(dict.fromkeys(missing_constants))
        missing_components = sorted(
            name for name in re.findall(r'<([A-Z][A-Za-z0-9_]*)\b', script)
            if name not in declarations and name not in imports and name not in {'React'}
        )
        if missing_components:
            return False, 'undefined JSX components: ' + ', '.join(dict.fromkeys(missing_components))
        return True, ''

    @staticmethod
    def _check_delimiters(source):
        """Check code delimiters without counting strings or comments.

        Remotion files commonly contain braces in CSS strings, template text,
        comments, and JSX attributes. Raw character counts therefore reject
        valid candidates. This lightweight scanner validates only syntax-like
        delimiters and enters template expressions for `${...}` blocks.
        """
        pairs = {')': '(', '}': '{', ']': '['}
        stack = []
        mode = 'code'
        quote = None
        escaped = False
        template_expression = []
        index = 0

        while index < len(source):
            char = source[index]
            next_char = source[index + 1] if index + 1 < len(source) else ''

            if mode == 'line_comment':
                if char in '\r\n':
                    mode = 'code'
                index += 1
                continue
            if mode == 'block_comment':
                if char == '*' and next_char == '/':
                    mode = 'code'
                    index += 2
                else:
                    index += 1
                continue
            if mode == 'string':
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote:
                    mode = 'code'
                    quote = None
                index += 1
                continue
            if mode == 'template':
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '`':
                    mode = 'code'
                elif char == '$' and next_char == '{':
                    stack.append(('{', True))
                    template_expression.append(len(stack))
                    mode = 'code'
                    index += 1
                index += 1
                continue

            if char == '/' and next_char == '/':
                mode = 'line_comment'
                index += 2
                continue
            if char == '/' and next_char == '*':
                mode = 'block_comment'
                index += 2
                continue
            if char in ('"', "'"):
                mode = 'string'
                quote = char
                escaped = False
                index += 1
                continue
            if char == '`':
                mode = 'template'
                escaped = False
                index += 1
                continue
            if char in '({[':
                stack.append((char, False))
            elif char in ')}]':
                expected = pairs[char]
                if not stack or stack[-1][0] != expected:
                    # JSX text may legally contain a literal closing delimiter
                    # (for example `>}`), so a lone closer is not enough to
                    # reject an otherwise valid Remotion source candidate.
                    index += 1
                    continue
                _opened, is_template_expression = stack.pop()
                if is_template_expression:
                    if template_expression:
                        template_expression.pop()
                    mode = 'template'
            index += 1

        if mode in ('string', 'template', 'block_comment'):
            return 'unterminated string, template literal, or comment'
        if stack:
            opened = stack[-1][0]
            closing = {'(': ')', '{': '}', '[': ']'}[opened]
            return f'unbalanced {opened}{closing}'
        return ''

    def _imported_names(self, script):
        names = set()
        for match in re.finditer(r'import\s+([^;]+?)\s+from\s+[\'\"]([^\'\"]+)[\'\"]', script, re.DOTALL):
            clause, _module = match.groups()
            clause = clause.strip()
            if clause.startswith('{'):
                names.update(
                    part.strip().split(' as ')[-1].strip()
                    for part in clause[1:-1].split(',')
                    if part.strip()
                )
            else:
                default = clause.split(',', 1)[0].strip()
                if default and re.match(r'^[A-Za-z_$][\w$]*$', default):
                    names.add(default)
                named = re.search(r'\{(.*?)\}', clause, re.DOTALL)
                if named:
                    names.update(
                        part.strip().split(' as ')[-1].strip()
                        for part in named.group(1).split(',')
                        if part.strip()
                    )
        return names

    def _declared_names(self, script):
        names = set(re.findall(r'\b(?:const|let|var|function|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)', script))
        names.update(re.findall(r'\b(?:const|let|var)\s*\{([^}]+)\}\s*=', script))
        for group in list(names):
            if ',' in group:
                names.discard(group)
                names.update(part.strip().split(':', 1)[0].strip() for part in group.split(','))
        return names

    def _remotion_references(self, script):
        known = {
            'AbsoluteFill', 'Audio', 'Composition', 'Easing', 'Img', 'Sequence', 'Video',
            'interpolate', 'random', 'spring', 'useCurrentFrame', 'useVideoConfig',
            'useCurrentScale',
        }
        return {name for name in known if re.search(r'\b' + re.escape(name) + r'\b', script)}

    def _step(self, kind, message, turn=0, attempt=0):
        step = AgentStep(kind, message, turn, attempt)
        self.steps.append(step)
        if self.emit_step:
            self.emit_step(step)

    def _finish(self, success, script, message):
        return AgentResult(success, script, message, self.steps)


__all__ = ['AgentResult', 'AgentStep', 'RemotionRefineAgent']
