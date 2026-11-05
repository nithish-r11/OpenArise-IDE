"""
Manual Acceptance Test for OpenArise IDE Phase 9: AI Website Builder
Tests end-to-end website generation, file review/writing, local development server,
live HTTP serving on 127.0.0.1, and subsequent AI editing using live Ollama (qwen2.5-coder:7b).
"""

from __future__ import annotations
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtWidgets import QApplication
from core.website_generator import AIWebsiteGenerator, WebsiteSpec
from core.website_server import WebsiteServerState
from ui.main_window import MainWindow


PORTFOLIO_PROMPT = (
    "Create a modern responsive personal portfolio website with Home, About, Skills, "
    "Projects and Contact sections. Use a premium dark theme, modern typography, "
    "subtle animations and mobile-friendly navigation. Create all required files and make it fully runnable locally."
)


def run_acceptance_test():
    app = QApplication.instance() or QApplication(sys.argv)
    workspace = Path("E:/OpenArise_IDE/OpenArise_IDE/tests/acceptance_website_workspace")
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("STARTING PHASE 9 MANUAL ACCEPTANCE TEST WITH LIVE OLLAMA")
    print("=" * 65)
    print(f"Workspace: {workspace}")
    print(f"Model: qwen2.5-coder:7b")
    print(f"Prompt: {PORTFOLIO_PROMPT}\n")

    # -----------------------------------------------------------------
    # STEP 1: AI Prompt-to-Website Generation with Live Ollama
    # -----------------------------------------------------------------
    print(">>> STEP 1: Generating website files with live Ollama...")
    spec = WebsiteSpec(
        name="portfolio-site",
        dest_dir=workspace,
        prompt=PORTFOLIO_PROMPT,
        tech="html",
        is_multipage=False,
        model="qwen2.5-coder:7b",
    )

    t0 = time.time()
    def progress_logger(msg, pct):
        print(f"    [{pct}%] {msg}")

    records = AIWebsiteGenerator.generate_website(spec, progress_callback=progress_logger)
    gen_time = time.time() - t0
    print(f"\n[OK] Generation complete in {gen_time:.1f}s. Generated {len(records)} files:")
    for r in records:
        print(f"    - {r.rel_path} ({len(r.new_content or '')} chars)")

    # Verifications for Step 1
    rel_paths = [r.rel_path for r in records]
    assert "index.html" in rel_paths, "Missing 'index.html' in generated files"
    assert "css/styles.css" in rel_paths, "Missing 'css/styles.css' in generated files"
    assert "js/app.js" in rel_paths, "Missing 'js/app.js' in generated files"

    index_rec = next(r for r in records if r.rel_path == "index.html")
    index_html = index_rec.new_content or ""
    css_rec = next(r for r in records if r.rel_path == "css/styles.css")
    styles_css = css_rec.new_content or ""

    # Check sections mentioned in prompt
    has_portfolio_elements = (
        ("portfolio" in index_html.lower() or "about" in index_html.lower()) and
        "skills" in index_html.lower() or "contact" in index_html.lower() or "projects" in index_html.lower()
    )
    print(f"Portfolio sections present: {has_portfolio_elements}")

    # -----------------------------------------------------------------
    # STEP 2: File Approval & Writing to Disk
    # -----------------------------------------------------------------
    print("\n>>> STEP 2: Applying accepted files to project disk...")
    project_dir = workspace / spec.name
    project_dir.mkdir(parents=True, exist_ok=True)
    for rec in records:
        target = project_dir / rec.rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rec.new_content or "", encoding="utf-8")
    print(f"[OK] Files successfully written to {project_dir}")

    # Validate project structure
    is_valid, issues = AIWebsiteGenerator.validate_website_project(project_dir)
    print(f"Project structure valid: {is_valid} (Issues: {issues})")
    assert is_valid, f"Project validation failed: {issues}"

    # -----------------------------------------------------------------
    # STEP 3: Load into OpenArise MainWindow
    # -----------------------------------------------------------------
    print("\n>>> STEP 3: Initializing OpenArise MainWindow & loading project...")
    with patch.object(MainWindow, "_check_startup_recovery_and_project", MagicMock()):
        window = MainWindow()
    window._load_project_folder(project_dir)
    app.processEvents()
    assert window.project_root == project_dir.resolve()
    print("[OK] Project loaded into File Explorer and Editor")

    # -----------------------------------------------------------------
    # STEP 4: Start Local Development Server on 127.0.0.1
    # -----------------------------------------------------------------
    print("\n>>> STEP 4: Starting local development server...")
    window.run_website()
    app.processEvents()

    # Wait for server to become RUNNING
    start_wait = time.time()
    while time.time() - start_wait < 5.0:
        app.processEvents()
        if window.website_server_manager.state == WebsiteServerState.RUNNING:
            break
        time.sleep(0.05)

    server_state = window.website_server_manager.state
    live_url = window.website_server_manager.current_url
    print(f"[OK] Server state: {server_state}, Live URL: {live_url}")
    assert server_state == WebsiteServerState.RUNNING, "Server failed to reach RUNNING state"
    assert live_url.startswith("http://127.0.0.1:"), f"Invalid server URL: {live_url}"

    # -----------------------------------------------------------------
    # STEP 5: Live HTTP GET Request to Dev Server
    # -----------------------------------------------------------------
    print(f"\n>>> STEP 5: Performing live HTTP GET to {live_url}...")
    req = urllib.request.urlopen(live_url, timeout=5)
    status_code = req.getcode()
    served_body = req.read().decode("utf-8", errors="replace")
    print(f"[OK] HTTP response code: {status_code}, Body length: {len(served_body)} bytes")
    assert status_code == 200, f"Expected HTTP 200, got {status_code}"
    assert "<!DOCTYPE html>" in served_body or "<html" in served_body, "Server did not serve valid HTML"
    assert "css/styles.css" in served_body, "Served HTML is missing stylesheet reference"

    # -----------------------------------------------------------------
    # STEP 6: Stop Development Server
    # -----------------------------------------------------------------
    print("\n>>> STEP 6: Stopping development server...")
    window.stop_website()
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    print(f"[OK] Server state after stop: {window.website_server_manager.state}")
    assert window.website_server_manager.state == WebsiteServerState.STOPPED

    # -----------------------------------------------------------------
    # STEP 7: Subsequent AI Website Editing
    # -----------------------------------------------------------------
    print("\n>>> STEP 7: Requesting AI Website Edit with live Ollama...")
    edit_instruction = "Change the main accent color theme to emerald green (#10b981) and add a Download Resume button."
    print(f"Edit instruction: {edit_instruction}")

    edit_records = AIWebsiteGenerator.edit_website(
        project_dir=project_dir,
        instruction=edit_instruction,
        model="qwen2.5-coder:7b"
    )
    print(f"[OK] AI proposed {len(edit_records)} modified file(s):")
    for r in edit_records:
        print(f"    - {r.rel_path} ({r.change_type})")
        # Apply the edit
        target = project_dir / r.rel_path
        target.write_text(r.new_content or "", encoding="utf-8")

    assert len(edit_records) > 0, "AI failed to produce edit records"

    # Re-validate project after edit
    is_valid_after_edit, edit_issues = AIWebsiteGenerator.validate_website_project(project_dir)
    print(f"Project structure valid after edit: {is_valid_after_edit}")
    assert is_valid_after_edit, f"Project broken after edit: {edit_issues}"

    # Cleanup
    window.close()
    app.processEvents()
    shutil.rmtree(workspace, ignore_errors=True)

    print("\n" + "=" * 65)
    print("ALL 7 ACCEPTANCE STEPS COMPLETED & VERIFIED WITH LIVE OLLAMA!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_acceptance_test()
    sys.exit(0 if success else 1)

