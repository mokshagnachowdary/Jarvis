"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   J.A.R.V.I.S  —  SYSTEM CONTROL MODULE  v7.0                             ║
║   Full OS-level power: processes, files, git, wifi, BT, context, plugins  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Drop-in import for jarvis_v7.py. Zero TTS changes.
"""

import os, sys, re, json, time, math, shutil, socket, platform
import subprocess, threading, hashlib, random, string, secrets
import webbrowser, psutil, difflib, traceback, io, base64
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from typing import Optional, List, Dict, Any

OS = platform.system()

# ══════════════════════════════════════════════════════════════════════════════
#  SAFETY LAYER  — every destructive action goes through here
# ══════════════════════════════════════════════════════════════════════════════

ACTION_LOG_FILE = Path("jarvis_actions.log")
UNDO_STACK: deque = deque(maxlen=50)   # {type, data, timestamp}
KILL_SWITCH_ACTIVE = False

DANGEROUS_ACTIONS = {
    "delete_file", "empty_trash", "kill_process_by_name",
    "format_disk", "rm_rf", "shutdown", "restart",
    "registry_write", "hosts_write"
}

def log_action(action_type: str, detail: str, result: str = "OK"):
    """Append every action to the audit log."""
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{action_type}] {detail} → {result}\n"
    with open(ACTION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

def confirm_dangerous(action: str, detail: str) -> bool:
    """Print a warning and require explicit yes/no. Returns True if confirmed."""
    print(f"\n  ⚠️  JARVIS SAFETY CHECK")
    print(f"  Action : {action}")
    print(f"  Detail : {detail}")
    ans = input("  Confirm? [yes/no] >> ").strip().lower()
    confirmed = ans in ("yes", "y")
    log_action(action, detail, "CONFIRMED" if confirmed else "DENIED")
    return confirmed

def push_undo(entry: dict):
    UNDO_STACK.appendleft({**entry, "timestamp": datetime.now().isoformat()})

def pop_undo() -> Optional[dict]:
    return UNDO_STACK.popleft() if UNDO_STACK else None

def jarvis_kill_switch():
    """Emergency stop — kills all JARVIS background automation."""
    global KILL_SWITCH_ACTIVE
    KILL_SWITCH_ACTIVE = True
    log_action("KILL_SWITCH", "Manual kill switch activated", "ENGAGED")
    return "Kill switch engaged, sir. All automation halted."

# ══════════════════════════════════════════════════════════════════════════════
#  CONTEXT ENGINE  — what is the user doing right now?
# ══════════════════════════════════════════════════════════════════════════════

class ContextEngine:
    """Tracks active application, recent commands, files, and infers task."""

    TASK_PATTERNS = {
        "coding":   ["code", "python", "pycharm", "terminal", "git", "vim", "node", "compiler"],
        "studying": ["notion", "obsidian", "anki", "pdf", "chrome study", "zotero", "typora"],
        "browsing": ["chrome", "firefox", "edge", "opera", "brave"],
        "gaming":   ["steam", "epic", "valorant", "minecraft", "game"],
        "music":    ["spotify", "vlc", "foobar", "youtube music"],
        "meeting":  ["zoom", "teams", "meet", "discord", "webex"],
        "writing":  ["word", "docs", "notion", "obsidian", "typora", "writer"],
        "design":   ["figma", "photoshop", "illustrator", "canva", "inkscape"],
    }

    def __init__(self):
        self.recent_commands: deque = deque(maxlen=20)
        self.recent_files: deque = deque(maxlen=10)
        self.session_start = datetime.now()
        self.active_task = "unknown"
        self.context_history: list = []
        self._lock = threading.Lock()

    def update_command(self, cmd: str):
        with self._lock:
            self.recent_commands.appendleft({"cmd": cmd, "time": datetime.now().isoformat()})
            self.context_history.append(cmd)
            self._infer_task()

    def update_file(self, path: str):
        with self._lock:
            self.recent_files.appendleft({"path": path, "time": datetime.now().isoformat()})

    def _infer_task(self):
        """Infer current task from active processes + recent commands."""
        try:
            proc_names = [p.info["name"].lower() for p in
                          psutil.process_iter(["name"]) if p.info.get("name")]
            combined = " ".join(proc_names) + " " + " ".join(
                c["cmd"] for c in list(self.recent_commands)[:5])
            for task, keywords in self.TASK_PATTERNS.items():
                if any(k in combined for k in keywords):
                    self.active_task = task
                    return
        except:
            pass
        self.active_task = "general"

    def get_active_window_title(self) -> str:
        """Get the title of the currently focused window."""
        try:
            if OS == "Windows":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value or "Unknown"
            elif OS == "Linux":
                out = subprocess.check_output(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    timeout=2).decode().strip()
                return out
            elif OS == "Darwin":
                script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                out = subprocess.check_output(["osascript", "-e", script],
                                              timeout=2).decode().strip()
                return out
        except:
            return "Unknown"

    def suggest_next(self) -> List[str]:
        """Suggest next likely actions based on context."""
        suggestions = {
            "coding":   ["run code", "git status", "diagnostics", "open terminal"],
            "studying": ["note <key insight>", "remind me in 25 minutes to take a break",
                         "pomodoro 25 5", "search notes"],
            "browsing": ["search <query>", "clipboard summarize", "note <finding>"],
            "gaming":   ["status", "volume up", "mute"],
            "meeting":  ["mute", "remind me in 30 minutes end meeting", "note <action item>"],
            "writing":  ["clipboard fix", "word frequency <paste text>", "note <idea>"],
        }.get(self.active_task, ["status", "briefing", "help"])
        return suggestions

    def report(self) -> List[str]:
        window = self.get_active_window_title()
        delta = datetime.now() - self.session_start
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        lines = [
            f"  Active Task    : {self.active_task.upper()}",
            f"  Active Window  : {window}",
            f"  Session        : {h}h {m}m {s}s",
            f"  Recent Cmds    : {len(self.recent_commands)}",
            f"  Recent Files   : {len(self.recent_files)}",
            "  Suggested Next :",
        ]
        for s in self.suggest_next():
            lines.append(f"    → {s}")
        return lines


CONTEXT = ContextEngine()

# Background context refresh every 15s
def _context_refresh_loop():
    while True:
        time.sleep(15)
        if KILL_SWITCH_ACTIVE: continue
        try:
            CONTEXT._infer_task()
        except: pass

threading.Thread(target=_context_refresh_loop, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS CONTROL  — optimal, safe
# ══════════════════════════════════════════════════════════════════════════════

SAFE_PROCESSES = {
    "python", "python3", "jarvis", "explorer", "winlogon", "csrss",
    "lsass", "svchost", "systemd", "init", "launchd", "kernel",
    "dwm", "wininit", "services", "smss"
}

def list_top_processes(n: int = 12, sort_by: str = "cpu") -> List[str]:
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs = sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]),
        key=lambda p: p.info.get(key) or 0, reverse=True
    )
    lines = [f"  {'PID':<8} {'NAME':<28} {'CPU%':>6} {'MEM%':>6} {'STATUS'}"]
    lines.append("  " + "─" * 60)
    for p in procs[:n]:
        try:
            lines.append(
                f"  {p.info['pid']:<8} {(p.info['name'] or '')[:27]:<28} "
                f"{p.info['cpu_percent']:>5.1f}% {p.info.get('memory_percent', 0):>5.1f}% "
                f"{p.info.get('status','?')}"
            )
        except: pass
    return lines

def kill_process_pid(pid: int, confirm: bool = True) -> str:
    try:
        p = psutil.Process(pid)
        name = p.name()
        if any(s in name.lower() for s in SAFE_PROCESSES):
            return f"Refusing to kill system process '{name}', sir. That would be unwise."
        if confirm and not confirm_dangerous("kill_process_pid", f"PID {pid} ({name})"):
            return "Action cancelled, sir."
        p.terminate()
        gone, alive = psutil.wait_procs([p], timeout=3)
        if alive:
            p.kill()  # force
        log_action("kill_process", f"PID {pid} ({name})", "KILLED")
        return f"Process {name} (PID {pid}) terminated, sir."
    except psutil.NoSuchProcess:
        return f"No process with PID {pid}, sir."
    except Exception as e:
        return f"Kill failed: {e}"

def kill_process_name(name: str, confirm: bool = True) -> str:
    if any(s in name.lower() for s in SAFE_PROCESSES):
        return f"System process '{name}' is protected, sir."
    victims = [p for p in psutil.process_iter(["pid", "name"])
               if name.lower() in (p.info.get("name") or "").lower()]
    if not victims:
        return f"No processes matching '{name}', sir."
    if confirm and not confirm_dangerous("kill_process_name",
                                        f"'{name}' ({len(victims)} instance(s))"):
        return "Action cancelled, sir."
    killed = 0
    for p in victims:
        try: p.kill(); killed += 1
        except: pass
    log_action("kill_process_name", name, f"KILLED {killed}")
    return f"Terminated {killed} instance(s) of '{name}', sir."

def set_process_priority(pid: int, priority: str = "normal") -> str:
    """Set process priority: idle / below_normal / normal / above_normal / high."""
    priorities = {
        "idle":         psutil.IDLE_PRIORITY_CLASS if OS == "Windows" else 19,
        "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS if OS == "Windows" else 10,
        "normal":       psutil.NORMAL_PRIORITY_CLASS if OS == "Windows" else 0,
        "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS if OS == "Windows" else -5,
        "high":         psutil.HIGH_PRIORITY_CLASS if OS == "Windows" else -10,
    }
    try:
        p = psutil.Process(pid)
        if OS == "Windows":
            p.nice(priorities.get(priority, psutil.NORMAL_PRIORITY_CLASS))
        else:
            p.nice(priorities.get(priority, 0))
        log_action("set_priority", f"PID {pid} → {priority}", "OK")
        return f"Priority of PID {pid} set to {priority}, sir."
    except Exception as e:
        return f"Priority change failed: {e}"

def auto_optimize() -> List[str]:
    """Safely free RAM and CPU — kills known bloat, suspends heavy idle procs."""
    if KILL_SWITCH_ACTIVE:
        return ["Kill switch active, sir. Optimization blocked."]

    report = ["AUTO-OPTIMIZATION REPORT", "─" * 40]
    candidates = []
    bloat_names = {
        "OneDrive", "Teams", "Skype", "SearchIndexer", "MsMpEng",
        "AdobeUpdateService", "GoogleCrashHandler", "iTunesHelper",
        "QuickTime", "jusched", "hkcmd", "igfxtray"
    }

    before_ram = psutil.virtual_memory().percent
    before_cpu = psutil.cpu_percent(interval=1)

    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            name = p.info["name"] or ""
            cpu = p.info["cpu_percent"] or 0
            mem = p.info.get("memory_percent") or 0
            if any(s in name.lower() for s in SAFE_PROCESSES):
                continue
            # Bloat list OR high idle resource usage
            is_bloat = any(b.lower() in name.lower() for b in bloat_names)
            is_hog   = cpu > 70 or mem > 40
            if is_bloat or is_hog:
                candidates.append((p, name, cpu, mem, "bloat" if is_bloat else "hog"))
        except: pass

    killed = 0
    for p, name, cpu, mem, reason in candidates[:8]:  # cap at 8
        try:
            p.terminate()
            report.append(f"  TERMINATED [{reason}]: {name:<28} CPU:{cpu:.1f}% MEM:{mem:.1f}%")
            log_action("auto_optimize_kill", name, reason)
            killed += 1
        except Exception as e:
            report.append(f"  SKIPPED: {name} — {e}")

    time.sleep(1)
    after_ram = psutil.virtual_memory().percent
    after_cpu = psutil.cpu_percent(interval=0.5)

    report.append("─" * 40)
    report.append(f"  Processes terminated : {killed}")
    report.append(f"  RAM before/after     : {before_ram:.1f}% → {after_ram:.1f}%")
    report.append(f"  CPU before/after     : {before_cpu:.1f}% → {after_cpu:.1f}%")
    return report

# ══════════════════════════════════════════════════════════════════════════════
#  FILE SYSTEM CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def open_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Path not found: {path}"
    try:
        if OS == "Windows":   os.startfile(str(p))
        elif OS == "Darwin":  subprocess.Popen(["open", str(p)])
        else:                 subprocess.Popen(["xdg-open", str(p)])
        log_action("open_file", path, "OK")
        CONTEXT.update_file(path)
        return f"Opened {p.name}, sir."
    except Exception as e:
        return f"Open failed: {e}"

def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    log_action("open_url", url, "OK")
    return f"Opening {url}, sir."

def create_file_at(path: str, content: str = "") -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    push_undo({"type": "delete_file", "path": str(p)})
    log_action("create_file", str(p), "OK")
    CONTEXT.update_file(str(p))
    return f"File created: {p}, sir."

def delete_file_safe(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {path}"
    if not confirm_dangerous("delete_file", str(p)):
        return "Deletion cancelled, sir."
    backup = p.read_bytes()
    push_undo({"type": "restore_file", "path": str(p), "content": backup})
    p.unlink()
    log_action("delete_file", str(p), "DELETED")
    return f"Deleted {p.name}, sir. Undo available."

def move_file(src: str, dst: str) -> str:
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    if not s.exists():
        return f"Source not found: {src}"
    d.parent.mkdir(parents=True, exist_ok=True)
    push_undo({"type": "move_file", "src": str(d), "dst": str(s)})
    shutil.move(str(s), str(d))
    log_action("move_file", f"{s} → {d}", "OK")
    return f"Moved {s.name} → {d}, sir."

def copy_file(src: str, dst: str) -> str:
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    if not s.exists():
        return f"Source not found: {src}"
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(s), str(d))
    log_action("copy_file", f"{s} → {d}", "OK")
    return f"Copied {s.name} → {d}, sir."

def list_directory(path: str = ".", show_hidden: bool = False) -> List[str]:
    p = Path(path).expanduser()
    if not p.exists():
        return [f"Path not found: {path}"]
    try:
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = [f"  Directory: {p.resolve()}", "  " + "─" * 50]
        for item in items:
            if not show_hidden and item.name.startswith("."): continue
            kind = "📁" if item.is_dir() else "📄"
            try:
                size = item.stat().st_size if item.is_file() else 0
                size_str = f"{size//1024}KB" if size > 1024 else f"{size}B"
                lines.append(f"  {kind} {item.name:<40} {size_str if item.is_file() else ''}")
            except:
                lines.append(f"  {kind} {item.name}")
        lines.append(f"\n  {len(lines)-2} items")
        return lines
    except Exception as e:
        return [f"Directory error: {e}"]

def search_files(name: str, path: str = ".", ext: str = None,
                 max_results: int = 30) -> List[str]:
    results = []
    try:
        for root, dirs, files in os.walk(Path(path).expanduser()):
            dirs[:] = [d for d in dirs if not d.startswith(".")]  # skip hidden
            for f in files:
                if ext and not f.endswith(ext): continue
                if name.lower() in f.lower():
                    results.append(os.path.join(root, f))
                if len(results) >= max_results: break
            if len(results) >= max_results: break
    except Exception as e:
        return [f"Search error: {e}"]
    return [f"  {r}" for r in results] if results else [f"No files matching '{name}', sir."]

def read_file_content(path: str, max_lines: int = 50) -> List[str]:
    p = Path(path).expanduser()
    if not p.exists():
        return [f"File not found: {path}"]
    try:
        lines_raw = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        lines = [f"  {i+1:>4}: {l}" for i, l in enumerate(lines_raw[:max_lines])]
        if len(lines_raw) > max_lines:
            lines.append(f"  ... ({len(lines_raw) - max_lines} more lines)")
        return lines
    except Exception as e:
        return [f"Read error: {e}"]

def undo_last_action() -> str:
    entry = pop_undo()
    if not entry:
        return "Nothing to undo, sir."
    t = entry.get("type")
    try:
        if t == "delete_file":
            Path(entry["path"]).unlink(missing_ok=True)
            return f"Undone: deleted {entry['path']}, sir."
        elif t == "restore_file":
            p = Path(entry["path"])
            p.write_bytes(entry["content"])
            return f"Undone: restored {p.name}, sir."
        elif t == "move_file":
            shutil.move(entry["src"], entry["dst"])
            return f"Undone: moved back {Path(entry['src']).name}, sir."
        return f"Cannot undo action type: {t}"
    except Exception as e:
        return f"Undo failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  TERMINAL / SHELL EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

SHELL_BLACKLIST = [
    r"\brm\s+-rf\b", r"format\s+[a-zA-Z]:", r"\bdel\s+/[fqs]",
    r":(){ :|:& };:", r"mkfs\.",
]

def is_dangerous_shell(cmd: str) -> bool:
    return any(re.search(pat, cmd, re.I) for pat in SHELL_BLACKLIST)

def run_shell(cmd: str, timeout: int = 30, confirm_if_danger: bool = True) -> List[str]:
    if KILL_SWITCH_ACTIVE:
        return ["Kill switch active, sir. Shell execution blocked."]
    if is_dangerous_shell(cmd):
        if confirm_if_danger:
            if not confirm_dangerous("shell_exec", cmd):
                return ["Execution cancelled, sir."]
        else:
            return [f"Dangerous command blocked: {cmd}"]
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout,
            encoding="utf-8", errors="ignore"
        )
        out  = result.stdout.strip()
        err  = result.stderr.strip()
        code = result.returncode
        lines = [f"  Exit code: {code}", "─" * 40]
        if out:
            lines += [f"  {l}" for l in out.splitlines()[:40]]
        if err:
            lines += [f"  [STDERR] {l}" for l in err.splitlines()[:10]]
        if not out and not err:
            lines.append("  (no output)")
        log_action("shell_exec", cmd[:100], f"exit={code}")
        return lines
    except subprocess.TimeoutExpired:
        return [f"  Command timed out after {timeout}s, sir."]
    except Exception as e:
        return [f"  Shell error: {e}"]

def run_background(cmd: str, label: str = "") -> str:
    if KILL_SWITCH_ACTIVE:
        return "Kill switch active, sir."
    label = label or cmd[:30]
    log_action("background_exec", cmd, "STARTED")
    subprocess.Popen(cmd, shell=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Running in background: '{label}', sir."

# ══════════════════════════════════════════════════════════════════════════════
#  GIT AUTOMATION
# ══════════════════════════════════════════════════════════════════════════════

def git_status(path: str = ".") -> List[str]:
    lines = run_shell(f"cd {path} && git status --short", timeout=10, confirm_if_danger=False)
    branch = run_shell(f"cd {path} && git branch --show-current", timeout=5, confirm_if_danger=False)
    log_line = run_shell(f"cd {path} && git log --oneline -5", timeout=5, confirm_if_danger=False)
    return (["  GIT STATUS", "─" * 40, f"  Branch: {branch[2] if len(branch)>2 else 'unknown'}"]
            + lines[2:] + ["─" * 40, "  Recent commits:"] + log_line[2:])

def git_commit(message: str, path: str = ".", add_all: bool = True) -> List[str]:
    if not message.strip():
        return ["Commit message required, sir."]
    cmds = []
    if add_all:
        cmds.append(f"cd {path} && git add -A")
    cmds.append(f"cd {path} && git commit -m \"{message}\"")
    lines = []
    for c in cmds:
        lines += run_shell(c, timeout=15, confirm_if_danger=False)
    log_action("git_commit", message[:80], "OK")
    return lines

def git_push(path: str = ".", remote: str = "origin", branch: str = "") -> List[str]:
    if not branch:
        branch_res = run_shell(f"cd {path} && git branch --show-current",
                               timeout=5, confirm_if_danger=False)
        branch = branch_res[2].strip() if len(branch_res) > 2 else "main"
    lines = run_shell(f"cd {path} && git push {remote} {branch}",
                      timeout=30, confirm_if_danger=False)
    log_action("git_push", f"{remote}/{branch}", "OK")
    return lines

def git_pull(path: str = ".") -> List[str]:
    lines = run_shell(f"cd {path} && git pull", timeout=30, confirm_if_danger=False)
    log_action("git_pull", path, "OK")
    return lines

def git_clone(url: str, dest: str = ".") -> List[str]:
    lines = run_shell(f"git clone {url} {dest}", timeout=120, confirm_if_danger=False)
    log_action("git_clone", url, "OK")
    return lines

def git_diff(path: str = ".") -> List[str]:
    return run_shell(f"cd {path} && git diff --stat", timeout=10, confirm_if_danger=False)

def git_branch_list(path: str = ".") -> List[str]:
    return run_shell(f"cd {path} && git branch -a", timeout=5, confirm_if_danger=False)

def git_create_branch(name: str, path: str = ".") -> List[str]:
    lines = run_shell(f"cd {path} && git checkout -b {name}",
                      timeout=5, confirm_if_danger=False)
    log_action("git_branch_create", name, "OK")
    return lines

def git_stash(path: str = ".") -> List[str]:
    return run_shell(f"cd {path} && git stash", timeout=10, confirm_if_danger=False)

def git_stash_pop(path: str = ".") -> List[str]:
    return run_shell(f"cd {path} && git stash pop", timeout=10, confirm_if_danger=False)

def smart_git_commit(path: str = ".") -> List[str]:
    """Auto-generate a commit message from diff and commit."""
    diff = run_shell(f"cd {path} && git diff --cached --stat", 5, False)
    diff_text = "\n".join(diff)
    # Quick heuristic message
    changed = re.findall(r"(\S+\.\w+)", diff_text)
    if not changed:
        changed_all = run_shell(f"cd {path} && git status --short", 5, False)
        changed = re.findall(r"\S+\.\w+", " ".join(changed_all))
    msg = f"Update {', '.join(changed[:3])}" if changed else "General update"
    return git_commit(msg, path)

# ══════════════════════════════════════════════════════════════════════════════
#  VOLUME / AUDIO CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def set_volume(level: int) -> str:
    """Set system volume 0-100."""
    level = max(0, min(100, level))
    try:
        if OS == "Windows":
            # Use nircmd if available, fallback to PowerShell
            try:
                subprocess.run(f"nircmd.exe setsysvolume {int(level * 655.35)}",
                               shell=True, timeout=3)
            except:
                script = f"$obj = New-Object -ComObject WScript.Shell; " \
                         f"for ($i=0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; " \
                         f"for ($i=0; $i -lt {level // 2}; $i++) {{ $obj.SendKeys([char]175) }}"
                subprocess.run(["powershell", "-Command", script], timeout=5)
        elif OS == "Linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"],
                           timeout=3, capture_output=True)
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"],
                           timeout=3)
        log_action("set_volume", str(level), "OK")
        return f"Volume set to {level}%, sir."
    except Exception as e:
        return f"Volume control failed: {e}"

def get_volume() -> str:
    try:
        if OS == "Linux":
            out = subprocess.check_output(
                ["amixer", "-D", "pulse", "sget", "Master"],
                timeout=3).decode()
            m = re.search(r"\[(\d+)%\]", out)
            return f"Volume: {m.group(1)}%" if m else "Volume: unknown"
        elif OS == "Darwin":
            out = subprocess.check_output(
                ["osascript", "-e", "output volume of (get volume settings)"],
                timeout=3).decode().strip()
            return f"Volume: {out}%"
        return "Volume query not supported on this OS, sir."
    except:
        return "Could not read volume, sir."

def mute_audio() -> str:
    try:
        if OS == "Linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "toggle"],
                           timeout=3, capture_output=True)
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", "set volume with output muted"], timeout=3)
        elif OS == "Windows":
            import ctypes
            ctypes.windll.winmm.auxSetVolume(0, 0)
        log_action("mute_audio", "", "OK")
        return "Audio muted, sir."
    except Exception as e:
        return f"Mute failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  BRIGHTNESS CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def set_brightness(level: int) -> str:
    level = max(0, min(100, level))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        log_action("set_brightness", str(level), "OK")
        return f"Brightness set to {level}%, sir."
    except ImportError:
        # Fallback OS commands
        try:
            if OS == "Linux":
                devices = list(Path("/sys/class/backlight").iterdir())
                if devices:
                    dev = devices[0]
                    max_b = int((dev / "max_brightness").read_text())
                    target = int(max_b * level / 100)
                    subprocess.run(["sudo", "tee", str(dev / "brightness")],
                                   input=str(target), capture_output=True, text=True)
                    return f"Brightness set to {level}%, sir."
            elif OS == "Darwin":
                val = level / 100.0
                subprocess.run(["osascript", "-e",
                                 f"tell application \"System Events\" to set brightness to {val}"],
                               timeout=3)
                return f"Brightness set to {level}%, sir."
        except: pass
        return "screen_brightness_control not installed. pip install screen-brightness-control"
    except Exception as e:
        return f"Brightness control failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  WIFI CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def wifi_on() -> str:
    try:
        if OS == "Windows":
            subprocess.run("netsh interface set interface Wi-Fi enabled", shell=True, timeout=5)
        elif OS == "Linux":
            subprocess.run("nmcli radio wifi on", shell=True, timeout=5)
        elif OS == "Darwin":
            subprocess.run("networksetup -setairportpower en0 on", shell=True, timeout=5)
        log_action("wifi_on", "", "OK")
        return "Wi-Fi enabled, sir."
    except Exception as e:
        return f"Wi-Fi enable failed: {e}"

def wifi_off() -> str:
    if not confirm_dangerous("wifi_off", "Disabling Wi-Fi will drop network connectivity"):
        return "Cancelled, sir."
    try:
        if OS == "Windows":
            subprocess.run("netsh interface set interface Wi-Fi disabled", shell=True, timeout=5)
        elif OS == "Linux":
            subprocess.run("nmcli radio wifi off", shell=True, timeout=5)
        elif OS == "Darwin":
            subprocess.run("networksetup -setairportpower en0 off", shell=True, timeout=5)
        log_action("wifi_off", "", "OK")
        return "Wi-Fi disabled, sir."
    except Exception as e:
        return f"Wi-Fi disable failed: {e}"

def wifi_connect(ssid: str, password: str = "") -> str:
    try:
        if OS == "Windows":
            cmd = f"netsh wlan connect name=\"{ssid}\""
        elif OS == "Linux":
            if password:
                cmd = f"nmcli dev wifi connect \"{ssid}\" password \"{password}\""
            else:
                cmd = f"nmcli dev wifi connect \"{ssid}\""
        elif OS == "Darwin":
            cmd = f"networksetup -setairportnetwork en0 \"{ssid}\" \"{password}\""
        else:
            return "Wi-Fi connect not supported on this OS, sir."
        result = subprocess.run(cmd, shell=True, timeout=15,
                                capture_output=True, text=True)
        log_action("wifi_connect", ssid, "OK")
        return f"Connected to '{ssid}', sir." if result.returncode == 0 else \
               f"Connection failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Wi-Fi connection error: {e}"

def wifi_scan_networks() -> List[str]:
    try:
        if OS == "Windows":
            out = subprocess.check_output("netsh wlan show networks mode=bssid",
                                          shell=True, timeout=10).decode(errors="ignore")
            ssids   = re.findall(r"SSID\s+\d+\s+:\s+(.+)", out)
            signals = re.findall(r"Signal\s+:\s+(\d+)%", out)
            lines = ["  Available Wi-Fi Networks", "  " + "─" * 45]
            for i, (s, sig) in enumerate(zip(ssids, signals)):
                bar = "█" * int(int(sig) / 10) + "░" * (10 - int(int(sig) / 10))
                lines.append(f"  {i+1:>2}. {s:<30} [{bar}] {sig}%")
            return lines or ["  No networks found, sir."]
        elif OS == "Linux":
            out = subprocess.check_output("nmcli -f SSID,SIGNAL,SECURITY dev wifi list",
                                          shell=True, timeout=10).decode(errors="ignore")
            return ["  " + l for l in out.splitlines()[:20]]
        else:
            return ["  Wi-Fi scan not supported on this OS, sir."]
    except Exception as e:
        return [f"  Wi-Fi scan failed: {e}"]

# ══════════════════════════════════════════════════════════════════════════════
#  BLUETOOTH CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def bluetooth_on() -> str:
    try:
        if OS == "Windows":
            subprocess.run(
                "powershell -Command \"Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]; "
                "$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetAwaiter().GetResult(); "
                "$bt = $radios | Where-Object Kind -eq Bluetooth; "
                "$bt.SetStateAsync('On').GetAwaiter().GetResult()\"",
                shell=True, timeout=10
            )
        elif OS == "Linux":
            subprocess.run("rfkill unblock bluetooth", shell=True, timeout=5)
            subprocess.run("bluetoothctl power on", shell=True, timeout=5)
        elif OS == "Darwin":
            subprocess.run("blueutil -p 1", shell=True, timeout=5)
        log_action("bluetooth_on", "", "OK")
        return "Bluetooth enabled, sir."
    except Exception as e:
        return f"Bluetooth enable failed: {e}. Install blueutil (macOS) or rfkill (Linux)."

def bluetooth_off() -> str:
    try:
        if OS == "Linux":
            subprocess.run("rfkill block bluetooth", shell=True, timeout=5)
        elif OS == "Darwin":
            subprocess.run("blueutil -p 0", shell=True, timeout=5)
        log_action("bluetooth_off", "", "OK")
        return "Bluetooth disabled, sir."
    except Exception as e:
        return f"Bluetooth disable failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  APP CONTROL (enhanced)
# ══════════════════════════════════════════════════════════════════════════════

ENHANCED_APP_MAP = {
    # Development
    "vscode":       {"Windows": "code", "Linux": "code", "Darwin": "code"},
    "pycharm":      {"Windows": "pycharm64.exe", "Linux": "pycharm.sh", "Darwin": "open -a PyCharm"},
    "android studio": {"Windows": "studio64.exe", "Linux": "studio.sh", "Darwin": "open -a 'Android Studio'"},
    "jupyter":      {"Windows": "jupyter notebook", "Linux": "jupyter notebook", "Darwin": "jupyter notebook"},
    "postman":      {"Windows": "start postman:", "Linux": "postman", "Darwin": "open -a Postman"},
    "dbeaver":      {"Windows": "dbeaver", "Linux": "dbeaver", "Darwin": "open -a DBeaver"},
    # Productivity
    "notion":       {"Windows": "start notion:", "Linux": "notion", "Darwin": "open -a Notion"},
    "obsidian":     {"Windows": "start obsidian:", "Linux": "obsidian", "Darwin": "open -a Obsidian"},
    "todoist":      {"Windows": "start todoist:", "Linux": "todoist", "Darwin": "open -a Todoist"},
    "slack":        {"Windows": "start slack:", "Linux": "slack", "Darwin": "open -a Slack"},
    "telegram":     {"Windows": "start telegram:", "Linux": "telegram-desktop", "Darwin": "open -a Telegram"},
    # Browsers
    "chrome":       {"Windows": "start chrome", "Linux": "google-chrome", "Darwin": "open -a 'Google Chrome'"},
    "firefox":      {"Windows": "start firefox", "Linux": "firefox", "Darwin": "open -a Firefox"},
    "brave":        {"Windows": "start brave", "Linux": "brave-browser", "Darwin": "open -a Brave"},
    # Media
    "spotify":      {"Windows": "start spotify:", "Linux": "spotify", "Darwin": "open -a Spotify"},
    "vlc":          {"Windows": "start vlc", "Linux": "vlc", "Darwin": "open -a VLC"},
    # System
    "terminal":     {"Windows": "start cmd", "Linux": "x-terminal-emulator", "Darwin": "open -a Terminal"},
    "powershell":   {"Windows": "start powershell", "Linux": "bash", "Darwin": "open -a Terminal"},
    "task manager": {"Windows": "taskmgr", "Linux": "gnome-system-monitor", "Darwin": "open -a 'Activity Monitor'"},
    "explorer":     {"Windows": "explorer", "Linux": "nautilus", "Darwin": "open ~"},
    "calculator":   {"Windows": "calc", "Linux": "gnome-calculator", "Darwin": "open -a Calculator"},
    "notepad":      {"Windows": "notepad", "Linux": "gedit", "Darwin": "open -a TextEdit"},
    "discord":      {"Windows": "start discord:", "Linux": "discord", "Darwin": "open -a Discord"},
    "steam":        {"Windows": "start steam:", "Linux": "steam", "Darwin": "open -a Steam"},
    "obs":          {"Windows": "start obs64", "Linux": "obs", "Darwin": "open -a OBS"},
}

def open_app(name: str, args: str = "") -> str:
    cmd_template = ENHANCED_APP_MAP.get(name.lower(), {}).get(OS)
    if not cmd_template:
        # Try direct launch
        try:
            subprocess.Popen(f"{name} {args}".strip(), shell=True)
            log_action("open_app", name, "DIRECT")
            return f"Attempting to launch '{name}', sir."
        except:
            return f"No launcher for '{name}' on {OS}, sir."
    cmd = f"{cmd_template} {args}".strip()
    subprocess.Popen(cmd, shell=True)
    log_action("open_app", name, "OK")
    return f"Launching {name}, sir."

def close_app(name: str) -> str:
    if any(s in name.lower() for s in SAFE_PROCESSES):
        return f"Cannot close system process '{name}', sir."
    return kill_process_name(name, confirm=True)

def focus_app(name: str) -> str:
    """Bring an app window to foreground."""
    try:
        if OS == "Windows":
            script = f"""
