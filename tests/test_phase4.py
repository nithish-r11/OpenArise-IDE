"""
Comprehensive Phase 4 integration tests for OpenArise IDE Extension Marketplace.
Validates packaging, security, traversal guards, hash verification,
manifest validation, registry, UI panel, commands, themes, and lifecycle hooks.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

# Ensure application root is in sys.path
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from extensions.models import (
    ExtensionState,
    ExtensionManifest,
    RegistryEntry,
    OPENARISE_VERSION,
)
from extensions.extension_manifest import ManifestValidator
from extensions.extension_security import ExtensionSecurity, SecurityException
from extensions.extension_installer import ExtensionInstaller
from extensions.extension_loader import ExtensionLoader
from extensions.extension_registry import ExtensionRegistryClient
from extensions.extension_manager import ExtensionManager
from ui.themes import THEMES


def create_dummy_oaext(output_path: Path, manifest_data: dict, python_code: str = "", extra_files: dict = None) -> Path:
    """Helper to generate a test .oaext package on the fly."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))
        if python_code:
            zf.writestr("extension.py", python_code)
        zf.writestr("README.md", "# Test Extension\nDocumentation for test extension.")
        if extra_files:
            for fname, fcontent in extra_files.items():
                zf.writestr(fname, fcontent)
    return out


