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
    page.get_by_role("button", name="Raw YAML", exact=True).click()
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


def test_every_field_has_visible_examples_and_export_matches_bot(editor, tmp_path):
    schema = editor.evaluate("window.CONFIG_SCHEMA")
    for section in schema:
        if section["id"] == "raw":
            continue
        editor.get_by_role("button", name=section["title"], exact=True).click()
        cards = editor.locator(".field-card")
        assert cards.count() == len(section["fields"])
        for index in range(cards.count()):
            expect(cards.nth(index).locator(".field-example")).to_be_visible()
            assert cards.nth(index).locator(".field-example pre").inner_text().strip()
    settings = export_settings(editor, tmp_path)
    assert settings == load_settings(ROOT / "examples" / "instructions.yaml")


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


def test_dark_mode_and_mobile_remain_readable(editor):
    editor.emulate_media(color_scheme="dark")
    assert (
        editor.locator("body").evaluate("el => getComputedStyle(el).color") == "rgb(225, 233, 245)"
    )
    for selector in [".field-input", ".field-card", ".field-example pre", ".notice.warning"]:
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
        assert colors[1] != "rgb(255, 255, 255)"
    editor.set_viewport_size({"width": 390, "height": 844})
    assert editor.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