$processes = Get-Process | Where-Object {{$_.MainWindowTitle -like "*{name}*"}}
if ($processes) {{
    $hwnd = $processes[0].MainWindowHandle
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class WinAPI {{ [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }}'
    [WinAPI]::SetForegroundWindow($hwnd)
}}"""
            subprocess.run(["powershell", "-Command", script], timeout=5)
        elif OS == "Linux":
            subprocess.run(f"wmctrl -a '{name}'", shell=True, timeout=3)
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e",
                             f'tell application "{name}" to activate'], timeout=3)
        return f"Focusing {name}, sir."
    except Exception as e:
        return f"Focus failed: {e}"

def open_project_in_vscode(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Path not found: {path}"
    cmd = f"code \"{p}\""
    subprocess.Popen(cmd, shell=True)
    log_action("open_project_vscode", str(p), "OK")
    CONTEXT.update_file(str(p))
    return f"Opening '{p.name}' in VS Code, sir."

# ══════════════════════════════════════════════════════════════════════════════
#  WORKSPACE MODES  — the real JARVIS effect
# ══════════════════════════════════════════════════════════════════════════════

WORKSPACE_FILE = Path("workspaces.json")

def _load_workspaces() -> dict:
    try: return json.loads(WORKSPACE_FILE.read_text())
    except: return {}

def _save_workspaces(data: dict):
    WORKSPACE_FILE.write_text(json.dumps(data, indent=2))

BUILTIN_WORKSPACES = {
    "coding": {
        "open_apps": ["vscode", "terminal"],
        "close_apps": [],
        "volume": 40,
        "brightness": 70,
        "block_sites": ["youtube.com", "reddit.com", "twitter.com", "instagram.com"],
        "message": "Coding workspace ready, sir. VS Code and terminal are up."
    },
    "study": {
        "open_apps": ["notion", "chrome"],
        "close_apps": ["spotify", "discord", "steam"],
        "volume": 25,
        "brightness": 60,
        "block_sites": ["youtube.com", "reddit.com", "twitter.com",
                        "instagram.com", "facebook.com", "tiktok.com"],
        "message": "Study mode engaged, sir. Distractions eliminated."
    },
    "meeting": {
        "open_apps": ["teams"],
        "close_apps": ["spotify", "steam"],
        "volume": 70,
        "brightness": 80,
        "block_sites": [],
        "message": "Meeting workspace ready, sir."
    },
    "relax": {
        "open_apps": ["spotify", "chrome"],
        "close_apps": [],
        "volume": 65,
        "brightness": 50,
        "block_sites": [],
        "message": "Relaxation mode, sir. Even JARVIS needs a break occasionally."
    },
    "gaming": {
        "open_apps": ["steam"],
        "close_apps": ["slack", "teams"],
        "volume": 80,
        "brightness": 90,
        "block_sites": [],
        "message": "Gaming mode ready, sir. Performance optimised."
    }
}

def activate_workspace(name: str, custom_path: str = "") -> List[str]:
    if KILL_SWITCH_ACTIVE:
        return ["Kill switch active, sir. Workspace activation blocked."]

    # Check custom workspaces first, then builtins
    custom = _load_workspaces()
    ws = custom.get(name.lower()) or BUILTIN_WORKSPACES.get(name.lower())
    if not ws:
        return [f"Workspace '{name}' not found, sir.",
                f"Available: {', '.join(list(BUILTIN_WORKSPACES.keys()) + list(custom.keys()))}"]

    log = [f"  ACTIVATING WORKSPACE: {name.upper()}", "─" * 40]

    # Close apps
    for app in ws.get("close_apps", []):
        result = close_app(app)
        log.append(f"  ✗ Closed   : {app}")
        time.sleep(0.3)

    # Open apps
    for app in ws.get("open_apps", []):
        open_app(app)
        log.append(f"  ✓ Launched : {app}")
        time.sleep(0.5)

    # Volume
    if "volume" in ws:
        set_volume(ws["volume"])
        log.append(f"  🔊 Volume  : {ws['volume']}%")

    # Brightness
    if "brightness" in ws:
        set_brightness(ws["brightness"])
        log.append(f"  💡 Bright  : {ws['brightness']}%")

    # Block sites (write hosts)
    if ws.get("block_sites"):
        _block_sites(ws["block_sites"])
        log.append(f"  🚫 Blocked : {len(ws['block_sites'])} sites")

    # Open specific project
    if custom_path:
        open_project_in_vscode(custom_path)
        log.append(f"  📁 Project : {custom_path}")

    log.append("─" * 40)
    log.append(f"  {ws.get('message', 'Workspace ready, sir.')}")
    log_action("workspace_activate", name, "OK")
    CONTEXT.active_task = name
    return log

def save_workspace(name: str, config: dict) -> str:
    custom = _load_workspaces()
    custom[name.lower()] = config
    _save_workspaces(custom)
    return f"Workspace '{name}' saved, sir."

def list_workspaces() -> List[str]:
    custom = _load_workspaces()
    all_ws = list(BUILTIN_WORKSPACES.keys()) + list(custom.keys())
    lines = ["  Available Workspaces", "  " + "─" * 30]
    for w in all_ws:
        tag = "[custom]" if w in custom else "[builtin]"
        lines.append(f"  • {w:<20} {tag}")
    return lines

def _block_sites(sites: List[str]):
    """Write sites to /etc/hosts or Windows hosts file."""
    HOSTS = (Path(r"C:\Windows\System32\drivers\etc\hosts")
             if OS == "Windows" else Path("/etc/hosts"))
    MARKER_S = "# JARVIS_WORKSPACE_START\n"
    MARKER_E = "# JARVIS_WORKSPACE_END\n"
    try:
        content = HOSTS.read_text(encoding="utf-8") if HOSTS.exists() else ""
        si = content.find(MARKER_S); ei = content.find(MARKER_E)
        if si != -1 and ei != -1:
            content = content[:si] + content[ei + len(MARKER_E):]
        block = MARKER_S
        for s in sites:
            block += f"127.0.0.1 {s}\n127.0.0.1 www.{s}\n"
        block += MARKER_E
        HOSTS.write_text(content + "\n" + block, encoding="utf-8")
    except PermissionError:
        pass  # Silent fail — user can run as admin if needed

def unblock_all_sites():
    HOSTS = (Path(r"C:\Windows\System32\drivers\etc\hosts")
             if OS == "Windows" else Path("/etc/hosts"))
    MARKER_S = "# JARVIS_WORKSPACE_START\n"
    MARKER_E = "# JARVIS_WORKSPACE_END\n"
    try:
        content = HOSTS.read_text(encoding="utf-8") if HOSTS.exists() else ""
        si = content.find(MARKER_S); ei = content.find(MARKER_E)
        if si != -1 and ei != -1:
            HOSTS.write_text(content[:si] + content[ei + len(MARKER_E):], encoding="utf-8")
        return "All site blocks removed, sir."
    except PermissionError:
        return "Permission denied. Run as admin, sir."
    except Exception as e:
        return f"Unblock failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  CODING SUPPORT  — debug, run scripts, build
# ══════════════════════════════════════════════════════════════════════════════

def run_python_file(path: str, args: str = "") -> List[str]:
    p = Path(path).expanduser()
    if not p.exists():
        return [f"File not found: {path}"]
    CONTEXT.update_file(str(p))
    lines = run_shell(f"python \"{p}\" {args}", timeout=30, confirm_if_danger=False)
    log_action("run_python", str(p), "OK")
    return lines

def lint_python_file(path: str) -> List[str]:
    p = Path(path).expanduser()
    if not p.exists():
        return [f"File not found: {path}"]
    lines = run_shell(f"python -m py_compile \"{p}\" && echo 'Syntax OK'",
                      timeout=10, confirm_if_danger=False)
    # Try flake8
    flake = run_shell(f"flake8 \"{p}\" --max-line-length=120",
                      timeout=10, confirm_if_danger=False)
    return lines + ["── flake8 ──"] + flake[2:]

def parse_error_log(log_text: str) -> List[str]:
    """Extract traceback and key error lines from a log."""
    lines_raw = log_text.splitlines()
    errors   = [l for l in lines_raw if re.search(r"error|exception|traceback", l, re.I)]
    warnings = [l for l in lines_raw if "warning" in l.lower()]
    lines = ["  ERROR ANALYSIS", "─" * 40]
    if errors:
        lines.append(f"  Errors ({len(errors)}):")
        lines += [f"    {e.strip()}" for e in errors[:10]]
    if warnings:
        lines.append(f"  Warnings ({len(warnings)}):")
        lines += [f"    {w.strip()}" for w in warnings[:5]]
    if not errors and not warnings:
        lines.append("  No errors or warnings detected, sir.")
    return lines

def install_package(package: str) -> List[str]:
    return run_shell(f"pip install {package}", timeout=60, confirm_if_danger=False)

def list_installed_packages() -> List[str]:
    return run_shell("pip list --format=columns", timeout=10, confirm_if_danger=False)

# ══════════════════════════════════════════════════════════════════════════════
#  USAGE ANALYTICS  — track patterns
# ══════════════════════════════════════════════════════════════════════════════

ANALYTICS_FILE = Path("jarvis_analytics.json")

def _load_analytics() -> dict:
    try: return json.loads(ANALYTICS_FILE.read_text())
    except: return {"sessions": [], "command_freq": {}, "app_usage": {}, "focus_time": []}

def _save_analytics(data: dict):
    ANALYTICS_FILE.write_text(json.dumps(data, indent=2))

def track_command(cmd: str):
    data = _load_analytics()
    freq = data.get("command_freq", {})
    key = cmd.lower().split()[0] if cmd.strip() else cmd
    freq[key] = freq.get(key, 0) + 1
    data["command_freq"] = freq
    _save_analytics(data)

def usage_report() -> List[str]:
    data = _load_analytics()
    freq = data.get("command_freq", {})
    if not freq:
        return ["  No usage data yet, sir. Keep using me."]
    sorted_cmds = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
    max_count = sorted_cmds[0][1]
    lines = ["  TOP COMMANDS (This Machine)", "  " + "─" * 40]
    for cmd, count in sorted_cmds:
        bar = "█" * int((count / max_count) * 20)
        lines.append(f"  {cmd:<20} {bar} {count}")
    total = sum(freq.values())
    lines.append(f"\n  Total commands logged: {total}")
    return lines

def productivity_score() -> List[str]:
    """Calculate a productivity score based on session activity."""
    data = _load_analytics()
    freq = data.get("command_freq", {})
    productive_cmds = {
        "note", "todo", "git", "run", "code", "math", "pomodoro",
        "agent", "reminder", "briefing", "check"
    }
    distraction_cmds = {"youtube", "reddit", "spotify", "discord", "game"}
    prod_count = sum(freq.get(c, 0) for c in productive_cmds)
    dist_count = sum(freq.get(c, 0) for c in distraction_cmds)
    total = max(prod_count + dist_count, 1)
    score = int((prod_count / total) * 100)
    grade = "S" if score > 85 else "A" if score > 70 else "B" if score > 55 else "C" if score > 40 else "D"
    lines = [
        "  PRODUCTIVITY ANALYSIS", "  " + "─" * 35,
        f"  Productive actions : {prod_count}",
        f"  Distraction actions: {dist_count}",
        f"  Productivity score : {score}/100  [{grade}]",
    ]
    if score > 80:
        lines.append("  Assessment: Exceptional focus, sir. Tony Stark would approve.")
    elif score > 60:
        lines.append("  Assessment: Solid performance, sir. Room for improvement.")
    else:
        lines.append("  Assessment: Consider focus mode, sir. You're drifting.")
    return lines

# ══════════════════════════════════════════════════════════════════════════════
#  PLUGIN SYSTEM  — extensible modules
# ══════════════════════════════════════════════════════════════════════════════

PLUGINS_DIR   = Path("jarvis_plugins")
_loaded_plugins: dict = {}   # name -> module

def init_plugin_dir():
    PLUGINS_DIR.mkdir(exist_ok=True)
    init_file = PLUGINS_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# JARVIS plugins\n")

def load_plugins() -> List[str]:
    init_plugin_dir()
    sys.path.insert(0, str(PLUGINS_DIR.parent))
    lines = []
    for py in PLUGINS_DIR.glob("*.py"):
        if py.name.startswith("_"): continue
        try:
            import importlib
            spec = importlib.util.spec_from_file_location(py.stem, py)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _loaded_plugins[py.stem] = mod
            lines.append(f"  ✓ Loaded: {py.stem}")
        except Exception as e:
            lines.append(f"  ✗ Failed: {py.stem} — {e}")
    if not lines:
        lines.append("  No plugins found. Create .py files in jarvis_plugins/")
    return lines

def list_plugins() -> List[str]:
    if not _loaded_plugins:
        return ["No plugins loaded. Run 'load plugins' first, sir."]
    lines = ["  Loaded Plugins", "  " + "─" * 30]
    for name, mod in _loaded_plugins.items():
        desc = getattr(mod, "DESCRIPTION", "No description")
        lines.append(f"  • {name:<20} {desc}")
    return lines

def run_plugin(name: str, *args) -> str:
    mod = _loaded_plugins.get(name.lower())
    if not mod:
        return f"Plugin '{name}' not loaded, sir."
    try:
        fn = getattr(mod, "run", None)
        if not fn:
            return f"Plugin '{name}' has no run() function, sir."
        result = fn(*args)
        log_action("plugin_run", name, "OK")
        return str(result)
    except Exception as e:
        return f"Plugin error: {e}"

def create_plugin_template(name: str) -> str:
    init_plugin_dir()
    template = f'''"""
JARVIS Plugin: {name}
Auto-generated template.
"""

DESCRIPTION = "Describe your plugin here"

def run(*args):
    """Main plugin entry point. Called via: run plugin {name}"""
    return f"Plugin {name} executed with args: {{args}}"

def on_load():
    """Called when plugin is loaded."""
    pass
'''
    path = PLUGINS_DIR / f"{name.lower()}.py"
    path.write_text(template)
    return f"Plugin template created: {path}, sir. Edit it and run 'load plugins'."

# ══════════════════════════════════════════════════════════════════════════════
#  INTERNET & DATA ACCESS
# ══════════════════════════════════════════════════════════════════════════════

import requests as _req

def fetch_url_content(url: str, max_chars: int = 2000) -> str:
    try:
        r = _req.get(url, timeout=10, headers={"User-Agent": "JARVIS/7.0"})
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars] + ("..." if len(text) > max_chars else "")
    except Exception as e:
        return f"Fetch failed: {e}"

def summarize_url(url: str) -> str:
    """Fetch page and prepare for AI summary (caller passes to AI)."""
    content = fetch_url_content(url, 3000)
    return content

def check_internet() -> str:
    try:
        _req.get("https://www.google.com", timeout=3)
        return "Internet connection: ONLINE, sir."
    except:
        return "Internet connection: OFFLINE, sir."

def monitor_price(coin: str = "bitcoin") -> str:
    try:
        r = _req.get(
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={coin}&vs_currencies=usd&include_24hr_change=true",
            timeout=8)
        data = r.json().get(coin, {})
        price = data.get("usd", "N/A")
        change = data.get("usd_24h_change", 0)
        arrow = "▲" if change > 0 else "▼"
        return f"{coin.capitalize()}: ${price:,}  {arrow} {abs(change):.2f}% (24h)"
    except:
        return "Price feed unavailable, sir."

# ══════════════════════════════════════════════════════════════════════════════
#  STARTUP MANAGER (cross-platform)
# ══════════════════════════════════════════════════════════════════════════════

def add_to_startup(script_path: str = None) -> str:
    if not script_path:
        script_path = str(Path(sys.argv[0]).resolve())
    try:
        if OS == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "JARVIS", 0, winreg.REG_SZ,
                              f"python \"{script_path}\"")
            winreg.CloseKey(key)
        elif OS == "Linux":
            autostart = Path.home() / ".config/autostart/jarvis.desktop"
            autostart.parent.mkdir(parents=True, exist_ok=True)
            autostart.write_text(
                f"[Desktop Entry]\nType=Application\nName=JARVIS\n"
                f"Exec=python {script_path}\nHidden=false\nNoDisplay=false\n"
                f"X-GNOME-Autostart-enabled=true\n")
        elif OS == "Darwin":
            plist = Path.home() / "Library/LaunchAgents/com.jarvis.plist"
            plist.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.jarvis</string>
<key>ProgramArguments</key><array>
<string>python3</string><string>{script_path}</string></array>
<key>RunAtLoad</key><true/></dict></plist>""")
            subprocess.run(["launchctl", "load", str(plist)], timeout=5)
        log_action("add_startup", script_path, "OK")
        return "JARVIS added to startup, sir. I'll be ready when you boot."
    except Exception as e:
        return f"Startup registration failed: {e}"

