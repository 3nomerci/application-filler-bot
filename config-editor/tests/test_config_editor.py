"""Exercise browser exports with the actual bot configuration loader."""

import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zipfile import ZipFile

import pytest
from playwright.sync_api import expect, sync_playwright

from application_filler.config import Settings, load_cover_letter_examples, load_settings

ROOT = Path(__file__).resolve().parents[2]
EDITOR = ROOT / "config-editor"

MOCK_REPOSITORY = """window.savedFiles = {};
window.saveCount = 0;
window.pickerCalls = 0;
window.permissionRequests = 0;
window.permission = 'granted';
window.writeOrder = [];
window.privateRequests = [];
const privateDirectory = {
  getFileHandle: async (name, options) => {
    if (!options?.create && !(name in window.savedFiles)) {
      throw new DOMException('Missing file', 'NotFoundError');
    }
    return { name,
      getFile: async () => new File([window.savedFiles[name]], name),
      createWritable: async () => {
        let pending;
        return {
          write: async (value) => {
            if (window.failWrite === name) throw new Error('Simulated write failure');
            pending = typeof value === 'string' ? value
              : Array.from(new Uint8Array(await value.arrayBuffer()));
          },
          close: async () => {
            window.savedFiles[name] = pending;
            window.writeOrder.push(name);
            if (name === 'instructions.yaml') window.saveCount += 1;
          },
          abort: async () => {}
        };
      }
    };
  }
};
window.testRepository = {
  kind: 'directory',
  name: decodeURIComponent(
    new URL('../', location.href).pathname.split('/').filter(Boolean).at(-1)),
  queryPermission: async () => window.permission,
  requestPermission: async () => {
    window.permissionRequests += 1;
    window.permission = window.denyPermission ? 'denied' : 'granted';
    return window.permission;
  },
  getDirectoryHandle: async (name, options) => {
    if (name === 'config-editor') {
      if (window.invalidRepository) throw new DOMException('Missing editor', 'NotFoundError');
      return {getFileHandle: async () => ({name: 'index.html'})};
    }
    if (name === 'private') {
      window.privateRequests.push(options || {});
      return privateDirectory;
    }
    throw new Error('Unexpected folder: ' + name);
  }
};
window.showDirectoryPicker = async () => {
  window.pickerCalls += 1;
  if (window.cancelPicker) throw new DOMException('Canceled', 'AbortError');
  return window.testRepository;
};
window.showSaveFilePicker = () => { throw new Error('Save As must never be used'); };
"""


@pytest.fixture(scope="session")
def chromium():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, chromium_sandbox=True)
        yield browser
        browser.close()


@pytest.fixture
def editor(chromium):
    context = chromium.new_context(accept_downloads=True, offline=True)
    page = context.new_page()
    page.add_init_script(MOCK_REPOSITORY)
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    page.goto((EDITOR / "index.html").as_uri())
    expect(page.locator("#save-folder-button")).to_be_enabled()
    yield page
    context.close()
    assert not failures


def raw_yaml(page, source):
    page.get_by_role("button", name="Advanced file editor", exact=True).click()
    page.locator("#raw-text").fill(source)


def export_settings(page, tmp_path):
    count = page.evaluate("window.saveCount")
    page.get_by_role("button", name="Save to private/", exact=True).click()
    page.wait_for_function("count => window.saveCount > count", arg=count)
    expect(page.locator("#save-folder-button")).to_be_enabled()
    path = tmp_path / "instructions.yaml"
    path.write_text(page.evaluate("window.savedFiles['instructions.yaml']"), encoding="utf-8")
    return load_settings(path)


def test_editor_contract_tracks_python_settings():
    source = (EDITOR / "contract.js").read_text(encoding="utf-8")
    contract = json.loads(source.split("window.CONFIG_CONTRACT = ", 1)[1].split(";\n", 1)[0])
    assert contract == Settings.model_json_schema()
    defaults = json.loads(source.split("window.CONFIG_DEFAULTS = ", 1)[1].removesuffix(";\n"))
    assert defaults == Settings().model_dump(mode="json")


def test_location_and_grade_guidance_round_trips_without_inventing_defaults(editor, tmp_path):
    editor.locator("#field-candidate-preferred_work_locations").fill("Paris\nMadrid")
    editor.locator("#field-candidate-work_arrangement").fill("Hybrid")
    editor.get_by_role("button", name="Education", exact=True).click()
    editor.locator("#field-candidate-education-masters-grade").fill("110")
    editor.locator("#field-candidate-education-masters-grading_scale").fill("out of 110")
    settings = export_settings(editor, tmp_path)
    assert settings.candidate["preferred_work_locations"] == ["Paris", "Madrid"]
    assert settings.candidate["work_arrangement"] == "Hybrid"
    assert settings.candidate["education"]["masters"]["grade"] == "110"
    assert settings.candidate["education"]["masters"]["class_rank"] is None
    assert settings.candidate["other_offers"] is None


