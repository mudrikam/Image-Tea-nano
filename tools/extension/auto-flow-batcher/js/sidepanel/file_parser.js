/**
 * Auto Flow Batcher - File & Text Parsers
 * Handles TXT / CSV line extraction, numbered list parsing, multiline concatenation, and file reading.
 */

/**
 * Escape HTML to prevent XSS in dynamic table and prompt rendering
 * @param {string} text 
 * @returns {string}
 */
export function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Parse prompts from text: supports both numbered format (1. ..., 2. ...) and simple line-by-line format
 * @param {string} text 
 * @returns {string[]}
 */
export function parsePrompts(text) {
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const prompts = [];
  let currentPrompt = '';
  let hasNumbering = false;

  // Detect if any line uses numbering
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed && /^\d+\.\s/.test(trimmed)) {
      hasNumbering = true;
      break;
    }
  }

  if (hasNumbering) {
    // Numbered mode (with multi-line continuation support)
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line === '') {
        if (currentPrompt.trim()) {
          prompts.push(currentPrompt.trim());
          currentPrompt = '';
        }
        continue;
      }

      const numberMatch = line.match(/^(\d+)\.\s*(.*)/);

      if (numberMatch) {
        if (currentPrompt.trim()) {
          prompts.push(currentPrompt.trim());
        }
        currentPrompt = numberMatch[2].trim();
      } else {
        if (currentPrompt) {
          currentPrompt += ' ' + line;
        } else {
          currentPrompt = line;
        }
      }
    }

    if (currentPrompt.trim()) {
      prompts.push(currentPrompt.trim());
    }
  } else {
    // Simple mode: each non-empty line = one prompt
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        prompts.push(trimmed);
      }
    }
  }

  return prompts;
}

/**
 * Reads a File object as text and returns parsed contents asynchronously
 * @param {File} file 
 * @returns {Promise<{ text: string, prompts: string[], fileName: string }>}
 */
export function readFileAsync(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      return reject(new Error('No file provided'));
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result;
      const prompts = parsePrompts(text);
      resolve({
        text,
        prompts,
        fileName: file.name
      });
    };
    reader.onerror = (err) => reject(err);
    reader.readAsText(file);
  });
}