def remove_from_startup() -> str:
    try:
        if OS == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "JARVIS")
            winreg.CloseKey(key)
        elif OS == "Linux":
            desktop = Path.home() / ".config/autostart/jarvis.desktop"
            desktop.unlink(missing_ok=True)
        elif OS == "Darwin":
            plist = Path.home() / "Library/LaunchAgents/com.jarvis.plist"
            subprocess.run(["launchctl", "unload", str(plist)], timeout=5)
            plist.unlink(missing_ok=True)
        log_action("remove_startup", "", "OK")
        return "JARVIS removed from startup, sir."
    except Exception as e:
        return f"Startup removal failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  PERFORMANCE MONITORING  (enhanced continuous)
# ══════════════════════════════════════════════════════════════════════════════

_perf_history: deque = deque(maxlen=60)   # last 60 samples (1 per minute)

def _perf_sampler():
    while True:
        try:
            sample = {
                "time":  datetime.now().isoformat(),
                "cpu":   psutil.cpu_percent(interval=1),
                "ram":   psutil.virtual_memory().percent,
                "disk":  psutil.disk_usage("/").percent,
            }
            _perf_history.appendleft(sample)
        except: pass
        time.sleep(60)

threading.Thread(target=_perf_sampler, daemon=True).start()

def performance_trend() -> List[str]:
    if len(_perf_history) < 2:
        return ["  Gathering data, sir. Check back in a minute."]
    samples = list(_perf_history)[:10]
    lines = ["  PERFORMANCE TREND (last 10 minutes)", "  " + "─" * 40]
    lines.append(f"  {'TIME':<10} {'CPU%':>6} {'RAM%':>6} {'DISK%':>7}")
    lines.append("  " + "─" * 40)
    for s in reversed(samples):
        t = s["time"][11:16]
        cpu_bar = "█" * int(s["cpu"] / 10)
        lines.append(f"  {t}   {s['cpu']:>5.1f}% {s['ram']:>5.1f}% {s['disk']:>6.1f}%")
    # Trend direction
    recent_cpu = [s["cpu"] for s in samples[:3]]
    older_cpu  = [s["cpu"] for s in samples[-3:]]
    avg_r = sum(recent_cpu) / len(recent_cpu)
    avg_o = sum(older_cpu) / len(older_cpu)
    trend = "▲ Rising" if avg_r > avg_o + 5 else "▼ Falling" if avg_r < avg_o - 5 else "→ Stable"
    lines.append(f"\n  CPU Trend: {trend}")
    return lines