def test_city_ranking_preserves_order_country_names_and_unlisted_city_policy(editor, tmp_path):
    control = editor.get_by_label("Preferred cities (highest preference first)", exact=True)
    control.fill("Paris, France\nMilan, Italy\nLondon, UK\nZurich, Switzerland")
    editor.get_by_label("Other offered cities", exact=True).select_option("any_order")
    settings = export_settings(editor, tmp_path)
    assert settings.candidate["preferred_work_locations"] == [
        "Paris, France",
        "Milan, Italy",
        "London, UK",
        "Zurich, Switzerland",
    ]
    assert settings.candidate["preferred_work_locations_unlisted"] == "any_order"
    editor.get_by_role("button", name="Education", exact=True).click()
    editor.get_by_role("button", name="Personal information", exact=True).click()
    expect(control).to_have_value("Paris, France\nMilan, Italy\nLondon, UK\nZurich, Switzerland")


def test_form_guidance_uses_plain_input_examples_and_export_matches_bot(editor, tmp_path):
    schema = editor.evaluate("window.CONFIG_SCHEMA")
    for section in schema:
        if section["id"] == "raw":
            continue
        editor.get_by_role("button", name=section["title"], exact=True).click()
        cards = editor.locator(".field-card")
        assert cards.count() == len(section["fields"])
        for index in range(cards.count()):
            card = cards.nth(index)
            expect(card.locator(".field-description")).to_be_visible()
            assert "yaml" not in card.inner_text().lower()
            assert card.locator("pre, .field-example").count() == 0
            controls = card.locator('.field-input:not([type="date"]), .field-textarea')
            for control in controls.all():
                assert control.get_attribute("placeholder")
                assert ": |-" not in control.get_attribute("placeholder")
    settings = export_settings(editor, tmp_path)
    assert settings == load_settings(ROOT / "examples" / "instructions.yaml")


def test_help_adds_details_without_repeating_caption_or_losing_input(editor):
    assert editor.get_by_role("button", name="More about Full name", exact=True).count() == 0
    editor.get_by_role("button", name="Salary preferences", exact=True).click()
    minimum = editor.locator("#field-salary-minimum")
    minimum.fill("EUR 50000 gross annual base")
    button = editor.get_by_role("button", name="More about Salary strategy", exact=True)
    button.click()
    hint = editor.locator("#field-salary-strategy-description").inner_text()
    help_panel = editor.locator("#field-salary-strategy-help")
    expect(help_panel).to_be_visible()
    details = help_panel.inner_text()
    assert hint not in details
    assert "employer’s advertised salary band" in details
    assert "seniority" in details
    assert "40,000" in details
    expect(minimum).to_have_value("EUR 50000 gross annual base")
    button.click()
    expect(help_panel).to_be_hidden()


def test_prefilled_cover_instructions_are_shown_once_and_empty_examples_stay_unsaved(
    editor, tmp_path
):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    instructions = editor.locator("#field-documents-instructions")
    assert instructions.input_value().strip()
    assert not instructions.evaluate("node => node.matches(':placeholder-shown')")
    card = instructions.locator("..")
    assert card.locator(".field-textarea").count() == 1
    assert card.locator("pre, .field-example").count() == 0
    background = editor.locator("#field-documents-background")
    expect(background).to_have_value("")
    assert background.evaluate("node => node.matches(':placeholder-shown')")
    assert export_settings(editor, tmp_path).documents.background == ""


@pytest.mark.parametrize("locale", ["it-IT", "en-US"])
def test_dates_follow_browser_input_and_export_as_bot_dates(chromium, tmp_path, locale):
    context = chromium.new_context(accept_downloads=True, offline=True, locale=locale)
    try:
        page = context.new_page()
        page.add_init_script(MOCK_REPOSITORY)
        page.goto((EDITOR / "index.html").as_uri())
        birth = page.locator("#field-candidate-date_of_birth")
        assert birth.get_attribute("type") == "date"
        hint = page.locator("#field-candidate-date_of_birth-description").inner_text()
        assert "date order shown" in hint
        assert not re.search(r"yyyy|YYYY|YYYY-MM-DD|gg/mm", hint)
        birth.fill("2000-12-31")
        page.get_by_role("button", name="Education", exact=True).click()
        page.locator("#field-candidate-education-bachelors-start_date").fill("2021-09-01")
        settings = export_settings(page, tmp_path)
        assert settings.candidate["date_of_birth"] == "2000-12-31"
        assert settings.candidate["education"]["bachelors"]["start_date"] == "2021-09-01"
    finally:
        context.close()


