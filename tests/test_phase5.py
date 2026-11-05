"""
Comprehensive Phase 5 integration tests for OpenArise IDE Git Integration.
Validates git detection, init, clone, status parsing, staging/unstaging,
commits, branch creation/switching/safe deletion, push/pull, visual diffs,
merge conflicts, commit history, .gitignore generation, AI commit prompt,
and destructive safeguards.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure application root is in sys.path
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from core.git_models import (
    GitFileStatusType,
    GitRepoState,
)
from core.git_service import GitService
from core.gitignore_generator import GitignoreGenerator
from ui.diff_viewer import DiffViewerDialog
from ui.branch_dialog import BranchDialog
from ui.git_history_dialog import GitHistoryDialog


def setup_local_git_repo(repo_dir: Path) -> Path:
    """Initializes and configures a clean local Git repository for tests."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    GitService.init_repo(repo_dir)
    # Configure user name and email
    GitService.run_git_sync(repo_dir, ["config", "user.name", "OpenArise Tester"])
    GitService.run_git_sync(repo_dir, ["config", "user.email", "tester@openarise.org"])
    GitService.run_git_sync(repo_dir, ["config", "commit.gpgsign", "false"])
    return repo_dir


def run_phase5_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_results = {}
    print("\n=======================================================")
    print("STARTING OPENARISE IDE PHASE 5 GIT INTEGRATION TEST SUITE")
    print("=======================================================\n")

    test_dir = Path(tempfile.mkdtemp(prefix="openarise_p5_test_"))
    print(f"Isolated test workspace: {test_dir}")

    window = MainWindow()
    window.show()
    app.processEvents()

    try:
        # TEST 1: Detect Git Installation
        print("[TEST 1] Verifying Git Installation Detection...")
        is_installed = GitService.is_git_installed()
        version_str = GitService.get_git_version()
        test_results["1_git_installation_detection"] = is_installed and "git version" in version_str.lower()
        print(f"  Result: {'PASS' if test_results['1_git_installation_detection'] else 'FAIL'} (Installed={is_installed}, Version='{version_str}')")

        # TEST 2: Initialize Repository
        print("[TEST 2] Verifying Git Repository Initialization...")
        repo_a = test_dir / "repo_a"
        init_ok, init_msg = GitService.init_repo(repo_a)
        is_repo = GitService.is_git_repository(repo_a)
        test_results["2_git_init"] = init_ok and is_repo and (repo_a / ".git").exists()
        print(f"  Result: {'PASS' if test_results['2_git_init'] else 'FAIL'} (InitOk={init_ok}, IsRepo={is_repo})")

        # Configure repo_a author
        setup_local_git_repo(repo_a)

        # Create initial commit in repo_a for subsequent tests
        initial_file = repo_a / "README.md"
        initial_file.write_text("# Repo A\nInitial repository contents.\n", encoding="utf-8")
        GitService.stage_file(repo_a, "README.md")
        commit_ok, _ = GitService.commit(repo_a, "Initial commit in Repo A")

        # TEST 3: Clone a Local Repository
        print("[TEST 3] Verifying Clone of Local Repository...")
        repo_b = test_dir / "repo_b"
        clone_ok, clone_msg = GitService.clone_repo(str(repo_a), repo_b)
        cloned_is_repo = GitService.is_git_repository(repo_b)
        cloned_file_exists = (repo_b / "README.md").exists()
        test_results["3_git_clone"] = clone_ok and cloned_is_repo and cloned_file_exists
        print(f"  Result: {'PASS' if test_results['3_git_clone'] else 'FAIL'} (Cloned={clone_ok}, IsRepo={cloned_is_repo})")

        # Configure repo_b
        GitService.run_git_sync(repo_b, ["config", "user.name", "OpenArise Tester"])
        GitService.run_git_sync(repo_b, ["config", "user.email", "tester@openarise.org"])

        # Switch window to repo_a
        window.project_root = repo_a
        window._load_project_folder(repo_a)
        app.processEvents()

        # TEST 4: Detect Modified and Untracked Files
        print("[TEST 4] Verifying Detection of Modified and Untracked Files...")
        # Create an untracked file and modify existing file
        untracked = repo_a / "new_script.py"
        untracked.write_text("print('hello world')\n", encoding="utf-8")
        initial_file.write_text("# Repo A\nModified line.\n", encoding="utf-8")

        status_ok, _, status_state = GitService.get_status(repo_a)
        has_untracked = any(f.path == "new_script.py" for f in status_state.untracked_files)
        has_modified = any(f.path == "README.md" for f in status_state.unstaged_files)

        test_results["4_detect_modified_untracked"] = status_ok and has_untracked and has_modified
        print(f"  Result: {'PASS' if test_results['4_detect_modified_untracked'] else 'FAIL'} (Untracked={has_untracked}, Modified={has_modified})")

        # TEST 5: Stage and Unstage Files
        print("[TEST 5] Verifying Staging and Unstaging Operations...")
        # Stage README.md
        stage_ok, _ = GitService.stage_file(repo_a, "README.md")
        _, _, state_staged = GitService.get_status(repo_a)
        is_staged = any(f.path == "README.md" for f in state_staged.staged_files)

        # Unstage README.md
        unstage_ok, _ = GitService.unstage_file(repo_a, "README.md")
        _, _, state_unstaged = GitService.get_status(repo_a)
        is_now_unstaged = any(f.path == "README.md" for f in state_unstaged.unstaged_files)

        test_results["5_stage_and_unstage"] = stage_ok and is_staged and unstage_ok and is_now_unstaged
        print(f"  Result: {'PASS' if test_results['5_stage_and_unstage'] else 'FAIL'} (Staged={is_staged}, Unstaged={is_now_unstaged})")

        # TEST 6: Commit Changes
        print("[TEST 6] Verifying Commit Workflow...")
        GitService.stage_all(repo_a)
        commit_res, commit_out = GitService.commit(repo_a, "Feature: Added new_script and updated README")
        _, _, state_after_commit = GitService.get_status(repo_a)
        is_clean_after = state_after_commit.is_clean

        test_results["6_commit_workflow"] = commit_res and is_clean_after
        print(f"  Result: {'PASS' if test_results['6_commit_workflow'] else 'FAIL'} (CommitOk={commit_res}, CleanTree={is_clean_after})")

        # TEST 7: Create and Switch Branches
        print("[TEST 7] Verifying Create and Switch Branches...")
        br_create_ok, _ = GitService.create_branch(repo_a, "feature/awesome-phase5")
        br_switch_ok, _ = GitService.switch_branch(repo_a, "feature/awesome-phase5")
        _, _, branch_state = GitService.get_status(repo_a)
        is_on_feature_branch = branch_state.current_branch == "feature/awesome-phase5"

        test_results["7_create_switch_branch"] = br_create_ok and br_switch_ok and is_on_feature_branch
        print(f"  Result: {'PASS' if test_results['7_create_switch_branch'] else 'FAIL'} (SwitchedToFeature={is_on_feature_branch})")

        # TEST 8: Delete Branches Safely (Guarding Current Branch)
        print("[TEST 8] Verifying Safe Branch Deletion & Active Branch Guard...")
        # Attempt to delete current branch: must be rejected
        del_curr_ok, del_curr_msg = GitService.delete_branch(repo_a, "feature/awesome-phase5")
        active_branch_protected = not del_curr_ok

        # Create temporary branch and delete it
        GitService.create_branch(repo_a, "temp/to-delete")
        del_temp_ok, _ = GitService.delete_branch(repo_a, "temp/to-delete")
        _, _, branches_list = GitService.get_branches(repo_a)
        temp_branch_gone = not any(b.name == "temp/to-delete" for b in branches_list)

        # Switch back to master/main
        main_branch_name = "master" if any(b.name == "master" for b in branches_list) else "main"
        GitService.switch_branch(repo_a, main_branch_name)

        test_results["8_safe_branch_deletion"] = active_branch_protected and del_temp_ok and temp_branch_gone
        print(f"  Result: {'PASS' if test_results['8_safe_branch_deletion'] else 'FAIL'} (ProtectedActive={active_branch_protected}, DeletedTemp={temp_branch_gone})")

        # TEST 9: Fetch and Pull
        print("[TEST 9] Verifying Fetch and Pull from Remote...")
        # In repo_a, make a commit on main
        update_file = repo_a / "remote_update.txt"
        update_file.write_text("Update from repo_a\n", encoding="utf-8")
        GitService.stage_all(repo_a)
        GitService.commit(repo_a, "Update from origin repo_a")

        # In repo_b (clone of repo_a), fetch and pull
        fetch_ok, _ = GitService.fetch(repo_b, remote="origin")
        pull_ok, _ = GitService.pull(repo_b, remote="origin")
        pulled_file_exists = (repo_b / "remote_update.txt").exists()

        test_results["9_fetch_and_pull"] = fetch_ok and pull_ok and pulled_file_exists
        print(f"  Result: {'PASS' if test_results['9_fetch_and_pull'] else 'FAIL'} (FetchOk={fetch_ok}, PullOk={pull_ok}, PulledFile={pulled_file_exists})")

        # TEST 10: Push to a Local Remote
        print("[TEST 10] Verifying Push to Local Remote...")
        # Create a bare remote repo to push to
        bare_remote = test_dir / "bare_remote.git"
        GitService.run_git_sync(test_dir, ["clone", "--bare", str(repo_a), str(bare_remote)])

        # In repo_a, add bare remote and push
        GitService.run_git_sync(repo_a, ["remote", "add", "test_bare", str(bare_remote)])
        push_file = repo_a / "pushed_content.txt"
        push_file.write_text("Pushed to bare remote\n", encoding="utf-8")
        GitService.stage_all(repo_a)
        GitService.commit(repo_a, "Commit to push to test_bare")

        push_ok, push_msg = GitService.push(repo_a, remote="test_bare", branch=main_branch_name)
        test_results["10_push_remote"] = push_ok
        print(f"  Result: {'PASS' if test_results['10_push_remote'] else 'FAIL'} (PushOk={push_ok})")

        # TEST 11: View Staged and Unstaged Diffs
        print("[TEST 11] Verifying Staged and Unstaged Diff Retrieval...")
        diff_test_file = repo_a / "diff_test.py"
        diff_test_file.write_text("line_1 = 1\nline_2 = 2\n", encoding="utf-8")
        GitService.stage_file(repo_a, "diff_test.py")

        # Staged diff check
        staged_ok, _, staged_diff = GitService.get_diff(repo_a, rel_file="diff_test.py", staged=True)
        staged_has_content = "+line_1 = 1" in staged_diff

        # Modify unstaged
        diff_test_file.write_text("line_1 = 1\nline_2 = 2\nline_3 = 3\n", encoding="utf-8")
        unstaged_ok, _, unstaged_diff = GitService.get_diff(repo_a, rel_file="diff_test.py", staged=False)
        unstaged_has_content = "+line_3 = 3" in unstaged_diff

        test_results["11_staged_unstaged_diffs"] = staged_ok and staged_has_content and unstaged_ok and unstaged_has_content
        print(f"  Result: {'PASS' if test_results['11_staged_unstaged_diffs'] else 'FAIL'} (StagedDiff={staged_has_content}, UnstagedDiff={unstaged_has_content})")

        # Clean up diff test file for subsequent tests
        GitService.discard_file(repo_a, "diff_test.py")
        GitService.unstage_file(repo_a, "diff_test.py")
        if diff_test_file.exists():
            diff_test_file.unlink()

        # TEST 12: Detect Merge Conflicts
        print("[TEST 12] Verifying Merge Conflict Detection...")
        # Create conflict branch
        GitService.create_branch(repo_a, "conflict_branch_1")
        GitService.create_branch(repo_a, "conflict_branch_2")

        conflict_target = repo_a / "conflict.txt"

        # Edit on branch 1
        GitService.switch_branch(repo_a, "conflict_branch_1")
        conflict_target.write_text("BRANCH 1 CONTENT\n", encoding="utf-8")
        GitService.stage_all(repo_a)
        GitService.commit(repo_a, "Branch 1 edit")

        # Edit on branch 2
        GitService.switch_branch(repo_a, "conflict_branch_2")
        conflict_target.write_text("BRANCH 2 CONFLICTING CONTENT\n", encoding="utf-8")
        GitService.stage_all(repo_a)
        GitService.commit(repo_a, "Branch 2 edit")

        # Attempt merge: should produce merge conflict
        GitService.run_git_sync(repo_a, ["merge", "conflict_branch_1"])
        _, _, conflict_state = GitService.get_status(repo_a)
        conflict_detected = any(f.path == "conflict.txt" for f in conflict_state.conflict_files)

        # Abort merge and return to clean state
        GitService.run_git_sync(repo_a, ["merge", "--abort"])
        GitService.switch_branch(repo_a, main_branch_name)

        test_results["12_merge_conflict_detection"] = conflict_detected
        print(f"  Result: {'PASS' if test_results['12_merge_conflict_detection'] else 'FAIL'} (ConflictDetected={conflict_detected})")

        # TEST 13: Git History Log Parsing
        print("[TEST 13] Verifying Git History Display & Parsing...")
        hist_ok, _, history_commits = GitService.get_history(repo_a, max_count=10)
        has_commits = len(history_commits) >= 2
        first_commit = history_commits[0]
        parsed_well = (
            bool(first_commit.sha)
            and len(first_commit.short_sha) == 7
            and bool(first_commit.author_name)
            and bool(first_commit.message)
        )

        test_results["13_git_history_display"] = hist_ok and has_commits and parsed_well
        print(f"  Result: {'PASS' if test_results['13_git_history_display'] else 'FAIL'} (CommitsCount={len(history_commits)}, ParsedWell={parsed_well})")

        # TEST 14: .gitignore Generation & Overwrite Guard
        print("[TEST 14] Verifying .gitignore Generation & Overwrite Safeguard...")
        gitignore_target_dir = test_dir / "gi_test"
        gitignore_target_dir.mkdir(parents=True, exist_ok=True)

        # Generate Python & Node.js template
        gen_ok, _ = GitignoreGenerator.generate_gitignore(gitignore_target_dir, ["Python", "Node.js"])
        gi_file = gitignore_target_dir / ".gitignore"
        gi_content = gi_file.read_text(encoding="utf-8") if gi_file.exists() else ""
        templates_written = "__pycache__" in gi_content and "node_modules" in gi_content

        # Overwrite protection test (without overwrite=True)
        overwrite_blocked, blocked_msg = GitignoreGenerator.generate_gitignore(
            gitignore_target_dir, ["Java"], overwrite=False
        )
        guard_active = (not overwrite_blocked) and "already exists" in blocked_msg

        test_results["14_gitignore_generator"] = gen_ok and templates_written and guard_active
        print(f"  Result: {'PASS' if test_results['14_gitignore_generator'] else 'FAIL'} (Generated={templates_written}, OverwriteGuardActive={guard_active})")

        # TEST 15: AI Commit-Message & Git Prompt Generation
        print("[TEST 15] Verifying AI Commit-Message Generation Trigger...", flush=True)
        # Prepare staged diff in repo_a
        ai_test_file = repo_a / "ai_code.py"
        ai_test_file.write_text("def calculate_metrics(items):\n    return sum(items)\n", encoding="utf-8")
        GitService.stage_file(repo_a, "ai_code.py")

        # Temporarily disconnect main window network chat during unit test
        try:
            window.git_panel.ai_prompt_requested.disconnect(window._handle_git_ai_prompt)
        except Exception:
            pass

        ai_prompt_received = []
        window.git_panel.ai_prompt_requested.connect(lambda p: ai_prompt_received.append(p))
        window.git_panel._ai_generate_commit_message()
        app.processEvents()

        prompt_generated = len(ai_prompt_received) > 0 and "calculate_metrics" in ai_prompt_received[0]
        test_results["15_ai_commit_message_generation"] = prompt_generated
        print(f"  Result: {'PASS' if test_results['15_ai_commit_message_generation'] else 'FAIL'} (PromptGenerated={prompt_generated})", flush=True)

        # TEST 16: Destructive Action Safeguards (Discard file & all)
        print("[TEST 16] Verifying Destructive Action Safeguards & Clean Shutdown...")
        # Modify a file
        ai_test_file.write_text("DIRTY_CHANGES_THAT_WILL_BE_DISCARDED\n", encoding="utf-8")
        discard_ok, _ = GitService.discard_file(repo_a, "ai_code.py", is_untracked=False)
        content_after = ai_test_file.read_text(encoding="utf-8")
        discard_restored = "calculate_metrics" in content_after

        # Clean window shutdown
        if hasattr(window, "chat_worker") and window.chat_worker and window.chat_worker.isRunning():
            window.chat_worker.cancel()
            window.chat_worker.wait(1000)
        window.close()
        app.processEvents()
        time.sleep(0.5)

        term_stopped = (
            window.terminal.process is None
            or window.terminal.process.state() == window.terminal.process.ProcessState.NotRunning
        )

        test_results["16_destructive_safeguards_shutdown"] = discard_ok and discard_restored and term_stopped
        print(f"  Result: {'PASS' if test_results['16_destructive_safeguards_shutdown'] else 'FAIL'} (DiscardRestored={discard_restored}, TermShutdown={term_stopped})", flush=True)

    finally:
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    print("\n=======================================================", flush=True)
    print("FINAL PHASE 5 TEST RESULTS SUMMARY", flush=True)
    print("=======================================================", flush=True)
    all_passed = True
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  - {test_name}: {status}", flush=True)
        if not passed:
            all_passed = False

    print("=======================================================", flush=True)
    print(f"OVERALL STATUS: {'ALL 16 PHASE 5 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}", flush=True)
    print("=======================================================\n", flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_phase5_tests())

