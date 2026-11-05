"""
Asynchronous and safe Git service for OpenArise IDE.
Executes Git commands via list arguments, avoids shell string interpolation,
protects credentials, and parses status, history, diffs, and branches.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.git_models import (
    GitBranch,
    GitCommit,
    GitFileChange,
    GitFileStatusType,
    GitRepoState,
    DiffFile,
    DiffLine,
)


class GitWorker(QThread):
    """Background worker thread for long-running Git operations (push, pull, clone, fetch)."""
    finished_signal = pyqtSignal(bool, str, str)  # (success, stdout, stderr)

    def __init__(self, repo_path: Optional[Path], args: List[str], parent=None):
        super().__init__(parent)
        self.repo_path = repo_path
        self.args = args

    def run(self):
        success, stdout, stderr = GitService.run_git_sync(self.repo_path, self.args)
        self.finished_signal.emit(success, stdout, stderr)


class GitService:
    """
    Core Git operations service.
    Enforces safe execution:
    - Never uses shell=True
    - Strict argument list passing
    - Safe credential handling
    """

    @staticmethod
    def is_git_installed() -> bool:
        """Returns True if the Git executable is available in PATH."""
        return shutil.which("git") is not None

    @classmethod
    def get_git_version(cls) -> str:
        """Returns the installed Git version string, or empty string if not installed."""
        if not cls.is_git_installed():
            return ""
        ok, out, _ = cls.run_git_sync(None, ["--version"])
        return out.strip() if ok else ""

    @staticmethod
    def run_git_sync(
        repo_path: Optional[Path],
        args: List[str],
        timeout: int = 30,
        env_extra: Optional[dict] = None,
    ) -> Tuple[bool, str, str]:
        """
        Safely executes a git command synchronously using subprocess.Popen with argument lists.
        Never invokes a shell.
        """
        git_bin = shutil.which("git")
        if not git_bin:
            return False, "", "Git is not installed or not found in system PATH."

        cwd = str(repo_path.resolve()) if repo_path and repo_path.exists() else None
        cmd = [git_bin] + args

        env = os.environ.copy()
        # Ensure standard English output for stable porcelain parsing
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        env["GIT_TERMINAL_PROMPT"] = "0"  # Prevent hangs on terminal password prompts
        if env_extra:
            env.update(env_extra)

        try:
            # CREATE_NO_WINDOW on Windows to prevent console flashing
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                env=env,
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode == 0, stdout, stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            return False, "", f"Git command timed out after {timeout} seconds."
        except Exception as exc:
            return False, "", str(exc)

    @classmethod
    def run_git_async(
        cls,
        repo_path: Optional[Path],
        args: List[str],
        callback: Callable[[bool, str, str], None],
        parent: Optional[QObject] = None,
    ) -> GitWorker:
        """Runs a Git command on a background worker thread."""
        worker = GitWorker(repo_path, args, parent)
        worker.finished_signal.connect(callback)
        worker.start()
        return worker

    @classmethod
    def is_git_repository(cls, path: Path) -> bool:
        """Returns True if path is inside a working Git repository."""
        if not path or not path.exists():
            return False
        # Fast path: direct .git directory or file
        if (path / ".git").exists():
            return True
        ok, out, _ = cls.run_git_sync(path, ["rev-parse", "--is-inside-work-tree"])
        if not (ok and out.strip() == "true"):
            return False
        # Guard against accidental ancestor repo traversal to user home or drive root
        top = cls.get_repo_root(path)
        if top:
            home = Path.home().resolve()
            if top == home and path.resolve() != home:
                return False
            if top.parent == top and path.resolve() != top:
                return False
            return True
        return False

    @classmethod
    def get_repo_root(cls, path: Path) -> Optional[Path]:
        """Finds top-level directory of the Git repository."""
        ok, out, _ = cls.run_git_sync(path, ["rev-parse", "--show-toplevel"])
        if ok and out.strip():
            return Path(out.strip()).resolve()
        return None

    @classmethod
    def init_repo(cls, path: Path) -> Tuple[bool, str]:
        """Initializes a new Git repository at path."""
        p = Path(path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        ok, out, err = cls.run_git_sync(p, ["init"])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def clone_repo(cls, source_url: str, target_dir: Path) -> Tuple[bool, str]:
        """Clones a remote repository or local path into target_dir."""
        target = Path(target_dir).resolve()
        parent_dir = target.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        ok, out, err = cls.run_git_sync(parent_dir, ["clone", source_url, target.name])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def get_status(cls, repo_path: Path) -> Tuple[bool, str, GitRepoState]:
        """
        Parses `git status --porcelain=v1 -b -uall -- .` into a structured GitRepoState.
        """
        if not cls.is_git_repository(repo_path):
            return False, "Not a git repository.", GitRepoState(is_repo=False, root_path=repo_path)

        root = cls.get_repo_root(repo_path) or repo_path
        ok, stdout, stderr = cls.run_git_sync(repo_path, ["status", "--porcelain=v1", "-b", "-uall", "--", "."])
        if not ok:
            return False, stderr, GitRepoState(is_repo=True, root_path=root)

        state = GitRepoState(is_repo=True, root_path=root)
        lines = stdout.splitlines()

        for line in lines:
            if not line:
                continue

            # Branch header: ## branch...tracking [ahead X, behind Y]
            if line.startswith("## "):
                branch_info = line[3:].strip()
                if "No commits yet on " in branch_info:
                    state.current_branch = branch_info.replace("No commits yet on ", "").strip()
                elif "..." in branch_info:
                    parts = branch_info.split("...")
                    state.current_branch = parts[0].strip()
                    # Check ahead / behind
                    m_ahead = re.search(r"ahead (\d+)", branch_info)
                    m_behind = re.search(r"behind (\d+)", branch_info)
                    if m_ahead:
                        state.ahead_count = int(m_ahead.group(1))
                    if m_behind:
                        state.behind_count = int(m_behind.group(1))
                else:
                    state.current_branch = branch_info.split()[0].strip()
                continue

            # Status lines: XY PATH
            if len(line) < 3:
                continue

            x = line[0]
            y = line[1]
            raw_path = line[3:].strip()

            # Handle renames: old -> new
            old_path = None
            if " -> " in raw_path:
                old_p, new_p = raw_path.split(" -> ", 1)
                old_path = old_p.strip('"')
                raw_path = new_p.strip('"')
            else:
                raw_path = raw_path.strip('"')

            # Conflict states: UU, AA, DD, etc.
            if x in "U" or y in "U" or (x == "A" and y == "A") or (x == "D" and y == "D"):
                state.conflict_files.append(
                    GitFileChange(path=raw_path, status_type=GitFileStatusType.CONFLICT, is_staged=False, old_path=old_path)
                )
                continue

            # Untracked
            if x == "?" and y == "?":
                state.untracked_files.append(
                    GitFileChange(path=raw_path, status_type=GitFileStatusType.UNTRACKED, is_staged=False)
                )
                continue

            # Staged changes (column 1 is non-space)
            if x != " " and x != "?":
                st_type = GitFileStatusType.MODIFIED
                if x == "A":
                    st_type = GitFileStatusType.ADDED
                elif x == "D":
                    st_type = GitFileStatusType.DELETED
                elif x == "R":
                    st_type = GitFileStatusType.RENAMED
                elif x == "C":
                    st_type = GitFileStatusType.COPIED

                state.staged_files.append(
                    GitFileChange(path=raw_path, status_type=st_type, is_staged=True, old_path=old_path)
                )

            # Unstaged changes (column 2 is non-space)
            if y != " " and y != "?":
                st_type = GitFileStatusType.MODIFIED
                if y == "D":
                    st_type = GitFileStatusType.DELETED

                state.unstaged_files.append(
                    GitFileChange(path=raw_path, status_type=st_type, is_staged=False, old_path=old_path)
                )

        return True, "Status retrieved.", state

    @classmethod
    def stage_file(cls, repo_path: Path, rel_file: str) -> Tuple[bool, str]:
        ok, out, err = cls.run_git_sync(repo_path, ["add", "--", rel_file])
        return ok, (out if ok else err)

    @classmethod
    def stage_all(cls, repo_path: Path) -> Tuple[bool, str]:
        ok, out, err = cls.run_git_sync(repo_path, ["add", "-A"])
        return ok, (out if ok else err)

    @classmethod
    def unstage_file(cls, repo_path: Path, rel_file: str) -> Tuple[bool, str]:
        # Try `git restore --staged` first, fallback to `git reset HEAD`
        ok, out, err = cls.run_git_sync(repo_path, ["restore", "--staged", "--", rel_file])
        if not ok:
            ok, out, err = cls.run_git_sync(repo_path, ["reset", "HEAD", "--", rel_file])
        return ok, (out if ok else err)

    @classmethod
    def unstage_all(cls, repo_path: Path) -> Tuple[bool, str]:
        ok, out, err = cls.run_git_sync(repo_path, ["restore", "--staged", "."])
        if not ok:
            ok, out, err = cls.run_git_sync(repo_path, ["reset", "HEAD"])
        return ok, (out if ok else err)

    @classmethod
    def discard_file(cls, repo_path: Path, rel_file: str, is_untracked: bool = False) -> Tuple[bool, str]:
        """Discards uncommitted changes for a file. Destructive; must be confirmed by UI."""
        full_path = (repo_path / rel_file).resolve()
        if is_untracked:
            if full_path.exists():
                try:
                    if full_path.is_dir():
                        shutil.rmtree(full_path)
                    else:
                        full_path.unlink()
                    return True, f"Removed untracked '{rel_file}'"
                except Exception as exc:
                    return False, str(exc)
            return True, ""

        # Discard modifications / restore deleted file
        ok, out, err = cls.run_git_sync(repo_path, ["restore", "--", rel_file])
        if not ok:
            ok, out, err = cls.run_git_sync(repo_path, ["checkout", "--", rel_file])
        return ok, (out if ok else err)

    @classmethod
    def discard_all(cls, repo_path: Path) -> Tuple[bool, str]:
        """Discards all unstaged modifications and removes untracked files."""
        ok1, out1, err1 = cls.run_git_sync(repo_path, ["restore", "."])
        if not ok1:
            cls.run_git_sync(repo_path, ["checkout", "--", "."])
        ok2, out2, err2 = cls.run_git_sync(repo_path, ["clean", "-fd"])
        return ok1 and ok2, f"{out1}\n{out2}".strip()

    @classmethod
    def commit(cls, repo_path: Path, message: str) -> Tuple[bool, str]:
        clean_msg = message.strip()
        if not clean_msg:
            return False, "Commit message cannot be empty."
        ok, out, err = cls.run_git_sync(repo_path, ["commit", "-m", clean_msg])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def get_branches(cls, repo_path: Path) -> Tuple[bool, str, List[GitBranch]]:
        ok, out, err = cls.run_git_sync(repo_path, ["branch", "-a"])
        if not ok:
            return False, err, []

        branches: List[GitBranch] = []
        for line in out.splitlines():
            line_str = line.strip()
            if not line_str or "->" in line_str:
                continue

            is_curr = line.startswith("* ")
            name = line[2:].strip()
            is_remote = name.startswith("remotes/")
            if is_remote:
                name = name.replace("remotes/", "")

            branches.append(GitBranch(name=name, is_current=is_curr, is_remote=is_remote))

        return True, "Branches retrieved.", branches

    @classmethod
    def create_branch(cls, repo_path: Path, branch_name: str) -> Tuple[bool, str]:
        clean_name = branch_name.strip()
        if not clean_name:
            return False, "Branch name cannot be empty."
        ok, out, err = cls.run_git_sync(repo_path, ["branch", clean_name])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def switch_branch(cls, repo_path: Path, branch_name: str) -> Tuple[bool, str]:
        clean_name = branch_name.strip()
        ok, out, err = cls.run_git_sync(repo_path, ["switch", clean_name])
        if not ok:
            # Fallback to checkout
            ok, out, err = cls.run_git_sync(repo_path, ["checkout", clean_name])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def delete_branch(cls, repo_path: Path, branch_name: str, force: bool = False) -> Tuple[bool, str]:
        flag = "-D" if force else "-d"
        ok, out, err = cls.run_git_sync(repo_path, ["branch", flag, branch_name.strip()])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def get_history(cls, repo_path: Path, max_count: int = 50) -> Tuple[bool, str, List[GitCommit]]:
        # Format using \x1f (unit separator) to avoid delimiter collisions
        fmt = "%H%x1f%h%x1f%an%x1f%ae%x1f%ad%x1f%at%x1f%s"
        ok, out, err = cls.run_git_sync(repo_path, ["log", f"-n{max_count}", f"--format={fmt}"])
        if not ok:
            return False, err, []

        commits: List[GitCommit] = []
        for line in out.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            parts = line_str.split("\x1f")
            if len(parts) >= 7:
                commits.append(
                    GitCommit(
                        sha=parts[0],
                        short_sha=parts[1],
                        author_name=parts[2],
                        author_email=parts[3],
                        date_str=parts[4],
                        timestamp=int(parts[5]) if parts[5].isdigit() else 0,
                        message=parts[6],
                    )
                )

        return True, "History retrieved.", commits

    @classmethod
    def get_diff(cls, repo_path: Path, rel_file: Optional[str] = None, staged: bool = False) -> Tuple[bool, str, str]:
        """Retrieves raw unified diff for staged or unstaged changes."""
        args = ["diff"]
        if staged:
            args.append("--cached")
        if rel_file:
            args.extend(["--", rel_file])

        ok, out, err = cls.run_git_sync(repo_path, args)
        if not ok:
            return False, err, ""

        # If unstaged diff of an untracked file is requested, generate simulated added diff
        if not out and rel_file:
            full_p = (repo_path / rel_file).resolve()
            if full_p.exists() and full_p.is_file():
                try:
                    content = full_p.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    simulated = [f"--- /dev/null", f"+++ b/{rel_file}", f"@@ -0,0 +1,{len(lines)} @@"]
                    for l in lines:
                        simulated.append(f"+{l}")
                    return True, "Generated untracked diff.", "\n".join(simulated)
                except Exception:
                    pass

        return True, "Diff retrieved.", out

    @classmethod
    def get_commit_diff(cls, repo_path: Path, commit_sha: str) -> Tuple[bool, str, str]:
        ok, out, err = cls.run_git_sync(repo_path, ["show", "--stat", "-p", commit_sha])
        return ok, (out if ok else err), (out if ok else "")

    @classmethod
    def fetch(cls, repo_path: Path, remote: str = "origin") -> Tuple[bool, str]:
        ok, out, err = cls.run_git_sync(repo_path, ["fetch", remote])
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def pull(cls, repo_path: Path, remote: str = "origin", branch: Optional[str] = None) -> Tuple[bool, str]:
        args = ["pull", remote]
        if branch:
            args.append(branch)
        ok, out, err = cls.run_git_sync(repo_path, args)
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def push(cls, repo_path: Path, remote: str = "origin", branch: Optional[str] = None) -> Tuple[bool, str]:
        args = ["push", remote]
        if branch:
            args.append(branch)
        ok, out, err = cls.run_git_sync(repo_path, args)
        return ok, (out.strip() if ok else err.strip())

    @classmethod
    def parse_diff(cls, raw_diff: str, file_path: str = "", is_staged: bool = False) -> DiffFile:
        """Parses a unified diff string into a structured DiffFile."""
        diff_file = DiffFile(path=file_path, is_staged=is_staged, raw_patch=raw_diff)
        lines: List[DiffLine] = []

        old_num = 0
        new_num = 0

        for line in raw_diff.splitlines():
            if line.startswith("@@"):
                # Hunk header @@ -old,len +new,len @@
                m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if m:
                    old_num = int(m.group(1))
                    new_num = int(m.group(2))
                lines.append(DiffLine(line_type="@", old_line_num=None, new_line_num=None, content=line))
            elif line.startswith("+") and not line.startswith("+++"):
                lines.append(DiffLine(line_type="+", old_line_num=None, new_line_num=new_num, content=line[1:]))
                new_num += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines.append(DiffLine(line_type="-", old_line_num=old_num, new_line_num=None, content=line[1:]))
                old_num += 1
            elif line.startswith(" "):
                lines.append(DiffLine(line_type=" ", old_line_num=old_num, new_line_num=new_num, content=line[1:]))
                old_num += 1
                new_num += 1

        diff_file.lines = lines
        return diff_file