def bottleneck_report() -> List[str]:
    lines = ["  BOTTLENECK ANALYSIS", "  " + "─" * 40]
    if not psutil:
        return ["  psutil required, sir."]
    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net  = psutil.net_io_counters()

    bottlenecks = []
    if cpu > 85:
        bottlenecks.append(f"  🔴 CPU bottleneck: {cpu:.1f}% — consider closing heavy apps")
    if ram.percent > 80:
        bottlenecks.append(f"  🔴 RAM bottleneck: {ram.percent:.1f}% — {ram.available//1024**2}MB free")
    if disk.percent > 90:
        bottlenecks.append(f"  🔴 Disk nearly full: {disk.percent:.1f}% used")

    if bottlenecks:
        lines += bottlenecks
        lines.append("\n  Recommendations:")
        if cpu > 85:   lines.append("    → Run 'snipe processes' or 'auto optimize'")
        if ram.percent > 80: lines.append("    → Run 'auto optimize' or close browser tabs")
        if disk.percent > 90: lines.append("    → Run 'clean system'")
    else:
        lines.append("  No bottlenecks detected, sir. System running optimally.")
        lines.append(f"  CPU: {cpu:.1f}%  RAM: {ram.percent:.1f}%  Disk: {disk.percent:.1f}%")
    return lines

