# Application Filler: operation and engineering guide

The [README](README.md) is the quick start. This is the single extended guide.

## How the agent works

Every real application uses Haiku as the decision-maker. It receives your configured
facts and permissions, visible page text and structured controls. It chooses whether
to open Apply, navigate, answer, upload, research, ask, submit or stop. After each
action it gets a fresh observation. It can recover from changed controls or rejected
actions by inspecting the page and choosing another supported action.

```text
Your links + instructions + candidate facts
                    |
                    v
        Haiku chooses next action <------- updated page / tool result
                    |                                  ^
                    v                                  |
         Permission checks -> browser/document tools ---+
                    |
          ready / submitted / blocked report
```

Python performs mechanical work: copying an explicitly selected fact, filling and
checking a control, attaching a PDF, rendering Markdown, enforcing approvals and
limiting requests. It does not route questions through a rules-first answer engine.
Exact copying and batched fills save tokens without replacing Claude's decisions.

Claude gets `read_page`, `click`, `navigate`, `answer_fields`, `request_input`,
`create_cover_letter`, `upload_document`, `submit_application` and `complete`, plus
Anthropic's hosted search/fetch when enabled. There is no shell, arbitrary JavaScript
execution, arbitrary file reader or key reader exposed to the model.

The executor supports native inputs/selects, labelled radio/checkbox groups,
accessible custom dropdowns, contenteditable inputs, open shadow DOM, visible frames,
popups and multi-step forms. It is a **DOM-based agent**, not a screenshot/coordinate
computer-use agent. Canvas controls, closed shadow roots and inaccessible widgets
can block it. Universal compatibility is a goal, not a guarantee.

## Docker explained

Docker packages Python, uv, Chromium and Linux libraries together. Docker Desktop
runs those containers on your computer. The browser at localhost is the container's
Chromium, not your usual Windows browser; it has no saved Windows browser passwords.

An **image** is an installed software template; a **container** is a running copy.
**Compose** starts related containers using `compose.yaml`. A **bind mount** exposes
a specific host folder inside a container:

| Service | Purpose | Host files mounted |
|---|---|---|
| `agent` | Agent, Chromium, optional viewer | `private/` read-only; `artifacts/` writable |
| `gateway` | Authenticated requests to Anthropic | Only the API secret file |
| `demo` | Offline scripted demo and validation | Same data mounts as agent; no key |
| `setup` | Initialize/migrate instructions | `private/` writable, only for setup; no key |
| `test` | Automated tests with fictional data | No host data/secret mounts |

Containers run as non-root, drop outer Linux capabilities, use read-only root
filesystems and writable temporary memory. Chromium's own sandbox remains enabled.
The seccomp policy permits its namespace/chroot operations. No privileged mode,
Docker socket, host networking or disabled sandbox is used. The viewer is published
only at `127.0.0.1:6080`; the gateway has no host port. Browser profiles disappear
when the container stops.

Docker provides useful containment, not perfect isolation. Keep Docker Desktop
updated; host administrators and people with Docker access remain powerful.

### Setup and everyday operation