def run_phase4_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================")
    print("STARTING OPENARISE IDE PHASE 4 EXTENSION TEST SUITE")
    print("=======================================================\n")

    test_dir = Path(tempfile.mkdtemp(prefix="openarise_p4_test_"))
    print(f"Isolated test workspace: {test_dir}")

    window = MainWindow()
    window.show()
    app.processEvents()

    # Configure window with isolated test workspace and extension directory
    window.project_root = test_dir
    window.context.set_project(test_dir)
    window.fs_model.setRootPath(str(test_dir))
    window.tree.setRootIndex(window.fs_model.index(str(test_dir)))
    window.terminal.set_working_directory(test_dir)

    # Use isolated extensions directory for tests
    isolated_ext_dir = test_dir / "installed_extensions"
    window.extension_manager = ExtensionManager(
        main_window=window,
        command_registry=window.command_registry,
        extensions_dir=isolated_ext_dir,
        consent_callback=lambda ext: True,  # Auto-consent in automated test harness
    )
    window.extensions_panel.manager = window.extension_manager
    app.processEvents()
    time.sleep(0.5)

    built_pkg_dir = APP_DIR / "assets" / "extensions"
    python_essentials_pkg = built_pkg_dir / "openarise.python-essentials-1.0.0.oaext"
    dracula_theme_pkg = built_pkg_dir / "openarise.theme-dracula-1.0.0.oaext"
    json_formatter_pkg = built_pkg_dir / "openarise.json-formatter-1.0.0.oaext"
    ai_prompts_pkg = built_pkg_dir / "openarise.ai-prompts-1.0.0.oaext"
    builtin_catalog_file = built_pkg_dir / "builtin_catalog.json"

    try:
        # TEST 1: Marketplace Browsing, Filtering & Search
        print("[TEST 1] Verifying Marketplace Catalog Browsing and Search...")
        reg_client = ExtensionRegistryClient(
            cache_dir=test_dir / "reg_cache",
            local_catalog_path=builtin_catalog_file,
        )
        fetch_ok, msg, catalog_entries = reg_client.fetch_catalog()
        has_4_entries = len(catalog_entries) >= 4
        categories = {e.category for e in catalog_entries}
        has_categories = {"Programming", "Themes", "Formatters", "AI"}.issubset(categories)

        # UI panel search test
        window.extensions_panel.manager.registry = reg_client
        window.extensions_panel.refresh_all()
        app.processEvents()

        window.extensions_panel.search_input.setText("Python")
        app.processEvents()
        browse_count = window.extensions_panel.browse_list.count()
        search_ok = browse_count >= 1

        window.extensions_panel.search_input.clear()
        app.processEvents()
        all_browse_count = window.extensions_panel.browse_list.count()
        reset_search_ok = all_browse_count >= 4

        test_results["1_marketplace_browsing_search"] = fetch_ok and has_4_entries and has_categories and search_ok and reset_search_ok
        print(f"  Result: {'PASS' if test_results['1_marketplace_browsing_search'] else 'FAIL'} (Entries={len(catalog_entries)}, Categories={categories})")

        # TEST 2: Local Package Installation (.oaext)
        print("[TEST 2] Verifying Local .oaext Package Installation...")
        install_ok, inst_msg, installed_py = window.extension_manager.install_from_file(python_essentials_pkg)
        target_installed_dir = isolated_ext_dir / "openarise.python-essentials" / "1.0.0"
        files_exist = (target_installed_dir / "manifest.json").exists() and (target_installed_dir / "extension.py").exists()

        test_results["2_local_package_installation"] = install_ok and installed_py is not None and files_exist
        print(f"  Result: {'PASS' if test_results['2_local_package_installation'] else 'FAIL'} (Installed={install_ok}, DirExists={files_exist})")

        # TEST 3: Manifest Validation Rules
        print("[TEST 3] Verifying Manifest Validation Rules...")
        valid_manifest_dict = {
            "id": "test.valid-extension",
            "name": "Valid Extension",
            "version": "1.2.3",
            "description": "A valid test extension.",
            "author": "Tester",
            "category": "Tools",
            "minimum_openarise_version": "1.0.0",
            "entry_point": "extension.py",
            "permissions": ["commands"],
        }
        val_ok, errs, manifest_obj = ManifestValidator.validate_dict(valid_manifest_dict)
        test_results["3_manifest_validation"] = val_ok and manifest_obj is not None and manifest_obj.id == "test.valid-extension"
        print(f"  Result: {'PASS' if test_results['3_manifest_validation'] else 'FAIL'} (Valid={val_ok})")

        # TEST 4: Invalid Package Rejection (Missing manifest, bad ID, missing fields)
        print("[TEST 4] Verifying Rejection of Invalid Packages...")
        # A: Missing manifest
        bad_pkg_no_manifest = test_dir / "bad_no_manifest.oaext"
        with zipfile.ZipFile(bad_pkg_no_manifest, "w") as zf:
            zf.writestr("something.txt", "no manifest")
        res_a, _, _ = window.extension_manager.install_from_file(bad_pkg_no_manifest)

        # B: Invalid manifest (missing required author & description)
        bad_pkg_invalid_manifest = test_dir / "bad_invalid_manifest.oaext"
        create_dummy_oaext(bad_pkg_invalid_manifest, {"id": "invalid.id", "name": "Broken"})
        res_b, _, _ = window.extension_manager.install_from_file(bad_pkg_invalid_manifest)

        # C: Malformed JSON
        bad_pkg_malformed = test_dir / "bad_malformed.oaext"
        with zipfile.ZipFile(bad_pkg_malformed, "w") as zf:
            zf.writestr("manifest.json", "{ broken json !!")
        res_c, _, _ = window.extension_manager.install_from_file(bad_pkg_malformed)

        test_results["4_invalid_package_rejection"] = (not res_a) and (not res_b) and (not res_c)
        print(f"  Result: {'PASS' if test_results['4_invalid_package_rejection'] else 'FAIL'} (NoManifestRejected={not res_a}, MissingFieldsRejected={not res_b}, MalformedRejected={not res_c})")

        # TEST 5: SHA-256 Hash Verification & Tampering Protection
        print("[TEST 5] Verifying SHA-256 Hash Verification & Tamper Detection...")
        correct_hash = ExtensionSecurity.calculate_sha256(python_essentials_pkg)
        match_ok, _ = ExtensionSecurity.verify_package_hash(python_essentials_pkg, correct_hash)
        mismatch_ok, _ = ExtensionSecurity.verify_package_hash(python_essentials_pkg, "deadbeef1234567890abcdef")

        # Attempt installer with mismatched expected hash
        installer = ExtensionInstaller(extensions_dir=test_dir / "tmp_hash_ext")
        inst_tampered_ok, tampered_msg, _ = installer.install_package(python_essentials_pkg, expected_hash="0000000000000000000000000000000000000000000000000000000000000000")

        test_results["5_sha256_verification"] = match_ok and (not mismatch_ok) and (not inst_tampered_ok) and ("mismatch" in tampered_msg.lower())
        print(f"  Result: {'PASS' if test_results['5_sha256_verification'] else 'FAIL'} (MatchOk={match_ok}, TamperBlocked={not inst_tampered_ok})")

        # TEST 6: ZIP Path Traversal Protection
        print("[TEST 6] Verifying ZIP Path Traversal Protection...")
        traversal_pkg = test_dir / "traversal_attack.oaext"
        with zipfile.ZipFile(traversal_pkg, "w") as zf:
            zf.writestr("manifest.json", json.dumps(valid_manifest_dict))
            zf.writestr("../../escaped_file.txt", "MALICIOUS PAYLOAD OUTSIDE DESTINATION")

        traversal_detected = False
        try:
            installer.install_package(traversal_pkg)
        except SecurityException:
            traversal_detected = True
        except Exception:
            pass

        # Verify no file escaped outside target dir
        escaped_file = test_dir / "escaped_file.txt"
        escape_blocked = not escaped_file.exists()

        test_results["6_zip_traversal_protection"] = escape_blocked
        print(f"  Result: {'PASS' if test_results['6_zip_traversal_protection'] else 'FAIL'} (EscapeBlocked={escape_blocked})")

        # TEST 7: Enable and Disable Lifecycle Operations
        print("[TEST 7] Verifying Extension Enable and Disable...")
        ext_id = "openarise.python-essentials"
        # Enable extension
        enable_ok, enable_msg = window.extension_manager.enable_extension(ext_id)
        is_active_now = window.extension_manager.is_active(ext_id)
        cmd_registered = window.command_registry.get("python.insert_docstring") is not None

        # Disable extension
        disable_ok, disable_msg = window.extension_manager.disable_extension(ext_id)
        is_active_after = window.extension_manager.is_active(ext_id)
        cmd_unregistered = window.command_registry.get("python.insert_docstring") is None

        test_results["7_enable_disable_lifecycle"] = enable_ok and is_active_now and cmd_registered and disable_ok and (not is_active_after) and cmd_unregistered
        print(f"  Result: {'PASS' if test_results['7_enable_disable_lifecycle'] else 'FAIL'} (Enabled={is_active_now}, CmdRegistered={cmd_registered}, Disabled={not is_active_after}, CmdCleaned={cmd_unregistered})")

        # TEST 8: Extension Uninstallation
        print("[TEST 8] Verifying Extension Uninstallation...")
        dummy_uninstall_pkg = test_dir / "to_uninstall.oaext"
        create_dummy_oaext(
            dummy_uninstall_pkg,
            {
                "id": "test.to-uninstall",
                "name": "To Uninstall",
                "version": "1.0.0",
                "description": "Temporary extension to test uninstallation.",
                "author": "Tester",
                "category": "Tools",
            }
        )
        window.extension_manager.install_from_file(dummy_uninstall_pkg)
        installed_before = any(e.manifest.id == "test.to-uninstall" for e in window.extension_manager.list_installed())

        uninst_ok, uninst_msg = window.extension_manager.uninstall_extension("test.to-uninstall")
        installed_after = any(e.manifest.id == "test.to-uninstall" for e in window.extension_manager.list_installed())
        dir_removed = not (isolated_ext_dir / "test.to-uninstall").exists()

        test_results["8_uninstallation"] = installed_before and uninst_ok and (not installed_after) and dir_removed
        print(f"  Result: {'PASS' if test_results['8_uninstallation'] else 'FAIL'} (Uninstalled={uninst_ok}, DirRemoved={dir_removed})")

        # TEST 9: Version Compatibility Verification
        print("[TEST 9] Verifying Application Version Compatibility Checks...")
        future_manifest = dict(valid_manifest_dict)
        future_manifest["id"] = "test.future-extension"
        future_manifest["minimum_openarise_version"] = "99.0.0"
        future_pkg = test_dir / "future_ext.oaext"
        create_dummy_oaext(future_pkg, future_manifest)

        fut_ok, fut_msg, _ = window.extension_manager.install_from_file(future_pkg)
        version_rejected = not fut_ok and "version >=" in fut_msg

        test_results["9_version_compatibility"] = version_rejected
        print(f"  Result: {'PASS' if test_results['9_version_compatibility'] else 'FAIL'} (FutureVersionRejected={version_rejected})")

        # TEST 10: Extension Command Registration & JSON Formatter Execution
        print("[TEST 10] Verifying Extension Command Registration & Execution...")
        # Install JSON Formatter
        window.extension_manager.install_from_file(json_formatter_pkg)
        window.extension_manager.enable_extension("openarise.json-formatter")

        format_cmd = window.command_registry.get("json.format_document")
        has_format_cmd = format_cmd is not None

        # Test formatting in active editor
        test_json_file = test_dir / "test_data.json"
        test_json_file.write_text('{"name":"OpenArise","phase":4,"active":true}', encoding="utf-8")
        ed = window.editor.open_file(str(test_json_file))
        app.processEvents()

        window.command_registry.execute("json.format_document")
        app.processEvents()

        formatted_text = ed.toPlainText()
        json_formatted_ok = '"name": "OpenArise"' in formatted_text and "\n" in formatted_text

        test_results["10_command_registration_execution"] = has_format_cmd and json_formatted_ok
        print(f"  Result: {'PASS' if test_results['10_command_registration_execution'] else 'FAIL'} (CmdExists={has_format_cmd}, JSONFormatted={json_formatted_ok})")

        # TEST 11: Declarative Theme Registration
        print("[TEST 11] Verifying Declarative Theme Registration (Dracula Pro)...")
        # Install Dracula theme
        window.extension_manager.install_from_file(dracula_theme_pkg)
        window.extension_manager.enable_extension("openarise.theme-dracula")

        dracula_pro_registered = "Dracula Pro" in THEMES
        dracula_css = THEMES.get("Dracula Pro", "")
        css_valid = "#22212c" in dracula_css

        test_results["11_theme_registration"] = dracula_pro_registered and css_valid
        print(f"  Result: {'PASS' if test_results['11_theme_registration'] else 'FAIL'} (DraculaProRegistered={dracula_pro_registered})")

        # TEST 12: Command Palette Integration with Extension Commands
        print("[TEST 12] Verifying Command Palette Integration with Extension Commands...")
        window.command_palette.show_palette()
        app.processEvents()

        window.command_palette.search_input.setText("JSON")
        app.processEvents()
        matching_count = window.command_palette.results_list.count()
        found_in_palette = False
        for i in range(matching_count):
            item = window.command_palette.results_list.item(i)
            cmd = item.data(Qt.ItemDataRole.UserRole)
            if cmd and cmd.id == "json.format_document":
                found_in_palette = True
                break

        window.command_palette.close()
        app.processEvents()

        test_results["12_command_palette_integration"] = found_in_palette
        print(f"  Result: {'PASS' if test_results['12_command_palette_integration'] else 'FAIL'} (FoundInPalette={found_in_palette})")

        # TEST 13: AI Prompt Pack Extension & Chat Integration
        print("[TEST 13] Verifying AI Prompt Pack Extension Integration...")
        window.extension_manager.install_from_file(ai_prompts_pkg)
        window.extension_manager.enable_extension("openarise.ai-prompts")

        ai_cmd = window.command_registry.get("ai.prompt_explain")
        has_ai_cmd = ai_cmd is not None

        test_results["13_ai_chat_extension_integration"] = has_ai_cmd
        print(f"  Result: {'PASS' if test_results['13_ai_chat_extension_integration'] else 'FAIL'} (AICommandRegistered={has_ai_cmd})")

        # TEST 14: Integrated Terminal & Application Clean Shutdown
        print("[TEST 14] Verifying Terminal Compatibility & Clean Shutdown...")
        terminal_responsive = window.terminal.process is not None

        # Clean window close
        window.close()
        app.processEvents()
        time.sleep(0.5)

        term_stopped = window.terminal.process is None or window.terminal.process.state() == window.terminal.process.ProcessState.NotRunning
        test_results["14_terminal_and_clean_shutdown"] = terminal_responsive and term_stopped
        print(f"  Result: {'PASS' if test_results['14_terminal_and_clean_shutdown'] else 'FAIL'} (TermResponsive={terminal_responsive}, TermShutdown={term_stopped})")

    finally:
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    print("\n=======================================================")
    print("FINAL PHASE 4 TEST RESULTS SUMMARY")
    print("=======================================================")
    all_passed = True
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=======================================================")
    print(f"OVERALL STATUS: {'ALL 14 PHASE 4 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=======================================================\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_phase4_tests())