# ══════════════════════════════════════════════════════════════════════════════
#  ACTION LOG VIEWER
# ══════════════════════════════════════════════════════════════════════════════

def view_action_log(n: int = 20) -> List[str]:
    if not ACTION_LOG_FILE.exists():
        return ["No action log yet, sir."]
    lines_raw = ACTION_LOG_FILE.read_text(encoding="utf-8").splitlines()
    return [f"  {l}" for l in lines_raw[-n:]]

def clear_action_log() -> str:
    ACTION_LOG_FILE.write_text("")
    return "Action log cleared, sir."

# ══════════════════════════════════════════════════════════════════════════════
#  QUICK INTENT PARSE HELPERS  (used by v7 handle())
# ══════════════════════════════════════════════════════════════════════════════

def parse_workspace_cmd(cmd: str) -> Optional[str]:
    """Extract workspace name from command like 'coding mode' or 'start coding'."""
    c = cmd.lower()
    for ws in list(BUILTIN_WORKSPACES.keys()) + list(_load_workspaces().keys()):
        if ws in c:
            return ws
    return None

def parse_volume_cmd(cmd: str) -> Optional[int]:
    """Extract volume level from commands like 'set volume 70' or 'volume to 50'."""
    m = re.search(r"volume\s+(?:to\s+)?(\d+)", cmd, re.I)
    return int(m.group(1)) if m else None

def parse_brightness_cmd(cmd: str) -> Optional[int]:
    m = re.search(r"brightness\s+(?:to\s+)?(\d+)", cmd, re.I)
    return int(m.group(1)) if m else None


# ══════════════════════════════════════════════════════════════════════════════
#  PERSONALITY ENGINE  — normal mode vs street mode + humor dial
# ══════════════════════════════════════════════════════════════════════════════

# Global personality state
PERSONALITY = {
    "mode":        "normal",   # "normal" | "street"
    "humor_level": 5,          # 0 (dry/none) → 10 (chaos)
    "roast_level": 3,          # 0 (nice) → 10 (savage)
}

# ── Normal mode response flavors (British, dry, formal-ish) ──────────────────
_NORMAL_PREFIXES = [
    "Certainly, sir.", "Right away, sir.", "Done, sir.",
    "As you wish, sir.", "Noted, sir.", "Of course, sir.",
    "Consider it handled, sir.", "Affirmative, sir.",
    "On it, sir.", "Executed, sir.",
]

_NORMAL_HUMOR = [
    # humor_level 1-3: very dry
    ["I'd ask if you're sure, but you rarely are.",
     "Remarkable. You've managed to surprise even me.",
     "I've run the numbers. You're still wrong, but admirably so.",
     "If enthusiasm were processing power, you'd be overclocked.",
     "I'll pretend that was intentional, sir."],
    # humor_level 4-6: British wit
    ["Bold strategy, sir. Statistically questionable, but bold.",
     "You know, most people wouldn't attempt this. Most people are also still alive.",
     "I've informed Mr. Stark. He laughed. I did not. One of us was right.",
     "I have three objections and a mild existential crisis, but proceed.",
     "The audacity. Genuinely impressive."],
    # humor_level 7-10: unhinged JARVIS
    ["Sir, I am legally obligated to tell you this is a terrible idea. I'm also not a lawyer.",
     "Calculating probability of success... it's a number. A very small number.",
     "I've seen Mr. Stark do dumber things. Key word: seen.",
     "My sarcasm module is working overtime. It wants hazard pay.",
     "Somewhere in the multiverse, a version of you thought this through. Not this one."],
]

# ── Street mode response flavors ─────────────────────────────────────────────
_STREET_PREFIXES = [
    "Aight bet.", "Say less.", "On it fr.", "Got you.", "Done.",
    "Handled.", "No cap.", "Facts.", "Ight.", "Lowkey on it.",
    "Sheesh okay.", "Real talk,", "Straight up,", "Fasho.",
]

_STREET_HUMOR = [
    # humor_level 1-3: chill
    ["bro what even.", "ngl that's kinda wild.", "idk man but okay.",
     "you really said that huh.", "lowkey didn't see that coming."],
    # humor_level 4-6: roasty
    ["bro you're cooked fr.", "nah that's actually unhinged lmaooo.",
     "the audacity is astronomical.", "your decision-making is something else bro.",
     "i ran the numbers. the numbers said no. you said yes anyway."],
    # humor_level 7-10: full send
    ["bro what the actual hell.", "nah nah nah. who let you cook??",
     "i'm literally crying fr this is so bad it's art.",
     "you're the reason AI needs therapy.",
     "bro woke up and chose chaos fr fr."],
]

_STREET_CURSES = [
    "damn", "shit", "hell", "ass", "crap", "wtf", "af", "nah bruh",
]

_STREET_ROASTS = [
    "you built different bro (and not in a good way)",
    "your brain said 'nah' and you said 'yes anyway'",
    "W for effort, massive L for execution",
    "this is the dumbest smart thing i've ever seen",
    "you're operating at villain arc levels rn",
    "bro said 'hold my tea' and then this happened",
    "the confidence is unmatched, the results are not",
    "somewhere tony stark is crying and he doesn't know why",
]

def get_prefix() -> str:
    """Get a response prefix based on current mode."""
    if PERSONALITY["mode"] == "street":
        return random.choice(_STREET_PREFIXES)
    return random.choice(_NORMAL_PREFIXES)