Run commands from this repository. The first build downloads substantial browser
and Linux packages. Later runs reuse the images.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose --env-file docker/compose.env run --rm --no-deps -T demo self-test --headless
```

The PowerShell execution-policy flag applies only to that invocation. Setup creates
directories, builds images and initializes/migrates instructions. It does not read
or create an API key. The self-test is free and does not contact Anthropic.

| Flag | Meaning |
|---|---|
| `--env-file docker/compose.env` | Use the deliberate empty environment file, ignoring any old `.env`. |
| `run` | Create a container for a command and start its required services. |
| `--rm` | Remove that container on exit; preserve host folders. |
| `--service-ports` | Publish the configured local viewer port. |
| `--no-deps` | Do not start related services; used for key-free tests/validation. |
| `-T` | No terminal allocation. Omit for interactive use. |
| `--headless` | Application option: no browser display/viewer. |

Visible interactive batch:

```powershell
docker compose --env-file docker/compose.env run --rm --service-ports agent run --links private/links.txt --interactive
```

One URL directly:

```powershell
docker compose --env-file docker/compose.env run --rm --service-ports agent run "https://employer.example/jobs/123" --interactive
```

Unattended and headless:

```powershell
docker compose --env-file docker/compose.env run --rm -T agent run --links private/links.txt --headless
```

Use `submission: auto` if the unattended run should submit. Manual + headless can
fill and report, but forms disappear at exit: reports cannot restore them. Visible
runs with an attached terminal wait at the end for your review/manual submission.

Run one batch at a time. This simplifies viewer access and submission bookkeeping.
Up to 20 URLs are accepted; each gets an isolated browser context. Blocked applications
do not cancel the others, although a run-wide budget can also block later URLs.
Use Alt+Tab inside the viewer to switch Chromium windows if needed.

Service state and shutdown:

```powershell
docker compose --env-file docker/compose.env ps
docker compose --env-file docker/compose.env --profile live down
```

After source/dependency/Dockerfile edits, rebuild:

```powershell
docker compose --env-file docker/compose.env build demo gateway
```

Agent and demo share the runtime image. Changes to private YAML, CV or links need
no rebuild; the next run reads the mounts. Recreate the gateway after changing keys.

### Viewing the browser and answering questions

Open http://localhost:6080/vnc.html and enter the temporary viewing password printed
in the terminal. This local VNC password is **not your API key**. Keep port 6080 local;
do not forward it through your router.

With `--interactive`, questions appear in the terminal. Supply missing answers,
approve proposals, or finish a login/challenge yourself in the browser and continue.
For missing-answer prompts, blank leaves it unresolved and `/quit` stops the run.
For approval prompts, `y` approves. Without interactive mode, a question flags that
application and moves to the next URL. With headless + interactive you can answer
terminal questions but cannot see a browser to finish a CAPTCHA/login.

Wait for an input or final-review prompt before editing browser fields yourself.
Changed-control checks reduce races but do not make concurrent human edits safe.

### Linux and macOS

Run `sh scripts/setup.sh`. Docker Desktop normally handles mount permissions on
Windows/macOS. On native Linux, use `--user "$(id -u):$(id -g)"` on agent/demo runs
so output files belong to your host user. Do not make the project world-writable
or run a privileged browser to solve permission errors. Windows/Docker Desktop is
the primary tested end-user workflow.

## API key and privacy

Create `.secrets/anthropic_api_key` yourself in a text editor. It contains only the
key: no variable name, quotes or JSON. Use Notepad's **All files** save option if
necessary to avoid `.txt`. Never paste its contents into chat or commands.

Compose mounts it at `/run/secrets/anthropic_api_key` **only in the gateway**. The
gateway keeps it in memory and adds the `x-api-key` header for a fixed Anthropic
HTTPS endpoint. The agent knows only the gateway address. Neither Claude's prompt
nor Chromium receives the key. Provider error bodies are sanitized. The gateway
rejects browser-origin/non-JSON requests and is not a general URL proxy.

`.secrets/`, `private/`, `artifacts/` and environment files are Git-ignored and excluded
from the Docker build context.

Local Compose secrets are **ordinary files on disk**, not an encrypted secrets vault.
Someone with sufficient Windows or Docker permissions can read them. Your gateway
and Anthropic must access the key to authenticate requests. The protection separates
it from the agent/tools/websites; it cannot promise no other process could ever read it. I reccomend to set a spending limit on the provider side! You can switch off auto-reload so that API requests will stop when your balance runs out, set a monthly spend limit from the billing section, set a virtual card as payment method with limited credit. Note: the default monthly spend limit is now 200000$ (set by Anthropic).

Keep `.secrets/` out of shared/cloud folders you do not trust. If exposed, revoke the
key in Anthropic's console, replace the file and recreate the gateway.

**Candidate data is separate from the API credential.** Anthropic receives configured
facts, background, style examples, visible page text and form values. Websites get
entered answers and PDFs; some autosave **before** final submission. This project
does not parse the fixed CV or send its PDF to Claude, but uploads it to the selected
application site. Provide letter-writing facts in `documents.background`.

The prompt prohibits identity/contact/health information in research queries. This
is an instruction to the model, not provable data-loss prevention around hosted
search. Provide only the candidate facts you need for these applications.

Reports omit raw transcripts, thinking content, keys and full entered field values.
They still contain reasons, questions, source URLs, salary evidence and generated
letters. A model-written reason can include personal information; `artifacts/`
remains private and reports are not automatically anonymized.

## Environment variables

An environment variable is a named value supplied to a process. It is not inherently
encrypted or secret. This application deliberately keeps the API key out of them.
You do not need an `.env` file.

| Variable | Set by | Purpose |
|---|---|---|
| `MODEL_GATEWAY_URL` | Compose | Internal `http://gateway:8765`; contains no key. |
| `GATEWAY_MAX_REQUESTS` | Compose | Secondary limit: 200 requests per gateway lifetime. Restarts reset it. |
| `FILLER_IN_DOCKER` | Image | Normal Docker execution path; not a security boundary. |
| `DISPLAY`, `HOME` | Image | Container virtual display and temporary home. |
| `PLAYWRIGHT_BROWSERS_PATH` | Image | Installed Chromium directory. |
| `UV_CACHE_DIR` | Image/developer shell | uv dependency cache. |

