# Application Filler

A browser agent that fills job applications from your links, personal facts and instructions.
**Claude Haiku 5.5 decides the actions**, using Anthropic's native browser toolset to
follow Apply links, navigate form steps, fill fields and upload documents. The browser
runs in Docker. Applications needing missing information, a login or an unsupported
interaction are flagged for your attention.

- **CV:** provide your own PDF. The agent uploads it unchanged; it does **not write,
  edit or tailor CVs**.
- **Cover letters:** optional automatic writing from your supplied background and
  instructions. The agent can enter a letter into a textbox or generate Markdown
  and a PDF for upload. You can require approval or disable this feature.
- **Submission:** manual by default; automatic submission is an explicit option.

The intended starting workflow is **interactive, with a visible browser and manual
submission**: configure your profile once, give it a few job links, answer any questions,
then review the completed forms before submitting. Website compatibility varies;
this is not a guarantee that every application can be completed unattended.

## 1. Install and initialize

You need Git and [Docker with Compose](https://docs.docker.com/compose/install/), running
Linux containers. Docker Desktop is suitable for Windows and macOS; Docker Engine
with the Compose plugin works on Linux. On Linux, your normal user must have access
to Docker. Python, **uv**, Chromium and PDF dependencies run inside the image; no
host Python installation is needed.

```sh
git clone https://github.com/3nomerci/application-filler-bot.git
cd application-filler-bot
```

**macOS / Linux:**

```sh
sh scripts/setup.sh
```

**Windows PowerShell:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Setup builds the images and creates `private/instructions.yaml` and `private/links.txt`.
It preserves existing personal files. On macOS/Linux it also creates an ignored
`compose.override.yaml` to match container users to your file ownership. Keep this
machine-specific file local. The remaining commands work in all three environments.

Run the free installation check:

```sh
docker compose --env-file docker/compose.env run --rm --no-deps -T demo self-test --headless
```

This uses fictional data, a local website and a scripted model. It exercises the
native browser executor without an API key or paid calls.

## 2. Enter your information and instructions

**Edit `private/instructions.yaml` in a text editor.** It is your local copy of the
[annotated template](examples/instructions.yaml). Edit the private copy, not the
public template. Nothing in the template claims a nationality, qualification or
personal status for you.

| Section | What to provide |
|---|---|
| `candidate` | Contact details, profile links, address, citizenships, existing work rights, relocation preference, availability and education. Add other factual keys if useful. |
| `instructions` | General preferences: jobs/locations you want, office or remote preferences, information the agent may infer, and when it should ask you. |
| `answers` | Whether to infer or ask, plus rules for salary, work authorization, disclosures, cookies and consent. |
| `salary` | Market or lower supported estimate, your minimum with currency/pay units, and any additional requirements. |
| `documents` | CV filename and optional cover-letter background, examples and writing instructions. |
| `submission` | `manual` to review and submit yourself, or `auto` to allow the agent to submit. |
| `model` / `browser` | API cost/call limits and browser action limits. Start with the supplied values. |

Replace the corresponding values in your private file with your own facts. This is
a fictional example, **not a complete configuration to paste over the template**:

```yaml
candidate:
  full_name: "Alex Example"
  email: "alex@example.com"
  phone: "+12025550123"
  linkedin: "https://www.linkedin.com/in/your-profile"
  github: "https://github.com/your-account"
  citizenships: [CA]
  residence_country: CA
  relocation: "Open to relocating within Canada"
  date_of_birth: null

instructions: >-
  Prefer backend engineering roles. I am willing to work in an office.
  Ask about anything not supported by my facts or these preferences.
```

Use quoted `"YYYY-MM-DD"` dates. Leave unknown facts blank or `null`; unknown does
not mean “No.” Use your own wording: the agent maps it to the form's choices, so you
do not need to know each website's exact labels. YAML indentation matters. Comments
starting with `#` explain the file to you; write instructions for the agent as actual
values under `instructions`, `salary.instructions` or `documents.instructions`.

### CV and optional cover letters

Put your finished CV at **`private/cv.pdf`**, or change `documents.cv` to another
PDF filename inside `private/`. There is no CV generation, rewriting or LaTeX workflow.

To use automatic cover letters, fill in `documents.background` with truthful skills,
experience and achievements, and edit `documents.instructions` for tone, language
and length. The agent does **not extract this background from your CV**. Optionally
place example letters in `private/` and list their filenames:

```yaml
documents:
  cv: cv.pdf
  cover_letter: trusted
  background: >-
    I build Python services. My recent project reduced batch processing time
    from 20 minutes to 8 minutes. Include only experience I have supplied.
  examples: [example-letter.md]
  instructions: >-
    Write a concise letter tailored to the role. Use a direct tone and avoid
    invented qualifications. Keep it under 300 words unless the form asks otherwise.
  retention: keep
```

Only list example files that exist; use `examples: []` if you have none. Examples
guide style, not factual claims. `cover_letter: review` requests approval before use;
`cover_letter: skip` disables writing. `retention: delete_after_run` deletes generated
Markdown/PDF files after the run; it never deletes your CV or examples. Generated
file letters are stored under `artifacts/documents/`; textbox letters are entered directly.

### Defaults in the supplied configuration

| Setting | Default behavior |
|---|---|
| `answers.mode: trusted` | Infer answers supported by your facts, instructions and permitted research. |
| Work authorization / salary: `infer` | Research relevant evidence; ask if facts, country, pay units or evidence are insufficient. Salary strategy is `market`; `low` chooses a supported lower estimate. |
| Personal disclosure / consent: `ask` | Ask before answering sensitive disclosures or accepting declarations. This overrides general trust. |
| `answers.cookies: accept_when_needed` | Accept cookies needed to access the application; prefer rejecting unnecessary optional cookies. |
| `answers.protected_category: negative_or_skip` | For employment protected-category questions, answer No only when `candidate.protected_category_member` is explicitly `false`; skip when `true`; ask when unknown. Other disclosure rules stay separate. |
| `documents.cover_letter: trusted` | Write a letter when requested, if you supplied enough factual background. |
| `navigation.handoffs: trusted` | Follow relevant public HTTPS recruiting-site handoffs without per-host setup. |
| `submission: manual` | Leave the final submission to you. |
| Model budget | $0.50 estimated per run, 40 calls per application, 100 calls per run, up to 6 web searches per application. These are local limits, not a provider billing guarantee. |

To always ask about salary, change the existing `answers.topics.salary` value to
`ask`. To review all inferred answers, set `answers.mode: review`. To preauthorize
a declaration, describe precisely what you accept under `instructions` and change
the appropriate topic policy. Trust permits supported inference, not invented facts.

## 3. Add your API key and job links

Real runs require an Anthropic API account with credits and access to the pinned
`claude-haiku-5-5` model and `browser_toolset_20260801`.

Using a text editor, create **`.secrets/anthropic_api_key`** and paste only your key
into it. Save as plain text with that exact filename, without a `.txt` extension.
Setup already created the folder. Keep the key out of YAML, source code and chat.
On macOS/Linux, restrict access to the file:

```sh
chmod 600 .secrets/anthropic_api_key
```

Compose runs two containers during real applications: **agent**, containing Chromium,
and **gateway**, which reads the key and forwards model requests. The browser container
never receives the key file or key environment variable. Both run on your computer;
Compose starts and connects them for you. Your configured facts and page observations
are sent to Anthropic; information entered/uploaded on applications reaches the websites.

Put one job URL per line in **`private/links.txt`**. Listing pages with an Apply button
are allowed; you do not have to find the final form. Lines starting with `#` are ignored.
Start with one or two links. A general application with no specified role uses a
Free/Open Application option when one is available.

Validate your file without making API calls:

```sh
docker compose --env-file docker/compose.env run --rm --no-deps -T demo validate
```

## 4. Run, review and submit

```sh
docker compose --env-file docker/compose.env run --rm --service-ports agent run --links private/links.txt --interactive
```

Open **http://localhost:6080/vnc.html** and connect using the temporary viewing
password printed in the terminal. This is the container's browser, separate from
your usual browser. Answer questions in the terminal. Wait for the agent's input
or final-review prompt before editing its browser yourself.

With the default `submission: manual`, review and submit in this browser **before
pressing Enter to close the run**. Closing the container discards forms and logins.
The tool does not save sessions for resuming later. Reports are saved in `artifacts/`.

Each checkbox approval shows one actual checkbox label and a proposed **Check** or
**Uncheck** choice. Answer `y` or `yes` to approve that choice only; `n`, `no` or
Enter declines it and leaves the field unchanged. Use `/quit` to stop. Required
privacy consent and optional future-job contact consent are separate decisions.
Your approval follows that exact field and value through the browser tools; it does
not authorize other checkboxes or final submission.

To practice with the real model on fictional forms (**uses credits**, including a
local fake submission):

```sh
docker compose --env-file docker/compose.env run --rm --service-ports agent run --demo --interactive
```

For unattended operation, omit `--interactive`; unanswered questions become blocked
reports and the batch continues. Add `--headless` to hide the browser. Set
`submission: auto` explicitly if you want final submission without review; otherwise
filled forms disappear when a headless run ends. The agent records submission
attempts to avoid automatically retrying uncertain submissions.

When finished:

```sh
docker compose --env-file docker/compose.env --profile live down
```

If you replace the key, reload it with
`docker compose --env-file docker/compose.env up -d --force-recreate gateway`.
The explicit `--env-file` keeps Compose from loading an unrelated local `.env`.

## Limitations and development

Logins, CAPTCHAs, missing preferences and some widgets need human help. The agent
does not create accounts, take interviews/assessments or bypass bot protection.
Docker isolates the browser environment; it does not guarantee correctness or make
all website interactions safe. Start with manual review and a provider-side spending
limit. Keep `private/`, `.secrets/`, `artifacts/` and local overrides out of Git; they
are ignored and excluded from Docker build inputs.

Python dependencies are managed with **uv**. For development, use
`uv sync --frozen --extra dev`, `uv run --frozen ruff check src tests` and
`uv run --frozen ruff format --check src tests`. Run the browser regression suite in Docker:

```sh
docker compose --env-file docker/compose.env build test
docker compose --env-file docker/compose.env run --rm --no-deps -T test
```

Tests and the free self-test make no paid API calls. `run --demo` and real applications do.
No project license has been assigned yet. Third-party notices are in
[docker/NOTICE.md](docker/NOTICE.md).
