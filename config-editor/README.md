# Optional configuration editor

A local, offline editor for Application Filler's `private/instructions.yaml` (version 2).

## Start

Open **`index.html`** in a modern browser. Double-clicking the file works on Windows, macOS, and Linux. You do **not** need Python, Node.js, Docker, a web server, or internet access to edit a configuration.

1. Click **Open YAML** and choose your existing `private/instructions.yaml`, or use **New** for a blank configuration.
2. Edit settings using the forms. Every field shows guidance and example YAML; **?** opens additional help. Examples are fictional; replace them with your own facts rather than treating them as defaults.
3. In **Documents & cover letters**, choose **Upload CV PDF** to select your existing CV (up to 10 MB). This sets `documents.cv` to the selected filename. No file is sent over the network or rewritten.
4. Where available, choose **Save to private/** and select the repository's `private/` folder to write `instructions.yaml` and the selected PDF together. Otherwise choose **Save file** or **Download** for YAML, and **Download selected PDF** for the CV. Move both to `private/`. **Selecting a PDF does not itself copy it into the repository.** If your CV is already in `private/`, you can just enter its relative path.
5. Validate before running the bot:

```sh
docker compose --env-file docker/compose.env run --rm --no-deps -T demo validate
```

The command above runs in the **application-filler-bot** directory, not the editor folder. The bot itself continues to run using the repository's Docker workflow.

## What to provide for cover letters

- **Factual background:** your degrees and dates, tools and methods you used, work or research, projects, your personal contributions and verified results, career interests and motivation. Copy relevant facts from your CV here; the bot does not extract them from the PDF. The field's example shows a possible structure, and **?** opens a checklist.
- **Example cover letters:** optional past letters that show your preferred voice. Paste a whole letter with line breaks per row, or enter a UTF-8 `.md`/`.txt` filename stored in `private/`. One-line entries are interpreted as filenames. Each example must be nonblank and at most 20 KB. Remove unused rows. Leave the list empty if you have none. These letters guide style, not factual claims.
- **Writing instructions:** preferred tone, word count, language, structure and which factual strengths to emphasise for different roles. For example, emphasise evaluation for research roles and implementation/testing for engineering roles.

Choose **Review before use** if you want to approve generated letters, or **Skip cover letters** if you do not want them. Background and examples stay blank in new configurations.

## Saving across browsers

- **Chromium-based desktop browsers** may offer direct file and folder selection/writing through the File System Access API. The browser asks for permission. Select the repository's `private/` folder for **Save to private/**; existing `instructions.yaml` and a selected CV with the same name are replaced there.
- **Firefox and Safari** generally use the import/download fallback. They can still use the editor without a server.
- The editor cannot silently modify `private/instructions.yaml`. The user explicitly selects or replaces the file.

## Data and behavior

- No network calls, CDN, cookies, local storage or analytics. All processing happens in the browser.
- Personal information is **not embedded** into the editor. The default template has blank personal fields.
- A bundled YAML parser handles quoted values, lists and multiline text offline. Document edits preserve comments and other candidate facts, though formatting may change. Edited multiline values use literal blocks.
- The **Raw YAML** tab lets advanced users edit the complete file. Checks use a generated copy of the bot's strict settings schema, including allowed keys, choices, numeric bounds and file-size limits. Custom factual keys belong under `candidate`; unknown settings elsewhere are rejected by the bot.
- The editor cannot check that a referenced file already exists in `private/`. Always run `demo validate` for authoritative bot-side validation, including referenced example-letter files.
- Light and dark themes follow your system preference, including fields, examples and notices.
- Do not add secrets (such as your Anthropic API key) to `instructions.yaml`. Follow the repository's `.secrets/anthropic_api_key` setup.

## Source files

```text
config-editor/
├── index.html    # page structure
├── styles.css    # responsive styling
├── schema.js     # field metadata, help, fictional examples and blank template
├── contract.js   # generated JSON Schema from the bot's Settings models
├── app.js        # YAML document edits, validation and local file handling
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
