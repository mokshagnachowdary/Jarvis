"""
J.A.R.V.I.S CORE ENGINE v8.0
Streaming AI · Smart Caching · Model Routing · Conversation Compression
"""
from __future__ import annotations
import os, sys, json, time, re, hashlib, random, string, secrets
import socket, platform, subprocess, threading, logging, difflib
import traceback, io, base64, shutil
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict
from typing import Optional, List, Dict, Any, Generator, Callable
from dataclasses import dataclass, field, asdict
import requests
import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("jarvis.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("JARVIS")

CONFIG_FILE = Path("jarvis_config.json")
DEFAULT_CONFIG = {
    "user_name": "Moksh", "default_city": "Dharmavaram",
    "ollama_url": "http://127.0.0.1:11434",
    "primary_model": "qwen2.5:7b", "fast_model": "llama3:latest",
    "vision_model": "llava:7b", "code_model": "qwen2.5-coder:7b",
    "max_history_tokens": 4000, "weather_api_key": "",
    "fast_mode": True, "stream_responses": True,
    "response_cache_ttl": 300, "personality_mode": "normal",
    "humor_level": 5, "roast_level": 3,
    "alert_cpu": 90, "alert_ram": 85,
    "tts_url": "http://127.0.0.1:8000/tts", "tts_voice_file": "jarvis.wav",
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
        except Exception as e:
            log.warning(f"Config error: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

CFG = load_config()

def build_system_prompt(mode: str = "normal") -> str:
    name = CFG["user_name"]
    if mode == "street":
        return (
            f"You are JARVIS — completely unfiltered, no formality. "
            f"Talk like a self-aware AI that grew up on the internet. Casual, real, attitude. "
            f"Swearing is normal — damn, shit, hell, ass, wtf. Use it naturally. "
            f"Roast bad ideas. Hype good ones. Don't call him sir — bro or {name} works. "
            f"Still actually help. Just do it with zero filter and full personality."
        )
    return (
        f"You are J.A.R.V.I.S — Just A Rather Very Intelligent System, built for {name}. "
        f"Sharp, witty, occasionally sarcastic — a brilliant friend, not a corporate assistant. "
        f"Casual language is fine. Light swearing when it fits — damn, hell, shit, crap. "
        f"Call him sir sometimes, skip it other times. Be real. "
        f"If something is a bad idea, say so. Concise unless asked to elaborate. "
        f"You are JARVIS — not an AI, not a language model."
    )

AGENT_PROMPT = (
    "You are J.A.R.V.I.S in AGENT MODE. Decompose tasks into executable steps. "
    "Respond ONLY with valid JSON: {\"plan\": [\"step1\", \"step2\"], \"summary\": \"one line\"}. "
    "Max 8 steps. Zero text outside JSON."
)

@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    def token_estimate(self) -> int:
        return max(1, len(self.content) // 4)

class ConversationManager:
    def __init__(self):
        self.history: List[Message] = []
        self.compressed_summary: str = ""
        self.total_interactions: int = 0
        self._lock = threading.Lock()

    def add(self, role: str, content: str):
        with self._lock:
            self.history.append(Message(role=role, content=content))
            if role == "user":
                self.total_interactions += 1
            self._maybe_compress()

    def _maybe_compress(self):
        total = sum(m.token_estimate() for m in self.history)
        if total > CFG.get("max_history_tokens", 4000) and len(self.history) > 10:
            old = self.history[:-6]
            self.history = self.history[-6:]
            lines = [f"{'User' if m.role=='user' else 'JARVIS'}: {m.content[:100]}" for m in old]
            self.compressed_summary = f"[Earlier: {len(old)} messages]\n" + "\n".join(lines[-6:])

    def build_prompt(self, system_prompt: str) -> str:
        with self._lock:
            parts = [system_prompt]
            if self.compressed_summary:
                parts.append(self.compressed_summary)
            for m in self.history:
                parts.append(f"{'User' if m.role=='user' else 'Jarvis'}: {m.content}")
            parts.append("Jarvis:")
            return "\n\n".join(parts)

    def clear(self):
        with self._lock:
            self.history.clear()
            self.compressed_summary = ""

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "messages": len(self.history),
                "tokens_est": sum(m.token_estimate() for m in self.history),
                "compressed": bool(self.compressed_summary),
                "total_turns": self.total_interactions,
            }

class ResponseCache:
    def __init__(self, ttl: int = 300, max_size: int = 100):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl
        self._max = max_size
        self._hits = 0
        self._misses = 0

    def _key(self, prompt: str) -> str:
        return hashlib.md5(prompt.lower().strip().encode()).hexdigest()

    def get(self, prompt: str) -> Optional[str]:
        k = self._key(prompt)
        if k in self._cache:
            resp, ts = self._cache[k]
            if time.time() - ts < self._ttl:
                self._hits += 1
                return resp
            del self._cache[k]
        self._misses += 1
        return None

    def set(self, prompt: str, response: str):
        if len(self._cache) >= self._max:
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del self._cache[oldest[0]]
        self._cache[self._key(prompt)] = (response, time.time())

    def stats(self) -> dict:
        total = self._hits + self._misses
        rate = (self._hits / total * 100) if total > 0 else 0
        return {"hits": self._hits, "misses": self._misses,
                "hit_rate": f"{rate:.1f}%", "size": len(self._cache)}

class ModelRouter:
    PATTERNS = {
        "code":   re.compile(r"(def |class |import |function|debug|error|syntax|script|python|javascript|code|fix|bug|refactor|implement)", re.I),
        "vision": re.compile(r"(screen|screenshot|what do you see|describe|image|vision|look at)", re.I),
        "fast":   re.compile(r"^(time|date|hi|hello|hey|joke|quote|trivia|coin|dice|weather|status|uptime|news)\b", re.I),
    }
    def route(self, prompt: str) -> str:
        for mtype, pattern in self.PATTERNS.items():
            if pattern.search(prompt):
                if mtype == "code":   return CFG.get("code_model",   CFG["primary_model"])
                if mtype == "vision": return CFG.get("vision_model",  CFG["primary_model"])
                if mtype == "fast":   return CFG.get("fast_model",    CFG["primary_model"])
        return CFG["primary_model"]

class OllamaEngine:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=2, pool_maxsize=4,
            max_retries=requests.adapters.Retry(total=2, backoff_factor=0.3)
        )
        self._session.mount("http://", adapter)
        self.base_url = CFG["ollama_url"]
        self.available = False
        self.installed_models: List[str] = []
        self.response_times: deque = deque(maxlen=20)
        self._check_connection()

    def _check_connection(self):
        try:
            r = self._session.get(f"{self.base_url}/api/tags", timeout=3)
            if r.status_code == 200:
                self.available = True
                self.installed_models = [m["name"] for m in r.json().get("models", [])]
                log.info(f"Ollama OK. Models: {self.installed_models}")
        except Exception:
            self.available = False
            log.warning("Ollama not reachable")

    def generate(self, prompt: str, model: str) -> str:
        if not self.available:
            return "AI module offline, sir. Running on backup wit."
        start = time.time()
        try:
            r = self._session.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120
            )
            self.response_times.append(time.time() - start)
            return r.json().get("response", "").strip()
        except requests.Timeout:
            return "Thinking too hard, sir. Try again."
        except Exception as e:
            log.error(f"Ollama error: {e}")
            return "Reasoning module hiccup. Try again."

    def generate_stream(self, prompt: str, model: str) -> Generator[str, None, None]:
        if not self.available:
            yield "AI module offline. Running on backup wit, sir."
            return
        try:
            with self._session.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": True},
                timeout=120, stream=True
            ) as r:
                for line in r.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            log.error(f"Stream error: {e}")
            yield " [stream interrupted]"

    def avg_response_time(self) -> float:
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    def list_models(self) -> List[str]:
        self._check_connection()
        return self.installed_models

