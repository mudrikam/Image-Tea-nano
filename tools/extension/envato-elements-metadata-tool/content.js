(() => {
  'use strict';
  if (window.top !== window.self || window.__EEMT_LOADED__) return;
  window.__EEMT_LOADED__ = true;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const TIMING = { scroll: 35, press: 20, settle: 55, field: 45 };
  const normalize = (value) => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const visible = (element) => {
    if (!element || !(element instanceof HTMLElement)) return false;
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };
  let runLogs = [];
  const report = (message) => {
    runLogs.push(message);
    if (runLogs.length > 100) runLogs = runLogs.slice(-100);
    console.log('[EEMT]', message);
    try { chrome.runtime.sendMessage({ type: 'EEMT_LOG', message }); } catch (_) {}
    chrome.storage.local.set({ eemt_state: { status: message, kind: message.startsWith('ERROR:') ? 'error' : '', logs: runLogs } });
  };

  function text(element) { return normalize(element?.textContent); }

  function findSection(label) {
    const wanted = normalize(label);
    const candidates = [...document.querySelectorAll('label, [class*="label"], [class*="Legend"], [class*="legend"]')];
    const node = candidates.find((item) => text(item) === wanted || text(item).includes(wanted));
    return node?.closest('[class*="section"], [class*="Attribute"], [class*="Fieldset"], section, fieldset, div') || null;
  }

  function findInput(label, type = null) {
    const directSelectors = {
      title: '[data-test-selector="item-submission-title"] input',
      tagline: '[data-test-selector="item-submission-sub-title"] input',
      'item description': '[data-test-selector="item-submission-description"] textarea',
      description: '[data-test-selector="item-submission-description"] textarea',
      dpi: '.DPIAttribute__root___2I7yz input',
    };
    const directSelector = directSelectors[normalize(label)];
    const direct = directSelector ? document.querySelector(directSelector) : null;
    if (direct && visible(direct) && !direct.disabled) return direct;
    const section = findSection(label);
    const candidates = [...(section || document).querySelectorAll('input, textarea')].filter((item) => {
      if (!visible(item)) return false;
      if (type && item.type !== type) return false;
      return item.type !== 'hidden' && !item.disabled;
    });
    return candidates[0] || null;
  }

  function setNativeValue(element, value) {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    setter?.call(element, value);
    element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: String(value) }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }

  async function clickHuman(element, label, timing = TIMING) {
    if (!element) throw new Error(`Could not find ${label}.`);
    element.scrollIntoView({ behavior: 'instant', block: 'center' });
    await sleep(timing.scroll || 0);
    element.focus?.();
    const rect = element.getBoundingClientRect();
    const init = { bubbles: true, cancelable: true, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2, button: 0 };
    element.dispatchEvent(new MouseEvent('mouseover', init));
    element.dispatchEvent(new MouseEvent('mousedown', init));
    await sleep(timing.press || 0);
    element.dispatchEvent(new MouseEvent('mouseup', init));
    element.click?.();
    report(`Clicked ${label}`);
    await sleep(timing.settle || 0);
  }

  async function pasteField(label, value, selector = null, directField = null) {
    const field = directField || (selector ? document.querySelector(selector) : findInput(label));
    if (!field) throw new Error(`Could not find ${label}.`);
    await clickHuman(field, label);
    setNativeValue(field, value || '');
    report(`Filled ${label}`);
    await sleep(TIMING.field);
  }

  async function typeSearchValue(input, value) {
    // Envato filters on the input event, so per-character humanization only
    // adds delay after the search control has already appeared.
    await clickHuman(input, 'dropdown search', { scroll: 0, press: 0, settle: 0 });
    setNativeValue(input, '');
    setNativeValue(input, String(value));
  }

  function findVisibleOption(option, excludedSection = null) {
    const wanted = normalize(option);
    const menu = [...document.querySelectorAll(
      '[role="listbox"], .DeprecatedDropdown__menuOuter___3c04W, .dropdown-menu-outer'
    )].filter((item) => visible(item) && !excludedSection?.contains(item)).pop();
    if (!menu) return null;
    return [...menu.querySelectorAll('[role="option"], [data-option-index], li, button, [data-name]')]
      .find((item) => visible(item) && normalize(item.textContent) === wanted) || null;
  }

  function clickableOption(element) {
    return element?.closest('[role="option"], [data-option-index], [data-name], li, button') || element;
  }

  function selectWithKeyboard(control) {
    control.focus?.();
    const key = (value, code = value, keyCode = 0) => {
      control.dispatchEvent(new KeyboardEvent('keydown', {
        key: value, code, keyCode, which: keyCode, bubbles: true, cancelable: true
      }));
      control.dispatchEvent(new KeyboardEvent('keyup', {
        key: value, code, keyCode, which: keyCode, bubbles: true, cancelable: true
      }));
    };
    key('ArrowDown', 'ArrowDown', 40);
    key('Enter', 'Enter', 13);
  }

  function getOptionSection(label) {
    const normalizedLabel = normalize(label);
    if (normalizedLabel === 'categories') return document.querySelector('.item-submission-categories');
    if (normalizedLabel === 'applications supported') {
      const sections = [...document.querySelectorAll('.ApplicationsSupportedAttribute__root___21EVj, [class*="ApplicationsSupportedAttribute_root"]')];
      return sections.find((section) => section.querySelector('.DeprecatedDropdown__menuOuter___3c04W, .dropdown-menu-outer')) ||
        sections.find((section) => section.querySelector('input[type="hidden"]')?.value) ||
        sections[sections.length - 1];
    }
    if (normalizedLabel === 'file types') {
      const sections = [...document.querySelectorAll(
        '.MultiSelectAttribute__root___1gjZs, [class*="MultiSelectAttribute_root"]'
      )].filter((section) => normalize(section.querySelector('[class*="MultiSelectAttribute_label"]')?.textContent) === 'file types');
      return sections.find((section) => section.querySelector('input[type="hidden"]')?.value) || sections[sections.length - 1];
    }
    if (normalizedLabel === 'dimensions') return document.querySelector('.DimensionsAttribute__root___1owYo');
    return findAttributeDropdown(label)?.closest('.SelectAttribute__root___3eaNK');
  }

  function getOptionDropdown(label, section = getOptionSection(label)) {
    const normalizedLabel = normalize(label);
    if (normalizedLabel === 'dimensions') return section?.querySelector('.DimensionsAttribute__unit___3w3Bl');
    return section?.querySelector('.DeprecatedDropdown__select___BFZQ9');
  }

  function getMultiSelectOptionState(label) {
    const section = getOptionSection(label);
    const dropdown = getOptionDropdown(label, section);
    const hiddenValues = normalize(dropdown?.querySelector('input[type="hidden"]')?.value || '')
      .split(',').map((value) => normalize(value)).filter(Boolean);
    const tags = [...(section?.querySelectorAll('[data-name]') || [])]
      .map((item) => normalize(item.getAttribute('data-name'))).filter(Boolean);
    return { section, dropdown, values: new Set([...hiddenValues, ...tags]) };
  }

  function findAttributeDropdown(label) {
    const wanted = normalize(label);
    if (wanted === 'dimensions') return document.querySelector('.DimensionsAttribute__unit___3w3Bl');
    return [...document.querySelectorAll('.SelectAttribute__root___3eaNK')]
      .find((item) => normalize(item.querySelector('.SelectAttribute__label___1B8Nh')?.textContent) === wanted)
      ?.querySelector('.DeprecatedDropdown__select___BFZQ9');
  }

  async function selectOption(label, option) {
    const directSelectors = {
      categories: '.item-submission-categories',
      'color space': '.AttributeList__section___2DxaW .DeprecatedDropdown__select___BFZQ9',
      orientation: '.AttributeList__section___2DxaW .DeprecatedDropdown__select___BFZQ9',
      'applications supported': '.ApplicationsSupportedAttribute__root___21EVj .DeprecatedDropdown__select___BFZQ9',
      'file types': '.MultiSelectAttribute__root___1gjZs .DeprecatedDropdown__select___BFZQ9',
      dimensions: '.DimensionsAttribute__root___1owYo .DimensionsAttribute__unit___3w3Bl',
    };
    const normalizedLabel = normalize(label);
    let section = findSection(label);
    if (normalizedLabel === 'categories') section = document.querySelector(directSelectors.categories);
    if (normalizedLabel === 'applications supported') section = getOptionSection(label);
    if (normalizedLabel === 'file types') section = getOptionSection(label);
    if (normalizedLabel === 'dimensions') section = document.querySelector('.DimensionsAttribute__root___1owYo');
    if (normalizedLabel === 'color space' || normalizedLabel === 'orientation') {
      section = findAttributeDropdown(label)?.closest('.SelectAttribute__root___3eaNK');
    }
    const native = section?.querySelector('select');
    if (native) {
      await clickHuman(native, `${label} dropdown`);
      const match = [...native.options].find((item) => normalize(item.textContent) === normalize(option));
      if (match) {
        native.value = match.value;
        native.dispatchEvent(new Event('change', { bubbles: true }));
      }
      report(`Selected ${option} in ${label}`);
      return;
    }
    const exactDropdown = findAttributeDropdown(label);
    const control = exactDropdown?.querySelector('.DeprecatedDropdown__control___31OEc') ||
      section?.querySelector('.DeprecatedDropdown__control___31OEc, [role="combobox"], .DeprecatedDropdown__input___2Ujjh');
    if (!control) throw new Error(`Could not find ${label} dropdown.`);
    const searchInput = section.querySelector('.DeprecatedDropdown__input___2Ujjh input') ||
      section.querySelector('.DeprecatedDropdown__input___2Ujjh');
    await clickHuman(control, `${label} dropdown`);
    if (searchInput instanceof HTMLInputElement) await typeSearchValue(searchInput, option);

    const optionElement = findVisibleOption(option, section);
    if (optionElement) {
      const target = clickableOption(optionElement);
      await clickHuman(target, `${option} option`, { scroll: 0, press: 0, settle: 0 });
    } else {
      // If the menu is rendered asynchronously, let the focused combo handle
      // the selection without blocking the rest of the form fill.
      selectWithKeyboard(control);
    }
    report(`Selected ${option} in ${label}`);
  }

  async function checkbox(label, checked) {
    const wanted = normalize(label);
    const input = [...document.querySelectorAll('input[type="checkbox"]')]
      .find((item) => normalize(item.closest('label')?.textContent).includes(wanted));
    if (!input) throw new Error(`Could not find ${label} checkbox.`);
    if (input.checked !== checked) await clickHuman(input.closest('label') || input, `${label} checkbox`);
    report(`${label}: ${checked ? 'checked' : 'unchecked'}`);
  }

  async function typeTag(input, value) {
    if (document.activeElement !== input) await clickHuman(input, 'tag input');
    setNativeValue(input, '');
    for (const character of String(value)) {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: character, bubbles: true }));
      setNativeValue(input, `${input.value || ''}${character}`);
      input.dispatchEvent(new KeyboardEvent('keyup', { key: character, bubbles: true }));
      await sleep(8 + Math.random() * 12);
    }
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    await sleep(70);
  }

  async function fillTags(tags) {
    const input = document.querySelector('#item-submission-tags') ||
      document.querySelector('.item-submission-tags input:not([type="hidden"])') ||
      [...document.querySelectorAll('input')].find((item) => /tag/i.test(item.placeholder || item.name || ''));
    if (!input) throw new Error('Could not find Tags input.');
    await clickHuman(input, 'tag input');
    for (const tag of Array.isArray(tags) ? tags : String(tags || '').split(',')) {
      const clean = String(tag).trim();
      if (!clean) continue;
      await typeTag(input, clean);
      report(`Added tag: ${clean}`);
    }
  }

  async function fillDimensions(metadata) {
    const section = document.querySelector('.DimensionsAttribute__root___1owYo');
    const inputs = [...(section || document).querySelectorAll('input:not([type="hidden"])')]
      .filter((item) => visible(item) && !item.disabled);
    if (inputs.length < 2) throw new Error('Could not find width and height entries.');
    await pasteField('Width', metadata.width, null, inputs[0]);
    await pasteField('Height', metadata.height, null, inputs[1]);
    await selectOption('Dimensions', metadata.dimensionUnit || 'px');
  }

  async function run(metadata) {
    runLogs = [];
    chrome.storage.local.set({ eemt_state: { metadata, status: 'Starting form filling...', kind: '', logs: [] } });
    await pasteField('Title', metadata.title);
    await pasteField('Tagline', metadata.tagline);
    await selectOption('Categories', 'Product Mockups');
    await pasteField('Item Description', metadata.description || metadata.item_description);
    await checkbox('Vector', false);
    await checkbox('Layered', true);
    await selectOption('Color Space', 'RGB');
    await selectOption('Orientation', 'Landscape');
    await pasteField('DPI', metadata.dpi);
    await fillDimensions(metadata);
    await checkbox('Documentation', true);
    // Fill tags before the remaining multi-select attributes. Envato rebuilds
    // these controls after each selection, so keeping this order avoids stale
    // dropdown instances and leaves the application field last to retry safely.
    await fillTags(metadata.tags);
    report('Skipped File Types and Applications Supported temporarily.');
    report('All requested metadata fields filled. Review before submitting.');
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== 'EEMT_FILL') return false;
    if (!/^https:\/\/elements-contributors\.envato\.com\/item-submissions\/[0-9a-f-]+(?:[/?#]|$)/i.test(location.href)) {
      const error = 'Buka halaman edit item Envato terlebih dahulu.';
      report(`ERROR: ${error}`);
      sendResponse({ ok: false, error });
      return false;
    }
    run(message.metadata || {}).then(() => sendResponse({ ok: true })).catch((error) => {
      report(`ERROR: ${error.message}`);
      sendResponse({ ok: false, error: error.message });
    });
    return true;
  });
})();