`docker/compose.env` contains only comments. Specifying it avoids loading an old
workspace `.env`. `ANTHROPIC_API_KEY` shell variables are ignored; only the secret
mount authenticates the gateway. Chromium receives a small OS/display environment.

## Instructions and trust

`examples/instructions.yaml` is the public blueprint. Setup copies it to
`private/instructions.yaml`, which you customize without putting facts in public
source. Unknown configuration keys and duplicate YAML keys are rejected.

```powershell
docker compose --env-file docker/compose.env run --rm --no-deps -T demo validate
```

YAML comments are for you and disappear during parsing. Required model guidance
belongs in actual values: `instructions`, `salary.instructions` and
`documents.instructions` are all sent to Claude.

`candidate` accepts additional factual keys: skills, education, availability,
explicit disclosure answers and so on. Leave unknown facts empty/null. Use your own
wording: `relocation: "Yes"` can map to "Yes, I am open to relocating" on a site.
You do not need its exact option wording in advance.

### Inference and exceptions

```yaml
answers:
  mode: trusted
  topics:
    work_authorization: infer
    salary: infer
    personal_disclosure: ask
    consent: ask
submission: manual
```

`trusted` allows supported inference; `review` asks before inferred answers.
Topic-level `ask` applies even when trusted. `skip` leaves that topic unanswered.
Supported topics are those shown above; omitted sensitive topics retain their ask
default. Required unanswered fields block completion/submission.

To preauthorize a disclosure, put your explicit answer in `candidate`, explain its
meaning under `instructions`, and set `personal_disclosure: infer`. The agent may
match wording, but must not invent your gender, disability or other personal facts.
Before enabling inferred consents, specify exactly which terms/declarations you
accept. Consent defaults to asking. Trust does not imply fabrication.

Explicit scalar facts can be copied without inference approval. Derivations require
review when configured. Approval tokens bind the question and answer; approval for
one field cannot be reused for another. Proposed answers can be approved with `y`,
so you do not have to type the site's exact option label.

### Citizenship and work authorization

The blueprint sets `citizenships: [IT]` for Italian nationality, change it if needed. Nationality does not establish residence or possession of a visa; supply
those facts separately. "European role" is insufficient: actual work country matters.

The model is instructed to consult official guidance for inferred answers and
distinguish right to work, sponsorship, visa possession and registration. EU rights
should not be extended indiscriminately to UK/non-EU roles. Ambiguity requires input.
This is research-assisted reasoning, not a static immigration database or a legals
determination.

### Expected salary

`salary.strategy: market` selects a supported central estimate; `low` selects a
defensible lower part of relevant compensation. Both use current evidence. An optional
minimum needs full units, e.g. `"EUR 50000 gross annual base"`.

Claude must establish role, seniority, location, contract, currency, gross/net,
base/total and annual/monthly/hourly basis. Prefer a relevant advertised band; ask
when comparisons or units are weak/unclear. Inferred salary and authorization answers
require source URLs from actual hosted search/fetch results in the current application.
Salary also requires structured amount and pay units. The executor does not independently
audit whether the market estimate is economically sound; that remains model judgment.

Set `model.web_searches_per_application: 0` to disable research tools. Answers that
require research then need user input. Source URLs and salary evidence go in reports.

### CV and cover letters

`documents.cv: cv.pdf` refers to `private/cv.pdf`, an existing PDF within the private
directory, at most 10 MB. It is uploaded unchanged. CV editing, LaTeX compilation and
resume parsing are outside this version and may be added in the future.