def test_relocation_choices_export_without_typing_programming_values(editor, tmp_path):
    select = editor.locator("#field-candidate-relocation")
    select.select_option("yes")
    assert export_settings(editor, tmp_path).candidate["relocation"] is True
    select.select_option("no")
    assert export_settings(editor, tmp_path).candidate["relocation"] is False
    select.select_option("unknown")
    assert export_settings(editor, tmp_path).candidate["relocation"] is None
    select.select_option("specific")
    editor.get_by_label("Where would you relocate?", exact=True).fill(
        "Open to relocating within the EU"
    )
    assert (
        export_settings(editor, tmp_path).candidate["relocation"]
        == "Open to relocating within the EU"
    )


def test_form_export_preserves_text_types_and_multiline_examples(editor, tmp_path):
    editor.locator("#field-candidate-full_name").fill("Alex Éxample: # developer")
    editor.locator("#field-candidate-phone").fill("+390123456789")
    editor.locator("#field-candidate-postal_code").fill("00123")
    editor.locator("#field-candidate-citizenships").fill("IT, FR")
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    background = "EDUCATION\nMSc in computing.\n\nPROJECTS\nBuilt Python tools: tested #1.\n"
    letter = "Dear Team,\n\nI enjoy rigorous evaluation.\n\nBest regards,\nAlex\n"
    editor.locator("#field-documents-background").fill(background)
    editor.get_by_role("button", name="+ Add example", exact=True).click()
    editor.locator("[data-example-text]").fill(letter)
    settings = export_settings(editor, tmp_path)
    assert settings.candidate["full_name"] == "Alex Éxample: # developer"
    assert settings.candidate["phone"] == "+390123456789"
    assert settings.candidate["postal_code"] == "00123"
    assert settings.candidate["citizenships"] == ["IT", "FR"]
    assert settings.documents.background == background
    assert load_cover_letter_examples(tmp_path, settings.documents) == [letter]


def test_new_profile_fields_have_neutral_defaults(editor, tmp_path):
    expect(editor.locator("#field-candidate-gender")).to_have_value("")
    expect(editor.locator("#field-candidate-veteran_status")).to_have_value("null")
    editor.get_by_role("button", name="Languages", exact=True).click()
    assert editor.locator(".language-row").count() == 0
    settings = export_settings(editor, tmp_path)
    assert settings.candidate["languages"] == {}
    assert settings.candidate["gender"] is None
    assert settings.candidate["veteran_status"] is None


def test_new_profile_controls_import_and_export_the_supplied_facts(editor, tmp_path):
    source = """version: 2
candidate:
  languages:
    English: C1/fluent
    Italian: Native
    French: Beginner
  gender: Man
  veteran_status: false
answers:
  topics:
    personal_disclosure: infer
"""
    editor.locator("#file-input").set_input_files(
        {"name": "instructions.yaml", "mimeType": "text/plain", "buffer": source.encode()}
    )
    expect(editor.get_by_label("Gender", exact=True)).to_have_value("Man")
    expect(editor.get_by_label("Veteran status", exact=True)).to_have_value("false")
    editor.get_by_role("button", name="Languages", exact=True).click()
    assert editor.locator(".language-row").count() == 3
    expect(editor.get_by_role("textbox", name="Language 1", exact=True)).to_have_value("English")
    expect(editor.get_by_role("textbox", name="Proficiency 1", exact=True)).to_have_value(
        "C1/fluent"
    )
    expect(editor.get_by_role("textbox", name="Proficiency 2", exact=True)).to_have_value("Native")
    expect(editor.get_by_role("textbox", name="Proficiency 3", exact=True)).to_have_value(
        "Beginner"
    )
    settings = export_settings(editor, tmp_path)
    assert settings.candidate["languages"] == {
        "English": "C1/fluent",
        "Italian": "Native",
        "French": "Beginner",
    }
    assert settings.candidate["gender"] == "Man"
    assert settings.candidate["veteran_status"] is False
    assert settings.answers.topics["personal_disclosure"] == "infer"
    editor.get_by_role("textbox", name="Proficiency 1", exact=True).fill("C2")
    editor.get_by_role("button", name="Remove language 3", exact=True).click()
    editor.get_by_role("button", name="Personal information", exact=True).click()
    editor.get_by_label("Gender", exact=True).fill("My own wording")
    editor.get_by_label("Veteran status", exact=True).select_option("true")
    edited = export_settings(editor, tmp_path)
    assert edited.candidate["languages"] == {"English": "C2", "Italian": "Native"}
    assert edited.candidate["gender"] == "My own wording"
    assert edited.candidate["veteran_status"] is True
    editor.get_by_label("Gender", exact=True).fill("")
    editor.get_by_label("Veteran status", exact=True).select_option("null")
    cleared = export_settings(editor, tmp_path)
    assert cleared.candidate["gender"] is None
    assert cleared.candidate["veteran_status"] is None


