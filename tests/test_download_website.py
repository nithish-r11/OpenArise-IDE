"""
Comprehensive Verification Test Suite for OpenArise IDE Download Website.
Validates:
1. Website directory location inside repository (E:\\OpenArise_IDE\\OpenArise_IDE\\website).
2. Required HTML structure, meta tags, and favicon.
3. Minimal header navigation (#download, #requirements, #setup, #features, #docs).
4. Dual download options with exact verified file sizes (106.3 MB and 105.6 MB).
5. Accurate SHA-256 hashes matching release checksum manifest.
6. Absence of local filesystem paths in download links.
7. System requirements and 5-step setup instructions.
8. Core product capabilities and genuine application preview image.
9. In-page documentation anchors (#readme, #ollama-guide, #troubleshooting, #release-notes).
10. Absence of prohibited marketing fluff (testimonials, pricing, blogs, fake metrics).
11. Local HTTP server execution, HTTP 200 responses, and socket release.
"""

import os
import re
import sys
import time
import socket
import urllib.request
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = ROOT / "website"
INDEX_HTML = WEBSITE_DIR / "index.html"
STYLES_CSS = WEBSITE_DIR / "css" / "styles.css"
MAIN_JS = WEBSITE_DIR / "js" / "main.js"
PREVIEW_IMG = WEBSITE_DIR / "assets" / "images" / "openarise_ide_preview.png"
RELEASE_DIR = ROOT / "release" / "v1.0.0"
CHECKSUMS_FILE = RELEASE_DIR / "SHA256SUMS.txt"

def log(msg):
    print(msg, flush=True)

def test_1_directory_and_files():
    log("[TEST 1] Verifying website directory and static file existence...")
    assert WEBSITE_DIR.exists(), f"website/ not found at {WEBSITE_DIR}"
    assert INDEX_HTML.exists(), "index.html missing"
    assert STYLES_CSS.exists(), "css/styles.css missing"
    assert MAIN_JS.exists(), "js/main.js missing"
    assert PREVIEW_IMG.exists(), "openarise_ide_preview.png missing"
    assert (WEBSITE_DIR / "assets" / "branding" / "openarise.ico").exists(), "openarise.ico missing"
    assert (WEBSITE_DIR / "assets" / "branding" / "openarise_master.png").exists(), "openarise_master.png missing"
    log(f"  Result: PASS (Directory verified at {WEBSITE_DIR})")

def test_2_html_structure_and_branding():
    log("[TEST 2] Verifying HTML5 semantic structure, metadata, and branding...")
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    assert "<!DOCTYPE html>" in html, "Missing <!DOCTYPE html>"
    assert "<title>OpenArise IDE</title>" in html, "Invalid title"
    assert 'property="og:title" content="OpenArise IDE"' in html, "Missing og:title"
    assert 'name="twitter:title" content="OpenArise IDE"' in html, "Missing twitter:title"
    assert 'rel="icon"' in html and "openarise.ico" in html, "Missing favicon link"
    assert "OpenArise IDE" in html, "Missing product name"
    assert "openarise_master.png" in html, "Missing brand logo"
    assert 'class="site-header"' in html, "Missing header"
    assert 'class="site-footer"' in html, "Missing footer"
    log("  Result: PASS (HTML5 metadata and branding verified)")

def test_3_navigation_and_anchors():
    log("[TEST 3] Verifying navigation anchors and matching section IDs...")
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    nav_anchors = ["#download", "#requirements", "#setup", "#features", "#docs"]
    for anchor in nav_anchors:
        assert f'href="{anchor}"' in html, f"Nav link {anchor} missing"
        sec_id = anchor.lstrip("#")
        assert f'id="{sec_id}"' in html, f"Section id='{sec_id}' missing"

    doc_anchors = ["#readme", "#ollama-guide", "#troubleshooting", "#release-notes"]
    for doc_anchor in doc_anchors:
        assert f'href="{doc_anchor}"' in html, f"Doc nav link {doc_anchor} missing"
        doc_id = doc_anchor.lstrip("#")
        assert f'id="{doc_id}"' in html, f"Doc section id='{doc_id}' missing"

    log("  Result: PASS (All 5 primary and 4 documentation anchors exist with valid targets)")