Use `documents.background` for truthful experience and `documents.instructions` for
writing preferences. Optional `.md`/`.txt` examples in `private/` influence style, not
facts. Claude writes Markdown; Python renders a local PDF with Unicode fonts. The
restricted renderer handles paragraphs/headings and plain list lines; it does not
execute arbitrary HTML or fetch external images/assets.

`documents.cover_letter` is `trusted`, `review` or `skip`. Review mode prints the file
location and asks before upload. Open the generated file in host `artifacts/`
(container `/app/artifacts/` maps there). Letter text in a form uses field-specific
approval. Missing factual background should trigger a question, not invented experience.

`retention: keep` saves Markdown/PDF under `artifacts/documents/<application-id>-<run-id>/`.
`delete_after_run` deletes only generated files when the run ends, after any visible
review. It never deletes your fixed CV/examples. Forced termination can interrupt cleanup.

### Navigation and submission

`navigation.handoffs: trusted` follows public HTTPS handoffs/embedded forms without
requiring a host list. Claude checks their relation to the job/employer. `ask` requires
approval for new navigation hosts; `allowed_hosts` preapproves them. The initial supplied
host is already authorized. Asset hosts do not each require separate approval.

`submission: manual` is independent of answer/letter trust. The last button is left
to you. `auto` authorizes one final attempt after checks. Claude reads the outcome
and must quote a newly observed acceptance statement; you configure no success phrase.

Before clicking, an attempt is reserved in `artifacts/submission-ledger/`. Timeouts
and uncertain results are never automatically retried. The same canonical input URL
cannot automatically submit again while its ledger entry exists. This is not resume
support and cannot deduplicate different URLs for one vacancy or manual submissions.
Verify employer status before manually removing a ledger entry; never clear the
ledger routinely just to rerun a batch.

Manual final-button guards are defense in depth: sites can attach submission side
effects to arbitrary controls and may autosave. They are not an absolute guarantee
against any possible website behavior. Trust permits model decisions but leaves
configured approvals, budgets and restricted tool capabilities in force.

## Model and costs

