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
        field('candidate.employment_status', 'Employment status', 'nullable', 'Employed, unemployed or student; this is separate from immigration/work rights.'),
        field('candidate.preferred_work_locations', 'Preferred cities (highest preference first)', 'ranked', 'Enter one city per line, starting with your first choice. Include the country when a city name could be ambiguous.', {
          placeholder: 'Paris, France\nZurich, Switzerland\nBerlin, Germany', wide: true,
          help: 'This is your general ranking across applications. If a form offers only some of these cities, the bot keeps their relative order and ignores cities that are not offered. For example, with the order Paris, Zurich, Berlin, a Zurich/Berlin form gets Zurich first. Other offered cities follow the policy below. A ranking does not establish your work authorization or override your relocation preference.'
        }),
        field('candidate.preferred_work_locations_unlisted', 'Other offered cities', 'select', 'Choose what the bot should do with offered cities missing from your ranked list.', {
          choices: [['ask', 'Ask me how to rank other cities'], ['any_order', 'Put other cities last, in any order']], wide: true, default: 'ask',
          help: 'Any order gives the bot permission to put unlisted cities after all matching ranked choices, using the form’s order for the remainder. It does not claim that you prefer one unlisted city over another, supply an immigration status or change your relocation preference.'
        }),
        field('candidate.work_arrangement', 'Work arrangement', 'nullable', 'Your remote, hybrid or on-site preference, including any flexibility.'),
        field('candidate.preferred_technical_areas', 'Preferred technical areas', 'tags', 'Rank your interests, separated by commas, for forms offering several teams.', { placeholder: 'Data engineering, Backend' }),
        field('candidate.referral_source', 'How you found the jobs', 'nullable', 'Optional. An actual source here overrides the LinkedIn default. Describe exceptions per employer if needed.'),
        field('candidate.pronouns', 'Pronouns', 'nullable', 'Optional. Separate from gender; optional disclosures still follow your policy.'),
        field('candidate.current_enrollment', 'Current studies', 'nullable', 'Whether and where you are currently enrolled, if known.'),
        field('candidate.future_studies', 'Future study plans', 'nullable', 'Include tentative plans if relevant; leave blank rather than assuming none.'),
        field('candidate.other_offers', 'Other offers and deadlines', 'nullable', 'Only real offers and timelines. Leave blank if not supplied.'),
        field('candidate.prior_applications', 'Prior applications / assessments', 'nullable', 'Employer, role and assessment or interview dates, if relevant to reapplication rules.'),
        field('candidate.assessment_availability', 'Assessment availability', 'nullable', 'Whether you can meet assessment deadlines. This does not authorize proctoring or let the agent take assessments.'),
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
        }),
        ...['bachelors', 'masters'].flatMap(level => {
          const title = level === 'bachelors' ? 'Bachelor’s' : 'Master’s';
          return [
            field(`candidate.education.${level}.degree_title`, `${title} degree title`, 'nullable', 'The official degree title.'),
            field(`candidate.education.${level}.discipline`, `${title} discipline`, 'nullable', 'Your field of study.'),
            field(`candidate.education.${level}.status`, `${title} status`, 'nullable', 'Completed, ongoing or planned, only if known.'),
            field(`candidate.education.${level}.grade`, `${title} grade`, 'nullable', 'Your actual result in its original scale.'),
            field(`candidate.education.${level}.grading_scale`, `${title} grading scale`, 'nullable', 'For example, out of 110. Do not convert a score into a percentile.'),
            field(`candidate.education.${level}.class_rank`, `${title} class rank`, 'nullable', 'Only an established ranking. Leave blank if unknown.')
          ];
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
        field('answers.defaults.referral_source', 'Default discovery source', 'nullable', 'Use this answer for “Where did you hear about us?” when you have not supplied another source.', {
          placeholder: 'LinkedIn',
          help: 'The bot selects the matching option or enters this text. If it is unavailable and the question is required, the bot asks you. It never invents a named referrer. Leave blank to ask instead of using a default.'
        }),
        field('answers.defaults.office_attendance', 'Default office attendance', 'select', 'Answer Yes to office attendance, including a stated number of days per week, unless your preferences say otherwise.', {
          choices: [['true', 'Yes — willing to attend'], ['false', 'No — not willing to attend'], ['null', 'Ask me when required']], nullableBoolean: true,
          help: 'An explicit remote-only preference, day limit, location restriction or specific instruction takes priority. This setting does not authorize assessments, legal declarations or work-rights answers.'
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
      description: 'Choose your documents and give the writer facts and style preferences for cover letters.',
      fields: [
        field('documents.cv', 'CV filename', 'text', 'Upload a finished PDF (up to 10 MB), or enter its filename if it is already in private/.', {
          placeholder: 'alex-example-cv.pdf',
          help: 'The PDF is uploaded to employers unchanged. Selecting it here updates the filename; Save to private/ copies selected PDFs together with your configuration. After choosing your cloned repository once, saves reuse its private/ folder. Browsers without direct folder access export a setup archive. A CV already stored in a subfolder can be entered as documents/cv.pdf.'
        }),
        field('documents.transcript', 'Transcript of records filename', 'nullable', 'Optional. Upload your academic transcript PDF (up to 10 MB), or keep transcript.pdf if you will place it in private/.', {
          placeholder: 'transcript.pdf',
          help: 'Save to private/ copies a selected transcript alongside your CV and configuration. The bot uploads it unchanged only when an application requests academic records. An absent file is fine; a required request makes the bot ask you. Leave blank or choose Do not use a transcript to disable it; existing files are never deleted. Use a different filename from your CV.'
        }),
        field('documents.cover_letter', 'Cover-letter behavior', 'select', 'Write a tailored letter whenever the form offers a cover-letter field, including optional fields.', {
          choices: [['trusted', 'Always write when offered'], ['review', 'Write and review before use'], ['skip', 'Skip cover letters']],
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
  employment_status: null # Employed/unemployed/student; separate from work authorization.
  relocation: ""
  preferred_work_locations: [] # Cities from most to least preferred; empty means unknown.
  preferred_work_locations_unlisted: ask # ask or any_order (append other offered cities).
  work_arrangement: null # Your preference for remote, hybrid or on-site work.
  preferred_technical_areas: [] # Ranked interests for forms offering several teams/specialties.
  referral_source: null # How you actually found these jobs; never assume the employer's website.
  start_date: ""
  date_of_birth: null # Quoted ISO date, e.g. "2000-12-31"; never infer a missing date.
  protected_category_member: null # Explicit false -> No; true -> skip; null -> ask.
  languages: {} # Map each language to your own proficiency; leave empty if not supplied.
  # Example shape (replace with your own facts):
  # languages:
  #   English: "B2 / upper-intermediate"
  #   French: "Beginner"
  gender: null # Optional self-described gender, e.g. "Man", "Woman" or your own wording.
  pronouns: null # Separate from gender; optional questions still follow disclosure policy.
  veteran_status: null # true: veteran; false: not a veteran; null: not supplied.
  # Gender/veteran answers still follow answers.topics.personal_disclosure (ask/infer/skip).
  education:
    bachelors:
      institution: ""
      institution_local_name: ""
      start_date: null # Quoted YYYY-MM-DD.
      end_date: null # Completion/expected completion date; specify status separately if known.
      degree_title: null
      discipline: null
      status: null # Completed/ongoing/planned, only if known.
      grade: null # Your actual grade, as text, e.g. "105"; not a percentile.
      grading_scale: null # Original scale, e.g. "out of 110".
      class_rank: null # Only if established; never inferred from the grade.
    masters:
      institution: ""
      institution_local_name: ""
      start_date: null
      end_date: null
      degree_title: null
      discipline: null
      status: null
      grade: null
      grading_scale: null
      class_rank: null
  current_enrollment: null # Whether/where you currently study; graduation dates alone are not enough.
  future_studies: null # Planned further degrees, including tentative plans if relevant.
  other_offers: null # Actual competing offers and deadlines; unknown does not mean none.
  prior_applications: null # Employer/role and assessment/interview dates, if applicable.
  assessment_availability: null # Your availability for time-limited assessments; agent cannot take them.

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
  Use my ranked locations and work preferences when supplied; residence and willingness
  to relocate alone do not establish a preferred work location or arrangement.
  Use the discovery-source and office-attendance defaults unless my specific preferences override them.
  Never invent named referrers, precise language levels, academic rankings or study plans.
  Ask when a required grade cannot be represented truthfully; skip optional grade questions.
  Ordinary application-data consent does not authorize proctoring or assessment commitments.
  Flag account/profile-creation steps for manual help before proceeding.
  Finish independent fields when an answer is missing, and collect separate questions for review.

answers:
  mode: trusted # trusted: allow supported inference; review: approve inferred answers first.
  protected_category: negative_or_skip # Employment protected category only; ask/skip also supported.
  cookies: accept_when_needed # Accept cookies needed to access the application; use ask to review.
  defaults:
    referral_source: LinkedIn # When no actual source is supplied; use only if the form allows it.
    office_attendance: true # Ordinary on-site/day-count questions; explicit preferences override.
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
  transcript: transcript.pdf # Optional fixed PDF in private/. Missing is fine; null disables it.
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
