/*
 * Application Filler configuration editor.
 * Bundled offline YAML parser; no server or network requests.
 * Document edits preserve comments and unrecognized candidate facts.
 */
(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const schema = window.CONFIG_SCHEMA;
  const fieldDefinitions = schema.flatMap((section) => section.fields);
  const fieldByPath = new Map(fieldDefinitions.map((field) => [field.path, field]));

  const state = {
    source: window.CONFIG_TEMPLATE,
    filename: 'instructions.yaml',
    fileHandle: null,
    section: 'profile',
    dirty: false,
    openHelp: null,
    cvFile: null,
    cvPending: false,
    savedSource: window.CONFIG_TEMPLATE
  };

  // Use YAML 1.1, as PyYAML does, with its spelling of boolean values.
  // Keep the parsed document so comments, quoted strings and block scalars survive edits.
  let cachedSource;
  let cachedDocument;

  function parseYaml(source = state.source) {
    if (source === cachedSource) return cachedDocument;
    const doc = YAML.parseDocument(source, {
      version: '1.1', schema: 'yaml-1.1', merge: false,
      prettyErrors: false, uniqueKeys: true,
      customTags: (tags) => tags.map((tag) => tag.tag === 'tag:yaml.org,2002:bool'
        ? { ...tag, test: tag.resolve('true').value
          ? /^(?:true|True|TRUE|yes|Yes|YES|on|On|ON)$/
          : /^(?:false|False|FALSE|no|No|NO|off|Off|OFF)$/ }
        : tag)
    });
    cachedSource = source;
    cachedDocument = doc;
    return doc;
  }

  function resolveDefinition(definition) {
    return definition?.$ref
      ? window.CONFIG_CONTRACT.$defs[definition.$ref.split('/').at(-1)] : definition;
  }

  function definitionAt(path) {
    let definition = window.CONFIG_CONTRACT;
    for (const part of path.split('.')) {
      definition = resolveDefinition(definition);
      definition = definition?.properties?.[part] || definition?.additionalProperties;
    }
    return resolveDefinition(definition);
  }

  function dataAt(path, source = state.source) {
    const doc = parseYaml(source);
    if (doc.errors.length) return undefined;
    try {
      const data = doc.toJS({ maxAliasCount: 100 });
      return path.split('.').reduce((value, part) => value?.[part], data);
    } catch { return undefined; }
  }

  function valueAt(path, source = state.source) {
    const value = dataAt(path, source);
    const fallback = path.split('.').reduce((item, part) => item?.[part], window.CONFIG_DEFAULTS);
    return value === undefined ? fallback ?? definitionAt(path)?.default ?? null : value;
  }

  function listAt(path, source = state.source) {
    const value = valueAt(path, source);
    if (Array.isArray(value)) return value;
    return path === 'candidate.citizenships' && typeof value === 'string' ? [value] : [];
  }

  function replaceField(path, value) {
    const field = fieldByPath.get(path);
    if (!field) throw new Error(`Unknown field: ${path}`);
    const doc = parseYaml().clone();
    if (doc.errors.length) throw new Error('Correct the file structure in Advanced file editor first.');
    if (field.type === 'number' || field.type === 'decimal') {
      value = value === '' ? null : Number(value);
    } else if (field.nullableBoolean) {
      if (value === 'true') value = true;
      else if (value === 'false') value = false;
      else if (value === 'null') value = null;
    } else if (['nullable', 'date'].includes(field.type) && value === '') {
      value = null;
    }
    const segments = path.split('.');
    for (let depth = 1; depth < segments.length; depth += 1) {
      const parentPath = segments.slice(0, depth);
      const parent = doc.getIn(parentPath, true);
      if (parent === undefined) doc.setIn(parentPath, doc.createNode({}));
      else if (!YAML.isMap(parent)) {
        throw new Error(`${parentPath.join('.')}: expected a settings group. Correct it in Advanced file editor first.`);
      }
    }
    const previous = doc.getIn(segments, true);
    const node = doc.createNode(value);
    YAML.visit(node, {
      Scalar(_key, scalar) {
        if (typeof scalar.value === 'string') {
          scalar.type = scalar.value.includes('\n') ? 'BLOCK_LITERAL' : 'QUOTE_DOUBLE';
        }
      }
    });
    if (node && previous) {
      for (const property of ['comment', 'commentBefore', 'spaceBefore', 'anchor']) {
        if (previous[property] !== undefined) node[property] = previous[property];
      }
    }
    doc.setIn(segments, node);
    state.source = doc.toString({ lineWidth: 0 });
    state.dirty = state.source !== state.savedSource;
    refreshHeader();
    updateNotices();
  }

  // Validate against JSON Schema generated from the bot's strict Pydantic models.
  function contractErrors(value, definition, path = '', doc = null) {
    definition = resolveDefinition(definition);
    const label = fieldByPath.get(path)?.label || path || 'Configuration';
    if (definition.anyOf) {
      return definition.anyOf.some((option) => !contractErrors(value, option, path, doc).length)
        ? [] : [`${label}: expected ${definition.anyOf.map((option) => option.type).join(' or ')}.`];
    }
    if (definition.const !== undefined && value !== definition.const) {
      return [`${label}: must be ${definition.const}.`];
    }
    if (definition.enum && !definition.enum.includes(value)) {
      return [`${label}: choose one of ${definition.enum.join(', ')}.`];
    }
    const isObject = value !== null && typeof value === 'object'
      && !Array.isArray(value) && !(value instanceof Date) && !(value instanceof Map) && !(value instanceof Set);
    const matches = {
      object: isObject, array: Array.isArray(value), string: typeof value === 'string',
      integer: Number.isSafeInteger(value), number: typeof value === 'number' && Number.isFinite(value),
      boolean: typeof value === 'boolean', null: value === null
    };
    if (definition.type && !matches[definition.type]) return [`${label}: expected ${definition.type}.`];
    const errors = [];
    if (definition.type === 'object') {
      for (const required of definition.required || []) {
        if (!Object.hasOwn(value, required)) errors.push(`${label}: missing ${required}.`);
      }
      for (const [key, child] of Object.entries(value)) {
        const childPath = path ? `${path}.${key}` : key;
        if (definition.propertyNames?.enum && !definition.propertyNames.enum.includes(key)) {
          errors.push(`${childPath}: unsupported key.`);
        }
        const childDefinition = definition.properties?.[key];
        if (childDefinition) errors.push(...contractErrors(child, childDefinition, childPath, doc));
        else if (definition.additionalProperties === false) errors.push(`${childPath}: unsupported key.`);
        else if (typeof definition.additionalProperties === 'object') {
          errors.push(...contractErrors(child, definition.additionalProperties, childPath, doc));
        }
      }
    }
    if (definition.type === 'array' && definition.items) {
      value.forEach((item, index) => errors.push(...contractErrors(item, definition.items, `${path}[${index}]`, doc)));
    }
    if (typeof value === 'number') {
      // JavaScript represents 400 and 400.0 equally; Pydantic strict integers do not.
      const scalar = doc?.getIn(path.split('.'), true);
      if (definition.type === 'integer' && scalar?.type === 'PLAIN'
          && (scalar.tag === 'tag:yaml.org,2002:float' || /[.eE]/.test(scalar.source || ''))) {
        errors.push(`${label}: expected an integer without a decimal point or exponent.`);
      }
      if (definition.minimum !== undefined && value < definition.minimum) errors.push(`${label}: minimum is ${definition.minimum}.`);
      if (definition.maximum !== undefined && value > definition.maximum) errors.push(`${label}: maximum is ${definition.maximum}.`);
      if (definition.exclusiveMinimum !== undefined && value <= definition.exclusiveMinimum) errors.push(`${label}: must be greater than ${definition.exclusiveMinimum}.`);
    }
    return errors;
  }

  function preflight(source = state.source) {
    const errors = [];
    const warnings = [];
    if (new TextEncoder().encode(source).length > 256000) {
      return { errors: ['Instructions exceed the bot’s 256 KB limit.'], warnings };
    }
    const doc = parseYaml(source);
    for (const problem of [...doc.errors, ...doc.warnings]) {
      const line = source.slice(0, problem.pos?.[0] || 0).split('\n').length;
      errors.push(`Line ${line}: invalid configuration structure (${problem.code}). Check indentation, values and duplicate settings.`);
    }
    if (errors.length) return { errors, warnings };
    YAML.visit(doc, {
      Pair(_key, pair) {
        if (!YAML.isScalar(pair.key) || typeof pair.key.value !== 'string') {
          errors.push('Setting names must be unique text values, as required by the bot.');
        } else if (pair.key.value === '<<' && pair.key.type === 'PLAIN') {
          errors.push('Merged settings are not supported by the bot. Write each setting explicitly.');
        }
      }
    });
    let data;
    try { data = doc.toJS({ maxAliasCount: 100 }); }
    catch { errors.push('Invalid or excessive references between settings.'); return { errors, warnings }; }
    errors.push(...contractErrors(data, window.CONFIG_CONTRACT, '', doc));
    if (errors.length) return { errors, warnings };
    for (const field of fieldDefinitions) {
      const value = valueAt(field.path, source);
      if (field.type === 'email' && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value))) {
        warnings.push(`${field.label}: this does not look like a complete email address.`);
      }
      if (field.type === 'url' && value) {
        try { if (!['https:', 'http:'].includes(new URL(String(value)).protocol)) throw new Error(); }
        catch { warnings.push(`${field.label}: enter an http:// or https:// URL.`); }
      }
    }
    for (const [index, example] of (data.documents?.examples || []).entries()) {
      if (!example.trim() || new TextEncoder().encode(example).length > 20000) {
        errors.push(`documents.examples[${index}]: provide nonblank text, at most 20 KB per example.`);
      } else if (!/[\n\r]/.test(example) && !/\.(md|txt)$/i.test(example)) {
        errors.push(`documents.examples[${index}]: use a .md/.txt filename or paste a letter with multiple lines.`);
      } else if (!/[\n\r]/.test(example)) {
        warnings.push(`documents.examples[${index}]: place the referenced file in private/ and run demo validate.`);
      }
    }
    if (!data.candidate?.full_name || !data.candidate?.email) warnings.push('Complete your name and email before running real applications.');
    if (valueAt('documents.cover_letter', source) !== 'skip' && !data.documents?.background?.trim()) {
      warnings.push('Cover letters need factual background: education, skills, experience, projects and motivation. The CV is not read automatically.');
    }
    if (data.submission === 'auto') warnings.push('Automatic submission is enabled. The bot may send completed applications.');
    if (data.answers?.topics?.consent === 'infer') warnings.push('Consent inference needs precise prior authorisation in your instructions.');
    return { errors, warnings };
  }

  function updateNotices() {
    const { errors, warnings } = preflight();
    const notices = $('#notices');
    notices.replaceChildren();
    for (const message of errors.slice(0, 5)) addNotice(notices, message, 'error');
    for (const message of warnings.slice(0, 3)) addNotice(notices, message, 'warning');
    $('#summary-status').textContent = errors.length
      ? `${errors.length} configuration issue${errors.length === 1 ? '' : 's'}`
      : warnings.length ? `${warnings.length} reminder${warnings.length === 1 ? '' : 's'}` : 'Preflight checks passed';
    $('#save-button').disabled = errors.length > 0;
    $('#download-button').disabled = errors.length > 0;
    $('#save-folder-button').disabled = errors.length > 0;
    return errors.length === 0;
  }

  function addNotice(parent, message, type) {
    const item = document.createElement('div');
    item.className = `notice ${type}`;
    item.textContent = message;
    parent.append(item);
  }

  function updateField(path, value) {
    try {
      replaceField(path, value);
      if (path === 'documents.cv' && state.cvFile && value !== state.cvFile.name) {
        state.cvFile = null;
        state.cvPending = false;
        render();
      }
    } catch (error) {
      toast(error.message);
      render();
    }
  }

  // --- Rendering -----------------------------------------------------------

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function refreshHeader() {
    $('#file-name').textContent = state.filename;
    $('#dirty-indicator').hidden = !state.dirty;
  }

  function renderNav() {
    const nav = $('#section-nav');
    nav.replaceChildren();
    for (const section of schema) {
      const button = el('button', 'nav-button', section.title);
      button.type = 'button';
      button.classList.toggle('active', state.section === section.id);
      button.setAttribute('aria-current', state.section === section.id ? 'page' : 'false');
      button.addEventListener('click', () => switchSection(section.id));
      nav.append(button);
    }
  }

  function switchSection(id) {
    if (!schema.some((section) => section.id === id)) return;
    if (id !== 'raw' && state.section === 'raw' && !updateNotices()) {
      toast('Fix the highlighted issues before returning to the form.');
      return;
    }
    state.section = id;
    state.openHelp = null;
    render();
  }

  function makeFieldControl(field) {
    const value = field.type === 'tags' || field.type === 'examples' ? listAt(field.path) : valueAt(field.path);
    const id = `field-${field.path.replaceAll('.', '-')}`;

    if (field.type === 'relocation') return makeRelocationControl(field, value, id);

    if (field.type === 'examples') {
      const control = makeExamplesControl(field, value || []);
      control.id = id;
      control.setAttribute('role', 'group');
      control.setAttribute('aria-label', field.label);
      control.setAttribute('aria-describedby', `${id}-description`);
      return control;
    }

    let control;
    if (field.type === 'select') {
      control = el('select', 'field-select');
      for (const [option, label] of field.choices) {
        const item = el('option', '', label);
        item.value = option;
        control.append(item);
      }
      const actual = value === null ? 'null' : String(value);
      if (![...control.options].some((option) => option.value === actual)) {
        const unknown = el('option', '', `Unsupported current value (${actual})`);
        unknown.value = actual;
        control.prepend(unknown);
      }
      control.value = actual;
      control.addEventListener('change', () => {
        if (field.path === 'submission' && control.value === 'auto'
            && !window.confirm('Allow automatic submission of job applications without final review?')) {
          control.value = 'manual';
          return;
        }
        updateField(field.path, control.value);
      });
    } else if (field.type === 'textarea') {
      control = el('textarea', `field-textarea${field.tall ? ' tall' : ''}`);
      control.value = value ?? '';
      control.placeholder = field.placeholder || '';
      control.spellcheck = true;
      control.addEventListener('input', () => updateField(field.path, control.value));
    } else {
      control = el('input', 'field-input');
      control.type = field.type === 'email' ? 'email' : field.type === 'date' ? 'date'
        : field.type === 'number' || field.type === 'decimal' ? 'number' : 'text';
      if (field.type === 'number' || field.type === 'decimal') {
        const definition = definitionAt(field.path);
        if (definition.minimum !== undefined) control.min = String(definition.minimum);
        if (definition.maximum !== undefined) control.max = String(definition.maximum);
        if (definition.exclusiveMinimum !== undefined) control.min = String(definition.exclusiveMinimum + 0.01);
        control.step = field.type === 'decimal' ? 'any' : '1';
      }
      control.value = field.type === 'tags' ? (value || []).join(', ')
        : field.type === 'date' && value instanceof Date ? value.toISOString().slice(0, 10)
        : value === null ? '' : String(value);
      control.placeholder = field.placeholder || (field.type === 'nullable' ? 'Leave blank for unknown' : '');
      control.addEventListener('input', () => {
        let next = control.value;
        if (field.type === 'tags') next = control.value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean);
        updateField(field.path, next);
      });
    }
    control.id = id;
    control.setAttribute('aria-describedby', `${id}-description`);
    if (field.path === 'model.id') control.readOnly = true;
    return field.path === 'documents.cv' ? makeCVControl(control) : control;
  }

  function makeRelocationControl(field, value, id) {
    const wrapper = el('div', 'relocation-control');
    const select = el('select', 'field-select');
    select.id = id;
    select.setAttribute('aria-describedby', `${id}-description`);
    for (const [option, label] of [['yes', 'Yes, willing to relocate'], ['no', 'No, not willing to relocate'], ['unknown', 'Unknown / leave unspecified'], ['specific', 'Describe my preference']]) {
      const node = el('option', '', label);
      node.value = option;
      select.append(node);
    }
    select.value = value === true ? 'yes' : value === false ? 'no' : value ? 'specific' : 'unknown';
    const detail = el('div', 'relocation-detail');
    detail.hidden = select.value !== 'specific';
    const label = el('label', 'field-caption', 'Where would you relocate?');
    label.htmlFor = `${id}-detail`;
    const input = el('input', 'field-input');
    input.id = label.htmlFor;
    input.placeholder = field.placeholder;
    input.value = typeof value === 'string' ? value : '';
    input.addEventListener('input', () => updateField(field.path, input.value));
    select.addEventListener('change', () => {
      detail.hidden = select.value !== 'specific';
      const next = { yes: true, no: false, unknown: null, specific: input.value }[select.value];
      updateField(field.path, next);
      if (!detail.hidden) input.focus();
    });
    detail.append(label, input);
    wrapper.append(select, detail);
    return wrapper;
  }

  function makeExamplesControl(field, examples) {
    const wrapper = el('div', 'examples-list');
    function commit() {
      const items = [...wrapper.querySelectorAll('[data-example-text]')].map((item) => item.value);
      updateField(field.path, items);
    }
    for (let index = 0; index < examples.length; index += 1) {
      const item = el('div', 'example-item');
      const header = el('div', 'example-head');
      const name = el('span', '', `Example ${index + 1}`);
      const remove = el('button', 'small-button', 'Remove');
      remove.type = 'button';
      remove.setAttribute('aria-label', `Remove example ${index + 1}`);
      remove.addEventListener('click', () => {
        const next = listAt(field.path);
        next.splice(index, 1);
        updateField(field.path, next);
        render();
      });
      header.append(name, remove);
      const textarea = el('textarea', 'field-textarea');
      textarea.value = examples[index];
      textarea.placeholder = field.placeholder;
      textarea.dataset.exampleText = String(index);
      textarea.setAttribute('aria-label', `Example letter ${index + 1}`);
      textarea.addEventListener('input', commit);
      item.append(header, textarea);
      wrapper.append(item);
    }
    if (!examples.length) wrapper.append(el('p', 'field-caption', 'No examples added. This is optional.'));
    const add = el('button', 'small-button add-example', '+ Add example');
    add.type = 'button';
    add.addEventListener('click', () => {
      updateField(field.path, [...listAt(field.path), '']);
      render();
      const inputs = [...document.querySelectorAll('[data-example-text]')];
      inputs.at(-1)?.focus();
    });
    wrapper.append(add);
    return wrapper;
  }

  function renderField(field) {
    const card = el('div', `field-card${field.wide ? ' wide' : ''}`);
    const header = el('div', 'field-header');
    const id = `field-${field.path.replaceAll('.', '-')}`;
    const label = el('label', 'field-label', field.label);
    label.htmlFor = id;
    header.append(label);
    const description = el('p', 'field-description', field.hint);
    description.id = `${id}-description`;
    card.append(header, description, makeFieldControl(field));
    if (!field.help && !field.checklist?.length) return card;
    const helpButton = el('button', 'help-button', '?');
    helpButton.type = 'button';
    helpButton.setAttribute('aria-label', `More about ${field.label}`);
    helpButton.setAttribute('aria-expanded', String(state.openHelp === field.path));
    helpButton.setAttribute('aria-controls', `${id}-help`);
    header.append(helpButton);
    const help = el('div', 'help-panel');
    help.id = `${id}-help`;
    help.hidden = state.openHelp !== field.path;
    if (field.help) help.append(el('p', '', field.help));
    if (field.checklist) {
      const checklist = el('ul');
      for (const item of field.checklist) checklist.append(el('li', '', item));
      help.append(checklist);
    }
    card.append(help);
    helpButton.addEventListener('click', () => {
      state.openHelp = state.openHelp === field.path ? null : field.path;
      for (const button of document.querySelectorAll('.help-button')) {
        const expanded = button === helpButton && state.openHelp === field.path;
        button.setAttribute('aria-expanded', String(expanded));
        document.getElementById(button.getAttribute('aria-controls')).hidden = !expanded;
      }
    });
    return card;
  }

  function render() {
    renderNav();
    refreshHeader();
    const section = schema.find((item) => item.id === state.section);
    $('#section-eyebrow').textContent = section.eyebrow;
    $('#section-title').textContent = section.title;
    $('#section-description').textContent = section.description;
    $('#raw-panel').hidden = section.id !== 'raw';
    $('#fields').hidden = section.id === 'raw';
    $('.help-hint').hidden = section.id === 'raw';
    $('#entry-guidance').hidden = section.id === 'raw';
    if (section.id === 'raw') {
      $('#raw-text').value = state.source;
    } else {
      const fields = $('#fields');
      fields.replaceChildren(...section.fields.map(renderField));
    }
    updateNotices();
  }

  // --- Files ---------------------------------------------------------------

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = el('a');
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function makeCVControl(filenameControl) {
    const wrapper = el('div', 'cv-control');
    const picker = el('input', 'cv-file-input');
    picker.type = 'file';
    picker.accept = '.pdf,application/pdf';
    picker.id = 'cv-file-input';
    picker.hidden = true;
    picker.setAttribute('aria-label', 'Upload CV PDF');
    const choose = el('button', 'small-button', 'Upload CV PDF');
    choose.type = 'button';
    choose.addEventListener('click', () => picker.click());
    picker.addEventListener('change', async () => {
      const file = picker.files?.[0];
      if (!file) return;
      try {
        if (!/\.pdf$/i.test(file.name)) throw new Error('Choose a file with a .pdf extension.');
        if (file.size > 10000000) throw new Error('The bot accepts files up to 10 MB.');
        if (!(await file.slice(0, 5).text()).startsWith('%PDF-')) throw new Error('This file does not have a PDF header.');
        replaceField('documents.cv', file.name);
        state.cvFile = file;
        state.cvPending = true;
        render();
        toast('CV selected locally. Save to private/ or download the PDF below.');
      } catch (error) { toast(error.message); }
      picker.value = '';
    });
    const actions = el('div', 'cv-actions');
    actions.append(choose);
    if (state.cvFile) {
      const download = el('button', 'small-button', 'Download selected PDF');
      download.type = 'button';
      download.addEventListener('click', () => {
        downloadBlob(state.cvFile, state.cvFile.name);
        state.cvPending = false;
        render();
        toast(`Move the downloaded PDF to private/${state.cvFile.name}. Save your configuration there too.`);
      });
      actions.append(download);
    }
    const message = state.cvFile
      ? `${state.cvFile.name} (${(state.cvFile.size / 1000).toFixed(1)} KB) selected. ${state.cvPending ? 'Ready to save into private/.' : 'Keep the PDF in private/ alongside your configuration.'}`
      : 'No PDF selected in this editor.';
    const status = el('p', 'field-caption', message);
    status.setAttribute('role', 'status');
    wrapper.append(filenameControl, picker, actions, status);
    return wrapper;
  }

  async function savePrivateFolder() {
    if (!verifyBeforeExport()) return;
    if (typeof window.showDirectoryPicker !== 'function') {
      downloadFile();
      return;
    }
    const source = state.source;
    const cvFile = state.cvFile;
    try {
      const directory = await window.showDirectoryPicker({ id: 'application-filler-private', mode: 'readwrite' });
      // Write the PDF first so a failed PDF write cannot leave YAML referencing it.
      async function write(name, contents) {
        const handle = await directory.getFileHandle(name, { create: true });
        const writable = await handle.createWritable();
        try {
          await writable.write(contents);
          await writable.close();
        } catch (error) {
          await writable.abort().catch(() => {});
          throw error;
        }
        return handle;
      }
      if (cvFile) {
        if (valueAt('documents.cv', source) !== cvFile.name) throw new Error('Choose your CV again to match the configured filename.');
        await write(cvFile.name, cvFile);
      }
      state.fileHandle = await write('instructions.yaml', source);
      state.filename = 'instructions.yaml';
      state.savedSource = source;
      state.dirty = state.source !== source;
      if (state.cvFile === cvFile) state.cvPending = false;
      render();
      toast(`Saved instructions.yaml${cvFile ? ' and your CV' : ''} in ${directory.name}/.`);
    } catch (error) {
      if (error.name !== 'AbortError') toast(`Could not save the folder: ${error.message}. Use the download buttons instead.`);
    }
  }

  let toastTimeout;
  function toast(message) {
    const node = $('#toast');
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => { node.hidden = true; }, 4200);
  }

  function loadFile(source, filename, fileHandle = null) {
    source = source.replace(/^\uFEFF/, '');
    const previous = { ...state };
    state.source = source;
    const result = preflight();
    if (result.errors.length) {
      Object.assign(state, previous);
      toast(`File has configuration issues: ${result.errors[0]}`);
      return;
    }
    state.cvFile = null;
    state.cvPending = false;
    state.filename = filename || 'instructions.yaml';
    state.fileHandle = fileHandle;
    state.savedSource = source;
    state.dirty = false;
    state.section = 'profile';
    render();
    toast('Configuration loaded locally.');
  }

  async function openFile() {
    if ((state.dirty || state.cvPending) && !window.confirm('Discard unsaved changes and open another file?')) return;
    if (typeof window.showOpenFilePicker === 'function') {
      try {
        const [handle] = await window.showOpenFilePicker({
          multiple: false,
          types: [{ description: 'Application Filler configuration', accept: { 'text/plain': ['.yaml', '.yml'] } }]
        });
        const file = await handle.getFile();
        loadFile(await file.text(), file.name, handle);
        return;
      } catch (error) {
        if (error.name === 'AbortError') return;
        // Local file:// and some browsers don't support the picker. Use <input>.
      }
    }
    $('#file-input').click();
  }

  function verifyBeforeExport() {
    if (updateNotices()) return true;
    toast('Correct the highlighted configuration issues before saving.');
    return false;
  }

  function downloadFile() {
    if (!verifyBeforeExport()) return;
    const file = new Blob([state.source], { type: 'text/yaml;charset=utf-8' });
    downloadBlob(file, /\.ya?ml$/i.test(state.filename) ? state.filename : 'instructions.yaml');
    state.savedSource = state.source;
    state.dirty = false;
    refreshHeader();
    toast(state.cvPending
      ? 'Configuration downloaded. Download your selected PDF in Documents & cover letters too; put both in private/.'
      : 'Configuration downloaded. Place it in your bot’s private/ folder.');
  }

  async function saveFile() {
    if (!verifyBeforeExport()) return;
    const source = state.source;
    if (typeof window.showSaveFilePicker !== 'function' && !state.fileHandle) {
      downloadFile();
      return;
    }
    try {
      let handle = state.fileHandle;
      if (!handle) {
        handle = await window.showSaveFilePicker({
          suggestedName: state.filename,
          types: [{ description: 'Application Filler configuration', accept: { 'text/plain': ['.yaml', '.yml'] } }]
        });
      }
      const writable = await handle.createWritable();
      await writable.write(source);
      await writable.close();
      state.fileHandle = handle;
      state.filename = handle.name;
      state.savedSource = source;
      state.dirty = state.source !== source;
      refreshHeader();
      toast('Configuration saved to your chosen file.');
    } catch (error) {
      if (error.name !== 'AbortError') toast(`Direct save was not available: ${error.message}. Use Download instead.`);
    }
  }

  // --- Lifecycle -----------------------------------------------------------

  $('#new-button').addEventListener('click', () => {
    if ((state.dirty || state.cvPending) && !window.confirm('Discard unsaved changes and start a new configuration?')) return;
    state.cvFile = null;
    state.cvPending = false;
    state.source = window.CONFIG_TEMPLATE;
    state.filename = 'instructions.yaml';
    state.fileHandle = null;
    state.savedSource = state.source;
    state.dirty = false;
    state.section = 'profile';
    render();
    toast('Blank version 2 configuration loaded.');
  });
  $('#open-button').addEventListener('click', openFile);
  $('#file-input').addEventListener('change', async (event) => {
    const file = event.target.files?.[0];
    if (file) loadFile(await file.text(), file.name);
    event.target.value = '';
  });
  $('#download-button').addEventListener('click', downloadFile);
  $('#save-button').addEventListener('click', saveFile);
  if (typeof window.showDirectoryPicker !== 'function') {
    $('#save-folder-button').textContent = 'Download for private/';
    $('#save-guidance').hidden = false;
  }
  $('#save-folder-button').addEventListener('click', savePrivateFolder);
  $('#raw-text').addEventListener('input', (event) => {
    state.source = event.target.value;
    state.dirty = state.source !== state.savedSource;
    refreshHeader();
    updateNotices();
  });
  window.addEventListener('beforeunload', (event) => {
    if (!state.dirty && !state.cvPending) return;
    event.preventDefault();
    event.returnValue = '';
  });
  window.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      savePrivateFolder();
    }
  });

  render();
})();