The client, schema and gateway pin **`claude-haiku-5-5`**.
There is no automatic model/provider fallback. Official sources:
[overview](https://platform.claude.com/docs/it/models/haiku-5-5/overview),
[IDs/versioning](https://platform.claude.com/docs/it/about-claude/models/model-ids-and-versions),
[prompting](https://platform.claude.com/docs/it/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5),
[thinking](https://platform.claude.com/docs/it/build-with-claude/thinking).

Adaptive thinking uses medium effort with omitted thinking display. Full assistant
blocks, including thinking signatures and hosted tool results, are preserved for the
next request. Temperature/top-p/top-k are not set.

| Limit | Default | Scope |
|---|---|---|
| `max_output_tokens` | 8192 | Response, including thinking; partial actions are not executed. |
| `max_request_chars` | 240000 | Whole serialized request; local cap, not model context size. |
| `max_calls_per_application` | 40 | One application. |
| `max_calls_per_run` | 100 | Whole batch. |
| `estimated_budget_usd` | 0.50 | Local estimated batch cost. |
| `web_searches_per_application` | 6 | At most two search/fetch uses per request. |
| `browser.max_actions` | 100 | Browser actions per application. |

Current limits allow thinking, tool schemas, instructions and job
context. Superseded browser snapshots are compacted. Instructions and full assistant
content are preserved; exceeding the request budget stops instead of silently dropping
important instructions.

As checked in the linked Anthropic docs, normal pricing is $0.10/million input and
$0.50/million output tokens up to 100k input. The higher-context tier is $0.50/$2.50.
Estimates account for that threshold and cache read/write rates. Hosted search costs
**$0.01 per search plus tokens**; fetch has no additional tool fee, but fetched text
uses tokens. Search can dominate a cheap model's bill. See
[search pricing](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
and [fetch pricing](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool).

The local budget is **not a hard billing cap**: research can add tokens, a failed
request may be billed, and provider prices may change. Successful usage updates the
estimate; errors consume a conservative reservation without automatic retry. Configure
provider-side limits/alerts where available.

## Reports and troubleshooting

`artifacts/run-<UTC timestamp>.json` contains per-application outcomes, research
sources, usage and estimated cost. It is updated after each application.

| Status | Meaning |
|---|---|
| `ready_for_review` | Filled, waiting for final review/submission in the open browser. |
| `submitted_confirmed` | Agent attempted submission and observed a new acceptance statement. |
| `blocked` | Input, unsupported UI, permission, budget, browser or provider problem. |
| `submission_unverified` | An attempt occurred; inspect before considering another submission. |

`input_number` identifies a link's position. Hashes and hosts identify applications
without storing potentially token-bearing full URLs. Exit codes: 0 all ready/confirmed;
2 some blocked/unverified; 1 setup/configuration error; 130 interrupted. Manually
submitting during the final review wait does not relabel the agent's earlier report.

| Problem | Action |
|---|---|
| Docker engine unavailable | Start Docker Desktop, wait, check `docker info`. |
| Secret missing | Save the exact filename without `.txt`. Never paste the key into logs/chat. |
| Provider failed | Check credits, model access and key yourself; gateway startup logs are sanitized. |
| Port 6080 occupied | Finish the previous viewer run; use one visible batch at a time. |
| Browser startup failed | Rebuild/update Docker and check sandbox support. Do not disable the sandbox. |
| Input needed unattended | Rerun interactively if no submission attempt occurred. |
| Previous attempt recorded | Check employer status before any manual ledger reset. |
| Version 1 instructions | Run setup; inspect the migrated YAML and timestamped backup. |

Migration preserves candidate facts and known submission/ask choices; the complete
old file is backed up. It cannot translate every old rule/document preference into
agent instructions. Copy additional preferences from the backup into the new schema.
Fresh installs copy the commented blueprint; migration writes YAML values without
preserving comments. Already-version-2 files are left unchanged.

### Anti-bot behavior and security limits

The agent works sequentially with a configurable settling delay. It does not rotate
proxies, spoof fingerprints or simulate elaborate mouse movements. Those techniques
add complexity and cannot guarantee acceptance. Docker does not hide your public IP.
Sites may restrict automation at any volume. Respect access rules and complete
challenges yourself; the tool does not bypass them.

HTTPS/private-address checks, blocked WebSockets and bounded tools reduce exposure.
They are **not a complete egress firewall**: DNS changes, redirects and website code
are difficult to constrain fully through browser routing alone. Prompt injection
also remains a risk. Key separation reduces the consequences, but Claude can still
misinterpret a malicious public page and disclose candidate data. Prefer known job
links, try review mode first, and provide only facts needed for the applications.

## Testing and development with uv

Docker installs Python dependencies with `uv sync --frozen` using `uv.lock`. No
Windows Python installation is needed for ordinary use.

Free smoke test:

```powershell
docker compose --env-file docker/compose.env run --rm --no-deps -T demo self-test --headless
```

Full tests in sandboxed Docker Chromium:

```powershell
docker compose --env-file docker/compose.env build test
docker compose --env-file docker/compose.env run --rm --no-deps -T test
```

Tests use fictional pages and mocked responses, covering Apply/redirect/multiple
steps, native/custom controls, uploads, PDFs, submission guards, approvals, source
provenance, protocol, budgets and key isolation. They do not measure live model quality.
CI runs without secrets. The README's `agent run --demo --interactive` performs a
**paid real-Haiku trial**, using a fictional profile and a local site only. It permits
submission to that local fixture and uses the default $0.50 estimated budget.

Developer tooling: `uv sync --frozen --extra dev`, then
`uv run --frozen ruff check src tests` and
`uv run --frozen ruff format --check src tests`. `--dev-local` is an explicit development
escape hatch, not the end-user workflow; local key environment variables are still
not authentication.

| Source module | Responsibility |
|---|---|
| `agent.py` | Prompt, model loop, tool permissions, approvals, evidence |
| `browser.py` | Generic observations/actions and navigation checks |
| `llm.py` | Messages API protocol, tools, usage/budgets |
| `gateway.py` | Isolated key and fixed upstream endpoint |
| `documents.py` | Local PDF rendering and generated-file cleanup |
| `config.py` | Typed YAML and private-path checks |
| `cli.py` | Initialization, migration, batches and reports |
| `demo.py` | Fictional website and clearly separated scripted model double |

No session resumption, saved logins, CV adaptation, interview automation or automatic
provider fallback is implemented.
Third-party Playwright notices remain in `docker/`.
