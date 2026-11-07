/* Form guidance uses plain input examples; file syntax is handled by the editor. */
(() => {
  'use strict';

  const field = (path, label, type, hint, options = {}) => ({
    path, label, type, hint, ...options
  });
  const topicChoices = [['infer', 'Answer using supplied facts and research'], ['ask', 'Ask me'], ['skip', 'Skip this topic']];

  window.CONFIG_SCHEMA = [
    {
      id: 'profile', title: 'Personal information', eyebrow: 'PROFILE',
      description: 'Your contact details and application facts. Leave information you do not know blank.',
      fields: [
        field('candidate.full_name', 'Full name', 'text', 'Use the name you want employers to see.', { placeholder: 'Alex Example' }),
        field('candidate.first_name', 'First name', 'text', 'Your given name.', { placeholder: 'Alex' }),
        field('candidate.last_name', 'Last name', 'text', 'Your family name or surname.', { placeholder: 'Example' }),
        field('candidate.email', 'Email', 'email', 'An address where employers can contact you.', { placeholder: 'alex@example.com' }),
        field('candidate.phone', 'Phone number', 'text', 'Include the international country code.', { placeholder: '+39 312 345 6789' }),
        field('candidate.date_of_birth', 'Date of birth', 'date', 'Optional. Use the calendar or the date order shown in this field.'),
        field('candidate.linkedin', 'LinkedIn URL', 'url', 'Paste your public profile link, or leave blank.', { placeholder: 'https://www.linkedin.com/in/alex-example' }),
        field('candidate.github', 'GitHub URL', 'url', 'Paste your GitHub profile link, or leave blank.', { placeholder: 'https://github.com/alex-example' }),
        field('candidate.website', 'Website / portfolio', 'url', 'Your personal website or portfolio, if you have one.', { placeholder: 'https://example.com/portfolio' }),
        field('candidate.address', 'Street address', 'text', 'Street name and house number. Optional.', { placeholder: '123 Example Street' }),
        field('candidate.city', 'City', 'text', 'The city where you currently live.', { placeholder: 'Toronto' }),
        field('candidate.region', 'Region / state', 'text', 'Your state, province or region.', { placeholder: 'Ontario' }),
        field('candidate.postal_code', 'Postal code', 'text', 'Enter the full postal code, including any leading zeroes.', { placeholder: '00123' }),
        field('candidate.country', 'Address country', 'text', 'The country in your postal address.', { placeholder: 'Canada' }),
        field('candidate.citizenships', 'Citizenships', 'tags', 'Use country codes separated by commas, such as IT, FR.', {
          placeholder: 'IT, FR',
          help: 'Include only nationalities you actually hold. Living in a country or having a work permit there does not make it a citizenship. The bot uses these facts when checking work rights.'
        }),
        field('candidate.residence_country', 'Country of residence', 'nullable', 'The country where you live today. Leave blank if unknown.', { placeholder: 'Italy' }),
        field('candidate.existing_work_statuses', 'Existing work statuses', 'nullable', 'Describe citizenship-based work rights or permits you already hold. Leave blank if unknown.', {
          placeholder: 'Italian citizen with EU work rights', wide: true,
          help: 'Being employed or unemployed is not a work-authorization status. If relevant, include the permit type, country and expiry date. The bot must distinguish existing permission from needing employer sponsorship.'
        }),
        field('candidate.relocation', 'Relocation preference', 'relocation', 'Choose whether you would move for a job, or describe where you would move.', { placeholder: 'Open to relocating within the EU' }),
        field('candidate.start_date', 'Availability / start date', 'text', 'Describe when you could start work.', { placeholder: 'Immediately, or after a two-month notice period' }),
        field('candidate.gender', 'Gender', 'nullable', 'Optional. Enter the wording you use for your gender, or leave blank.', {
          placeholder: 'Man',
          help: 'This supplies a fact for gender questions. It does not establish your pronouns or an answer to a different question about legal sex. The Personal disclosures policy in Agent behavior still decides whether the bot asks, uses supplied facts or skips the question.'
        }),
        field('candidate.veteran_status', 'Veteran status', 'select', 'Your military veteran status. Leave Unknown selected when you have not supplied this fact.', {
          choices: [['null', 'Unknown / not supplied'], ['true', 'Veteran'], ['false', 'Not a veteran']], nullableBoolean: true,
          help: 'Not a veteran is an explicit negative answer; Unknown is missing information. Employer questions may use a narrower definition, such as a specific protected-veteran category. The bot should read that definition and ask if your supplied fact is insufficient. The Personal disclosures policy still applies.'
        }),
        field('candidate.protected_category_member', 'Protected-category membership', 'select', 'Choose Unknown if you are unsure whether the employment category applies to you.', {
          choices: [['null', 'Unknown / ask me'], ['true', 'Yes'], ['false', 'No']], nullableBoolean: true,
          help: 'Some countries have legally defined employment categories, such as Italy’s categorie protette. This fact works with the protected-category policy in Agent behavior; other demographic and disability questions follow the personal-disclosure policy.'
        })
      ]
    },
    {
      id: 'languages', title: 'Languages', eyebrow: 'PROFILE',
      description: 'The languages you can use and your proficiency in each.',
      fields: [
        field('candidate.languages', 'Language skills', 'languages', 'Add one language per row and describe your level. Enter plain text in both fields.', {
          placeholder: 'English', levelPlaceholder: 'C1 / fluent', wide: true,
          help: 'Use a level you can support: for example C1 / fluent, Native or Beginner. The bot reads each language and level as a supplied fact, then matches the application’s wording and options. It should ask when it cannot establish a suitable answer; a self-reported level does not imply a formal certificate.'
        })
      ]
    },
    {
      id: 'education', title: 'Education', eyebrow: 'PROFILE',
      description: 'Your institutions and study dates. Leave dates blank when you do not know the full date.',
      fields: [
        field('candidate.education.bachelors.institution', 'Bachelor’s institution', 'text', 'The official name of your university or college.', { placeholder: 'University of Example' }),
        field('candidate.education.bachelors.institution_local_name', 'Local institution name', 'text', 'The institution’s name in its original language, if different.', { placeholder: 'Université Exemple' }),
        field('candidate.education.bachelors.start_date', 'Bachelor’s start date', 'date', 'Use the calendar or the date order shown in this field. Leave blank if unknown.'),
        field('candidate.education.bachelors.end_date', 'Bachelor’s end date', 'date', 'Actual or expected completion. Use the date order shown in this field.', {
          help: 'If the degree is still in progress, say so in your factual background. If you only know the month or year, leave the date blank and describe what you know there instead of inventing a day.'
        }),
        field('candidate.education.masters.institution', 'Master’s institution', 'text', 'The official name of your university or college.', { placeholder: 'Example Polytechnic' }),
        field('candidate.education.masters.institution_local_name', 'Local institution name', 'text', 'The institution’s name in its original language, if different.', { placeholder: 'Politecnico di Esempio' }),
        field('candidate.education.masters.start_date', 'Master’s start date', 'date', 'Use the calendar or the date order shown in this field. Leave blank if unknown.'),
        field('candidate.education.masters.end_date', 'Master’s end date', 'date', 'Actual or expected completion. Use the date order shown in this field.', {
          help: 'If the degree is still in progress, say so in your factual background. If you only know the month or year, leave the date blank and describe what you know there instead of inventing a day.'
        })
      ]
    },
    {
      id: 'behavior', title: 'Agent behavior', eyebrow: 'POLICIES',
      description: 'Set your preferences and decide which answers need your approval.',
      fields: [
        field('instructions', 'General agent instructions', 'textarea', 'Describe preferred roles, locations, work arrangements and situations where the bot should ask you. Standard instructions are already filled in; edit them as needed.', {
          placeholder: 'Prefer backend engineering roles in Canada. I can work in an office. Ask when a question cannot be answered from my facts.', wide: true, tall: true,
          help: 'These rules apply across applications. Put compensation preferences in Salary preferences and letter-writing style in Documents & cover letters so each set of instructions is easy to maintain.'
        }),
        field('answers.mode', 'Answer mode', 'select', 'Choose whether supported answers can be used immediately or need your review.', {
          choices: [['trusted', 'Trusted — use supported answers'], ['review', 'Review — approve suggested answers']],
          help: 'Topic-specific rules below still apply. For example, Ask me for consent continues to require a decision even in Trusted mode. Neither mode authorizes invented personal facts.'
        }),
        field('answers.protected_category', 'Protected-category policy', 'select', 'Choose how the bot handles questions about protected employment categories.', {
          choices: [['negative_or_skip', 'Use membership: No, skip or ask'], ['ask', 'Always ask me'], ['skip', 'Always skip']],
          help: 'With Use membership, an explicit No in your profile allows a No answer; Yes causes the question to be skipped; Unknown causes the bot to ask. This rule applies only to the employment category, not every sensitive disclosure.'
        }),
        field('answers.cookies', 'Cookie handling', 'select', 'Allow cookies needed to reach an application, or ask before accepting.', {
          choices: [['accept_when_needed', 'Accept when needed'], ['ask', 'Ask first']],
          help: 'The bot should prefer rejecting optional cookies. Employer privacy declarations and consent to contact you are handled separately by the consent policy.'
        }),
        field('answers.topics.work_authorization', 'Work authorization', 'select', 'Choose whether to research work rights from your facts, ask you, or skip.', {
          choices: topicChoices,
          help: 'Research needs the actual work country and your supplied citizenships or permits. The bot checks official guidance and asks if the location, your status or the question is unclear.'
        }),
        field('answers.topics.salary', 'Salary questions', 'select', 'Choose whether to estimate expected pay, ask you, or skip.', {
          choices: topicChoices,
          help: 'Estimated answers use Salary preferences and current comparable evidence. Expected pay is different from past salary; the bot must never invent salary history.'
        }),
        field('answers.topics.personal_disclosure', 'Personal disclosures', 'select', 'Set the policy for sensitive personal questions.', {
          choices: [['ask', 'Ask me'], ['infer', 'Use explicitly supplied facts'], ['skip', 'Skip this topic']],
          help: 'This includes identity, disability, ethnicity, veteran status and criminal history. Choosing supplied facts only permits answers supported by information you have actually provided.'
        }),
        field('answers.topics.consent', 'Consent and declarations', 'select', 'Choose how to handle agreements, declarations and permission requests.', {
          choices: [['ask', 'Ask me'], ['infer', 'Use my explicit prior authorization'], ['skip', 'Skip this topic']],
          help: 'If you authorize answers in advance, describe precisely which declarations you accept in General agent instructions. Approving one checkbox does not authorize other checkboxes or final submission.'
        })
      ]
    },
    {
      id: 'salary', title: 'Salary preferences', eyebrow: 'COMPENSATION',
      description: 'Guide the expected salary the bot proposes when an application asks for a number.',
      fields: [
        field('salary.strategy', 'Salary strategy', 'select', 'Market aims around the middle of a researched pay range. Low aims toward its lower end, while respecting your minimum.', {
          wide: true,
          choices: [['market', 'Market — typical pay for a comparable role'], ['low', 'Low — lower end of comparable pay']],
          help: 'The bot first looks for the employer’s advertised salary band. Otherwise it researches recent pay for similar roles, seniority, work location and contract type. It compares matching currencies, pay periods and gross/net or base/total amounts. This is a researched judgment, not a fixed formula or guaranteed offer. If reliable comparisons are missing or contradictory, it asks you.',
          checklist: [
            'Illustration only: for a relevant EUR 40,000–60,000 gross annual base range, Market could aim near EUR 50,000; Low could aim nearer EUR 40,000–45,000. The actual choice depends on the evidence and your experience.',
            'Your minimum is a floor for either strategy. The bot should ask if the available range conflicts with that floor.',
            'This setting is used only when salary questions allow an estimated answer. If you choose Ask me for salary questions, you provide the amount instead.'
          ]
        }),
        field('salary.minimum', 'Minimum acceptable salary', 'nullable', 'Optional. Include currency, amount, before/after tax, pay period and base/total pay.', {
          placeholder: 'EUR 50000 gross annual base', wide: true,
          help: 'Gross means before tax; net means take-home pay. Annual, monthly and hourly amounts cannot be compared directly. Base pay excludes bonuses and equity, while total compensation may include them. Leave blank to avoid setting a fixed floor.'
        }),
        field('salary.instructions', 'Salary research instructions', 'textarea', 'Add source preferences or special requirements. Standard research instructions are already filled in.', {
          placeholder: 'Prefer the employer’s published pay range. Ask if the currency or working hours are unclear.', wide: true, tall: true,
          help: 'Useful details include the contract type you want, whether bonuses should count, and circumstances that should always require your input. Keep the numeric floor in Minimum acceptable salary.'
        })
      ]
    },
    {
      id: 'documents', title: 'Documents & cover letters', eyebrow: 'APPLICATION MATERIALS',
      description: 'Choose your CV and give the writer facts and style preferences for optional cover letters.',
      fields: [
        field('documents.cv', 'CV filename', 'text', 'Upload a finished PDF (up to 10 MB), or enter its filename if it is already in private/.', {
          placeholder: 'alex-example-cv.pdf',
          help: 'The PDF is uploaded to employers unchanged. Selecting it here updates the filename; Save to private/ copies the selected PDF together with your configuration. If direct folder saving is unavailable, download the files and move them to private/ yourself. A file in a subfolder can be entered as documents/cv.pdf.'
        }),
        field('documents.cover_letter', 'Cover-letter behavior', 'select', 'Choose whether to generate letters immediately, review them first, or skip them.', {
          choices: [['trusted', 'Generate when needed'], ['review', 'Review before use'], ['skip', 'Skip cover letters']],
          help: 'Letters can be entered into a textbox or generated as a document, depending on the application. This decision is separate from permission to submit the final application.'
        }),
        field('documents.retention', 'Generated-letter retention', 'select', 'Choose whether generated letters stay on disk after a run.', {
          choices: [['keep', 'Keep generated letters'], ['delete_after_run', 'Delete generated letters after run']],
          help: 'Cleanup affects only the bot’s generated letter files. Your CV and the example letters you supplied are preserved.'
        }),
        field('documents.background', 'Factual background', 'textarea', 'Provide your education, skills, experience, projects, contributions, results and career interests. Copy relevant facts from your CV here; the writer does not extract them from the PDF.', {
          placeholder: `Example — replace with your own facts:

Education: MSc in Computer Science, Example University, 2026.
Skills: Python, PyTorch, SQL, Git and automated testing.

Thesis: built an image-classification pipeline and compared models.
My contribution: preprocessing and evaluation with subject-separated data splits.
Team project: implemented data validation and tests for a financial dashboard.

Interests: junior ML engineering and applied research.
Motivation: I enjoy rigorous evaluation and learning from domain experts.`,
          wide: true, tall: true,
          help: 'Focus on evidence the writer can cite. Specific contributions help it connect your experience to a job. Only include dates, grades, tools and numerical outcomes you can verify.',
          checklist: [
            'Education: degree, subject, institution and completion or expected date.',
            'Experience and projects: the problem, your own role, what you did and the result.',
            'Skills: the tools or methods you used and where you used them.',
            'Motivation: roles or domains you want and what interests you about them.'
          ]
        }),
        field('documents.examples', 'Example cover letters', 'examples', 'Optional. Add one past letter per entry to show the voice and structure you like.', {
          placeholder: 'Dear Hiring Team,\n\nI am interested in your junior ML role. I enjoyed building and evaluating models during my thesis.\n\nThank you for considering my application.\nAlex Example',
          wide: true,
          help: 'Paste the complete letter with its paragraph breaks, or enter the name of a UTF-8 .md or .txt file stored in private/. A one-line entry is treated as a filename. Each entry must be nonblank and at most 20 KB. These examples guide style; factual claims must come from your background.'
        }),
        field('documents.instructions', 'Cover-letter writing instructions', 'textarea', 'Set the language, tone, length and emphasis. Standard writing instructions are already filled in; edit them to suit you.', {
          placeholder: 'Write 250–350 words in the job’s language. Use a natural, specific tone. Emphasise research for research roles and implementation for engineering roles.',
          wide: true, tall: true,
          help: 'You can tell the writer how to adapt to different opportunities, for example by prioritising thesis methods for research roles and testing or teamwork for software roles. Your qualifications and achievements belong in Factual background.'
        })
      ]
    },
    {
      id: 'navigation', title: 'Navigation & submission', eyebrow: 'AUTOMATION',
      description: 'Choose which recruiting sites the bot may follow and who submits completed applications.',
      fields: [
        field('navigation.handoffs', 'Recruiting-site handoffs', 'select', 'Allow relevant recruiting links, or ask before opening a new website.', {
          choices: [['trusted', 'Follow relevant recruiting links'], ['ask', 'Ask before visiting a new website']],
          help: 'An employer’s Apply button may lead to a separate recruiting platform. Trusted navigation permits relevant public HTTPS handoffs; logins and unsupported challenges can still require your help.'
        }),
        field('navigation.allowed_hosts', 'Pre-approved hosts', 'tags', 'Optional. Enter website hostnames separated by commas, without https:// or page paths.', {
          placeholder: 'jobs.example.org, apply.example.com', wide: true,
          help: 'This list preapproves sites when you otherwise ask about new websites. For a link such as https://jobs.example.org/apply/123, enter only jobs.example.org.'
        }),
        field('submission', 'Final submission mode', 'select', 'Choose who sends the completed application to the employer.', {
          choices: [['manual', 'Manual — I review and submit'], ['auto', 'Automatic — bot may submit']], wide: true,
          help: 'With Manual, submit in the bot’s visible browser before closing the run. Automatic permits the bot to send completed applications, even when answer and letter generation are also trusted.'
        })
      ]
    },
    {
      id: 'advanced', title: 'Advanced settings', eyebrow: 'RUNTIME',
      description: 'Limits on model use, estimated cost and browser activity. Start with the supplied defaults.',
      fields: [
        field('model.id', 'Model ID', 'text', 'The model version required by this project. This value is fixed.', { placeholder: 'claude-haiku-5-5' }),
        field('model.effort', 'Model effort', 'select', 'Choose how much reasoning effort the model uses.', {
          choices: [['low', 'Low'], ['medium', 'Medium'], ['high', 'High']],
          help: 'Higher effort can make complex decisions take longer and use more tokens. It does not increase your configured call or budget limits.'
        }),
        field('model.max_output_tokens', 'Maximum output tokens', 'number', 'Limit the size of one model response, including reasoning. Allowed: 1,024–12,000.', { placeholder: '8192' }),
        field('model.max_request_chars', 'Maximum request characters', 'number', 'Limit the text sent in one model request. Allowed: 10,000–350,000 characters.', { placeholder: '240000' }),
        field('model.max_calls_per_application', 'Calls per application', 'number', 'Stop working on a job after this many model calls. Allowed: 1–100.', { placeholder: '40' }),
        field('model.max_calls_per_run', 'Calls per run', 'number', 'Limit model calls across the entire batch of jobs. Allowed: 1–200.', { placeholder: '100' }),
        field('model.estimated_budget_usd', 'Estimated budget (USD)', 'decimal', 'Estimated spend allowed for one run. Enter a number greater than 0, up to 5.', {
          placeholder: '0.50',
          help: 'This is a local estimate based on recorded usage, not a provider billing cap. Set a spending limit in your provider account as well. Use a decimal point when entering a fractional dollar amount.'
        }),
        field('model.web_searches_per_application', 'Web searches per application', 'number', 'Allow 0–20 research searches per job. Enter 0 to disable searches.', {
          placeholder: '6',
          help: 'Research supports salary estimates, work-rights checks and company facts. When searches are unavailable, the bot should ask about answers that need external evidence.'
        }),
        field('browser.delay_ms', 'Browser action delay (ms)', 'number', 'Pause between browser actions. 400 ms means 0.4 seconds. Allowed: 100–5,000.', { placeholder: '400' }),
        field('browser.max_actions', 'Maximum browser actions', 'number', 'Stop after this many browser interactions per application. Allowed: 1–300.', { placeholder: '100' }),
        field('browser.snapshot_chars', 'Browser snapshot characters', 'number', 'Limit text kept from one page snapshot. Allowed: 2,000–40,000 characters.', { placeholder: '18000' })
      ]
    },
    {
      id: 'raw', title: 'Advanced file editor', eyebrow: 'FILE CONTENTS',
      description: 'For experienced users: edit the underlying configuration file directly.',
      fields: []
    }
  ];

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
  languages: {} # Map each language to your own proficiency; leave empty if not supplied.
  # Example shape (replace with your own facts):
  # languages:
  #   English: "B2 / upper-intermediate"
  #   French: "Beginner"
  gender: null # Optional self-described gender, e.g. "Man", "Woman" or your own wording.
  veteran_status: null # true: veteran; false: not a veteran; null: not supplied.
  # Gender/veteran answers still follow answers.topics.personal_disclosure (ask/infer/skip).
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