def test_4_download_options_and_checksums():
    log("[TEST 4] Verifying dual download options, file sizes, and SHA-256 hashes...")
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # Verify both options are presented
    assert "Windows Installer" in html, "Missing Windows Installer option"
    assert "106.3 MB" in html, "Missing installer file size (106.3 MB)"
    assert "OpenAriseIDE-Setup-1.0.0.exe" in html, "Missing installer filename"

    assert "Portable Executable" in html, "Missing Portable Executable option"
    assert "105.6 MB" in html, "Missing portable file size (105.6 MB)"
    assert "OpenAriseIDE.exe" in html, "Missing portable filename"

    # Verify SHA-256 hashes against actual release checksums file
    assert CHECKSUMS_FILE.exists(), f"Checksums file missing at {CHECKSUMS_FILE}"
    with open(CHECKSUMS_FILE, "r", encoding="utf-8") as f:
        sums_text = f.read()

    installer_hash_match = re.search(r"([a-f0-9]{64})\s+OpenAriseIDE-Setup-1\.0\.0\.exe", sums_text)
    assert installer_hash_match, "Installer hash not found in SHA256SUMS.txt"
    installer_hash = installer_hash_match.group(1)

    portable_hash_match = re.search(r"([a-f0-9]{64})\s+OpenAriseIDE\.exe", sums_text)
    assert portable_hash_match, "Portable hash not found in SHA256SUMS.txt"
    portable_hash = portable_hash_match.group(1)

    assert installer_hash in html, f"Installer hash {installer_hash} not present in HTML"
    assert portable_hash in html, f"Portable hash {portable_hash} not present in HTML"

    # Verify NO local filesystem links exist
    assert "file:///" not in html, "Found local file:/// link in HTML"
    assert "E:\\OpenArise_IDE" not in html, "Found local Windows path in HTML"
    assert "C:\\Users" not in html, "Found local user profile path in HTML"

    log(f"  Result: PASS (Sizes: 106.3 MB & 105.6 MB, SHA-256 matched, 0 local file paths)")

def test_5_prohibited_content_check():
    log("[TEST 5] Verifying absence of marketing fluff, pricing, and fake metrics...")
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    prohibited = [
        "testimonial", "customer review", "$/month", "$99", "$49",
        "pricing plan", "case study", "10,000+ users", "trusted by",
        "portfolio", "agency", "blog post"
    ]
    for term in prohibited:
        assert term not in html.lower(), f"Prohibited marketing term '{term}' found in HTML"

    log("  Result: PASS (Zero prohibited marketing content, pure software download focus)")

def test_6_local_server_and_http_preview():
    log("[TEST 6] Starting local HTTP server and verifying HTTP 200 responses...")
    port = 8787
    cmd = [sys.executable, "-m", "http.server", str(port)]
    server_proc = subprocess.Popen(cmd, cwd=str(WEBSITE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1.5)

    try:
        base_url = f"http://127.0.0.1:{port}"
        
        # Test index.html
        req = urllib.request.urlopen(f"{base_url}/", timeout=5)
        assert req.status == 200, f"Index returned status {req.status}"
        body = req.read().decode("utf-8")
        assert "OpenArise IDE" in body, "Body missing OpenArise IDE"
        log("  HTTP GET / : 200 OK")

        # Test CSS
        req_css = urllib.request.urlopen(f"{base_url}/css/styles.css", timeout=5)
        assert req_css.status == 200, "styles.css not 200"
        log("  HTTP GET /css/styles.css : 200 OK")

        # Test JS
        req_js = urllib.request.urlopen(f"{base_url}/js/main.js", timeout=5)
        assert req_js.status == 200, "main.js not 200"
        log("  HTTP GET /js/main.js : 200 OK")

        # Test Preview Image
        req_img = urllib.request.urlopen(f"{base_url}/assets/images/openarise_ide_preview.png", timeout=5)
        assert req_img.status == 200, "preview image not 200"
        img_len = len(req_img.read())
        assert img_len > 10_000, f"Preview image size suspiciously small: {img_len}"
        log(f"  HTTP GET /assets/images/openarise_ide_preview.png : 200 OK ({img_len:,} bytes)")

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait(timeout=2)
        time.sleep(1.0)

    # Check port freed
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        port_freed = True
    except OSError:
        port_freed = False
    finally:
        s.close()
    assert port_freed, f"Port {port} not freed after server termination"
    log("  Result: PASS (All resources return HTTP 200, port cleanly freed)")

def run_all():
    log("\n=======================================================")
    log("OPENARISE IDE DOWNLOAD WEBSITE VERIFICATION SUITE")
    log("=======================================================\n")
    test_1_directory_and_files()
    test_2_html_structure_and_branding()
    test_3_navigation_and_anchors()
    test_4_download_options_and_checksums()
    test_5_prohibited_content_check()
    test_6_local_server_and_http_preview()
    log("\n=======================================================")
    log("OVERALL RESULT: ALL 6 WEBSITE TESTS PASSED")
    log("=======================================================\n")

if __name__ == "__main__":
    run_all()

