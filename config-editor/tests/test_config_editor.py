"""Exercise browser exports with the actual bot configuration loader."""

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from application_filler.config import Settings, load_cover_letter_examples, load_settings

ROOT = Path(__file__).resolve().parents[2]
EDITOR = ROOT / "config-editor"


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
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    page.goto((EDITOR / "index.html").as_uri())
    yield page
    context.close()
    assert not failures


def raw_yaml(page, source):
    page.get_by_role("button", name="Advanced file editor", exact=True).click()
    page.locator("#raw-text").fill(source)


def export_settings(page, tmp_path):
    with page.expect_download() as event:
        page.get_by_role("button", name="Download", exact=True).click()
    path = tmp_path / "instructions.yaml"
    event.value.save_as(path)
    return load_settings(path)


def test_editor_contract_tracks_python_settings():
    source = (EDITOR / "contract.js").read_text(encoding="utf-8")
    contract = json.loads(source.split("window.CONFIG_CONTRACT = ", 1)[1].split(";\n", 1)[0])
    assert contract == Settings.model_json_schema()
    defaults = json.loads(source.split("window.CONFIG_DEFAULTS = ", 1)[1].removesuffix(";\n"))
    assert defaults == Settings().model_dump(mode="json")


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
    expect(editor.locator("#download-button")).to_be_disabled()
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
    expect(editor.locator("#download-button")).to_be_disabled()
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
    expect(editor.locator("#download-button")).to_be_disabled()


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
    assert editor.locator("#download-button").is_enabled() == valid
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


def test_cv_upload_download_and_reject_invalid_files(editor, tmp_path):
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    original = b"%PDF-1.4\n% Fictional test CV\n%%EOF\n"
    editor.locator("#cv-file-input").set_input_files(
        {"name": "alex-cv.pdf", "mimeType": "application/pdf", "buffer": original}
    )
    expect(editor.locator("#field-documents-cv")).to_have_value("alex-cv.pdf")
    assert export_settings(editor, tmp_path).documents.cv == "alex-cv.pdf"
    with editor.expect_download() as event:
        editor.get_by_role("button", name="Download selected PDF", exact=True).click()
    path = tmp_path / event.value.suggested_filename
    event.value.save_as(path)
    assert path.read_bytes() == original
    editor.locator("#cv-file-input").set_input_files(
        {"name": "invalid.pdf", "mimeType": "application/pdf", "buffer": b"Not a PDF"}
    )
    expect(editor.locator("#toast")).to_contain_text("PDF header")
    expect(editor.locator("#field-documents-cv")).to_have_value("alex-cv.pdf")


def test_save_private_folder_writes_yaml_and_unchanged_pdf(editor, tmp_path):
    editor.add_init_script("""window.savedFiles = {};
      window.showDirectoryPicker = async () => ({ name: 'private',
        getFileHandle: async (name) => ({ name,
          createWritable: async () => ({
            write: async (value) => { window.savedFiles[name] = typeof value === 'string'
              ? value : Array.from(new Uint8Array(await value.arrayBuffer())); },
            close: async () => {}, abort: async () => {}
          })
        })
      });""")
    editor.reload()
    assert editor.locator(".toolbar .primary").get_attribute("id") == "save-folder-button"
    editor.get_by_role("button", name="Documents & cover letters", exact=True).click()
    original = b"%PDF-1.4\n%%EOF\n"
    editor.locator("#cv-file-input").set_input_files(
        {"name": "cv.pdf", "mimeType": "application/pdf", "buffer": original}
    )
    expect(editor.get_by_role("button", name="Download selected PDF", exact=True)).to_be_visible()
    editor.get_by_role("button", name="Save to private/", exact=True).click()
    expect(editor.locator("#toast")).to_contain_text("Saved instructions.yaml and your CV")
    saved = editor.evaluate("window.savedFiles")
    assert bytes(saved["cv.pdf"]) == original
    path = tmp_path / "instructions.yaml"
    path.write_text(saved["instructions.yaml"], encoding="utf-8")
    assert load_settings(path).documents.cv == "cv.pdf"


def test_primary_save_has_a_download_fallback_without_folder_access(editor, tmp_path):
    editor.add_init_script(
        "Object.defineProperty(window, 'showDirectoryPicker', {value: undefined});"
    )
    editor.reload()
    button = editor.get_by_role("button", name="Download for private/", exact=True)
    expect(button).to_be_visible()
    assert editor.locator(".toolbar .primary").get_attribute("id") == "save-folder-button"
    expect(editor.locator("#save-guidance")).to_be_visible()
    with editor.expect_download() as event:
        button.click()
    path = tmp_path / event.value.suggested_filename
    event.value.save_as(path)
    assert load_settings(path).version == 2


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