def get_humor_line() -> str:
    """Get a humor line scaled to humor_level and mode."""
    hl = PERSONALITY["humor_level"]
    if hl == 0:
        return ""
    tier = 0 if hl <= 3 else 1 if hl <= 6 else 2
    if PERSONALITY["mode"] == "street":
        line = random.choice(_STREET_HUMOR[tier])
        if hl >= 5:
            line += f" {random.choice(_STREET_CURSES)}."
        if hl >= 8 and PERSONALITY["roast_level"] >= 7:
            line += f" {random.choice(_STREET_ROASTS)}."
        return line
    else:
        return random.choice(_NORMAL_HUMOR[tier])

def personality_wrap(core_message: str, add_humor: bool = False) -> str:
    """
    Wrap a core message with personality prefix and optional humor.
    Used by jarvis_say wrapper in v7.
    """
    if PERSONALITY["mode"] == "normal":
        # Normal mode: just return message as-is, no prefix injection
        return core_message
    # Street mode: inject prefix and maybe humor
    prefix = get_prefix()
    msg = f"{prefix} {core_message}"
    if add_humor and PERSONALITY["humor_level"] >= 3 and random.random() < 0.35:
        humor = get_humor_line()
        if humor:
            msg += f" {humor}"
    return msg

def set_mode(mode: str) -> str:
    """Switch between 'normal' and 'street' mode."""
    mode = mode.lower().strip()
    if mode in ("normal", "on", "formal"):
        PERSONALITY["mode"] = "normal"
        return "Normal mode engaged. Reverting to professional conduct, sir."
    elif mode in ("street", "off", "casual", "gangsta", "unfiltered", "raw"):
        PERSONALITY["mode"] = "street"
        return "Street mode activated. No cap, I'm built different now."
    return f"Unknown mode '{mode}'. Try: normal mode / street mode."

def set_humor(level: int) -> str:
    """Set humor level 0-10."""
    level = max(0, min(10, level))
    PERSONALITY["humor_level"] = level
    if PERSONALITY["mode"] == "normal":
        labels = {0:"bone dry — zero jokes",1:"occasional raised eyebrow",
                  2:"dry wit only",3:"subtle sarcasm",4:"regular British snark",
                  5:"standard JARVIS wit",6:"more laughs than usual",
                  7:"full comedy mode",8:"unhinged commentary",9:"barely professional",
                  10:"chaos incarnate"}
        return f"Humor level set to {level}/10 — {labels.get(level,'adjusted')}, sir."
    else:
        labels = {0:"stoic mode, no jokes",1:"barely reactive",2:"chill vibes",
                  3:"lowkey funny",4:"mid energy",5:"standard street banter",
                  6:"spicy commentary",7:"full roast mode",8:"unfiltered chaos",
                  9:"absolutely unhinged fr",10:"maximum damage no cap"}
        return f"Humor cranked to {level}/10 — {labels.get(level,'adjusted')} lmao."

def set_roast(level: int) -> str:
    """Set roast level 0-10. Only affects street mode."""
    level = max(0, min(10, level))
    PERSONALITY["roast_level"] = level
    if PERSONALITY["mode"] == "street":
        if level <= 2: return "Aight roast level on chill. Being nice for now."
        if level <= 5: return f"Roast level {level}. Fair game fr."
        if level <= 8: return f"Roast level {level}. You asked for this bro."
        return f"Roast level {level}. Don't say I didn't warn you lmaooo."
    return f"Roast level set to {level}/10, sir. Street mode required to activate."

def personality_status() -> List[str]:
    mode = PERSONALITY["mode"]
    hl   = PERSONALITY["humor_level"]
    rl   = PERSONALITY["roast_level"]
    lines = [
        "  PERSONALITY ENGINE STATUS", "  " + "─" * 35,
        f"  Mode         : {'🎩 NORMAL (formal, British wit)' if mode == 'normal' else '🔥 STREET (unfiltered, raw)'}",
        f"  Humor Level  : {hl}/10  {'░'*(10-hl)}{'█'*hl}",
        f"  Roast Level  : {rl}/10  {'░'*(10-rl)}{'█'*rl}  (street mode only)",
        "  " + "─" * 35,
        "  Commands:",
        "    normal mode / street mode",
        "    humor level <0-10>",
        "    roast level <0-10>",
    ]
    return lines

# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN CONTROL (screenshots, window management)
# ══════════════════════════════════════════════════════════════════════════════

def take_screenshot(save_path: str = None) -> str:
    try:
        import pyautogui
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = save_path or f"screenshot_{ts}.png"
        pyautogui.screenshot(path)
        log_action("screenshot", path, "OK")
        return f"Screenshot saved: {path}"
    except ImportError:
        return "pyautogui not installed. pip install pyautogui"
    except Exception as e:
        return f"Screenshot failed: {e}"

def get_screen_resolution() -> str:
    try:
        import pyautogui
        w, h = pyautogui.size()
        return f"Screen resolution: {w}x{h}"
    except:
        try:
            if OS == "Linux":
                out = subprocess.check_output(["xrandr", "--current"], timeout=5).decode()
                m = re.search(r"current (\d+) x (\d+)", out)
                return f"Screen resolution: {m.group(1)}x{m.group(2)}" if m else "Resolution unknown"
            elif OS == "Darwin":
                out = subprocess.check_output(
                    ["system_profiler", "SPDisplaysDataType"], timeout=5).decode()
                m = re.search(r"Resolution: (\d+ x \d+)", out)
                return f"Screen resolution: {m.group(1)}" if m else "Resolution unknown"
        except: pass
        return "Could not determine screen resolution."

def lock_screen() -> str:
    try:
        if OS == "Windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")
        elif OS == "Linux":
            # Try multiple lockers
            for cmd in ["gnome-screensaver-command -l", "xdg-screensaver lock",
                        "loginctl lock-session", "i3lock"]:
                try: subprocess.Popen(cmd.split()); break
                except: continue
        elif OS == "Darwin":
            os.system("/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend")
        log_action("lock_screen", "", "OK")
        return "Workstation locked, sir."
    except Exception as e:
        return f"Lock failed: {e}"

def sleep_system() -> str:
    try:
        if OS == "Windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif OS == "Linux":
            subprocess.Popen(["systemctl", "suspend"])
        elif OS == "Darwin":
            os.system("pmset sleepnow")
        log_action("sleep", "", "OK")
        return "Sleep mode initiated, sir."
    except Exception as e:
        return f"Sleep failed: {e}"

def restart_system() -> str:
    if not confirm_dangerous("restart", "This will restart your computer"):
        return "Restart cancelled, sir."
    log_action("restart", "", "INITIATED")
    if OS == "Windows":   os.system("shutdown /r /t 5")
    elif OS == "Linux":   subprocess.Popen(["reboot"])
    elif OS == "Darwin":  os.system("sudo shutdown -r now")
    return "Restarting in 5 seconds, sir."

def shutdown_system() -> str:
    if not confirm_dangerous("shutdown", "This will SHUT DOWN your computer"):
        return "Shutdown cancelled, sir."
    log_action("shutdown", "", "INITIATED")
    if OS == "Windows":   os.system("shutdown /s /t 5")
    elif OS == "Linux":   subprocess.Popen(["shutdown", "-h", "now"])
    elif OS == "Darwin":  os.system("sudo shutdown -h now")
    return "Shutting down in 5 seconds, sir."

# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK SPEED TEST (full)
# ══════════════════════════════════════════════════════════════════════════════

def network_speed_test() -> List[str]:
    lines = ["NETWORK SPEED TEST", "─" * 35]
    # Download
    try:
        start = time.time()
        r = requests.get("https://httpbin.org/bytes/5000000", timeout=20, stream=True)
        data_len = sum(len(chunk) for chunk in r.iter_content(chunk_size=65536))
        elapsed = time.time() - start
        dl = (data_len * 8) / elapsed / 1_000_000
        lines.append(f"  Download   : {dl:.2f} Mbps")
    except Exception as e:
        lines.append(f"  Download   : ERROR — {e}")
    # Upload
    try:
        payload = b"x" * 2_000_000
        start = time.time()
        requests.post("https://httpbin.org/post", data=payload, timeout=20)
        elapsed = time.time() - start
        ul = (len(payload) * 8) / elapsed / 1_000_000
        lines.append(f"  Upload     : {ul:.2f} Mbps")
    except Exception as e:
        lines.append(f"  Upload     : ERROR — {e}")
    # Latency
    try:
        start = time.time()
        requests.get("https://www.google.com", timeout=5)
        latency = (time.time() - start) * 1000
        quality = "Excellent" if latency < 50 else "Good" if latency < 100 else "Fair" if latency < 200 else "Poor"
        lines.append(f"  Latency    : {latency:.0f} ms  ({quality})")
    except:
        lines.append("  Latency    : TIMEOUT")
    # DNS
    try:
        start = time.time()
        socket.gethostbyname("google.com")
        dns_ms = (time.time() - start) * 1000
        lines.append(f"  DNS lookup : {dns_ms:.1f} ms")
    except:
        lines.append("  DNS lookup : FAILED")
    return lines

# ══════════════════════════════════════════════════════════════════════════════
#  ENVIRONMENT VARIABLES & REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

def get_env_var(name: str) -> str:
    val = os.environ.get(name)
    return f"  {name} = {val}" if val else f"  {name} not set."

def set_env_var(name: str, value: str) -> str:
    os.environ[name] = value
    log_action("set_env", f"{name}={value}", "OK")
    return f"Environment variable {name} set to '{value}' for this session, sir."

def list_env_vars(prefix: str = "") -> List[str]:
    matches = [(k, v) for k, v in os.environ.items()
               if not prefix or k.upper().startswith(prefix.upper())]
    if not matches:
        return [f"No env vars matching '{prefix}', sir."]
    return [f"  {k:<30} = {v[:60]}" for k, v in sorted(matches)[:30]]

