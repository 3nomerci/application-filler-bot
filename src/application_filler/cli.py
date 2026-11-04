import argparse
import json
import os
import shutil
import sys
import tempfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

import yaml
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from pydantic import ValidationError

from .agent import ApplicationAgent
from .browser import BrowserError, BrowserSession, NetworkGuard
from .config import load_cover_letter_examples, load_settings, load_yaml
from .demo import ScriptedDemoClient, demo_server, demo_settings
from .documents import remove_generated, render_letter
from .llm import ClaudeClient


def initialize(upgrade=False):
    root = Path("private")
    root.mkdir(exist_ok=True)
    target = root / "instructions.yaml"
    if not target.exists():
        shutil.copyfile("examples/instructions.yaml", target)
    elif upgrade:
        old = load_yaml(target)
        if isinstance(old, dict) and old.get("version") == 1:
            fresh = load_yaml(Path("examples/instructions.yaml"))
            # Preserve user-entered facts without printing them or reading any .env/secret file.
            fresh["candidate"].update(old.get("candidate", {}))
            fresh["submission"] = old.get("submission", {}).get("mode", "manual")
            for name, rule in old.get("rules", {}).items():
                if name in {"expected_salary", "work_authorization", "sponsorship", "consent"}:
                    if rule.get("action") == "ask":
                        topic = {
                            "expected_salary": "salary",
                            "sponsorship": "work_authorization",
                        }.get(name, name)
                        fresh["answers"]["topics"][topic] = "ask"
            backup = root / (
                "instructions-v1-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".yaml"
            )
            shutil.copyfile(target, backup)
            target.write_text(
                yaml.safe_dump(fresh, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            print(
                "Version 1 backed up and migrated. Previous ask policies were preserved; "
                "set salary/work_authorization to infer if desired. Review the new instructions."
            )
    links = root / "links.txt"
    if not links.exists():
        links.write_text("# One job listing or application URL per line.\n", encoding="utf-8")
    print("Edit private/instructions.yaml and place your unchanged CV at private/cv.pdf.")


def run(args, settings):
    if not os.getenv("FILLER_IN_DOCKER") and not args.dev_local:
        raise ValueError(
            "Run the agent through Docker; see README.md. --dev-local is for developers."
        )
    urls = list(getattr(args, "urls", []))
    if getattr(args, "links", None):
        urls += [
            x.strip()
            for x in args.links.read_text(encoding="utf-8-sig").splitlines()
            if x.strip() and not x.lstrip().startswith("#")
        ]
    urls = list(dict.fromkeys(urls))
    local_demo = args.command == "self-test" or getattr(args, "demo", False)
    if local_demo and urls:
        raise ValueError("The demo does not accept real URLs")
    if not local_demo and not 1 <= len(urls) <= 20:
        raise ValueError("Supply 1–20 URLs or --links private/links.txt")
    if args.interactive and not sys.stdin.isatty():
        raise ValueError("Interactive mode requires an attached terminal")
    private = args.config.resolve().parent
    artifacts = Path("artifacts")
    artifacts.mkdir(exist_ok=True)
    reports, agents, contexts = [], [], []
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = artifacts / f"run-{timestamp}.json"
    client = ScriptedDemoClient() if args.command == "self-test" else ClaudeClient(settings.model)

    def save():
        report_path.write_text(
            json.dumps(
                {
                    "applications": reports,
                    "usage": client.usage,
                    "estimated_usd": round(client.estimated_usd, 6),
                    "scripted_test": args.command == "self-test",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    with ExitStack() as stack:
        if local_demo:
            print(
                "Using fictional profile and local site. "
                + (
                    "Scripted model: no API calls."
                    if args.command == "self-test"
                    else "REAL Haiku API calls: credits will be used."
                )
            )
            urls = [stack.enter_context(demo_server())]
            private = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            _, pdf = render_letter(
                "# Alex Example\n\nFictional CV: I build Python services.", private
            )
            shutil.copyfile(pdf, private / "cv.pdf")
            settings = demo_settings()
        os.environ.setdefault(
            "PLAYWRIGHT_BROWSERS_PATH", str(Path(".cache/ms-playwright").resolve())
        )
        pw = stack.enter_context(sync_playwright())
        # Only a minimal OS/display environment reaches Chromium; it never receives API credentials.
        permitted = {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
            "DISPLAY",
            "XAUTHORITY",
            "LANG",
            "LC_ALL",
        }
        env = {k: v for k, v in os.environ.items() if k.upper() in permitted}
        browser = pw.chromium.launch(headless=args.headless, chromium_sandbox=True, env=env)
        stack.callback(browser.close)
        try:
            for index, url in enumerate(urls):
                print(f"Application {index + 1}/{len(urls)}: agent starting")
                try:
                    guard = NetworkGuard(url, settings, demo=local_demo)
                    context = browser.new_context(accept_downloads=False, service_workers="block")
                    contexts.append(context)
                    session = BrowserSession(context, guard, settings)
                    session.open(url, initial=True)
                    agent = ApplicationAgent(
                        session, client, settings, url, private, artifacts, args.interactive
                    )
                    agents.append(agent)
                    try:
                        report = agent.run()
                    except (KeyboardInterrupt, EOFError):
                        agent.report["input_number"] = index + 1
                        agent.report["reason"] = "Interrupted; inspect any submission attempt"
                        reports.append(agent.report)
                        raise
                except (BrowserError, OSError, ValueError, PlaywrightError):
                    report = {
                        "status": "blocked",
                        "reason": "Navigation/browser failed; no automatic retry",
                    }
                report["input_number"] = index + 1
                reports.append(report)
                save()
                print(f"  {report['status']} — {report['reason']}")
            if not args.headless and sys.stdin.isatty():
                print(
                    "Browsers remain open for review/manual submission. Press Enter when finished."
                )
                input()
        finally:
            for agent in agents:
                if settings.documents.retention == "delete_after_run":
                    remove_generated(agent.generated, agent.directory)
            save()
    print(f"Report: {report_path}; estimated API cost: ${client.estimated_usd:.4f}")
    if args.headless:
        print("Browsers closed. Unsubmitted form values are not retained.")
    return (
        0
        if reports
        and all(r["status"] in {"ready_for_review", "submitted_confirmed"} for r in reports)
        else 2
    )


def main():
    parser = argparse.ArgumentParser(description="Docker-first Claude job-application agent")
    parser.add_argument("--config", type=Path, default=Path("private/instructions.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create personal instructions; never touches API secrets")
    init.add_argument(
        "--upgrade", action="store_true", help="Back up and migrate version 1 instructions"
    )
    sub.add_parser("validate", help="Validate configuration without printing private facts")
    for command in ("run", "self-test"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--headless", action="store_true")
        cmd.add_argument("--interactive", action="store_true")
        cmd.add_argument("--dev-local", action="store_true", help=argparse.SUPPRESS)
        if command == "run":
            cmd.add_argument("urls", nargs="*")
            cmd.add_argument("--links", type=Path)
            cmd.add_argument(
                "--demo",
                action="store_true",
                help="Real Haiku on fictional local forms; uses credits",
            )
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.upgrade)
            return 0
        settings = (
            demo_settings()
            if args.command == "self-test" or getattr(args, "demo", False)
            else load_settings(args.config)
        )
        if args.command == "validate":
            load_cover_letter_examples(args.config.resolve().parent, settings.documents)
            print(
                "Instructions and cover-letter examples valid. "
                "No API key was read and no API calls were made."
            )
            return 0
        return run(args, settings)
    except ValidationError as exc:
        print("Invalid configuration:", file=sys.stderr)
        for error in exc.errors(include_input=False):
            print("  " + ".".join(map(str, error["loc"])) + ": " + error["type"], file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Cannot continue: {exc}", file=sys.stderr)
        return 1
    except PlaywrightError:
        print(
            "Browser startup failed. Check the Docker build and Chromium sandbox.", file=sys.stderr
        )
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Stopped. Submission attempts will not be automatically retried.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