def test_language_rows_can_be_added_renamed_and_removed_without_losing_drafts(editor, tmp_path):
    editor.get_by_role("button", name="Languages", exact=True).click()
    editor.get_by_role("button", name="+ Add language", exact=True).click()
    expect(editor.locator("#save-folder-button")).to_be_disabled()
    expect(editor.locator("#dirty-indicator")).to_be_visible()
    editor.get_by_role("textbox", name="Language 1", exact=True).fill("English")
    editor.get_by_role("button", name="Personal information", exact=True).click()
    editor.get_by_role("button", name="Languages", exact=True).click()
    expect(editor.get_by_role("textbox", name="Language 1", exact=True)).to_have_value("English")
    editor.get_by_role("textbox", name="Proficiency 1", exact=True).fill("C1/fluent")
    assert export_settings(editor, tmp_path).candidate["languages"] == {"English": "C1/fluent"}
    editor.get_by_role("button", name="+ Add language", exact=True).click()
    editor.get_by_role("textbox", name="Language 2", exact=True).fill("english")
    editor.get_by_role("textbox", name="Proficiency 2", exact=True).fill("B2")
    expect(editor.locator("#save-folder-button")).to_be_disabled()
    expect(editor.locator("#notices")).to_contain_text("each language can appear only once")
    editor.get_by_role("textbox", name="Language 2", exact=True).fill("French")
    assert export_settings(editor, tmp_path).candidate["languages"] == {
        "English": "C1/fluent",
        "French": "B2",
    }
    editor.get_by_role("button", name="Remove language 1", exact=True).click()
    assert export_settings(editor, tmp_path).candidate["languages"] == {"French": "B2"}
    editor.get_by_role("button", name="Remove language 1", exact=True).click()
    assert export_settings(editor, tmp_path).candidate["languages"] == {}


def test_import_replaces_unfinished_language_drafts_and_raw_changes_refresh_controls(editor):
    editor.get_by_role("button", name="Languages", exact=True).click()
    editor.get_by_role("button", name="+ Add language", exact=True).click()
    editor.get_by_role("textbox", name="Language 1", exact=True).fill("Unfinished")
    editor.locator("#file-input").set_input_files(
        {
            "name": "instructions.yaml",
            "mimeType": "text/plain",
            "buffer": b"candidate: {languages: {French: Beginner}}\n",
        }
    )
    editor.get_by_role("button", name="Languages", exact=True).click()
    expect(editor.get_by_role("textbox", name="Language 1", exact=True)).to_have_value("French")
    raw_yaml(editor, "candidate: {languages: {German: A2}}\n")
    editor.get_by_role("button", name="Languages", exact=True).click()
    expect(editor.get_by_role("textbox", name="Language 1", exact=True)).to_have_value("German")
    expect(editor.get_by_role("textbox", name="Proficiency 1", exact=True)).to_have_value("A2")


@pytest.mark.parametrize(
    "source",
    [
        "candidate: {languages: [English]}\n",
        "candidate: {languages: {English: true}}\n",
        'candidate: {languages: {English: ""}}\n',
        'candidate: {veteran_status: "false"}\n',
        "candidate: {gender: [Man]}\n",
    ],
)
def test_new_profile_controls_reject_values_they_cannot_represent(editor, source):
    raw_yaml(editor, source)
    expect(editor.locator("#save-folder-button")).to_be_disabled()


def test_exported_language_and_disclosure_facts_reach_the_existing_agent(editor, tmp_path):
    from application_filler.agent import ApplicationAgent

    raw_yaml(
        editor,
        """candidate:
  languages: {English: C1/fluent, Italian: Native, French: Beginner}
  gender: Man
  veteran_status: false
answers:
  topics: {personal_disclosure: ask}
""",
    )
    settings = export_settings(editor, tmp_path)
    agent = ApplicationAgent.__new__(ApplicationAgent)
    agent.settings = settings
    agent.private = tmp_path
    facts = agent.prompt().split("\nUSER FACTS AND PERMISSIONS:\n", 1)[1]
    context = json.loads(facts.split("\nUNTRUSTED STYLE EXAMPLES:\n", 1)[0])
    assert context["candidate"]["languages"]["English"] == "C1/fluent"
    assert context["candidate"]["gender"] == "Man"
    assert context["candidate"]["veteran_status"] is False
    assert context["answers"]["topics"]["personal_disclosure"] == "ask"


