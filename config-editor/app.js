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
  const checkoutKey = new URL('../', window.location.href).href;
  const expectedRepositoryName = decodeURIComponent(new URL(checkoutKey).pathname.split('/').filter(Boolean).at(-1) || 'repository');
  const supportsFolderAccess = typeof window.showDirectoryPicker === 'function';

  const state = {
    source: window.CONFIG_TEMPLATE,
    filename: 'instructions.yaml',
    repositoryHandle: null,
    folderRemembered: false,
    restoringFolder: true,
    saving: false,
    section: 'profile',
    dirty: false,
    openHelp: null,
    cvFile: null,
    cvPending: false,
    transcriptFile: null,
    transcriptPending: false,
    languageRows: null,
    languageDraftDirty: false,
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
    return value === undefined ? fallback ?? fieldByPath.get(path)?.default ?? definitionAt(path)?.default ?? null : value;
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
  function languageErrors(rows) {
    const errors = [];
    const names = new Set();
    rows.forEach(({ language, level }, index) => {
      const name = language.trim();
      if (!name) errors.push(`Language ${index + 1}: enter a language name or remove this row.`);
      if (!level.trim()) errors.push(`Language ${index + 1}: enter a proficiency level or remove this row.`);
      if (name && names.has(name.toLowerCase())) errors.push('Language skills: each language can appear only once.');
      names.add(name.toLowerCase());
    });
    return errors;
  }

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
    const languages = data.candidate?.languages;
    if (languages != null && (typeof languages !== 'object' || Array.isArray(languages)
        || languages instanceof Date || languages instanceof Map || languages instanceof Set
        || Object.values(languages).some((level) => typeof level !== 'string'))) {
      errors.push('Language skills: supply a language name and text proficiency level for each entry.');
    } else {
      const rows = state.languageRows ?? Object.entries(languages || {}).map(([language, level]) => ({ language, level }));
      errors.push(...languageErrors(rows));
    }
    if (data.candidate?.gender != null && typeof data.candidate.gender !== 'string') {
      errors.push('Gender: enter your own wording or leave it blank.');
    }
    if (data.candidate?.veteran_status != null && typeof data.candidate.veteran_status !== 'boolean') {
      errors.push('Veteran status: choose Veteran, Not a veteran or Unknown.');
    }
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
    const cvPath = valueAt('documents.cv', source);
    const transcriptPath = valueAt('documents.transcript', source);
    if (cvPath && transcriptPath && cvPath.replaceAll('\\', '/').toLowerCase() === transcriptPath.replaceAll('\\', '/').toLowerCase()) {
      errors.push('Use different filenames for your CV and transcript.');
    }
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
    $('#save-folder-button').disabled = errors.length > 0 || state.saving || state.restoringFolder;
    $('#open-button').disabled = state.saving || state.restoringFolder;
    $('#new-button').disabled = state.saving;
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
      for (const kind of ['cv', 'transcript']) {
        if (path === `documents.${kind}` && state[`${kind}File`] && value !== state[`${kind}File`].name) {
          state[`${kind}File`] = null;
          state[`${kind}Pending`] = false;
          render();
        }
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
    $('#dirty-indicator').hidden = !state.dirty && !state.languageDraftDirty;
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
    if (id === 'raw' && state.languageDraftDirty) {
      toast('Complete or remove unfinished language rows before opening the file editor.');
      return;
    }
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

    if (field.type === 'languages') return makeLanguagesControl(field, value, id);
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
    } else if (field.type === 'textarea' || field.type === 'ranked') {
      control = el('textarea', `field-textarea${field.tall ? ' tall' : ''}`);
      control.value = field.type === 'ranked' ? (Array.isArray(value) ? value.join('\n') : '') : value ?? '';
      control.placeholder = field.placeholder || '';
      control.spellcheck = true;
      control.addEventListener('input', () => updateField(field.path, field.type === 'ranked'
        ? control.value.split(/\r?\n/).map((city) => city.trim()).filter(Boolean) : control.value));
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
    return ['documents.cv', 'documents.transcript'].includes(field.path)
      ? makePDFControl(control, field.path.split('.')[1]) : control;
  }

  function makeLanguagesControl(field, value, id) {
    if (state.languageRows === null) {
      state.languageRows = Object.entries(value || {}).map(([language, level]) => ({ language, level }));
    }
    const wrapper = el('div', 'languages-list');
    wrapper.id = id;
    wrapper.setAttribute('role', 'group');
    wrapper.setAttribute('aria-label', field.label);
    wrapper.setAttribute('aria-describedby', `${id}-description`);

    function commit() {
      state.languageDraftDirty = true;
      if (!languageErrors(state.languageRows).length) {
        const languages = Object.fromEntries(state.languageRows.map(({ language, level }) => [language.trim(), level.trim()]));
        try {
          replaceField(field.path, languages);
          state.languageDraftDirty = false;
        } catch (error) { toast(error.message); }
      }
      refreshHeader();
      updateNotices();
    }

    state.languageRows.forEach((row, index) => {
      const item = el('div', 'language-row');
      const nameId = `${id}-name-${index}`;
      const levelId = `${id}-level-${index}`;
      const nameLabel = el('label', 'language-label', 'Language');
      nameLabel.htmlFor = nameId;
      const name = el('input', 'field-input');
      name.id = nameId;
      name.type = 'text';
      name.placeholder = field.placeholder;
      name.value = row.language;
      name.setAttribute('aria-label', `Language ${index + 1}`);
      name.dataset.languageName = String(index);
      name.addEventListener('input', () => { row.language = name.value; commit(); });
      const nameGroup = el('div', 'language-cell');
      nameGroup.append(nameLabel, name);

      const levelLabel = el('label', 'language-label', 'Proficiency');
      levelLabel.htmlFor = levelId;
      const level = el('input', 'field-input');
      level.id = levelId;
      level.type = 'text';
      level.placeholder = field.levelPlaceholder;
      level.value = row.level;
      level.setAttribute('aria-label', `Proficiency ${index + 1}`);
      level.addEventListener('input', () => { row.level = level.value; commit(); });
      const levelGroup = el('div', 'language-cell');
      levelGroup.append(levelLabel, level);

      const remove = el('button', 'small-button', 'Remove');
      remove.type = 'button';
      remove.setAttribute('aria-label', `Remove language ${index + 1}`);
      remove.addEventListener('click', () => {
        state.languageRows.splice(index, 1);
        commit();
        render();
      });
      item.append(nameGroup, levelGroup, remove);
      wrapper.append(item);
    });
    if (!state.languageRows.length) wrapper.append(el('p', 'field-caption', 'No languages supplied. Add only those you want the agent to use.'));
    const add = el('button', 'small-button add-language', '+ Add language');
    add.type = 'button';
    add.addEventListener('click', () => {
      state.languageRows.push({ language: '', level: '' });
      commit();
      render();
      document.querySelector('.language-row:last-of-type [data-language-name]')?.focus();
    });
    wrapper.append(add);
    return wrapper;
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
    updateSaveDestination();
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

  function makePDFControl(filenameControl, kind) {
    const title = kind === 'cv' ? 'CV' : 'transcript';
    const wrapper = el('div', 'cv-control');
    const picker = el('input', 'cv-file-input');
    picker.type = 'file';
    picker.accept = '.pdf,application/pdf';
    picker.id = `${kind}-file-input`;
    picker.hidden = true;
    picker.setAttribute('aria-label', `Upload ${title} PDF`);
    const choose = el('button', 'small-button', `Upload ${title} PDF`);
    choose.type = 'button';
    choose.addEventListener('click', () => picker.click());
    picker.addEventListener('change', async () => {
      const file = picker.files?.[0];
      if (!file) return;
      try {
        if (!/\.pdf$/i.test(file.name)) throw new Error('Choose a file with a .pdf extension.');
        if (file.size > 10000000) throw new Error('The bot accepts files up to 10 MB.');
        if (!(await file.slice(0, 5).text()).startsWith('%PDF-')) throw new Error('This file does not have a PDF header.');
        const otherKind = kind === 'cv' ? 'transcript' : 'cv';
        if (file.name.toLowerCase() === String(valueAt(`documents.${otherKind}`) || '').toLowerCase()) {
          throw new Error('Use different filenames for your CV and transcript.');
        }
        replaceField(`documents.${kind}`, file.name);
        state[`${kind}File`] = file;
        state[`${kind}Pending`] = true;
        render();
        toast(supportsFolderAccess
          ? `${title} selected locally. Save to private/ saves it with your configuration.`
          : `${title} selected locally. Export setup includes it with your configuration.`);
      } catch (error) { toast(error.message); }
      picker.value = '';
    });
    const actions = el('div', 'cv-actions');
    actions.append(choose);
    if (kind === 'transcript') {
      const remove = el('button', 'small-button', 'Do not use a transcript');
      remove.type = 'button';
      remove.addEventListener('click', () => {
        replaceField('documents.transcript', null);
        state.transcriptFile = null;
        state.transcriptPending = false;
        render();
      });
      actions.append(remove);
    }
    const file = state[`${kind}File`];
    const message = file
      ? `${file.name} (${(file.size / 1000).toFixed(1)} KB) selected. ${state[`${kind}Pending`] ? 'Ready to save into private/.' : 'Keep the PDF in private/ alongside your configuration.'}`
      : 'No PDF selected in this editor.';
    const status = el('p', 'field-caption', message);
    status.setAttribute('role', 'status');
    wrapper.append(filenameControl, picker, actions, status);
    return wrapper;
  }

  function updateSaveDestination() {
    const guidance = $('#save-guidance');
    $('#change-folder-button').hidden = !supportsFolderAccess || !state.repositoryHandle;
    $('#change-folder-button').disabled = state.saving;
    if (!supportsFolderAccess) {
      guidance.textContent = 'This browser cannot save directly to a folder. Export the setup, then extract its private/ folder into your cloned repository. Use Chrome or Edge for direct saving.';
    } else if (state.repositoryHandle) {
      guidance.textContent = `Save destination: ${state.repositoryHandle.name}/private/. ${state.folderRemembered ? 'This repository is remembered in your browser.' : 'This repository is selected for this tab.'}`;
    } else {
      guidance.textContent = `Choose your cloned ${expectedRepositoryName} repository folder once. Saves write the configuration and any selected PDFs into its private/ folder.`;
    }
  }

  async function restoreRepository() {
    try {
      if (!supportsFolderAccess) return;
      const handle = await window.CONFIG_FOLDER_STORE.load(checkoutKey);
      if (handle?.kind === 'directory' && typeof handle.getDirectoryHandle === 'function') {
        state.repositoryHandle = handle;
        state.folderRemembered = true;
      }
    } catch {
      // Private browsing or browser policy may prevent persistence. Tab reuse still works.
    } finally {
      state.restoringFolder = false;
      updateSaveDestination();
      updateNotices();
    }
  }

  async function repositoryDirectory(change = false) {
    if (state.repositoryHandle && !change) {
      const handle = state.repositoryHandle;
      if (typeof handle.queryPermission === 'function'
          && await handle.queryPermission({ mode: 'readwrite' }) !== 'granted'
          && await handle.requestPermission({ mode: 'readwrite' }) !== 'granted') {
        throw new Error('Folder access was not granted. Allow access to save, or choose Change repository.');
      }
      return handle;
    }
    const options = { id: 'application-filler-repository', mode: 'readwrite' };
    if (state.repositoryHandle) options.startIn = state.repositoryHandle;
    const handle = await window.showDirectoryPicker(options);
    try {
      const editor = await handle.getDirectoryHandle('config-editor');
      await editor.getFileHandle('index.html');
    } catch {
      throw new Error('Select the cloned repository folder containing config-editor/index.html.');
    }
    state.repositoryHandle = handle;
    state.folderRemembered = false;
    try {
      await window.CONFIG_FOLDER_STORE.save(checkoutKey, handle);
      state.folderRemembered = true;
    } catch { /* The selected handle remains usable for the rest of this tab. */ }
    updateSaveDestination();
    return handle;
  }

  async function savePrivateFolder() {
    if (state.saving || state.restoringFolder || !verifyBeforeExport()) return;
    const source = state.source;
    const cvFile = state.cvFile;
    const transcriptFile = state.transcriptFile;
    state.saving = true;
    updateNotices();
    updateSaveDestination();
    try {
      for (const [kind, file] of [['cv', cvFile], ['transcript', transcriptFile]]) {
        if (file && valueAt(`documents.${kind}`, source) !== file.name) {
          throw new Error(`Choose your ${kind} again to match the configured filename.`);
        }
      }
      if (!supportsFolderAccess) {
        downloadBlob(await window.createSetupArchive(source, cvFile, transcriptFile), 'application-filler-setup.zip');
      } else {
        const root = await repositoryDirectory();
        const directory = await root.getDirectoryHandle('private', { create: true });
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
        }
        if (cvFile) await write(cvFile.name, cvFile);
        if (transcriptFile) await write(transcriptFile.name, transcriptFile);
        await write('instructions.yaml', source);
      }
      state.filename = 'instructions.yaml';
      state.savedSource = source;
      state.dirty = state.source !== source;
      if (state.cvFile === cvFile) state.cvPending = false;
      if (state.transcriptFile === transcriptFile) state.transcriptPending = false;
      render();
      toast(supportsFolderAccess
        ? `Saved instructions.yaml${cvFile ? ' and your CV' : ''}${transcriptFile ? ' and your transcript' : ''} in ${state.repositoryHandle.name}/private/.`
        : 'Setup exported. Extract its private/ folder into your cloned repository.');
    } catch (error) {
      if (error.name !== 'AbortError') toast(`Could not save: ${error.message}`);
    } finally {
      state.saving = false;
      updateNotices();
      updateSaveDestination();
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

  function loadFile(source, filename) {
    source = source.replace(/^\uFEFF/, '');
    const previous = { ...state };
    state.source = source;
    state.languageRows = null;
    state.languageDraftDirty = false;
    const result = preflight();
    if (result.errors.length) {
      Object.assign(state, previous);
      toast(`File has configuration issues: ${result.errors[0]}`);
      return;
    }
    state.cvFile = null;
    state.cvPending = false;
    state.transcriptFile = null;
    state.transcriptPending = false;
    state.filename = filename || 'instructions.yaml';
    state.savedSource = source;
    state.dirty = false;
    state.section = 'profile';
    render();
    toast('Configuration loaded locally.');
  }

  async function openFile() {
    if (state.saving || state.restoringFolder) return;
    if ((state.dirty || state.cvPending || state.transcriptPending || state.languageDraftDirty) && !window.confirm('Discard unsaved changes and open another file?')) return;
    if (supportsFolderAccess) {
      state.saving = true;
      updateNotices();
      updateSaveDestination();
      try {
        const root = await repositoryDirectory();
        const directory = await root.getDirectoryHandle('private');
        const handle = await directory.getFileHandle('instructions.yaml');
        loadFile(await (await handle.getFile()).text(), 'instructions.yaml');
      } catch (error) {
        if (error.name !== 'AbortError') toast(error.name === 'NotFoundError'
          ? 'No saved configuration was found in private/. Fill in a new profile and save it.'
          : `Could not open the configuration: ${error.message}`);
      } finally {
        state.saving = false;
        updateNotices();
        updateSaveDestination();
      }
      return;
    }
    $('#file-input').click();
  }

  function verifyBeforeExport() {
    if (updateNotices()) return true;
    toast('Correct the highlighted configuration issues before saving.');
    return false;
  }

  // --- Lifecycle -----------------------------------------------------------

  $('#new-button').addEventListener('click', () => {
    if ((state.dirty || state.cvPending || state.transcriptPending || state.languageDraftDirty) && !window.confirm('Discard unsaved changes and start a new configuration?')) return;
    state.cvFile = null;
    state.cvPending = false;
    state.transcriptFile = null;
    state.transcriptPending = false;
    state.languageRows = null;
    state.languageDraftDirty = false;
    state.source = window.CONFIG_TEMPLATE;
    state.filename = 'instructions.yaml';
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
  if (!supportsFolderAccess) $('#save-folder-button').textContent = 'Export setup (.zip)';
  $('#save-folder-button').addEventListener('click', savePrivateFolder);
  $('#change-folder-button').addEventListener('click', async () => {
    state.saving = true;
    updateNotices();
    updateSaveDestination();
    try { await repositoryDirectory(true); }
    catch (error) { if (error.name !== 'AbortError') toast(error.message); }
    finally {
      state.saving = false;
      updateNotices();
      updateSaveDestination();
    }
  });
  $('#raw-text').addEventListener('input', (event) => {
    state.source = event.target.value;
    state.languageRows = null;
    state.languageDraftDirty = false;
    state.dirty = state.source !== state.savedSource;
    refreshHeader();
    updateNotices();
  });
  window.addEventListener('beforeunload', (event) => {
    if (!state.dirty && !state.cvPending && !state.transcriptPending && !state.languageDraftDirty) return;
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
  restoreRepository();
})();
