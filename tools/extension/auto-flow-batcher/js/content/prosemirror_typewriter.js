// ProseMirror Typewriter Input for Auto Flow Batcher
(function () {
  window.AFB_Typewriter = {
    async typeIntoProseMirror(editorEl, text, isRunningFn = () => true, log = console.log) {
      if (!text || !editorEl) return false;

      editorEl.scrollIntoView({ behavior: 'instant', block: 'center' });
      editorEl.focus();
      await new Promise(r => setTimeout(r, 100));

      let targetNode = editorEl.querySelector('p') || editorEl;

      // Select all inside target and clear
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(targetNode);
      sel.removeAllRanges();
      sel.addRange(range);
      await new Promise(r => setTimeout(r, 40));

      try {
        document.execCommand('delete', false);
      } catch (_) {
        targetNode.textContent = '';
      }
      await new Promise(r => setTimeout(r, 60));

      // Human-like typewriter simulation
      const minDelay = 15;
      const maxDelay = 45;

      for (let i = 0; i < text.length && isRunningFn(); i++) {
        const char = text[i];
        let typedOk = false;
        try {
          typedOk = document.execCommand('insertText', false, char);
        } catch (_) {}

        if (!typedOk) {
          targetNode.dispatchEvent(new InputEvent('beforeinput', {
            inputType: 'insertText',
            data: char,
            bubbles: true,
            cancelable: true
          }));
          targetNode.dispatchEvent(new InputEvent('input', {
            inputType: 'insertText',
            data: char,
            bubbles: true,
            cancelable: true
          }));
        }

        let delay = Math.random() * (maxDelay - minDelay) + minDelay;
        if (char === ' ') delay *= 2.5;
        await new Promise(r => setTimeout(r, delay));
      }

      targetNode.dispatchEvent(new Event('input', { bubbles: true }));
      targetNode.dispatchEvent(new Event('change', { bubbles: true }));
      targetNode.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
      await new Promise(r => setTimeout(r, 150));

      const finalContent = (editorEl.textContent || '').trim();
      log(`[AFB] Typewriter completed. Editor content: "${finalContent}"`);
      return finalContent.includes(text.trim());
    }
  };
})();
