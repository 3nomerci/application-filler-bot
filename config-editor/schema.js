/* Public, declarative field definitions. No personal information is embedded. */
(() => {
  'use strict';

  const field = (path, label, type, explanation, example, options = {}) => ({
    path, label, type, explanation, example, ...options
  });

  window.CONFIG_SCHEMA = [
    {
      id: 'profile', title: 'Personal information', eyebrow: 'PROFILE',
      description: 'Facts used to fill applications. Leave unknown information unknown; do not guess.',
      fields: [
        field('candidate.full_name', 'Full name', 'text', 'Your complete legal or preferred application name, as appropriate for your documents. Keep it consistent with your CV.', 'candidate:\n  full_name: "Alex Example"'),
        field('candidate.first_name', 'First name', 'text', 'Given name used when the form asks for first name separately.', 'first_name: "Alex"'),
        field('candidate.last_name', 'Last name', 'text', 'Family name or surname used when the form asks separately.', 'last_name: "Example"'),
        field('candidate.email', 'Email', 'email', 'Email address on which employers should contact you. It should be an address you can access.', 'email: "alex@example.com"'),
        field('candidate.phone', 'Phone number', 'text', 'Telephone number including the international dialling prefix. Keeping the +country code makes this work across countries.', 'phone: "+12025550123"'),
        field('candidate.date_of_birth', 'Date of birth', 'date', 'Optional birth date, in YYYY-MM-DD format. Leave blank if you do not want to supply it. Missing is not the same as a negative answer.', 'date_of_birth: "2000-12-31"\n# or: date_of_birth: null'),
        field('candidate.linkedin', 'LinkedIn URL', 'url', 'Public profile URL. Leave blank if you do not have one.', 'linkedin: "https://www.linkedin.com/in/alex-example"'),
        field('candidate.github', 'GitHub URL', 'url', 'Public GitHub profile. This is optional.', 'github: "https://github.com/alex-example"'),
        field('candidate.website', 'Website / portfolio', 'url', 'An optional personal site or portfolio URL, if relevant to the applications.', 'website: "https://example.com/portfolio"'),
        field('candidate.address', 'Street address', 'text', 'Street and house number if you want the agent to use a postal address. Omit if you prefer not to share it.', 'address: "123 Example Street"'),
        field('candidate.city', 'City', 'text', 'Current city. This is different from the cities where you are willing to work.', 'city: "Toronto"'),
        field('candidate.region', 'Region / state', 'text', 'State, province or administrative region for your residence.', 'region: "Ontario"'),
        field('candidate.postal_code', 'Postal code', 'text', 'Postal or ZIP code in your current address. Keep leading zeroes by treating it as text.', 'postal_code: "01234"'),
        field('candidate.country', 'Address country', 'text', 'Country appearing in the postal address; distinct from citizenship and residence status.', 'country: "Canada"'),
        field('candidate.citizenships', 'Citizenships', 'tags', 'List the country codes of nationalities you actually hold. This affects work-authorisation questions; do not infer citizenship from where you live.', 'citizenships: [IT]\n# or: citizenships: [CA, FR]', { placeholder: 'e.g. IT, FR' }),
        field('candidate.residence_country', 'Country of residence', 'nullable', 'Country in which you live today. This is not necessarily the same as citizenship or existing work authorisation.', 'residence_country: "CA"\n# or: residence_country: null'),
        field('candidate.existing_work_statuses', 'Existing work statuses', 'nullable', 'Work permits or other existing authorisations that you can truthfully claim. Leave unknown instead of assuming you have no right to work.', 'existing_work_statuses: "EU citizen with EU work rights"\n# or: existing_work_statuses: null', { wide: true }),
        field('candidate.relocation', 'Relocation preference', 'flex', 'Accepts true (willing), false (not willing), a specific text preference, or null (unknown). Text may be more informative than a simple yes/no.', 'relocation: true\n# or: relocation: "Open to relocating within the EU"'),
        field('candidate.start_date', 'Availability / start date', 'text', 'When you can start working. Can be a descriptive preference or a calendar date; use the wording that accurately describes your availability.', 'start_date: "Immediately"\n# or: start_date: "2027-01-15"'),
        field('candidate.protected_category_member', 'Protected-category membership', 'select', 'Controls a special protected-category policy for employment forms. Use Unknown unless you explicitly know whether the configured category applies; this is not a general demographic disclosure setting.', 'protected_category_member: null\n# or: protected_category_member: false', { choices: [['null', 'Unknown / ask'], ['true', 'Yes'], ['false', 'No']], nullableBoolean: true })
      ]
    },
    {
      id: 'education', title: 'Education', eyebrow: 'PROFILE',
      description: 'Academic credentials and dates. Use exact facts or leave the fields blank.',
      fields: [
        field('candidate.education.bachelors.institution', 'Bachelor’s institution', 'text', 'Official name of the school or university that awarded or will award your bachelor’s degree.', 'institution: "University of Example"'),
        field('candidate.education.bachelors.institution_local_name', 'Local institution name', 'text', 'Name of the institution in its original language, if different from the international name.', 'institution_local_name: "Université Exemple"'),
        field('candidate.education.bachelors.start_date', 'Bachelor’s start date', 'date', 'Date your bachelor’s program started. Use YYYY-MM-DD; do not invent days if you only know the year.', 'start_date: "2021-09-01"'),
        field('candidate.education.bachelors.end_date', 'Bachelor’s end date', 'date', 'Actual or expected completion date. If the program is unfinished, clarify its status in your background.', 'end_date: "2024-07-15"'),
        field('candidate.education.masters.institution', 'Master’s institution', 'text', 'Official name of the university awarding or expected to award the master’s degree.', 'institution: "Example Polytechnic"'),
        field('candidate.education.masters.institution_local_name', 'Local institution name', 'text', 'Institution name in its original language if relevant.', 'institution_local_name: "Politecnico di Esempio"'),
        field('candidate.education.masters.start_date', 'Master’s start date', 'date', 'The actual start date of your master’s program, in YYYY-MM-DD format.', 'start_date: "2024-09-01"'),
        field('candidate.education.masters.end_date', 'Master’s end date', 'date', 'Actual or expected master’s completion date. Clarify expected completion in your background.', 'end_date: "2026-10-01"')
      ]
    },
    {
      id: 'behavior', title: 'Agent behavior', eyebrow: 'POLICIES',
      description: 'Control which answers the agent may infer and when it must ask for approval.',
      fields: [
        field('instructions', 'General agent instructions', 'textarea', 'Your overall rules: preferred roles, preferred locations, availability, what the agent may infer, and conditions that require clarification. The agent reads this text as instructions.', 'instructions: |-\n  Prefer backend engineering roles in Canada.\n  Do not invent qualifications. Ask when unsure.', { wide: true, tall: true }),
        field('answers.mode', 'Answer mode', 'select', 'Trusted allows answers supported by your facts and permitted research. Review asks for approval of inferred answers. Neither mode permits inventing information.', 'mode: trusted\n# or: mode: review', { choices: [['trusted', 'Trusted — infer supported answers'], ['review', 'Review — approve inferred answers']] }),
        field('answers.protected_category', 'Protected-category policy', 'select', 'How to handle the special employment protected-category question. negative_or_skip gives No only if membership is explicitly false, skips if true, and asks when unknown; ask always requests input; skip avoids answering.', 'protected_category: negative_or_skip', { choices: [['negative_or_skip', 'No / skip based on explicit fact'], ['ask', 'Always ask'], ['skip', 'Always skip']] }),
        field('answers.cookies', 'Cookie handling', 'select', 'Accept only the cookies needed to reach an application, or ask for a decision. This is separate from consent to employer declarations.', 'cookies: accept_when_needed\n# or: cookies: ask', { choices: [['accept_when_needed', 'Accept when needed'], ['ask', 'Ask first']] }),
        field('answers.topics.work_authorization', 'Work authorization', 'select', 'Infer only when the work country and supplied citizenship/status support a sound answer. Ask instead if you prefer to decide every visa or sponsorship question.', 'work_authorization: infer\n# or: work_authorization: ask', { choices: [['infer', 'Infer with evidence'], ['ask', 'Ask me']] }),
        field('answers.topics.salary', 'Salary questions', 'select', 'Infer uses your salary strategy and available market evidence. Ask requires your response instead of an estimated expectation.', 'salary: infer\n# or: salary: ask', { choices: [['infer', 'Infer with evidence'], ['ask', 'Ask me']] }),
        field('answers.topics.personal_disclosure', 'Personal disclosures', 'select', 'Sensitive questions about identity, disability, criminal history, or similar topics. Ask is safer than letting the agent infer personal information.', 'personal_disclosure: ask', { choices: [['ask', 'Ask me'], ['infer', 'Infer only when explicitly authorised']] }),
        field('answers.topics.consent', 'Consent and declarations', 'select', 'Questions requesting a legal declaration, agreement or consent. Keep Ask unless your instructions explicitly describe which declarations you authorise.', 'consent: ask', { choices: [['ask', 'Ask me'], ['infer', 'Use explicitly authorised consent']] })
      ]
    },
    {
      id: 'salary', title: 'Salary preferences', eyebrow: 'COMPENSATION',
      description: 'Define how estimated salary expectations should be selected.',
      fields: [
        field('salary.strategy', 'Salary strategy', 'select', 'Market selects a supported central market estimate. Low selects the lower defensible part of a comparable compensation range, not an arbitrary discount.', 'strategy: market\n# or: strategy: low', { choices: [['market', 'Market — central supported estimate'], ['low', 'Low — lower supported estimate']] }),
        field('salary.minimum', 'Minimum acceptable salary', 'nullable', 'Optional floor. Include currency, gross/net, time basis and base/total, so the agent does not compare incompatible numbers.', 'minimum: "EUR 50000 gross annual base"\n# or: minimum: null', { wide: true }),
        field('salary.instructions', 'Salary research instructions', 'textarea', 'Additional constraints for compensation research, such as preferred sources, location, role seniority, and what to do when evidence is weak.', 'instructions: |-\n  Prefer posted salary bands.\n  Ask if the evidence is contradictory.', { wide: true, tall: true })
      ]
    },
    {
      id: 'documents', title: 'Documents & cover letters', eyebrow: 'APPLICATION MATERIALS',
      description: 'Upload your finished CV, then supply facts, optional sample letters and writing preferences. The bot does not extract cover-letter background from your PDF.',
      fields: [
        field('documents.cv', 'CV filename', 'text', 'Upload your finished PDF below to set this filename, or enter a path relative to private/ if the file is already there. Save to private/ writes the selected PDF unchanged alongside instructions.yaml where supported. Otherwise download both files and move them to private/. Maximum PDF size: 10 MB.', 'cv: "alex-example-cv.pdf"\n# Save the PDF at private/alex-example-cv.pdf'),
        field('documents.cover_letter', 'Cover-letter behavior', 'select', 'Trusted writes a letter when needed; Review asks for approval; Skip disables generated cover letters. This is independent of final application submission.', 'cover_letter: review', { choices: [['trusted', 'Trusted — generate when needed'], ['review', 'Review before use'], ['skip', 'Skip cover letters']] }),
        field('documents.retention', 'Generated-letter retention', 'select', 'Keep saves generated Markdown/PDF cover letters. delete_after_run removes only generated cover letters when a run ends; never deletes your CV or example letters.', 'retention: keep', { choices: [['keep', 'Keep generated letters'], ['delete_after_run', 'Delete generated letters after run']] }),
        field('documents.background', 'Factual background', 'textarea', 'This is the evidence the writer may use, not a request about tone. Supply your own education, skills, work/research/projects, concrete contributions and outcomes, career interests and personal motivation. Include dates, tools and numbers only when accurate. The CV is not read automatically; paste the relevant facts here even if they also appear in the PDF.', `background: |-
  EDUCATION & BACKGROUND
  MSc in Computer Science, Example University, completed in 2026.
  BSc in Software Engineering. A semester abroad involved teamwork
  with students from several academic backgrounds.

  TECHNICAL SKILLS
  Python, PyTorch, pandas, SQL, Git and pytest.
  Machine learning, data analysis and model evaluation.

  EXPERIENCE, RESEARCH & PROJECTS
  Master's thesis: classified microscopy images using a small dataset.
  Built the preprocessing and training pipeline in Python/PyTorch.
  Compared a CNN with a pretrained transformer; kept samples from
  the same subject in one split to avoid data leakage.
  Team project: developed a dashboard for financial time-series analysis.
  My contribution was data validation and automated tests.

  CAREER INTERESTS & MOTIVATION
  Interested in junior ML engineering and applied research roles.
  Enjoy connecting rigorous evaluation with useful applications.
  Value international teams and learning from domain specialists.`, {
          wide: true, tall: true,
          guidance: 'Tell the writer what is true about you: education, tools, experience, your contributions, results, career interests and motivation. Copy relevant facts from your CV here; uploading the PDF does not fill this field.',
          checklist: [
            'Education: degree, subject, institution, completion or expected date; grades only if you want them mentioned.',
            'Skills: tools and methods you actually used, and the context in which you used them.',
            'Experience and projects: problem, your role, work you did, outcome and any verified numbers.',
            'Career interests and motivation: roles or domains you want, why they interest you, and what you value in a team.',
            'Use only your own facts. The fictional example below is a guide to content and structure.'
          ]
        }),
        field('documents.examples', 'Example cover letters', 'examples', 'Optional past letters that show your preferred tone and structure. Paste a whole letter with line breaks in each row, or reference an existing UTF-8 .md/.txt file in private/. Each example must be nonblank and at most 20 KB. A one-line value is treated as a filename. These samples guide style; the writer must take factual claims from your background instead.', `examples:
  - |-
    Dear Example Analytics Team,

    I am interested in your junior ML engineer role. My recent
    thesis involved image classification with Python and PyTorch.

    I enjoyed building a reproducible evaluation pipeline and
    investigating why models failed on unfamiliar samples.
    I would like to bring that curiosity to an applied research team.

    Thank you for considering my application.
    Best regards,
    Alex Example
# Or reference a file you saved in private/:
# examples: ["previous-letter.md"]
# Without examples: examples: []`, {
          wide: true,
          guidance: 'Optional: paste a past letter per row to demonstrate your preferred voice. Use multiple lines for pasted letters. You can also enter a .md/.txt filename stored in private/. Leave the list empty if you have none.'
        }),
        field('documents.instructions', 'Cover-letter writing instructions', 'textarea', 'Describe how to write: tone, length, language, structure and which parts of your supplied background to emphasise for different opportunities. Facts belong in Factual background. Company-specific claims should be verified, and insufficient evidence should lead to a question.', `instructions: |-
  Write a concise, specific letter in the job's language.
  Aim for 250–350 words unless the form gives a different limit.
  Use only my candidate facts and factual background as evidence.
  Use my example letters for tone and structure, not new claims.
  For research roles, emphasise evaluation and thesis contributions.
  For software roles, emphasise implementation, testing and teamwork.
  Sound natural, honest and enthusiastic; avoid generic praise.
  Verify claims about the employer. Ask if my background is insufficient.`, {
          wide: true, tall: true,
          guidance: 'Tell the writer how to present your facts: preferred language, word count, tone and emphasis. For example, prioritise thesis research for research jobs and implementation/testing for engineering jobs.'
        })
      ]
    },
    {
      id: 'navigation', title: 'Navigation & submission', eyebrow: 'AUTOMATION',
      description: 'Control permitted navigation and whether applications can be submitted automatically.',
      fields: [
        field('navigation.handoffs', 'Recruiting-site handoffs', 'select', 'Trusted follows relevant public HTTPS recruiting-platform links. Ask requires approval before navigating to new hosts.', 'handoffs: trusted\n# or: handoffs: ask', { choices: [['trusted', 'Trusted — follow relevant links'], ['ask', 'Ask before new hosts']] }),
        field('navigation.allowed_hosts', 'Pre-approved hosts', 'tags', 'Hostnames the agent may navigate to without asking when host approval is required. Use hostnames only, not full URLs or paths.', 'allowed_hosts: [jobs.example.org, apply.example.com]', { wide: true, placeholder: 'jobs.example.org, apply.example.com' }),
        field('submission', 'Final submission mode', 'select', 'Manual stops for you to review and submit. Auto authorises the bot to submit completed applications; use only when you are prepared for an irreversible submission.', 'submission: manual\n# or: submission: auto', { choices: [['manual', 'Manual — I review and submit'], ['auto', 'Automatic — bot may submit']], wide: true })
      ]
    },
    {
      id: 'advanced', title: 'Advanced settings', eyebrow: 'RUNTIME',
      description: 'Model, budget and browser limits. The repository defaults are reasonable starting values.',
      fields: [
        field('model.id', 'Model ID', 'text', 'The bot requires this exact model snapshot. This value is fixed by the project and cannot be changed in the form.', 'id: claude-haiku-5-5'),
        field('model.effort', 'Model effort', 'select', 'Controls reasoning effort. Higher effort may increase latency or token usage; the model must support the selected effort.', 'effort: medium', { choices: [['low', 'Low'], ['medium', 'Medium'], ['high', 'High']] }),
        field('model.max_output_tokens', 'Maximum output tokens', 'number', 'Per-request limit covering the model output and thinking tokens. A higher value permits longer replies but can cost more.', 'max_output_tokens: 8192'),
        field('model.max_request_chars', 'Maximum request characters', 'number', 'Local cap on characters supplied in one model request, not the model context-window size.', 'max_request_chars: 240000'),
        field('model.max_calls_per_application', 'Calls per application', 'number', 'Maximum model calls spent on one job application. A limit prevents unlimited retry loops.', 'max_calls_per_application: 40'),
        field('model.max_calls_per_run', 'Calls per run', 'number', 'Maximum model calls for the complete batch of applications.', 'max_calls_per_run: 100'),
        field('model.estimated_budget_usd', 'Estimated budget (USD)', 'decimal', 'Local estimated API budget for a run, not a guarantee of provider billing. Set actual provider-side limits separately.', 'estimated_budget_usd: 0.50'),
        field('model.web_searches_per_application', 'Web searches per application', 'number', 'Maximum external searches for compensation, work rules and company facts. Zero disables searches and can cause the agent to ask more questions.', 'web_searches_per_application: 6'),
        field('browser.delay_ms', 'Browser action delay (ms)', 'number', 'Delay between browser actions, in milliseconds. Example: 400 means 0.4 seconds.', 'delay_ms: 400'),
        field('browser.max_actions', 'Maximum browser actions', 'number', 'Per-application cap on browser interactions. Stops runaway navigation and repeated clicks.', 'max_actions: 100'),
        field('browser.snapshot_chars', 'Browser snapshot characters', 'number', 'Upper bound on characters retained from a browser snapshot to limit prompt size. This field may be missing from older private copies.', 'snapshot_chars: 18000')
      ]
    },
    {
      id: 'raw', title: 'Raw YAML', eyebrow: 'EXPERT EDITOR',
      description: 'Edit the complete file, including custom fields and comments. Syntax changes should be checked with the bot validator.',
      fields: []
    }
  ];

  for (const section of window.CONFIG_SCHEMA) {
    for (const definition of section.fields) {
      if (definition.path.startsWith('answers.topics.')) {
        definition.choices.push(['skip', 'Skip this topic']);
      }
    }
  }

  // A neutral v2 template. Blank personal facts are intentional.
  window.CONFIG_TEMPLATE = `# Setup copies this to private/instructions.yaml; only edit your private copy.
# Comments are for humans. All instructions the agent must follow are real values below.
version: 2

candidate:
  full_name: ""
  first_name: ""
  last_name: ""
  email: ""
  phone: ""
  linkedin: ""
  github: ""
  address: ""
  citizenships: [] # Your actual citizenships as country codes, e.g. [IT] or [CA, FR].
  residence_country: null # Do not confuse nationality with residence.
  existing_work_statuses: null # Unknown, not a claim that no statuses exist.
  relocation: ""
  start_date: ""
  date_of_birth: null # Quoted ISO date, e.g. "2000-12-31"; never infer a missing date.
  protected_category_member: null # Explicit false -> No; true -> skip; null -> ask.
  education:
    bachelors:
      institution: ""
      institution_local_name: ""
      start_date: null # Quoted YYYY-MM-DD.
      end_date: null # Completion/expected completion date; specify status separately if known.
    masters:
      institution: ""
      institution_local_name: ""
      start_date: null
      end_date: null

instructions: >-
  Apply for the jobs I provide using truthful facts and these preferences.
  Read the job and the actual questions/options; do not expect me to know their wording.
  Follow Apply links and relevant recruiting-platform handoffs. Work through multi-step forms.
  Do not create accounts, take tests or interviews, buy anything, or bypass challenges.
  Establish the actual work country before answering visa or sponsorship questions.
  Use only my supplied citizenships and existing work statuses, checking official guidance.
  Do not assume nationality from my name/address or invent a visa or residence permit.
  Distinguish the right to work, employer sponsorship and residence registration.
  Ask if job location, personal status or question meaning cannot be established.

answers:
  mode: trusted # trusted: allow supported inference; review: approve inferred answers first.
  protected_category: negative_or_skip # Employment protected category only; ask/skip also supported.
  cookies: accept_when_needed # Accept cookies needed to access the application; use ask to review.
  topics:
    work_authorization: infer
    salary: infer
    personal_disclosure: ask # Identity, disability, ethnicity, veteran/criminal history.
    consent: ask # Set infer only with explicit consent instructions describing what you accept.

salary:
  strategy: market # market or low (lower defensible part of comparable pay, not arbitrary discount).
  minimum: null # Optional, e.g. "EUR 50000 gross annual base".
  instructions: >-
    Research recent compensation for the role, seniority, work location and contract type.
    Prefer a relevant advertised band. Use market for a supported central value, low for
    the lower defensible part. Respect my minimum if supplied. Keep evidence URLs and pay
    basis. Never mix gross/net, base/total, annual/monthly/hourly or currencies. Ask if the
    evidence is weak or contradictory. Expected pay is not my previous salary.

documents:
  cv: cv.pdf # Put your approved fixed PDF in private/cv.pdf. Never modified by the agent.
  cover_letter: trusted # trusted, review, or skip. Independent of final submission.
  retention: keep # keep or delete_after_run; affects only generated cover-letter MD/PDF.
  background: "" # Your truthful experience/skills/achievements; not a fictional example.
  examples: [] # Private .md/.txt filenames or multiline text using '- |'; style, not facts.
  instructions: >-
    Write a concise, specific cover letter for this employer and role, in the job's language.
    Aim for 250–350 words unless the form gives another limit. Use only candidate facts and
    my background as evidence. Use examples for tone and structure. Avoid generic praise,
    invented qualifications or claims about the company that have not been verified.
    Request input if my factual background is insufficient.

navigation:
  handoffs: trusted # trusted allows public HTTPS handoffs; ask blocks new navigation hosts.
  allowed_hosts: [] # Only needed to preapprove extra hosts in ask mode.

submission: manual # manual or auto. Trusting answers does not automatically permit submission.

model:
  id: claude-haiku-5-5 # This is a fixed snapshot ID, not a rolling alias.
  effort: medium # low, medium, high. Adaptive thinking remains enabled.
  max_output_tokens: 8192 # Includes thinking; per API request.
  max_request_chars: 240000 # Application limit, not the model's context window.
  max_calls_per_application: 40
  max_calls_per_run: 100
  estimated_budget_usd: 0.50 # Local estimate. Set provider spending limits as well.
  web_searches_per_application: 6 # Set 0 to disable web tools; research-dependent answers then ask.

browser:
  delay_ms: 400
  max_actions: 100
  snapshot_chars: 18000
`;
})();
