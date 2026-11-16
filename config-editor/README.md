# Optional configuration editor

A local, offline editor for Application Filler's `private/instructions.yaml` (version 2).

## Start

Open **`index.html`** in a modern browser. Double-clicking the file works on Windows, macOS, and Linux. You do **not** need Python, Node.js, Docker, a web server, or internet access to edit a configuration.

1. Click **Open configuration** and select your **cloned repository folder** the first time (the folder containing `config-editor/`, not `private/`). The editor opens `private/instructions.yaml` automatically. Use **New** for a blank configuration.
2. Enter plain text in the forms, without surrounding quotation marks. Short captions explain what to provide; empty text fields show example entries. Date fields follow the date order displayed by your browser. **?** appears where there is extra information to explain. Examples are suggestions and are never saved as your personal facts.
3. In **Documents & cover letters**, choose **Upload CV PDF** to select your existing CV (up to 10 MB). Optionally choose **Upload transcript PDF** for your transcript of records. Each selection updates its filename. No file is sent over the network or rewritten.
4. Press **Save to private/**. It writes `private/instructions.yaml` and the selected PDFs directly into the same repository, creating `private/` if necessary. The repository is remembered, so subsequent saves do not show a folder picker. If you started with **New**, choose the repository the first time you save. **Selecting a PDF does not itself copy it into the repository.** For documents already in `private/`, just enter their relative paths.
5. Validate before running the bot:

```sh
docker compose --env-file docker/compose.env run --rm --no-deps -T demo validate
```

The command above runs in the **application-filler-bot** directory, not the editor folder. The bot itself continues to run using the repository's Docker workflow.

## Languages, gender and veteran status

In **Personal information → Preferred cities**, enter one city per line, most
preferred first. Include a country where needed to distinguish a place name.
The editor stores the order in `candidate.preferred_work_locations`. When a form
offers only some cities from the list, the agent keeps their relative order.
**Other offered cities** controls whether it asks about unlisted cities or puts
them after the ranked choices in any order. Preferences do not establish visas
or work rights and do not override your relocation preference.

In **Languages**, add a language name and proficiency per row. Levels are plain
text, such as `C1/fluent`, `Native` or `Beginner`. Empty rows and duplicate language
names must be completed or removed before saving. The editor stores these pairs
directly under `candidate.languages`, alongside the other personal facts.

**Personal information** has a free-text **Gender** field and a **Veteran status**
selector. Gender can stay blank. Veteran status distinguishes **Veteran**, **Not a
veteran** and **Unknown / not supplied**; unknown is never converted into a No.
New configurations supply no languages, gender or veteran status by default.

The agent receives the complete candidate profile as facts in its model context.
For example, it can reference `candidate.languages.English` when answering an
English-proficiency question. It reads the actual question and available choices,
then uses the supplied level to choose a supported answer. This does not establish
language-test certification or a different proficiency you have not supplied.

Gender and veteran questions are subject to **Agent behavior → Personal disclosures**:

- **Ask me:** requests approval before answering, even when the fact is stored.
- **Use explicitly supplied facts:** allows relevant answers from the supplied profile;
  the bot should ask if the question's definition or choices need more information.
- **Skip this topic:** skips the question.

Storing these facts does not change the disclosure policy or submission permission.
Different questions, such as pronouns or a specific protected-veteran category,
must be interpreted separately rather than assumed from a broad profile entry.

## What to provide for cover letters

- **Factual background:** your degrees and dates, tools and methods you used, work or research, projects, your personal contributions and verified results, career interests and motivation. Copy relevant facts from your CV here; the bot does not extract them from the PDF. The field's example shows a possible structure, and **?** opens a checklist.
- **Example cover letters:** optional past letters that show your preferred voice. Paste a whole letter with line breaks per row, or enter a UTF-8 `.md`/`.txt` filename stored in `private/`. One-line entries are interpreted as filenames. Each example must be nonblank and at most 20 KB. Remove unused rows. Leave the list empty if you have none. These letters guide style, not factual claims.
- **Writing instructions:** preferred tone, word count, language, structure and which factual strengths to emphasise for different roles. Standard instructions are already filled in and can be edited. For example, emphasise evaluation for research roles and implementation/testing for engineering roles.

Enabled letters are supplied whenever the form offers a cover-letter field, including optional fields. Choose **Write and review before use** to approve them first, or **Skip cover letters** to disable them. Background and examples stay blank in new configurations.

## Transcript of records and answer defaults

The transcript is optional. Place it at `private/transcript.pdf`, enter another relative
PDF filename, or select it with **Upload transcript PDF**. Save copies the original
PDF alongside your CV and configuration. If the file is absent, the bot skips optional
transcript fields and asks you when one is required. It never substitutes the CV or
generates academic records. **Do not use a transcript** disables it without deleting files.

Under **Agent behavior**, **Default discovery source** is LinkedIn. It is used when
you have not supplied an actual source and the form accepts that option or free text.
If unavailable for a required question, the bot asks. **Default office attendance**
is Yes, including ordinary questions about days per week; explicit remote-only
preferences, day limits, location restrictions or other instructions override it.
Set either default to ask instead if preferred. Consent and review policies still apply.

## Saving across browsers

- **Chrome and Edge:** choose the cloned repository once when opening or saving. Configuration and selected CV/transcript PDFs are written into its `private/` subfolder; existing files with those names are replaced. The destination is shown above the form. **Change repository** lets you select it again.
- **Remembering the folder:** the browser stores the granted directory handle in IndexedDB, separately for each checkout's editor URL. Reloading the editor restores the destination. The browser may ask you to renew permission after a restart or revocation; no new folder selection is needed while the handle and permission remain valid. If browser storage is blocked, the folder is reused for the current tab.
- **Firefox, Safari or other browsers without direct folder access:** the same primary action becomes **Export setup (.zip)**. It exports one archive containing `private/instructions.yaml` and selected PDFs. Extract its `private/` folder into your cloned repository. There are no separate configuration or PDF download buttons.
- Knowing that `private/` is next to `config-editor/` does not grant browser write access. A browser page still needs one initial folder selection. No server, Python installation, extension or container is needed for the editor.
- **Ctrl+S / Cmd+S** uses the same save action.

## Data and behavior

- No network calls, CDN, cookies or analytics. All processing happens in the browser. Only the selected repository's directory handle is remembered in IndexedDB; candidate facts, configuration contents, PDFs and API keys are not cached there.
- Personal information is **not embedded** into the editor. The default template has blank personal fields.
- A bundled YAML parser handles quoted values, lists and multiline text offline. Document edits preserve comments and other candidate facts, though formatting may change. Edited multiline values use literal blocks.
- **Advanced file editor** lets experienced users edit the complete configuration file. Checks use a generated copy of the bot's strict settings schema, including allowed keys, choices, numeric bounds and file-size limits. Custom factual keys belong under `candidate`; unknown settings elsewhere are rejected by the bot. Guided fields handle file formatting automatically.
- The editor cannot check that a referenced file already exists in `private/`. Always run `demo validate` for authoritative bot-side validation, including referenced example-letter files.
- The editor always uses a light theme, including native fields and the file editor, even when your system prefers dark mode.
- Do not add secrets (such as your Anthropic API key) to `instructions.yaml`. Follow the repository's `.secrets/anthropic_api_key` setup.

## Source files

```text
config-editor/
├── index.html    # page structure
├── styles.css    # responsive styling
├── schema.js     # field metadata, help, fictional examples and blank template
├── contract.js   # generated JSON Schema from the bot's Settings models
├── app.js        # YAML document edits, validation and local file handling
├── folder-store.js # remembers the granted repository handle for each checkout
├── archive.js    # combined setup export for browsers without folder access
├── vendor/       # offline YAML parser, license and rebuild instructions
├── tests/        # local browser and bot-loader regression tests
└── README.md
```

No build step or dependency installation is required to use the editor. The YAML
parser and its license are included; see [vendor/README.md](vendor/README.md).

For maintainers changing `src/application_filler/config.py`, regenerate the checked-in
schema using the development environment:

```sh
uv run --frozen python scripts/update_config_editor_schema.py
```

This is a development task only. Users run the editor directly in their browser
and run the bot/validator in Docker; they do not need host Python.

The editor is not copied into Docker images. Its regression tests run separately
from a local source checkout using the project's development dependencies:

```sh
uv run --frozen --extra dev playwright install chromium
uv run --frozen --extra dev pytest config-editor/tests
```

These tests open `index.html` directly with browser networking disabled, check
exports with the bot's configuration loader, and exercise local PDF handling.