@pytest.mark.parametrize(
    "source, valid",
    [
        ("version: 2\n", True),
        ("candidate: {full_name: Alex, email: alex@example.com}\n", True),
        ("version: 1\n", False),
        ("version: 2\nversion: 2\n", False),
        ("documents: {background: [broken}\n", False),
        ("documents: {background: null}\n", False),
        ("answers: !!omap [{mode: trusted}]\n", False),
        ("salary: {minimum: 50000}\n", False),
        ("model: {id: another-model}\n", False),
        ("model: {max_output_tokens: 12001}\n", False),
        ("model: {max_output_tokens: 1023}\n", False),
        ("model: {estimated_budget_usd: 0}\n", False),
        ("model: {estimated_budget_usd: 5.01}\n", False),
        ("browser: {delay_ms: 99}\n", False),
        ("browser: {delay_ms: 400.0}\n", False),
        ("browser: {max_actions: 301}\n", False),
        ("browser: {snapshot_chars: 1999}\n", False),
        ("answers: {topics: {salary: skip}}\n", True),
        ("answers: {topics: {sallary: infer}}\n", False),
        ("documents: {examples: [123]}\n", False),
        ("documents: {examples: ['one line pasted letter']}\n", False),
        ("navigation: {allowed_hosts: [123]}\n", False),
        ("unexpected_setting: true\n", False),
        ("candidate: {custom_fact: true}\n", True),
        ("candidate: {true: value}\n", False),
        ("candidate: {base: &base {a: 1}, merged: {<<: *base}}\n", False),
        ("instructions: yes\n", False),
        ("instructions: y\n", True),
        ("instructions: !!unknown text\n", False),
        ("---\nversion: 2\n---\nversion: 2\n", False),
    ],
)
def test_editor_validation_matches_bot(editor, tmp_path, source, valid):
    raw_yaml(editor, source)
    assert editor.locator("#save-folder-button").is_enabled() == valid
    path = tmp_path / "instructions.yaml"
    path.write_text(source, encoding="utf-8")
    if valid:
        load_settings(path)
    else:
        with pytest.raises(ValueError):
            settings = load_settings(path)
            load_cover_letter_examples(tmp_path, settings.documents)


def test_import_and_edit_folded_text_comments_and_custom_facts(editor, tmp_path):
    source = """\ufeffversion: 2
# Keep my configuration comment
candidate:
  full_name: Alex
  citizenships: IT
  custom_fact: 'Leading zero: 00123'
documents:
  background: >-
    First paragraph wraps
    to a second line.

    Another paragraph.
  examples:
    - |+
      Dear Team,

      I enjoy research.

      Alex

"""
    path = tmp_path / "import.yaml"
    path.write_text(source, encoding="utf-8")
    before = load_settings(path)
    editor.locator("#file-input").set_input_files(path)
    editor.locator("#field-candidate-full_name").fill("Alex Example")
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    expect(editor.locator("#field-documents-background")).to_have_value(before.documents.background)
    expect(editor.locator("[data-example-text]")).to_have_value(before.documents.examples[0])
    after = export_settings(editor, tmp_path)
    assert after.documents == before.documents
    assert after.candidate["custom_fact"] == before.candidate["custom_fact"]
    assert "# Keep my configuration comment" in (tmp_path / "instructions.yaml").read_text()


def test_missing_sections_use_bot_defaults_and_can_be_added(editor, tmp_path):
    raw_yaml(editor, "version: 2\n")
    editor.get_by_role("button", name="Agent behavior", exact=True).click()
    expect(editor.locator("#field-answers-topics-salary")).to_have_value("infer")
    editor.locator("#field-answers-mode").select_option("review")
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    expect(editor.locator("#field-documents-cv")).to_have_value("cv.pdf")
    editor.locator("#field-documents-background").fill("I build Python tools.")
    settings = export_settings(editor, tmp_path)
    assert settings.answers.mode == "review"
    assert settings.documents.background == "I build Python tools."