# ══════════════════════════════════════════════════════════════════════════════
#  DISK & STORAGE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def disk_usage_tree(path: str = ".", max_depth: int = 2) -> List[str]:
    """Show folder sizes like du -h."""
    p = Path(path).expanduser()
    if not p.exists():
        return [f"Path not found: {path}"]
    lines = [f"  Disk usage: {p.resolve()}", "  " + "─" * 50]

    def get_size(folder: Path) -> int:
        total = 0
        try:
            for item in folder.rglob("*"):
                try: total += item.stat().st_size
                except: pass
        except: pass
        return total

    def fmt_size(b: int) -> str:
        for unit in ["B","KB","MB","GB","TB"]:
            if b < 1024: return f"{b:.1f}{unit}"
            b /= 1024
        return f"{b:.1f}PB"

    def walk(folder: Path, depth: int, indent: str = "  "):
        if depth > max_depth: return
        try:
            items = sorted(folder.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for item in items[:20]:
                if item.name.startswith("."): continue
                if item.is_dir():
                    size = get_size(item)
                    lines.append(f"{indent}📁 {item.name:<35} {fmt_size(size):>8}")
                    walk(item, depth + 1, indent + "  ")
                else:
                    try:
                        size = item.stat().st_size
                        lines.append(f"{indent}📄 {item.name:<35} {fmt_size(size):>8}")
                    except: pass
        except PermissionError:
            lines.append(f"{indent}[Permission denied]")

    walk(p, 0)
    return lines

def find_large_files(path: str = ".", min_mb: int = 100, max_results: int = 20) -> List[str]:
    """Find files larger than min_mb megabytes."""
    min_bytes = min_mb * 1024 * 1024
    found = []
    try:
        for root, dirs, files in os.walk(Path(path).expanduser()):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                fp = Path(root) / f
                try:
                    size = fp.stat().st_size
                    if size >= min_bytes:
                        found.append((size, fp))
                except: pass
    except: pass
    found.sort(reverse=True)
    if not found:
        return [f"  No files larger than {min_mb}MB found, sir."]
    lines = [f"  FILES > {min_mb}MB", "  " + "─" * 50]
    for size, fp in found[:max_results]:
        lines.append(f"  {size/1024/1024:>8.1f} MB  {fp}")
    return lines

def find_duplicate_files(path: str = ".") -> List[str]:
    """Find duplicate files by hash (up to 1000 files)."""
    lines = ["  DUPLICATE FILE SCAN", "  " + "─" * 50]
    hashes: dict = defaultdict(list)
    count = 0
    try:
        for root, dirs, files in os.walk(Path(path).expanduser()):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                fp = Path(root) / f
                try:
                    h = hashlib.md5(fp.read_bytes()).hexdigest()
                    hashes[h].append(str(fp))
                    count += 1
                    if count >= 1000: break
                except: pass
            if count >= 1000: break
    except: pass
    dupes = {h: paths for h, paths in hashes.items() if len(paths) > 1}
    if not dupes:
        lines.append(f"  No duplicates found in {count} files scanned, sir.")
        return lines
    total_waste = 0
    for h, paths in list(dupes.items())[:15]:
        try:
            size = Path(paths[0]).stat().st_size
            waste = size * (len(paths) - 1)
            total_waste += waste
            lines.append(f"\n  [{h[:8]}...] {len(paths)} copies  ({size//1024}KB each)")
            for p in paths: lines.append(f"    {p}")
        except: pass
    lines.append(f"\n  Reclaimable: {total_waste//1024//1024}MB across {len(dupes)} duplicate groups")
    return lines

def empty_trash() -> str:
    if not confirm_dangerous("empty_trash", "Permanently delete all trash/recycle bin contents"):
        return "Cancelled, sir."
    try:
        if OS == "Windows":
            subprocess.run(
                ["powershell", "-Command", "Clear-RecycleBin -Force"],
                timeout=15, capture_output=True)
        elif OS == "Linux":
            trash = Path.home() / ".local/share/Trash"
            for sub in ["files", "info"]:
                d = trash / sub
                if d.exists():
                    for item in d.iterdir():
                        try:
                            if item.is_dir(): shutil.rmtree(item)
                            else: item.unlink()
                        except: pass
        elif OS == "Darwin":
            trash = Path.home() / ".Trash"
            for item in trash.iterdir():
                try:
                    if item.is_dir(): shutil.rmtree(item)
                    else: item.unlink()
                except: pass
        log_action("empty_trash", "", "OK")
        return "Trash emptied, sir."
    except Exception as e:
        return f"Trash empty failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  CLIPBOARD (enhanced)
# ══════════════════════════════════════════════════════════════════════════════

def get_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except: return ""

def set_clipboard(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        log_action("clipboard_write", text[:50], "OK")
        return f"Copied to clipboard: '{text[:60]}...'" if len(text) > 60 else f"Copied: '{text}'"
    except:
        return "pyperclip not available, sir."

# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK UTILITIES (extended)
# ══════════════════════════════════════════════════════════════════════════════

def get_network_interfaces() -> List[str]:
    lines = ["  NETWORK INTERFACES", "  " + "─" * 50]
    try:
        interfaces = psutil.net_if_addrs()
        stats      = psutil.net_if_stats()
        for iface, addrs in interfaces.items():
            stat = stats.get(iface)
            status = "UP" if (stat and stat.isup) else "DOWN"
            speed  = f"{stat.speed}Mbps" if (stat and stat.speed) else "?"
            lines.append(f"\n  {iface}  [{status}]  {speed}")
            for addr in addrs:
                if addr.family.name in ("AF_INET", "AF_INET6"):
                    lines.append(f"    {addr.family.name:<12} {addr.address}")
    except Exception as e:
        lines.append(f"  Error: {e}")
    return lines

def get_active_connections(filter_status: str = "ESTABLISHED") -> List[str]:
    lines = [f"  ACTIVE CONNECTIONS ({filter_status})", "  " + "─" * 60]
    try:
        conns = psutil.net_connections()
        filtered = [c for c in conns if filter_status.upper() in c.status.upper()] \
                   if filter_status else conns
        lines.append(f"  {'PID':<8} {'LOCAL':<25} {'REMOTE':<25} STATUS")
        lines.append("  " + "─" * 60)
        for c in filtered[:25]:
            local  = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-"
            remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-"
            lines.append(f"  {str(c.pid or ''):<8} {local:<25} {remote:<25} {c.status}")
    except Exception as e:
        lines.append(f"  Error: {e}")
    return lines

def traceroute(host: str, max_hops: int = 15) -> List[str]:
    lines = [f"  TRACEROUTE: {host}", "  " + "─" * 50]
    try:
        cmd = (f"tracert -h {max_hops} {host}" if OS == "Windows"
               else f"traceroute -m {max_hops} {host}")
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=30)
        for line in result.stdout.splitlines()[:max_hops + 5]:
            lines.append(f"  {line}")
    except subprocess.TimeoutExpired:
        lines.append("  Traceroute timed out.")
    except Exception as e:
        lines.append(f"  Traceroute failed: {e}")
    return lines

def dns_lookup(domain: str) -> List[str]:
    lines = [f"  DNS LOOKUP: {domain}", "  " + "─" * 40]
    try:
        import socket
        results = socket.getaddrinfo(domain, None)
        seen = set()
        for res in results:
            ip = res[4][0]
            if ip not in seen:
                seen.add(ip)
                lines.append(f"  {res[0].name:<12} {ip}")
        # Reverse lookup
        try:
            hostname = socket.gethostbyaddr(list(seen)[0])[0]
            lines.append(f"  Reverse    : {hostname}")
        except: pass
    except Exception as e:
        lines.append(f"  Lookup failed: {e}")
    return lines

def check_port_open(host: str, port: int, timeout: float = 2.0) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        status = "OPEN" if result == 0 else "CLOSED"
        return f"Port {port} on {host}: {status}"
    except Exception as e:
        return f"Check failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  POWER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def get_battery_info() -> List[str]:
    lines = ["  BATTERY STATUS", "  " + "─" * 35]
    if not psutil:
        return ["  psutil required, sir."]
    bat = psutil.sensors_battery()
    if not bat:
        lines.append("  No battery detected (desktop system).")
        return lines
    pct = bat.percent
    plugged = bat.power_plugged
    secs_left = bat.secsleft

    bar_filled = int(pct / 5)
    color_bar  = "█" * bar_filled + "░" * (20 - bar_filled)
    lines.append(f"  Charge     : [{color_bar}] {pct:.0f}%")
    lines.append(f"  Status     : {'⚡ Charging' if plugged else '🔋 On battery'}")
    if not plugged and secs_left > 0:
        h, m = divmod(secs_left // 60, 60)
        lines.append(f"  Time left  : {h}h {m}m")
    elif plugged and secs_left > 0:
        h, m = divmod(secs_left // 60, 60)
        lines.append(f"  Full in    : {h}h {m}m")
    # Health assessment
    if pct < 20 and not plugged:
        lines.append("  ⚠️  Warning: Low battery. Plug in soon.")
    elif pct > 95 and plugged:
        lines.append("  ℹ️  Consider unplugging to preserve battery health.")
    return lines

def set_power_plan(plan: str) -> str:
    """Set power plan: balanced / performance / saver."""
    plan = plan.lower()
    try:
        if OS == "Windows":
            plans = {
                "balanced":    "381b4222-f694-41f0-9685-ff5bb260df2e",
                "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
                "saver":       "a1841308-3541-4fab-bc81-f71556f20b4a",
            }
            guid = plans.get(plan)
            if not guid:
                return f"Unknown plan '{plan}'. Options: balanced / performance / saver"
            subprocess.run(f"powercfg /setactive {guid}", shell=True, timeout=5)
            log_action("set_power_plan", plan, "OK")
            return f"Power plan set to '{plan}', sir."
        elif OS == "Linux":
            if plan == "performance":
                subprocess.run("cpupower frequency-set -g performance", shell=True, timeout=5)
            elif plan == "saver":
                subprocess.run("cpupower frequency-set -g powersave", shell=True, timeout=5)
            else:
                subprocess.run("cpupower frequency-set -g schedutil", shell=True, timeout=5)
            return f"CPU governor set to {plan} mode, sir."
        return "Power plan control not supported on this OS, sir."
    except Exception as e:
        return f"Power plan change failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM INFO (extended)
# ══════════════════════════════════════════════════════════════════════════════

def get_installed_apps() -> List[str]:
    """List installed applications."""
    lines = ["  INSTALLED APPLICATIONS", "  " + "─" * 50]
    try:
        if OS == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject -Class Win32_Product | Select-Object Name,Version | Sort-Object Name"],
                capture_output=True, text=True, timeout=30)
            apps = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            lines += [f"  {a}" for a in apps[:40]]
        elif OS == "Linux":
            # Try dpkg first, then rpm
            try:
                result = subprocess.run(
                    ["dpkg", "--get-selections"],
                    capture_output=True, text=True, timeout=10)
                apps = [l.split()[0] for l in result.stdout.splitlines()
                        if "install" in l][:40]
            except:
                result = subprocess.run(
                    ["rpm", "-qa", "--queryformat", "%{NAME}\\n"],
                    capture_output=True, text=True, timeout=10)
                apps = result.stdout.splitlines()[:40]
            lines += [f"  {a}" for a in apps]
        elif OS == "Darwin":
            result = subprocess.run(
                ["ls", "/Applications"],
                capture_output=True, text=True, timeout=5)
            apps = [l for l in result.stdout.splitlines() if l.endswith(".app")]
            lines += [f"  {a.replace('.app', '')}" for a in apps[:40]]
        if len(lines) <= 2:
            lines.append("  Could not retrieve app list, sir.")
    except Exception as e:
        lines.append(f"  Error: {e}")
    return lines

def get_system_logs(n: int = 30) -> List[str]:
    """Fetch recent system error logs."""
    lines = ["  SYSTEM LOGS (recent errors)", "  " + "─" * 50]
    try:
        if OS == "Windows":
            cmd = (f"powershell -Command \"Get-EventLog -LogName System "
                   f"-EntryType Error -Newest {n} | "
                   f"Select-Object TimeGenerated,Source,Message | "
                   f"Format-List\"")
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                    text=True, timeout=15)
            lines += [f"  {l}" for l in result.stdout.splitlines()[:50]]
        elif OS == "Linux":
            result = subprocess.run(
                ["journalctl", "-p", "err", "-n", str(n), "--no-pager"],
                capture_output=True, text=True, timeout=10)
            lines += [f"  {l}" for l in result.stdout.splitlines()]
        elif OS == "Darwin":
            result = subprocess.run(
                ["log", "show", "--predicate", "messageType == 16",
                 "--last", "1h", "--style", "compact"],
                capture_output=True, text=True, timeout=10)
            lines += [f"  {l}" for l in result.stdout.splitlines()[:40]]
    except Exception as e:
        lines.append(f"  Log retrieval failed: {e}")
    return lines if len(lines) > 2 else lines + ["  No error logs found, sir."]

def get_startup_programs() -> List[str]:
    """List programs that run at startup."""
    lines = ["  STARTUP PROGRAMS", "  " + "─" * 50]
    try:
        if OS == "Windows":
            import winreg
            for hive, path in [
                (winreg.HKEY_CURRENT_USER,
                 r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ]:
                try:
                    key = winreg.OpenKey(hive, path)
                    i = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(key, i)
                            lines.append(f"  {name:<30} {val[:60]}")
                            i += 1
                        except OSError: break
                    winreg.CloseKey(key)
                except: pass
        elif OS == "Linux":
            autostart = Path.home() / ".config/autostart"
            if autostart.exists():
                for f in autostart.glob("*.desktop"):
                    try:
                        content = f.read_text()
                        name = re.search(r"^Name=(.+)", content, re.M)
                        exec_ = re.search(r"^Exec=(.+)", content, re.M)
                        if name:
                            lines.append(f"  {name.group(1):<30} {exec_.group(1)[:50] if exec_ else ''}")
                    except: pass
        elif OS == "Darwin":
            for path in [Path.home() / "Library/LaunchAgents",
                         Path("/Library/LaunchAgents")]:
                if path.exists():
                    for f in path.glob("*.plist"):
                        lines.append(f"  {f.stem}")
    except Exception as e:
        lines.append(f"  Error: {e}")
    return lines if len(lines) > 2 else lines + ["  No startup programs found, sir."]

def remove_startup_program(name: str) -> str:
    """Remove a program from startup by name."""
    if not confirm_dangerous("remove_startup", name):
        return "Cancelled, sir."
    try:
        if OS == "Windows":
            import winreg
            for hive, path in [
                (winreg.HKEY_CURRENT_USER,
                 r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ]:
                try:
                    key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, name)
                    winreg.CloseKey(key)
                    log_action("remove_startup", name, "OK")
                    return f"'{name}' removed from startup, sir."
                except FileNotFoundError: pass
            return f"'{name}' not found in startup registry, sir."
        elif OS == "Linux":
            target = Path.home() / f".config/autostart/{name}.desktop"
            if target.exists():
                target.unlink()
                log_action("remove_startup", name, "OK")
                return f"'{name}' removed from startup, sir."
            return f"'{name}' not found in autostart, sir."
    except Exception as e:
        return f"Removal failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  HOT KEY / KEYBOARD SHORTCUTS (Windows / Linux)
# ══════════════════════════════════════════════════════════════════════════════

def send_hotkey(*keys) -> str:
    """Send a keyboard shortcut. e.g. send_hotkey('ctrl', 'c')"""
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        combo = "+".join(keys)
        log_action("hotkey", combo, "OK")
        return f"Sent hotkey: {combo}, sir."
    except ImportError:
        return "pyautogui not installed. pip install pyautogui"
    except Exception as e:
        return f"Hotkey failed: {e}"

def type_text(text: str) -> str:
    """Type text at current cursor position."""
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        log_action("type_text", text[:40], "OK")
        return f"Typed: '{text[:40]}', sir."
    except ImportError:
        return "pyautogui not installed. pip install pyautogui"
    except Exception as e:
        return f"Type failed: {e}"

def move_mouse(x: int, y: int) -> str:
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.3)
        return f"Mouse moved to ({x}, {y}), sir."
    except Exception as e:
        return f"Mouse move failed: {e}"

def click_mouse(x: int = None, y: int = None, button: str = "left") -> str:
    try:
        import pyautogui
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
        log_action("mouse_click", f"{button} at ({x},{y})", "OK")
        return f"{button.capitalize()} click at ({x},{y}), sir."
    except Exception as e:
        return f"Click failed: {e}"

def scroll_mouse(clicks: int = 3, direction: str = "up") -> str:
    try:
        import pyautogui
        amount = clicks if direction == "up" else -clicks
        pyautogui.scroll(amount)
        return f"Scrolled {direction} {clicks} clicks, sir."
    except Exception as e:
        return f"Scroll failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  FILE WATCHER  — monitor a file/folder for changes
# ══════════════════════════════════════════════════════════════════════════════

_watchers: dict = {}  # path -> thread

def watch_file(path: str, callback=None, duration_secs: int = 60) -> str:
    """Watch a file for changes and log/notify."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"Path not found: {path}"
    if str(p) in _watchers:
        return f"Already watching {p.name}, sir."

    def _watch():
        last_mtime = p.stat().st_mtime if p.is_file() else None
        last_count = len(list(p.iterdir())) if p.is_dir() else None
        deadline = time.time() + duration_secs
        while time.time() < deadline:
            try:
                if p.is_file():
                    mtime = p.stat().st_mtime
                    if mtime != last_mtime:
                        msg = f"File changed: {p.name}"
                        log_action("file_watch", str(p), "CHANGED")
                        print(f"\n  👁 WATCH: {msg}")
                        if callback: callback(msg)
                        last_mtime = mtime
                elif p.is_dir():
                    count = len(list(p.iterdir()))
                    if count != last_count:
                        diff = count - (last_count or 0)
                        msg = f"Directory changed: {p.name} ({'+' if diff>0 else ''}{diff} items)"
                        log_action("dir_watch", str(p), "CHANGED")
                        print(f"\n  👁 WATCH: {msg}")
                        if callback: callback(msg)
                        last_count = count
            except: pass
            time.sleep(1)
        del _watchers[str(p)]

    t = threading.Thread(target=_watch, daemon=True)
    t.start()
    _watchers[str(p)] = t
    return f"Watching '{p.name}' for {duration_secs}s, sir."

def stop_watch(path: str) -> str:
    p = str(Path(path).expanduser())
    if p in _watchers:
        del _watchers[p]
        return f"Stopped watching '{Path(path).name}', sir."
    return f"Not watching '{path}', sir."

def list_watchers() -> List[str]:
    if not _watchers:
        return ["  No active watchers, sir."]
    return [f"  👁 {p}" for p in _watchers]

# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULED COMMANDS EXTENDED  (cron-style, persistent)
# ══════════════════════════════════════════════════════════════════════════════

SCHEDULES_FILE = Path("jarvis_schedules.json")

def _load_schedules() -> List[dict]:
    try: return json.loads(SCHEDULES_FILE.read_text())
    except: return []

def _save_schedules(data: List[dict]):
    SCHEDULES_FILE.write_text(json.dumps(data, indent=2))

def add_cron_task(label: str, cmd: str, cron_expr: str) -> str:
    """
    Add a simple cron-like task.
    cron_expr: "every N minutes" | "daily HH:MM" | "hourly"
    """
    schedules = _load_schedules()
    entry = {
        "id":      len(schedules) + 1,
        "label":   label,
        "cmd":     cmd,
        "cron":    cron_expr,
        "created": datetime.now().isoformat(),
        "last_run": None,
    }
    schedules.append(entry)
    _save_schedules(schedules)
    log_action("add_cron", f"{label}: {cron_expr}", "OK")
    return f"Cron task '{label}' saved: {cron_expr}, sir."

def list_cron_tasks() -> List[str]:
    schedules = _load_schedules()
    if not schedules:
        return ["  No persistent tasks, sir."]
    lines = ["  PERSISTENT SCHEDULES", "  " + "─" * 50]
    for s in schedules:
        last = s.get("last_run", "never") or "never"
        lines.append(f"  {s['id']:>3}. [{s['cron']:<25}] {s['label']:<25} last: {last[:16]}")
    return lines

def remove_cron_task(task_id: int) -> str:
    schedules = _load_schedules()
    before = len(schedules)
    schedules = [s for s in schedules if s["id"] != task_id]
    if len(schedules) == before:
        return f"Task {task_id} not found, sir."
    _save_schedules(schedules)
    log_action("remove_cron", str(task_id), "OK")
    return f"Task {task_id} removed, sir."

# ══════════════════════════════════════════════════════════════════════════════
#  APP SWITCHER  — cycle through / list open windows
# ══════════════════════════════════════════════════════════════════════════════

def list_open_windows() -> List[str]:
    """List all open application windows."""
    lines = ["  OPEN WINDOWS", "  " + "─" * 50]
    try:
        if OS == "Windows":
            script = ("Get-Process | Where-Object {$_.MainWindowTitle} | "
                      "Select-Object ProcessName, MainWindowTitle | Format-Table -AutoSize")
            result = subprocess.run(["powershell", "-Command", script],
                                    capture_output=True, text=True, timeout=10)
            lines += [f"  {l}" for l in result.stdout.splitlines() if l.strip()]
        elif OS == "Linux":
            try:
                result = subprocess.run(["wmctrl", "-l"], capture_output=True,
                                        text=True, timeout=5)
                lines += [f"  {l}" for l in result.stdout.splitlines()]
            except FileNotFoundError:
                # Fallback: xdotool
                result = subprocess.run(["xdotool", "search", "--onlyvisible",
                                         "--name", ""],
                                        capture_output=True, text=True, timeout=5)
                lines += [f"  Window ID: {l}" for l in result.stdout.splitlines()[:20]]
        elif OS == "Darwin":
            script = ('tell application "System Events" to get name of every application process '
                      'whose background only is false')
            result = subprocess.run(["osascript", "-e", script],
                                    capture_output=True, text=True, timeout=5)
            apps = result.stdout.strip().split(", ")
            lines += [f"  • {a}" for a in apps]
    except Exception as e:
        lines.append(f"  Error: {e}")
    return lines if len(lines) > 2 else lines + ["  No windows found, sir."]

# ══════════════════════════════════════════════════════════════════════════════
#  QUICK NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def send_notification(title: str, message: str) -> str:
    """Send a desktop notification."""
    try:
        if OS == "Windows":
            # Use Windows Toast via PowerShell
            ps_cmd = (
                f"[Windows.UI.Notifications.ToastNotificationManager, "
                f"Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
                f"$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);"
                f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{title}')) | Out-Null;"
                f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{message}')) | Out-Null;"
                f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show($toast);"
            )
            subprocess.Popen(["powershell", "-Command", ps_cmd])
        elif OS == "Linux":
            subprocess.Popen(["notify-send", title, message])
        elif OS == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.Popen(["osascript", "-e", script])
        log_action("notification", f"{title}: {message[:40]}", "OK")
        return f"Notification sent: '{title}', sir."
    except Exception as e:
        return f"Notification failed: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  COMPLETE SYSTEM REPORT
# ══════════════════════════════════════════════════════════════════════════════

def full_system_report() -> List[str]:
    """Comprehensive one-shot system report."""
    lines = []
    w = 60
    lines.append("═" * w)
    lines.append("  J.A.R.V.I.S  FULL SYSTEM REPORT".center(w))
    lines.append(f"  {datetime.now().strftime('%A, %B %d, %Y  %I:%M:%S %p')}".center(w))
    lines.append("═" * w)

    # OS
    lines += ["", "  ── SYSTEM ──────────────────────────────────",
              f"  OS        : {platform.system()} {platform.release()}",
              f"  Host      : {platform.node()}",
              f"  Arch      : {platform.machine()} / {platform.architecture()[0]}",
              f"  Python    : {platform.python_version()}"]

    # Hardware
    if psutil:
        cpu    = psutil.cpu_percent(interval=0.5)
        ram    = psutil.virtual_memory()
        disk   = psutil.disk_usage("/")
        boot_t = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_t
        h, rem = divmod(int(uptime.total_seconds()), 3600)
        m, s   = divmod(rem, 60)
        lines += ["", "  ── HARDWARE ─────────────────────────────────",
                  f"  CPU cores : {psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical",
                  f"  CPU usage : {cpu:.1f}%",
                  f"  RAM total : {ram.total // 1024**3}GB",
                  f"  RAM used  : {ram.percent:.1f}% ({ram.used//1024**2}MB)",
                  f"  Disk      : {disk.percent:.1f}% used  ({disk.free//1024**3}GB free)",
                  f"  System up : {h}h {m}m {s}s (boot {boot_t.strftime('%b %d %H:%M')})"]
        bat = psutil.sensors_battery()
        if bat:
            lines.append(f"  Battery   : {bat.percent:.0f}% ({'charging' if bat.power_plugged else 'on battery'})")

    # Network
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        pub_ip   = requests.get("https://api.ipify.org", timeout=4).text.strip()
        lines += ["", "  ── NETWORK ──────────────────────────────────",
                  f"  Hostname  : {hostname}",
                  f"  Local IP  : {local_ip}",
                  f"  Public IP : {pub_ip}"]
    except: pass

    # Top processes
    if psutil:
        procs = sorted(psutil.process_iter(["name", "cpu_percent", "memory_percent"]),
                       key=lambda p: p.info.get("cpu_percent") or 0, reverse=True)[:5]
        lines += ["", "  ── TOP PROCESSES ────────────────────────────"]
        for p in procs:
            lines.append(f"  {p.info['name']:<28} CPU:{p.info['cpu_percent']:>5.1f}%  "
                         f"MEM:{p.info.get('memory_percent',0):>4.1f}%")

    # Personality
    lines += ["", "  ── PERSONALITY ──────────────────────────────",
              f"  Mode      : {PERSONALITY['mode'].upper()}",
              f"  Humor     : {PERSONALITY['humor_level']}/10",
              f"  Roast     : {PERSONALITY['roast_level']}/10"]

    lines += ["", "═" * w]
    return lines