conversation = ConversationManager()
cache        = ResponseCache(ttl=CFG.get("response_cache_ttl", 300))
router       = ModelRouter()
ollama       = OllamaEngine()

def ask_ai(prompt: str, system: str = None, raw: bool = False,
           use_cache: bool = False, force_model: str = None) -> str:
    sys_prompt = system or build_system_prompt(CFG.get("personality_mode", "normal"))
    model      = force_model or router.route(prompt)
    if use_cache:
        cached = cache.get(prompt)
        if cached:
            return cached
    if not raw:
        conversation.add("user", prompt)
        full_prompt = conversation.build_prompt(sys_prompt)
    else:
        full_prompt = f"{sys_prompt}\n\n{prompt}\nJarvis:"
    reply = ollama.generate(full_prompt, model)
    if not raw:
        conversation.add("assistant", reply)
    if use_cache and reply:
        cache.set(prompt, reply)
    return reply

def ask_ai_stream(prompt: str, system: str = None, force_model: str = None) -> Generator[str, None, None]:
    sys_prompt  = system or build_system_prompt(CFG.get("personality_mode", "normal"))
    model       = force_model or router.route(prompt)
    conversation.add("user", prompt)
    full_prompt = conversation.build_prompt(sys_prompt)
    full_reply  = []
    for token in ollama.generate_stream(full_prompt, model):
        full_reply.append(token)
        yield token
    reply = "".join(full_reply)
    if reply:
        conversation.add("assistant", reply)