def test_cv_upload_save_and_reject_invalid_files(editor, tmp_path):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    original = b"%PDF-1.4\n% Fictional test CV\n%%EOF\n"
    editor.locator("#cv-file-input").set_input_files(
        {"name": "alex-cv.pdf", "mimeType": "application/pdf", "buffer": original}
    )
    expect(editor.locator("#field-documents-cv")).to_have_value("alex-cv.pdf")
    assert export_settings(editor, tmp_path).documents.cv == "alex-cv.pdf"
    assert bytes(editor.evaluate("window.savedFiles['alex-cv.pdf']")) == original
    assert editor.get_by_role("button", name="Download selected PDF", exact=True).count() == 0
    editor.locator("#cv-file-input").set_input_files(
        {"name": "invalid.pdf", "mimeType": "application/pdf", "buffer": b"Not a PDF"}
    )
    expect(editor.locator("#toast")).to_contain_text("PDF header")
    expect(editor.locator("#field-documents-cv")).to_have_value("alex-cv.pdf")


def test_transcript_and_cv_save_together_and_can_disable_without_deleting(editor, tmp_path):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    cv = b"%PDF-1.4\n% Fictional CV\n%%EOF\n"
    records = b"%PDF-1.4\n% Fictional transcript\n%%EOF\n"
    for kind, data in [("cv", cv), ("transcript", records)]:
        editor.locator(f"#{kind}-file-input").set_input_files(
            {"name": f"{kind}.pdf", "mimeType": "application/pdf", "buffer": data}
        )
    settings = export_settings(editor, tmp_path)
    assert settings.documents.transcript == "transcript.pdf"
    saved = editor.evaluate("window.savedFiles")
    assert bytes(saved["cv.pdf"]) == cv
    assert bytes(saved["transcript.pdf"]) == records
    assert editor.evaluate("window.writeOrder") == ["cv.pdf", "transcript.pdf", "instructions.yaml"]
    editor.get_by_role("button", name="Do not use a transcript", exact=True).click()
    assert export_settings(editor, tmp_path).documents.transcript is None
    assert bytes(editor.evaluate("window.savedFiles['transcript.pdf']")) == records


def test_failed_transcript_save_does_not_write_configuration(editor):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    editor.locator("#transcript-file-input").set_input_files(
        {"name": "records.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\n%%EOF\n"}
    )
    editor.evaluate("window.failWrite = 'records.pdf'")
    editor.locator("#save-folder-button").click()
    expect(editor.locator("#toast")).to_contain_text("Could not save")
    expect(editor.locator("#save-folder-button")).to_be_enabled()
    expect(editor.locator("#dirty-indicator")).to_be_visible()
    assert "instructions.yaml" not in editor.evaluate("window.savedFiles")


