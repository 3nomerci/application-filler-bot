import json

import pytest
from conftest import reference

from application_filler.agent import Answer, Complete
from application_filler.browser import BrowserError
from application_filler.config import ConfigurationError, Documents, Settings, transcript_file


@pytest.mark.parametrize("mode", ["manual", "auto"])
@pytest.mark.parametrize("kind", ["textarea", "file"])
def test_optional_letter_must_be_supplied_before_finishing(application, mode, kind):
    control = "<textarea></textarea>" if kind == "textarea" else '<input type="file">'
    html = f"""<form onsubmit="event.preventDefault();window.sent=true">
    <label>Name<input></label><label>Cover letter (optional){control}</label>
    <button>Submit application</button></form>"""
    with application({"/": html}) as a:
        a.settings.submission = mode
        a.answer(
            Answer(
                ref=reference(a, "Name"),
                source="full_name",
                category="general",
                basis="profile",
                reason="Profile",
            )
        )
        submit = reference(a, "Submit application")

        def finish():
            if mode == "auto":
                return a.execute("submit_application", {"ref": submit})
            return a.complete(Complete(status="ready_for_review", reason="Done", ref=submit))

        with pytest.raises(BrowserError, match="Cover letter"):
            finish()
        assert not a.attempted
        assert not (a.artifacts / "submission-ledger").exists()
        ref = reference(a, "Cover letter (optional)")
        if kind == "textarea":
            a.answer(
                Answer(
                    ref=ref,
                    value="I build Python services and am interested in this role.",
                    category="cover_letter",
                    basis="inference",
                    reason="Supplied background",
                )
            )
        else:
            a.execute("create_cover_letter", {"markdown": "Dear team,\n\nI build Python services."})
            a.execute("upload_document", {"ref": ref, "kind": "cover_letter"})
            # Some accepted-upload widgets clear their native input afterwards.
            a.browser.page.locator('input[type="file"]').evaluate("el=>el.value=''")
        finish()
        assert a.attempted == (mode == "auto")
        if mode == "manual":
            assert a.report["status"] == "ready_for_review"


@pytest.mark.parametrize("disabled", [False, True])
def test_cover_letter_skip_and_unrelated_forms_do_not_block(application, disabled):
    html = """<form><label>Name<input></label><button>Submit application</button></form>
    <form><label>Cover letter<textarea></textarea></label></form>"""
    if disabled:
        html = html.replace(
            "</label><button>",
            "</label><label>Cover letter<textarea disabled></textarea></label><button>",
        )
    with application({"/": html}) as a:
        a.settings.submission = "manual"
        a.answer(
            Answer(
                ref=reference(a, "Name"),
                source="full_name",
                category="general",
                basis="profile",
                reason="Profile",
            )
        )
        a.complete(
            Complete(
                status="ready_for_review",
                reason="Application complete",
                ref=reference(a, "Submit application"),
            )
        )
        assert a.report["status"] == "ready_for_review"
    with application({"/": "<form><label>Cover letter<textarea></textarea></label></form>"}) as a:
        a.settings.documents.cover_letter = "skip"
        a.browser.inspect()
        assert a.application_invalid_fields() == []


@pytest.mark.parametrize("native", [False, True])
def test_transcript_upload_is_exact_supplied_pdf(application, native):
    with application(
        {"/": '<label>Transcript of records<input type="file" required></label>'}
    ) as a:
        original = b"%PDF-1.4\n% Fictional academic records\n%%EOF\n"
        (a.private / "transcript.pdf").write_bytes(original)
        ref = reference(a, "Transcript of records")
        if native:
            a.native.execute(
                "file_upload",
                {
                    "target": {"type": "ref", "ref": ref},
                    "document_ids": ["transcript"],
                },
            )
        else:
            a.execute("upload_document", {"ref": ref, "kind": "transcript"})
        uploaded = a.browser.page.locator("input").evaluate(
            "async el=>Array.from(new Uint8Array(await el.files[0].arrayBuffer()))"
        )
        assert bytes(uploaded) == original
        assert (a.private / "transcript.pdf").read_bytes() == original
        assert not a.application_invalid_fields()
        assert not a.generated


@pytest.mark.parametrize("required", [False, True])
def test_missing_transcript_does_not_upload_another_document(application, required):
    html = (
        f'<label>Transcript of records<input type="file" {"required" if required else ""}></label>'
    )
    with application({"/": html}) as a:
        ref = reference(a, "Transcript of records")
        assert transcript_file(a.private, a.settings.documents) is None
        with pytest.raises(BrowserError, match="No transcript PDF"):
            a.execute("upload_document", {"ref": ref, "kind": "transcript"})
        assert a.browser.page.locator("input").evaluate("el=>el.files.length") == 0
        assert bool(a.application_invalid_fields()) == required


def test_transcript_discovery_optional_disable_and_invalid_files(tmp_path):
    docs = Documents()
    assert transcript_file(tmp_path, docs) is None
    supplied = tmp_path / "transcript.pdf"
    supplied.write_bytes(b"not a PDF")
    with pytest.raises(ConfigurationError, match="documents.transcript"):
        transcript_file(tmp_path, docs)
    docs.transcript = None
    assert transcript_file(tmp_path, docs) is None
    supplied.write_bytes(b"%PDF-1.4\n%%EOF\n")
    docs.transcript = supplied.name
    assert transcript_file(tmp_path, docs) == supplied
    docs.transcript = "../outside.pdf"
    with pytest.raises(ConfigurationError):
        transcript_file(tmp_path, docs)
    docs.transcript = supplied.name
    with supplied.open("wb") as output:
        output.truncate(10_000_001)
    with pytest.raises(ConfigurationError):
        transcript_file(tmp_path, docs)


def test_document_availability_is_initial_task_data_not_changing_system(application):
    with application({"/": "<p>Application</p>"}) as a:

        class Client:
            calls = 0

            def message(self, system, messages, *_args):
                self.calls += 1
                assert json.loads(messages[0]["content"])["documents_available"] == {
                    "transcript": False
                }
                (a.private / "transcript.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
                assert a.prompt() == system
                return {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "done",
                            "name": "complete",
                            "input": {"status": "blocked", "reason": "Offline test"},
                        }
                    ]
                }

        a.client = Client()
        assert a.run()["model_calls"] == 1


def test_answer_defaults_can_be_overridden_or_disabled():
    settings = Settings()
    assert settings.answers.defaults.referral_source == "LinkedIn"
    assert settings.answers.defaults.office_attendance is True
    settings = Settings.model_validate(
        {
            "answers": {
                "defaults": {
                    "referral_source": "University careers service",
                    "office_attendance": False,
                }
            }
        }
    )
    assert settings.answers.defaults.referral_source == "University careers service"
    assert settings.answers.defaults.office_attendance is False
    settings = Settings.model_validate(
        {
            "answers": {
                "defaults": {
                    "referral_source": None,
                    "office_attendance": None,
                }
            }
        }
    )
    assert settings.answers.defaults.referral_source is None
    assert settings.answers.defaults.office_attendance is None
