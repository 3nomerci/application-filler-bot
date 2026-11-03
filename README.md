# Application Filler

A **Claude-driven browser agent running in Docker**. Give it job links, your facts,
instructions and a fixed PDF CV. Claude reads each page, chooses what to do, follows
Apply links and recruiting-site handoffs, answers questions, prepares cover letters,
and works through form steps. Applications it cannot finish are flagged individually.

**Claude is the main decision-maker on every real run.** Python provides bounded
browser actions, exact copying of facts, PDF rendering, verification and budgets.
Real applications require the API; the free self-test uses an explicitly scripted test double.

The pinned model is `claude-haiku-5-5`, with adaptive thinking. Under
[Anthropic's versioning policy](https://platform.claude.com/docs/it/about-claude/models/model-ids-and-versions).

## Start here: Windows and Docker Desktop

Open PowerShell **in this project folder**, with Docker Desktop running Linux containers.
Python and uv run inside Docker; you do not need to install them on Windows.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose --env-file docker/compose.env run --rm --no-deps -T demo self-test --headless
```

Setup builds the images and creates your personal files. An existing version 1
configuration is backed up and migrated; inspect the result before real use.
The self-test uses fictional data and a local website, **no key and no credits**.
It exercises Apply → redirect → multiple steps → PDF uploads → confirmation.

1. Edit **`private/instructions.yaml`**, your personal copy of
   [the annotated blueprint](examples/instructions.yaml). Fill in your facts and
   `documents.background`, and choose your trust and submission settings.
2. Put your approved CV at **`private/cv.pdf`**. It is uploaded unchanged.
3. Put job URLs in **`private/links.txt`**, one per line. Listing pages with an Apply
   button are supported; you do not need to find the final form first.
4. Create the key file yourself:

```powershell
notepad .secrets/anthropic_api_key
```

Paste only the Anthropic API key into Notepad, save and close it. Use that exact filename,
without `.txt`. **Do not paste the key into chat, YAML, shell commands or source code.**
Only the separate API gateway receives this file; the browser container does not.
Read the [key/privacy explanation](DOCUMENTATION.md#api-key-and-privacy) for the limits
of this protection.

Validate instructions without contacting Anthropic:

```powershell
docker compose --env-file docker/compose.env run --rm --no-deps -T demo validate
```

Then try **real Haiku on the fictional practice application**. This uses credits but
does not submit a real job application or read your candidate profile:

```powershell
docker compose --env-file docker/compose.env run --rm --service-ports agent run --demo --interactive
```

For your own applications:

```powershell
docker compose --env-file docker/compose.env run --rm --service-ports agent run --links private/links.txt --interactive
```

Open **http://localhost:6080/vnc.html**, connect and enter the temporary viewing password
printed in the terminal. This shows the container's Chromium browser. Answer agent
questions in PowerShell. In manual submission mode, review and submit in this browser
**before pressing Enter to close the run**. Forms and logins are not saved for later.

When finished, shut down the gateway:

```powershell
docker compose --env-file docker/compose.env --profile live down
```

## Choose your autonomy

These settings in your instructions are independent:

| Setting | Meaning |
|---|---|
| `answers.mode: trusted` | Claude may infer supported answers from facts, context and research. |
| `answers.mode: review` | Inferred answers require your approval. |
| `answers.topics.<topic>: ask` | Always ask for that topic, including in trusted mode. |
| `salary.strategy: market` or `low` | Research a central or lower defensible estimate; ask if evidence is insufficient. |
| `documents.cover_letter: trusted` | Generate and attach a factual tailored letter without prior approval. |
| `navigation.handoffs: trusted` | Follow public HTTPS application handoffs without per-host setup. |
| `submission: manual` or `auto` | Leave final submission to you, or authorize one agent attempt. |

The blueprint is tailored to Italian citizenship. **Europe is not one immigration
jurisdiction**: EU rights must not be applied indiscriminately to UK or other non-EU
roles. Claude researches official guidance and asks when country/status is unclear.

You give preferences in your own wording; Claude maps them to the site's options.
YAML comments explain settings to you. Actual instructions are values sent to Claude.
There is no per-site confirmation phrase for you to configure.

For unattended work, omit `--interactive`: questions become blocked reports and the
batch continues. Add `--headless` to hide the browser; use `submission: auto` if you
want it to complete applications, because unsubmitted forms disappear at exit.

## What to expect

The agent loop, Docker viewer, key gateway, research tools, interactive answers,
fixed CV uploads, Markdown/PDF letters and optional submission are implemented.
Tests use real Chromium and mocked/scripted model responses. **Live Haiku quality
and compatibility with individual hiring sites still need your paid trial**; these
tests do not establish that the model can complete any arbitrary website reliably.

Complex widgets, inaccessible frames, login/challenge screens and ambiguous questions
may need human help. This version has no CAPTCHA bypass, anti-detect browser, proxy
rotation, account creation, interviews, saved logins or session resumption.

[DOCUMENTATION.md](DOCUMENTATION.md) explains Docker, API privacy, variables, all
settings, costs, reports, architecture, limitations and development with **uv**.
