# Auto Flow Batcher — Implementation Plan & Progress Log

## Project Context
Rebuilding "Auto Flow Batcher" Chrome extension from scratch:
- **Keep** all GUI (HTML/CSS) intact
- **Clear** all old logic from JS files and rebuild from first principles
- **Target**: Google Flow (https://labs.google/fx/tools/flow) — Slate.js-based editor
- **Goal**: Reliable multi-prompt automation WITHOUT fallbacks — single robust strategy

---

## Phase 1: Foundation & GUI — ✅ COMPLETE

### Manifest (v3)
- ✅ `manifest.json`: Permissions (`activeTab`, `clipboardWrite`, `sidePanel`), host permissions for Flow URL
- ✅ Icons defined at root `icons/` field + `action.default_icon` for toolbar visibility
- ✅ Side panel entrypoint configured

### Sidepanel UI — ✅ Complete
- ✅ Landing page: Logo (128×128), branding text "Desainia Studio", "Open Flow" button
- ✅ Start interface: #mainInterface with log area, manual textarea,Start Batch button
- ✅ Start button now has SVG play icon (inline)
- ✅ Badge updated: "V3 API" → "Desainia Studio"
- ✅ Custom scrollbar styling for `.log-area` and `textarea.manual-input` (consistent look)
- ✅ Landing page shown by default; switches to #mainInterface when on Flow

### Icons
- ✅ Icons present: `logo_16.png`, `logo_32.png`, `logo_48.png`, `logo_128.png`, `logo_256.png`
- ✅ Thumbs.db removed (was causing load errors)

---

## Phase 2: Content Script Core — ✅ COMPLETE (MULTI-PROMPT FIXED)

### Editor Detection — ✅ Robust
- ✅ Slate editor: `[data-slate-editor="true"]`
- ✅ Fallback: `[role="textbox"][contenteditable="true"]`
- ✅ Legacy fallback: `.sc-522e4d41-5.gihCJr`
- ✅ Polling up to 40×150ms for editor availability

### Paragraph Node Handling — ✅ Stable
- ✅ Target: `p[data-slate-node="element"]` or `p`
- ✅ Fresh paragraph re-acquired before dispatch (avoids stale references after React re-render)

### Selection Strategy — ✅ SELECT-ALL + INSERT (NO CLEAR)
- ✅ **No delete/clear commands** — avoids Slate state corruption
- ✅ Select all via `Range.selectNodeContents(pEl)` (no collapse — full selection)
- ✅ Re-acquire fresh paragraph, re-apply selection before dispatch

### Event Dispatch — ✅ Single beforeinput
- ✅ `InputEvent` with `inputType: 'insertText'`, `data: <prompt>`
- ✅ Dispatched on **fresh paragraph element** (not editor div)
- ✅ `canceled=true` is expected; Slate processes it anyway
- ✅ No `input`/`keydown`/`paste` fallbacks — one strategy only

### Verification — ✅ Accurate
- ✅ Read `textContent.trim()` from fresh paragraph after 1500ms delay
- ✅ Compare against expected prompt

### Content Script Loader — ✅ Auto-Inject
- ✅ If content script missing on Flow tab, sidepanel triggers injection automatically

---

## Phase 3: Sidepanel Logic — ✅ COMPLETE

### Message Passing
- ✅ `PING` ↔ content script (health check)
- ✅ `PROCESS_PROMPT` → triggers `processPrompt(prompt)`

### Logging
- ✅ Logs forwarded from content script to sidepanel via `LOG_FROM_CONTENT`
- ✅ Auto-clear logs when sidepanel opens
- ✅ Auto-clear logs on navigation to Flow URL (keeps logs relevant)

### Flow URL Detection — ✅ Dynamic
- ✅ Checks `window.location.href` on load
- ✅ Monitors `tab_update` (navigation)
- ✅ Monitors `tabactivation` (tab switch)
- ✅ Matches pattern: `https://labs.google/fx/tools/flow*`
- ✅ Switches UI: landing page ⇄ #mainInterface accordingly

### Open Flow Button
- ✅ Creates new tab with `https://labs.google/fx/tools/flow`
- ✅ Also checks existing tabs and switches to Flow if already open

---

## Phase 4: Known Issues & Resolutions

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Extension icons not showing | Missing `icons` field in manifest (MV3) | Added root `icons` + `action.default_icon` |
| Badge still "V3 API" | Hardcoded in sidepanel badge element | Updated text to "Desainia Studio" |
| Content script not found on Flow | Timing: Flow loads after extension | Auto-inject if `window.afbReady` missing |
| Prompt 1 succeeds; Prompt 2+ append text | Used `range.collapse(false)` — zero-length selection at end | Removed collapse; full selection kept |
| Prompt 2+ fail ("Paragraph not found") | Stale DOM ref after React re-render | Re-acquire fresh `pEl` before every dispatch |
| Slate state corruption after clear | Used `execCommand('delete')` | Eliminated clear entirely; Select-All + Insert replaces |

**Current Status (2026-04-23 13:09):**
- ✅ Multi-prompt now replaces text correctly (no more appending)
- ⚠️ **Known behavior**: `beforeinput.canceled=true` — this is normal; Slate processes despite cancellation
- ✅ Tested: 4 prompts in sequence ALL replaced correctly (no accumulation)

---

## Phase 5: Next Steps / TODO

### Short-term (Polish)
- [ ] Add option to toggle **auto-open Flow** on extension click (setting in sidepanel)
- [ ] Capture Flow's generative output count (optional readout in log)
- [ ] Error boundary: if paragraph structure changes (different Slate version), retry with alternative selector
- [ ] Configurable delay timings (currently hardcoded: 300ms, 200ms, 1500ms)
- [ ] Manual prompt input send button (already has textarea — wire up "Send" hotkey Ctrl+Enter)

### Medium-term (Reliability)
- [ ] Stability polling: confirm paragraph text stable before selection (read same value 3× consecutive checks)
- [ ] Fallback strategy: if `beforeinput` fails (no text after 2s), try keyboard simulation `navigator.clipboard.writeText` + `document.execCommand('paste')` **only as fallback** (not primary)
- [ ] Multi-line detection: if Flow switches to multi-paragraph mode, batch across all `<p>` nodes

### Long-term (Features)
- [ ] Batch prompt queue UI (upload text file, CSV, or paste list)
- [ ] Prompt history / templates dropdown
- [ ] Flow output capture & copy-to-clipboard automation
- [ ] Statistics: success rate, average latency
- [ ] Settings page (persist via `chrome.storage`)

---

## Architecture Quick-Reference

### Content Script Strategy (SINGLE SOURCE OF TRUTH)
```
Editor → Paragraph → Selection (all) → beforeinput(insertText) → Verify
         ↑
   Re-acquired fresh before dispatch
```

### Timing Constants (tunable)
- Editor polling: 40 × 150ms = 6s max
- Focus delay: 300ms
- Selection delay: 200ms
- Render wait: 1500ms

### Slate DOM Structure Target
```html
<p data-slate-node="element">
  <span data-slate-node="text">
    <span data-slate-leaf="true">
      <span data-slate-string="true">TEXT_HERE</span>
    </span>
  </span>
</p>
```

Placeholder:
```html
<span data-slate-placeholder="true">What do you want to create?</span>
```

---

## File Inventory

### Modified Files
- `manifest.json` — MV3, icons, permissions, sidePanel
- `sidepanel.html` — Landing page, badge, start button icon, scrollbar CSS
- `sidepanel.js` — URL detection, UI switching, log forwarding, auto-clear
- `content.js` — Full rewrite vPURE → vMULTI-RELIABLE → vSELECT-ALL-INSERT

### Assets (static/)
- `icons/logo_16.png`
- `icons/logo_32.png`
- `icons/logo_48.png`
- `icons/logo_128.png`
- `icons/logo_256.png`

---

## Development Log (Chronological)

1. **Initial cleanup**: Stripped all old JS logic, kept HTML/CSS skeleton
2. **Icons & Badge**: Added manifest icons, changed badge text
3. **Landing page**: Added branding + Open Flow button
4. **URL detection**: Dynamic UI switching based on tab URL
5. **Content script v1**: Simple clear+insert → failed due to Slate corruption
6. **Content script v2**: Keyboard backspace clear → still flaky
7. **Content script v3**: Stable paragraph wait + fresh refs → prompt 1 OK, prompt 2+ fail (stale refs)
8. **Content script v4 (current)**: Select-All + Insert (NO delete), proper full selection → multi-prompt ✅

**Test result log** (latest):
- 4 prompts: all replaced correctly, no accumulation
- `beforeinput.canceled=true` every time — normal


---

## Checklist: Ready for Production?
- [x] GUI fully intact and styled
- [x] Icons display in Chrome toolbar
- [x] Landing page functional
- [x] URL detection works on navigation & tab switch
- [x] Multi-prompt automation reliable (no text accumulation)
- [x] No reliance on deprecated APIs
- [x] Content script auto-injects when needed
- [ ] Manual testing across different Flow editor states (empty, placeholder, multi-line)
- [ ] Performance profiling (latency per prompt)
- [ ] Edge case: Flow in iframe or sandbox (unlikely but verify)

---

**Last updated**: 2026-04-23 13:09 — Multi-prompt append bug fixed (selection collapse removed)