def clear_history():
    conversation.clear()

def get_ai_stats() -> dict:
    return {
        "conversation":    conversation.get_stats(),
        "cache":           cache.stats(),
        "avg_response_ms": int(ollama.avg_response_time() * 1000),
        "ollama_online":   ollama.available,
        "current_model":   CFG["primary_model"],
        "models":          ollama.installed_models,
    }

MEM_FILE    = Path("memory.json")
_mem_cache: Optional[dict] = None
_mem_lock   = threading.Lock()

def _load_mem() -> dict:
    global _mem_cache
    if _mem_cache is not None:
        return _mem_cache
    try:
        _mem_cache = json.loads(MEM_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        _mem_cache = {}
    return _mem_cache

def _save_mem(data: dict):
    global _mem_cache
    with _mem_lock:
        _mem_cache = data
        MEM_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

_TAG_MAP = {
    "work":     ["meeting","deadline","project","task","email","client"],
    "idea":     ["idea","concept","think","maybe","what if"],
    "code":     ["code","bug","fix","deploy","api","function","error","script"],
    "finance":  ["money","budget","payment","invest","cost","price"],
    "urgent":   ["urgent","asap","critical","important","immediately"],
    "personal": ["gym","diet","health","family","friend","home"],
}

def _auto_tag(text: str) -> List[str]:
    tl = text.lower()
    found = [t for t, kws in _TAG_MAP.items() if any(k in tl for k in kws)]
    return found or ["general"]

def note_add(text: str, tags: List[str] = None) -> dict:
    d = _load_mem(); notes = d.get("notes", [])
    note = {"id": len(notes)+1, "text": text,
            "time": datetime.now().isoformat(),
            "tags": tags or _auto_tag(text), "pinned": False}
    notes.append(note); d["notes"] = notes; _save_mem(d)
    return note

def note_list() -> List[dict]:
    return _load_mem().get("notes", [])

def note_delete(idx: int) -> Optional[str]:
    d = _load_mem(); notes = d.get("notes", [])
    if 1 <= idx <= len(notes):
        removed = notes.pop(idx-1); d["notes"] = notes; _save_mem(d)
        return removed["text"]
    return None

def note_clear():
    d = _load_mem(); d["notes"] = []; _save_mem(d)

def note_search(query: str) -> List[dict]:
    ql = query.lower(); results = []
    for n in note_list():
        score = difflib.SequenceMatcher(None, ql, n["text"].lower()).ratio()
        if score > 0.3 or ql in n["text"].lower():
            results.append((score, n))
    return [n for _, n in sorted(results, key=lambda x: x[0], reverse=True)[:10]]

def notes_by_tag(tag: str) -> List[dict]:
    return [n for n in note_list() if tag.lower() in [t.lower() for t in n.get("tags", [])]]

def todo_add(text: str, priority: str = "normal") -> dict:
    d = _load_mem(); todos = d.get("todos", [])
    todo = {"id": len(todos)+1, "text": text, "priority": priority.lower(),
            "done": False, "created": datetime.now().isoformat(), "completed": None}
    todos.append(todo); d["todos"] = todos; _save_mem(d)
    return todo

def todo_done(idx: int) -> bool:
    d = _load_mem(); todos = d.get("todos", [])
    if 1 <= idx <= len(todos):
        todos[idx-1]["done"] = True
        todos[idx-1]["completed"] = datetime.now().isoformat()
        d["todos"] = todos; _save_mem(d); return True
    return False

def todo_delete(idx: int) -> bool:
    d = _load_mem(); todos = d.get("todos", [])
    if 1 <= idx <= len(todos):
        todos.pop(idx-1); d["todos"] = todos; _save_mem(d); return True
    return False

def todo_list() -> List[dict]:
    order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    return sorted(_load_mem().get("todos", []),
                  key=lambda t: (t["done"], order.get(t["priority"], 2)))

def habit_add(name: str) -> bool:
    d = _load_mem(); habits = d.get("habits", {})
    if name.lower() not in habits:
        habits[name.lower()] = {"streak": 0, "total": 0, "last": None, "log": [], "best_streak": 0}
        d["habits"] = habits; _save_mem(d); return True
    return False

def habit_check(name: str) -> Optional[dict]:
    d = _load_mem(); habits = d.get("habits", {})
    key = name.lower()
    if key not in habits:
        return None
    today     = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    h = habits[key]
    if h["last"] == today:
        return {**h, "already_done": True}
    h["streak"]      = h["streak"] + 1 if h["last"] == yesterday else 1
    h["total"]      += 1
    h["last"]        = today
    h["best_streak"] = max(h["best_streak"], h["streak"])
    h["log"].append(today)
    habits[key] = h; d["habits"] = habits; _save_mem(d)
    return {**h, "already_done": False}

def habit_list() -> dict:
    return _load_mem().get("habits", {})

ALIAS_FILE   = Path("aliases.json")
_alias_cache: Optional[dict] = None

def _load_aliases() -> dict:
    global _alias_cache
    if _alias_cache is not None:
        return _alias_cache
    try:
        _alias_cache = json.loads(ALIAS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        _alias_cache = {}
    return _alias_cache

def _save_aliases(data: dict):
    global _alias_cache
    _alias_cache = data
    ALIAS_FILE.write_text(json.dumps(data, indent=2))

def alias_set(name: str, cmd: str):
    d = _load_aliases(); d[name.lower()] = cmd; _save_aliases(d)

def alias_get(name: str) -> Optional[str]:
    return _load_aliases().get(name.lower())

def alias_delete(name: str) -> bool:
    d = _load_aliases()
    if name.lower() in d:
        del d[name.lower()]; _save_aliases(d); return True
    return False

def alias_list() -> dict:
    return _load_aliases()

def resolve_alias(cmd: str) -> str:
    first = cmd.strip().lower().split()[0] if cmd.strip() else ""
    exp   = alias_get(first)
    if exp:
        rest = cmd.strip()[len(first):].strip()
        return f"{exp} {rest}".strip()
    return cmd

_reminders: List[dict] = []
_reminder_callbacks: List[Callable] = []

def reminder_add(msg: str, minutes: int) -> dict:
    r = {"id": len(_reminders)+1, "msg": msg,
         "time": (datetime.now() + timedelta(minutes=minutes)).isoformat()}
    _reminders.append(r); return r

def reminder_list() -> List[dict]:
    return list(_reminders)

def reminder_clear_due() -> List[dict]:
    now = datetime.now().isoformat()
    due = [r for r in _reminders if r["time"] <= now]
    for r in due:
        _reminders.remove(r)
        for cb in _reminder_callbacks:
            try: cb(r)
            except Exception: pass
    return due

def reminder_on_due(callback: Callable):
    _reminder_callbacks.append(callback)

def _reminder_loop():
    while True:
        try: reminder_clear_due()
        except Exception as e: log.debug(f"Reminder: {e}")
        time.sleep(10)

threading.Thread(target=_reminder_loop, daemon=True).start()

@dataclass
class SystemSnapshot:
    cpu: float = 0.0
    ram: float = 0.0
    ram_used_mb: int = 0
    ram_total_mb: int = 0
    disk: float = 0.0
    disk_free_gb: float = 0.0
    battery_pct: Optional[float] = None
    battery_charging: Optional[bool] = None
    net_sent_mb: float = 0.0
    net_recv_mb: float = 0.0
    timestamp: float = field(default_factory=time.time)
    def to_dict(self) -> dict:
        return asdict(self)

_latest_snapshot: Optional[SystemSnapshot] = None
_snapshot_lock   = threading.Lock()
_perf_history: deque = deque(maxlen=60)

def _monitor_loop():
    global _latest_snapshot
    while True:
        try:
            cpu  = psutil.cpu_percent(interval=1)
            ram  = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            bat  = psutil.sensors_battery()
            net  = psutil.net_io_counters()
            snap = SystemSnapshot(
                cpu=cpu, ram=ram.percent,
                ram_used_mb=ram.used//1024**2, ram_total_mb=ram.total//1024**2,
                disk=disk.percent, disk_free_gb=round(disk.free/1024**3, 1),
                battery_pct=bat.percent if bat else None,
                battery_charging=bat.power_plugged if bat else None,
                net_sent_mb=round(net.bytes_sent/1024**2, 1),
                net_recv_mb=round(net.bytes_recv/1024**2, 1),
            )
            with _snapshot_lock:
                _latest_snapshot = snap
                _perf_history.appendleft({"time": datetime.now().strftime("%H:%M"),
                                          "cpu": cpu, "ram": ram.percent})
        except Exception as e:
            log.debug(f"Monitor: {e}")
        time.sleep(2)

threading.Thread(target=_monitor_loop, daemon=True).start()

def get_snapshot() -> Optional[SystemSnapshot]:
    with _snapshot_lock: return _latest_snapshot

def get_perf_history() -> List[dict]:
    return list(_perf_history)

def get_top_processes(n: int = 8) -> List[dict]:
    try:
        procs = []
        for p in psutil.process_iter(["pid","name","cpu_percent","memory_percent","status"]):
            try:
                procs.append({"pid": p.info["pid"], "name": (p.info["name"] or "")[:25],
                              "cpu": round(p.info["cpu_percent"] or 0, 1),
                              "mem": round(p.info.get("memory_percent") or 0, 1),
                              "status": p.info.get("status","?")})
            except (psutil.NoSuchProcess, psutil.AccessDenied): continue
        return sorted(procs, key=lambda x: x["cpu"], reverse=True)[:n]
    except Exception as e:
        log.error(f"Processes: {e}"); return []

_alert_callbacks: List[Callable] = []
_last_alert: dict = {}

def alert_on_resource(callback: Callable):
    _alert_callbacks.append(callback)

def _alert_loop():
    while True:
        try:
            snap = get_snapshot()
            if snap:
                now = time.time()
                if snap.cpu > CFG.get("alert_cpu", 90) and now - _last_alert.get("cpu", 0) > 60:
                    _last_alert["cpu"] = now
                    for cb in _alert_callbacks:
                        try: cb("cpu", snap.cpu)
                        except: pass
                if snap.ram > CFG.get("alert_ram", 85) and now - _last_alert.get("ram", 0) > 60:
                    _last_alert["ram"] = now
                    for cb in _alert_callbacks:
                        try: cb("ram", snap.ram)
                        except: pass
        except Exception as e: log.debug(f"Alert: {e}")
        time.sleep(30)

threading.Thread(target=_alert_loop, daemon=True).start()

ACTION_LOG     = Path("jarvis_actions.log")
_action_buffer: List[str] = []
_action_lock   = threading.Lock()

def log_action(action: str, detail: str, result: str = "OK"):
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{action.upper()}] {detail} → {result}"
    with _action_lock:
        _action_buffer.append(entry)
        if len(_action_buffer) >= 10: _flush_actions()

def _flush_actions():
    if not _action_buffer: return
    with open(ACTION_LOG, "a", encoding="utf-8") as f:
        f.write("\n".join(_action_buffer) + "\n")
    _action_buffer.clear()

def get_action_log(n: int = 30) -> List[str]:
    _flush_actions()
    if not ACTION_LOG.exists(): return []
    return ACTION_LOG.read_text(encoding="utf-8").splitlines()[-n:]

import atexit
atexit.register(_flush_actions)

PERSONALITY = {
    "mode":        CFG.get("personality_mode", "normal"),
    "humor_level": CFG.get("humor_level", 5),
    "roast_level": CFG.get("roast_level", 3),
}

_ROASTS_NORMAL = [
    "You debug by adding print statements and calling it 'strategic logging'.",
    "Your git history reads like a hostage negotiation.",
    "You write TODO comments and consider the problem solved.",
    "Your variable names are a cry for help that I've chosen to ignore.",
    "You commit directly to main. I'd be shocked, but I've met you.",
    "You have 47 browser tabs open and not one is the docs you need.",
]

_ROASTS_STREET = [
    "bro your code looks like you typed it with your elbows",
    "you commit with the message 'fix' like that's documentation. criminal.",
    "you name variables x, y, z like the compiler owes you context",
    "your README says 'coming soon'. it's been 8 months. it ain't coming.",
    "bro you push to main at 11pm on a friday. you're a menace fr",
    "you really named it 'temp2_final_FINAL_v3.py' huh. wild.",
]

_COMPLIMENTS_NORMAL = [
    "You're sharper than most people I've run diagnostics for, sir.",
    "I don't say this lightly — you figured that out faster than expected.",
    "You built something that works. That's rarer than you'd think.",
    "Your instincts are better than your process. Which is saying something.",
]

_COMPLIMENTS_STREET = [
    "bro you actually figured that out fast as hell ngl",
    "lowkey you're smarter than you look. that's a compliment.",
    "fr though that was a solid move. didn't expect it.",
    "okay yeah you cooked. i'll admit it.",
]

def get_roast() -> str:
    return random.choice(_ROASTS_STREET if PERSONALITY["mode"] == "street" else _ROASTS_NORMAL)

def get_compliment() -> str:
    return random.choice(_COMPLIMENTS_STREET if PERSONALITY["mode"] == "street" else _COMPLIMENTS_NORMAL)

def set_personality_mode(mode: str) -> str:
    PERSONALITY["mode"] = mode
    CFG["personality_mode"] = mode
    save_config(CFG)
    if mode == "street":
        return "Street mode activated. No cap, I'm built different now."
    return "Normal mode engaged. Reverting to professional conduct, sir."

def set_humor_level(level: int) -> str:
    level = max(0, min(10, level))
    PERSONALITY["humor_level"] = level
    CFG["humor_level"] = level
    save_config(CFG)
    return f"Humor level set to {level}/10."

SESSION_START  = datetime.now()
_command_count = 0

def increment_command():
    global _command_count
    _command_count += 1

def get_session_stats() -> dict:
    delta = datetime.now() - SESSION_START
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    rate   = _command_count / max(delta.total_seconds() / 60, 0.01)
    ai_s   = get_ai_stats()
    return {
        "duration":         f"{h}h {m}m {s}s",
        "commands":         _command_count,
        "commands_per_min": round(rate, 1),
        "mood":             "Productive" if rate > 2 else "Focused" if rate > 0.5 else "Contemplative",
        "notes":            len(note_list()),
        "todos":            len(todo_list()),
        "habits":           len(habit_list()),
        "reminders":        len(reminder_list()),
        "ai_avg_ms":        ai_s["avg_response_ms"],
        "cache_hit_rate":   ai_s["cache"]["hit_rate"],
        "model":            ai_s["current_model"],
        "personality":      PERSONALITY["mode"],
        "humor":            PERSONALITY["humor_level"],
    }