def test_transcript_rejects_invalid_pdf_and_cv_filename_collision(editor):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    editor.locator("#transcript-file-input").set_input_files(
        {"name": "invalid.pdf", "mimeType": "application/pdf", "buffer": b"not PDF"}
    )
    expect(editor.locator("#toast")).to_contain_text("PDF header")
    editor.locator("#transcript-file-input").set_input_files(
        {"name": "CV.PDF", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\n%%EOF\n"}
    )
    expect(editor.locator("#toast")).to_contain_text("different filenames")
    editor.locator("#field-documents-transcript").fill("cv.pdf")
    expect(editor.locator("#save-folder-button")).to_be_disabled()
    expect(editor.locator("#notices")).to_contain_text("different filenames")


def test_discovery_and_office_defaults_round_trip_and_can_be_disabled(editor, tmp_path):
    editor.get_by_role("button", name="Agent behavior", exact=True).click()
    source = editor.locator("#field-answers-defaults-referral_source")
    office = editor.locator("#field-answers-defaults-office_attendance")
    expect(source).to_have_value("LinkedIn")
    expect(office).to_have_value("true")
    source.fill("University careers service")
    office.select_option("false")
    settings = export_settings(editor, tmp_path)
    assert settings.answers.defaults.referral_source == "University careers service"
    assert settings.answers.defaults.office_attendance is False
    source.fill("")
    office.select_option("null")
    settings = export_settings(editor, tmp_path)
    assert settings.answers.defaults.referral_source is None
    assert settings.answers.defaults.office_attendance is None


def test_save_private_folder_writes_yaml_and_unchanged_pdf(editor, tmp_path):
    assert editor.locator(".toolbar .primary").get_attribute("id") == "save-folder-button"
    assert editor.locator(".toolbar button").count() == 3
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    original = b"%PDF-1.4\n%%EOF\n"
    editor.locator("#cv-file-input").set_input_files(
        {"name": "cv.pdf", "mimeType": "application/pdf", "buffer": original}
    )
    settings = export_settings(editor, tmp_path)
    expect(editor.locator("#toast")).to_contain_text("Saved instructions.yaml and your CV")
    saved = editor.evaluate("window.savedFiles")
    assert bytes(saved["cv.pdf"]) == original
    assert settings.documents.cv == "cv.pdf"
    assert editor.evaluate("window.writeOrder") == ["cv.pdf", "instructions.yaml"]
    editor.get_by_role("button", name="Personal information", exact=True).click()
    editor.locator("#field-candidate-full_name").fill("Alex Example")
    assert export_settings(editor, tmp_path).candidate["full_name"] == "Alex Example"
    assert editor.evaluate("window.pickerCalls") == 1
    assert all(options == {"create": True} for options in editor.evaluate("window.privateRequests"))


def test_open_connects_once_and_later_saves_use_the_same_repository(editor, tmp_path):
    editor.evaluate("window.savedFiles['instructions.yaml'] = 'candidate: {full_name: Alex}\\n'")
    editor.get_by_role("button", name="Open configuration", exact=True).click()
    expect(editor.locator("#field-candidate-full_name")).to_have_value("Alex")
    editor.locator("#field-candidate-full_name").fill("Alex Example")
    assert export_settings(editor, tmp_path).candidate["full_name"] == "Alex Example"
    assert editor.evaluate("window.pickerCalls") == 1
    expect(editor.locator("#save-guidance")).to_contain_text("/private/")


def test_save_renews_permission_without_reopening_the_picker(editor, tmp_path):
    export_settings(editor, tmp_path)
    editor.evaluate("window.permission = 'prompt'")
    editor.locator("#field-candidate-full_name").fill("Alex")
    export_settings(editor, tmp_path)
    assert editor.evaluate("window.pickerCalls") == 1
    assert editor.evaluate("window.permissionRequests") == 1
    editor.evaluate("window.permission = 'prompt'; window.denyPermission = true")
    editor.locator("#field-candidate-full_name").fill("Unsaved edit")
    count = editor.evaluate("window.saveCount")
    editor.locator("#save-folder-button").click()
    expect(editor.locator("#toast")).to_contain_text("Folder access was not granted")
    expect(editor.locator("#dirty-indicator")).to_be_visible()
    assert editor.evaluate("window.saveCount") == count


def test_new_profile_reuses_the_connected_repository(editor, tmp_path):
    export_settings(editor, tmp_path)
    editor.get_by_role("button", name="New", exact=True).click()
    editor.locator("#field-candidate-full_name").fill("New profile")
    assert export_settings(editor, tmp_path).candidate["full_name"] == "New profile"
    assert editor.evaluate("window.pickerCalls") == 1


def test_canceling_repository_change_keeps_the_previous_destination(editor, tmp_path):
    export_settings(editor, tmp_path)
    editor.evaluate("window.cancelPicker = true")
    editor.get_by_role("button", name="Change repository", exact=True).click()
    expect(editor.locator("#save-folder-button")).to_be_enabled()
    editor.evaluate("window.cancelPicker = false")
    editor.locator("#field-candidate-full_name").fill("Same destination")
    assert export_settings(editor, tmp_path).candidate["full_name"] == "Same destination"
    assert editor.evaluate("window.pickerCalls") == 2  # One connection and one canceled change.


@pytest.mark.parametrize("failure", ["cancel", "invalid_repository", "pdf_write"])
def test_failed_or_canceled_save_keeps_edits_and_does_not_write_yaml(editor, failure):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    editor.locator("#cv-file-input").set_input_files(
        {"name": "cv.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\n%%EOF\n"}
    )
    if failure == "cancel":
        editor.evaluate("window.cancelPicker = true")
    elif failure == "invalid_repository":
        editor.evaluate("window.invalidRepository = true")
    else:
        editor.evaluate("window.failWrite = 'cv.pdf'")
    editor.locator("#save-folder-button").click()
    if failure != "cancel":
        expect(editor.locator("#toast")).to_contain_text("Could not save")
    expect(editor.locator("#save-folder-button")).to_be_enabled()
    expect(editor.locator("#dirty-indicator")).to_be_visible()
    assert "instructions.yaml" not in editor.evaluate("window.savedFiles")


@pytest.mark.parametrize("with_cv", [False, True])
@pytest.mark.parametrize("with_transcript", [False, True])
def test_primary_save_exports_a_single_archive_without_folder_access(
    editor, tmp_path, with_cv, with_transcript
):
    editor.add_init_script(
        "Object.defineProperty(window, 'showDirectoryPicker', "
        "{value: undefined, configurable: true});"
    )
    editor.reload()
    button = editor.get_by_role("button", name="Export setup (.zip)", exact=True)
    expect(button).to_be_visible()
    assert editor.locator(".toolbar .primary").get_attribute("id") == "save-folder-button"
    expect(editor.locator("#save-guidance")).to_be_visible()
    original = b"%PDF-1.4\n% Fictional CV\n%%EOF\n"
    if with_cv:
        editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
        editor.locator("#cv-file-input").set_input_files(
            {"name": "résumé.pdf", "mimeType": "application/pdf", "buffer": original}
        )
    records = b"%PDF-1.4\n% Fictional transcript\n%%EOF\n"
    if with_transcript:
        editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
        editor.locator("#transcript-file-input").set_input_files(
            {"name": "records.pdf", "mimeType": "application/pdf", "buffer": records}
        )
    with editor.expect_download() as event:
        button.click()
    path = tmp_path / event.value.suggested_filename
    event.value.save_as(path)
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        expected = {"private/instructions.yaml"}
        if with_cv:
            expected.add("private/résumé.pdf")
            assert archive.read("private/résumé.pdf") == original
        if with_transcript:
            expected.add("private/records.pdf")
            assert archive.read("private/records.pdf") == records
        assert set(archive.namelist()) == expected
        config = tmp_path / "instructions.yaml"
        config.write_bytes(archive.read("private/instructions.yaml"))
        assert load_settings(config).version == 2


def test_repository_handle_is_restored_across_reload_and_scoped_to_checkout(chromium):
    class EditorHandler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            return super().translate_path(re.sub(r"^/(copy-a|copy-b)/config-editor/", "/", path))

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(EditorHandler, directory=str(EDITOR)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    context = chromium.new_context()
    try:
        page = context.new_page()
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.add_init_script("""window.showDirectoryPicker = async () => {
          localStorage.setItem('pickerCalls', Number(localStorage.getItem('pickerCalls') || 0) + 1);
          const storage = await navigator.storage.getDirectory();
          const root = await storage.getDirectoryHandle(
            location.pathname.split('/')[1], {create: true});
          const editor = await root.getDirectoryHandle('config-editor', {create: true});
          await editor.getFileHandle('index.html', {create: true});
          return root;
        };""")
        origin = f"http://127.0.0.1:{server.server_port}"
        first = f"{origin}/copy-a/config-editor/index.html"
        page.goto(first)
        page.locator("#field-candidate-full_name").fill("Alex in first checkout")
        page.locator("#save-folder-button").click()
        expect(page.locator("#toast")).to_contain_text("copy-a/private/")
        expect(page.locator("#save-guidance")).to_contain_text("remembered")
        page.reload()
        expect(page.locator("#save-guidance")).to_contain_text("copy-a/private/")
        page.get_by_role("button", name="Open configuration", exact=True).click()
        expect(page.locator("#field-candidate-full_name")).to_have_value("Alex in first checkout")
        assert page.evaluate("localStorage.getItem('pickerCalls')") == "1"
        page.goto(f"{origin}/copy-b/config-editor/index.html")
        expect(page.locator("#save-folder-button")).to_be_enabled()
        expect(page.locator("#change-folder-button")).to_be_hidden()
        page.locator("#save-folder-button").click()
        expect(page.locator("#toast")).to_contain_text("copy-b/private/")
        assert page.evaluate("localStorage.getItem('pickerCalls')") == "2"
        page.goto(first)
        page.get_by_role("button", name="Open configuration", exact=True).click()
        expect(page.locator("#field-candidate-full_name")).to_have_value("Alex in first checkout")
        assert page.evaluate("localStorage.getItem('pickerCalls')") == "2"
        assert not failures
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        worker.join()


def test_system_dark_mode_keeps_the_light_theme_and_mobile_layout(editor):
    editor.emulate_media(color_scheme="dark")
    assert editor.locator("html").evaluate("el => getComputedStyle(el).colorScheme") == "light only"
    for selector in [".field-input", ".field-card", ".notice.warning"]:
        colors = editor.locator(selector).first.evaluate(
            "el => [getComputedStyle(el).color, getComputedStyle(el).backgroundColor]"
        )

        def luminance(color):
            channels = [int(value) / 255 for value in re.findall(r"\d+", color)[:3]]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return sum(
                c * weight for c, weight in zip(linear, [0.2126, 0.7152, 0.0722], strict=True)
            )

        light, dark = sorted(map(luminance, colors), reverse=True)
        assert (light + 0.05) / (dark + 0.05) >= 4.5
        if selector != ".notice.warning":
            assert colors[1] == "rgb(255, 255, 255)"
    editor.set_viewport_size({"width": 390, "height": 844})
    assert editor.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
