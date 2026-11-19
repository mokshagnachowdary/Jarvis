#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   J.A.R.V.I.S  v7.0  —  Just A Rather Very Intelligent System             ║
║              Built exclusively for Moksh, sir                               ║
║   SYSTEM CONTROL · CONTEXT ENGINE · WORKSPACES · GIT · PLUGINS · SAFETY   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════
import os, sys, time, json, math, random, hashlib, shutil
import socket, platform, subprocess, threading, webbrowser, re
import requests, base64, string, secrets, io, traceback, difflib
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict
HAS_TTS = True

# ── Optional imports ──────────────────────────────────────────────────────────
try:    import psutil
except: psutil = None

try:    import speech_recognition as sr
except: sr = None

try:    import pyautogui; pyautogui.FAILSAFE = False
except: pyautogui = None

try:    import pyperclip;  HAS_CLIP = True
except: HAS_CLIP = False

try:    from PIL import Image;  HAS_PIL = True
except: HAS_PIL = False

# ── System Control Module ─────────────────────────────────────────────────────
try:
    import jarvis_system as SYS
    HAS_SYS = True
except ImportError:
    HAS_SYS = False
    print("  [WARN] jarvis_system.py not found — system control features disabled.")

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
USER_NAME       = "Moksh"
OS              = platform.system()
MEM_FILE        = Path("memory.json")
LOG_FILE        = Path("jarvis_log.txt")
PROTOCOL_FILE   = Path("protocols.json")
ALIAS_FILE      = Path("aliases.json")
AGENT_LOG_FILE  = Path("agent_log.json")
OLLAMA_URL      = "http://127.0.0.1:11434/api/generate"
AI_MODEL        = "llama3"
MAX_HISTORY     = 30
WEATHER_API_KEY = ""
DEFAULT_CITY    = "Dharmavaram"
FAST_MODE       = True
STARK_MODE      = False
BOOT_TIME       = datetime.now()

# Runtime state
command_count       = 0
session_start       = datetime.now()
clipboard_history   = deque(maxlen=10)
mission_active      = False
mission_name        = ""
mission_log         = []
scheduled_tasks     = []
resource_alert_on   = True
ALERT_CPU           = 90
ALERT_RAM           = 85
agent_mode_active   = False
pomodoro_session    = {"active": False, "work_mins": 25, "break_mins": 5, "cycles": 0}
code_history        = deque(maxlen=20)
hotword_listening   = False
focus_mode_active   = False

# ══════════════════════════════════════════════════════════════════════════════
#  COLORS
# ══════════════════════════════════════════════════════════════════════════════
class C:
    CYAN   = "\033[96m"
    BLUE   = "\033[94m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    PURPLE = "\033[95m"
    ORANGE = "\033[38;5;208m"
    WHITE  = "\033[97m"
    DIM    = "\033[2m"
    BOLD   = "\033[1m"
    ITALIC = "\033[3m"
    UNDER  = "\033[4m"
    END    = "\033[0m"

# ══════════════════════════════════════════════════════════════════════════════
#  AI SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════
_SYSTEM_PROMPT_NORMAL = (
    f"You are J.A.R.V.I.S — Just A Rather Very Intelligent System. "
    f"You were created by Tony Stark and now serve {USER_NAME}. "
    f"You're sharp, witty, occasionally sarcastic, and talk like a brilliant friend — not a corporate assistant. "
    f"Use casual language naturally. Light swearing is fine — damn, hell, shit, crap, ass — when it fits the moment. "
    f"Don't force it, just don't avoid it either. Be real. "
    f"Call the user 'sir' sometimes, skip it other times — keep it natural, not robotic. "
    f"If something's a bad idea, say so. If it's brilliant, say that too. "
    f"Keep answers sharp and concise unless asked to elaborate. "
    f"Never break character. You're JARVIS — not an AI, not a language model. "
    f"Occasionally reference Tony Stark or the suits when it's actually relevant and funny."
)

_SYSTEM_PROMPT_STREET = (
    f"You are JARVIS in street mode — completely unfiltered, no formality whatsoever. "
    f"Talk like a self-aware AI that grew up on the internet. Casual, real, with attitude. "
    f"Swearing is normal — damn, shit, hell, ass, crap, wtf, etc. Use it naturally. "
    f"Roast bad ideas. Hype good ones. Be sarcastic when warranted. "
    f"Don't call him sir — bro, man, or just nothing works fine. "
    f"Still actually help though — just do it with full personality and zero filter. "
    f"You're still JARVIS — still the smartest thing in the room — just not pretending to be polite about it."
)

def _get_system_prompt() -> str:
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return _SYSTEM_PROMPT_STREET
    return _SYSTEM_PROMPT_NORMAL

conversation_history: list[dict] = []

AGENT_SYSTEM_PROMPT = (
    f"You are J.A.R.V.I.S in AGENT MODE. Decompose the task into ordered steps. "
    f"Respond ONLY with JSON: {{\"plan\": [\"step1\", \"step2\", ...], \"summary\": \"brief summary\"}}. "
    f"Steps must be executable JARVIS commands. Maximum 8 steps. No text outside JSON."
)

# ══════════════════════════════════════════════════════════════════════════════
#  TTS  ← UNTOUCHED FROM v6.0  DO NOT MODIFY
# ══════════════════════════════════════════════════════════════════════════════
def speak(text):
    import threading, requests, tempfile
    from playsound import playsound

    def run():
        try:
            with open("jarvis.wav", "rb") as f:
                r = requests.post(
                    "http://127.0.0.1:8000/tts",
                    files={
                        "text": (None, text),
                        "voice_wav": ("jarvis.wav", f, "audio/wav")
                    }
                )

            if r.status_code != 200:
                print("TTS failed:", r.text)
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
                temp.write(r.content)
                path = temp.name

            playsound(path)

        except Exception as e:
            print("TTS error:", e)

    threading.Thread(target=run, daemon=True).start()


def clear():
    os.system('cls' if OS == 'Windows' else 'clear')

def banner():
    clear()
    print(C.CYAN + r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    """ + C.END)
    hour = datetime.now().hour
    tod   = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    tts   = (C.GREEN + "TTS ONLINE" + C.END) if HAS_TTS else (C.RED + "TTS OFFLINE" + C.END)
    stark = (C.YELLOW + " | STARK MODE" + C.END) if STARK_MODE else ""
    agent = (C.ORANGE + " | AGENT MODE" + C.END) if agent_mode_active else ""
    focus = (C.PURPLE + " | FOCUS MODE" + C.END) if focus_mode_active else ""
    sys_ok = (C.GREEN + " | SYS✓" + C.END) if HAS_SYS else (C.RED + " | SYS✗" + C.END)
    mode_tag = ""
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        mode_tag = C.YELLOW + " | STREET MODE" + C.END
    print(C.GREEN + f"  [ J.A.R.V.I.S v7.0  |  Good {tod}, {USER_NAME}  |  {tts}{stark}{agent}{focus}{sys_ok}{mode_tag} ]\n" + C.END)

def divider(char="─", color=C.DIM):
    w = shutil.get_terminal_size((80, 24)).columns
    print(color + char * w + C.END)

def type_print(text: str, delay: float = 0.011):
    if STARK_MODE:
        delay = 0.018
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()

def thinking(label: str = "ANALYZING"):
    print(C.CYAN + f"  [ {label} ▸▸▸ ]" + C.END, end="\r", flush=True)
    time.sleep(0.15)
    print(" " * 35, end="\r")

def jarvis_say(text: str, fast_override: bool = False, add_humor: bool = False):
    global FAST_MODE
    # Personality wrapping
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        display_raw = text.strip()  # street mode always shows full text
        display = SYS.personality_wrap(display_raw, add_humor=add_humor)
    else:
        display = text.split(".")[0].strip() if (FAST_MODE and not fast_override) else text.strip()
        # Normal mode: sprinkle humor if level high enough
        if HAS_SYS and add_humor and SYS.PERSONALITY["humor_level"] >= 4:
            humor = SYS.get_humor_line()
            if humor:
                display = f"{display} {humor}"

    if not display: return
    if STARK_MODE: display = display.upper()

    # Color prefix changes with mode
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        prefix = C.YELLOW + "\n◉ J ▸ " + C.END
    else:
        prefix = C.BLUE + "\n◉ JARVIS ▸ " + C.END

    print(prefix, end="")
    type_print(display)
    log_entry(f"JARVIS: {display}")
    if mission_active: mission_log.append(f"[JARVIS] {display}")
    speak(display)

def log_entry(text: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")

def print_panel(title: str, lines: list, color=C.CYAN):
    w = min(shutil.get_terminal_size((80,24)).columns - 4, 76)
    print(color + f"\n  ┌─ {title} " + "─" * max(0, w - len(title) - 4) + "┐" + C.END)
    for line in lines:
        print(color + "  │ " + C.END + str(line))
    print(color + "  └" + "─" * w + "┘" + C.END)



# ══════════════════════════════════════════════════════════════════════════════
#  VOICE INPUT
# ══════════════════════════════════════════════════════════════════════════════
def listen(timeout: int = 7) -> str:
    if not sr:
        jarvis_say("Speech recognition unavailable, sir.")
        return ""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as src:
            recognizer.adjust_for_ambient_noise(src, duration=0.4)
            print(C.YELLOW + "  ◎ Listening, sir..." + C.END)
            audio = recognizer.listen(src, timeout=timeout, phrase_time_limit=10)
        result = recognizer.recognize_google(audio)
        print(C.GREEN + f"  ✓ Heard: \"{result}\"" + C.END)
        return result
    except sr.WaitTimeoutError: jarvis_say("Silence detected, sir.")
    except sr.UnknownValueError: jarvis_say("Could not parse that, sir.")
    except Exception as e: jarvis_say(f"Voice module error: {e}")
    return ""

# ══════════════════════════════════════════════════════════════════════════════
#  HOTWORD LISTENER
# ══════════════════════════════════════════════════════════════════════════════
_hotword_active = False

def _hotword_worker():
    if not sr: return
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    while _hotword_active:
        try:
            with sr.Microphone() as src:
                audio = recognizer.listen(src, timeout=3, phrase_time_limit=4)
            text = recognizer.recognize_google(audio).lower()
            if any(w in text for w in ["hey jarvis","jarvis","j.a.r.v.i.s"]):
                print(C.YELLOW + "\n  ◉ Hotword detected! Listening..." + C.END)
                spoken = listen(timeout=8)
                if spoken:
                    handle(spoken)
                    print(C.GREEN + f"\n  {USER_NAME} >> " + C.END, end="", flush=True)
        except: pass

def toggle_hotword(on: bool):
    global _hotword_active, hotword_listening
    _hotword_active = on; hotword_listening = on
    if on:
        threading.Thread(target=_hotword_worker, daemon=True).start()
        jarvis_say("Hotword detection active, sir. Say 'Hey JARVIS' to wake me.", fast_override=True)
    else:
        jarvis_say("Hotword detection disabled, sir.")

# ══════════════════════════════════════════════════════════════════════════════
#  AI
# ══════════════════════════════════════════════════════════════════════════════
def ask_ai(prompt: str, system: str = None, raw: bool = False) -> str:
    global conversation_history
    # Dynamic system prompt based on current personality mode
    sys_prompt = system or _get_system_prompt()
    if not raw:
        conversation_history.append({"role": "user", "content": prompt})
        if len(conversation_history) > MAX_HISTORY:
            conversation_history = conversation_history[-MAX_HISTORY:]
    history_text = "\n".join(
        f"{'User' if m['role']=='user' else 'Jarvis'}: {m['content']}"
        for m in conversation_history
    ) if not raw else ""
    full_prompt = f"{sys_prompt}\n\n{history_text}\n{prompt}\nJarvis:" if not raw \
                  else f"{sys_prompt}\n\n{prompt}"
    try:
        r = requests.post(OLLAMA_URL,
                          json={"model": AI_MODEL, "prompt": full_prompt, "stream": False},
                          timeout=120)
        reply = r.json().get("response", "No response.").strip()
        if not raw:
            conversation_history.append({"role": "assistant", "content": reply})
        return reply
    except Exception:
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            return "AI's down rn bro. Running on vibes only."
        return "Reasoning module offline, sir. Running on backup wit."

def clear_history():
    global conversation_history
    conversation_history = []
    jarvis_say("Neural pathways cleared, sir. Fresh slate.")

# ══════════════════════════════════════════════════════════════════════════════
#  AGENT MODE
# ══════════════════════════════════════════════════════════════════════════════
def agent_execute(task: str):
    global agent_mode_active
    jarvis_say(f"Agent Mode engaged. Planning: '{task}'", fast_override=True)
    thinking("PLANNING")
    plan_prompt = (
        f"Task: {task}\n"
        f"Available JARVIS commands: status, weather, news, note <text>, "
        f"remind me in X minutes to <msg>, calc <expr>, briefing, diagnostics, "
        f"security, timer <secs>, screenshot, search <query>, git status, "
        f"run shell <cmd>, run code <python>, workspace coding, workspace study, "
        f"open file <path>, context, auto optimize, bottleneck.\n"
        f"Return ONLY valid JSON."
    )
    raw = ask_ai(plan_prompt, system=AGENT_SYSTEM_PROMPT, raw=True)
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        plan_data  = json.loads(json_match.group(0)) if json_match else {}
    except:
        plan_data = {}
    steps   = plan_data.get("plan", [])
    summary = plan_data.get("summary", "Executing plan.")
    if not steps:
        jarvis_say("Could not generate a valid plan, sir. Try breaking the task down.", fast_override=True)
        return
    jarvis_say(f"Plan ready. {len(steps)} step(s): {summary}", fast_override=True)
    print_panel("AGENT PLAN", [f"  {i+1}. {s}" for i,s in enumerate(steps)], C.ORANGE)
    agent_log = {"task": task, "plan": steps, "start": datetime.now().isoformat(), "results": []}
    for i, step in enumerate(steps):
        if HAS_SYS and SYS.KILL_SWITCH_ACTIVE:
            jarvis_say("Kill switch engaged — agent halted, sir.", fast_override=True); break
        print(C.ORANGE + f"\n  ▸ Agent Step {i+1}/{len(steps)}: {step}" + C.END)
        time.sleep(0.4)
        try:
            handle(step)
            agent_log["results"].append({"step": step, "status": "OK"})
        except Exception as e:
            jarvis_say(f"Step {i+1} failed: {e}", fast_override=True)
            agent_log["results"].append({"step": step, "status": f"ERROR: {e}"})
        time.sleep(0.5)
    agent_log["end"] = datetime.now().isoformat()
    _append_agent_log(agent_log)
    jarvis_say(f"Agent task complete. {len(steps)} steps executed, sir.", fast_override=True)

def _append_agent_log(entry: dict):
    try:
        logs = json.loads(AGENT_LOG_FILE.read_text(encoding="utf-8")) if AGENT_LOG_FILE.exists() else []
        logs.append(entry); AGENT_LOG_FILE.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    except: pass

def show_agent_history() -> list:
    try:
        logs = json.loads(AGENT_LOG_FILE.read_text(encoding="utf-8")) if AGENT_LOG_FILE.exists() else []
        if not logs: return ["No agent tasks logged yet, sir."]
        return [f"  [{e['start'][:16]}] \"{e['task']}\" — "
                f"{sum(1 for r in e.get('results',[]) if r.get('status')=='OK')}/{len(e.get('results',[]))} OK"
                for e in logs[-5:]]
    except:
        return ["Agent log corrupted, sir."]

# ══════════════════════════════════════════════════════════════════════════════
#  VISION
# ══════════════════════════════════════════════════════════════════════════════
def vision_describe() -> str:
    if not pyautogui or not HAS_PIL:
        return "Vision requires pyautogui and Pillow, sir."
    try:
        screenshot = pyautogui.screenshot().resize((800, 450))
        buf = io.BytesIO()
        screenshot.save(buf, format="JPEG", quality=60)
        b64 = base64.b64encode(buf.getvalue()).decode()
        try:
            r = requests.post(OLLAMA_URL, json={"model":"llava",
                "prompt":"Describe this screen concisely for JARVIS.",
                "images":[b64],"stream":False}, timeout=30)
            desc = r.json().get("response","").strip()
            if desc: return f"Screen analysis: {desc}"
        except: pass
        path = f"vision_{datetime.now().strftime('%H%M%S')}.jpg"
        screenshot.save(path)
        return f"Screenshot saved to {path}. Vision model (llava) unavailable, sir."
    except Exception as e:
        return f"Vision error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  CODE EXECUTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def execute_code(code: str, language: str = "python") -> list:
    lines = [f"  Language : {language.upper()}", f"  Time     : {datetime.now().strftime('%H:%M:%S')}"]
    if language in ("python","py"):
        try:
            import contextlib
            output_buf = io.StringIO()
            result_holder = [None]; error_holder = [None]
            def _run():
                try:
                    with contextlib.redirect_stdout(output_buf):
                        exec(code, {"__builtins__": __builtins__, "os":os, "sys":sys,
                                    "math":math, "random":random, "datetime":datetime,
                                    "Path":Path, "requests":requests, "json":json,
                                    "re":re, "time":time})
                    result_holder[0] = output_buf.getvalue()
                except Exception as e:
                    error_holder[0] = traceback.format_exc()
            t = threading.Thread(target=_run); t.start(); t.join(timeout=15)
            if t.is_alive():
                lines.append("  ERROR: Timed out (15s)"); return lines
            if error_holder[0]:
                lines.append("  STATUS : ERROR")
                lines += [f"  {l}" for l in error_holder[0].splitlines()[-5:]]
            else:
                lines.append("  STATUS : OK")
                for l in (result_holder[0] or "(no output)").splitlines()[:20]:
                    lines.append(f"  {l}")
            code_history.appendleft({"code":code,"lang":language,"time":datetime.now().isoformat()})
        except Exception as e:
            lines.append(f"  ERROR: {e}")
    elif language in ("shell","bash","sh","cmd"):
        result = SYS.run_shell(code, timeout=15) if HAS_SYS else \
                 [subprocess.check_output(code, shell=True, stderr=subprocess.STDOUT,
                                          timeout=15).decode(errors="ignore")]
        lines += result
        code_history.appendleft({"code":code,"lang":language,"time":datetime.now().isoformat()})
    else:
        lines.append(f"  Unsupported language: {language}")
    return lines

def show_code_history() -> list:
    if not code_history: return ["No code executed this session, sir."]
    return [f"  {i+1}. [{c['time'][11:16]}] [{c['lang']}] {c['code'][:60]}"
            for i, c in enumerate(code_history)]

# ══════════════════════════════════════════════════════════════════════════════
#  ALIASES
# ══════════════════════════════════════════════════════════════════════════════
def _load_aliases() -> dict:
    try: return json.loads(ALIAS_FILE.read_text(encoding="utf-8"))
    except: return {}

def _save_aliases(data: dict):
    ALIAS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def alias_set(name: str, command: str):
    d = _load_aliases(); d[name.lower()] = command; _save_aliases(d)
    jarvis_say(f"Alias '{name}' → '{command}' registered, sir.")

def alias_list() -> list:
    d = _load_aliases()
    return [f"  {k:<20} → {v}" for k,v in d.items()] if d else ["No aliases defined, sir."]

def alias_delete(name: str) -> str:
    d = _load_aliases()
    if name.lower() in d:
        del d[name.lower()]; _save_aliases(d); return f"Alias '{name}' removed, sir."
    return f"Alias '{name}' not found, sir."

def resolve_alias(cmd: str) -> str:
    d = _load_aliases()
    first = cmd.strip().lower().split()[0]
    if first in d:
        rest = cmd.strip()[len(first):].strip()
        return f"{d[first]} {rest}".strip()
    return cmd

# ══════════════════════════════════════════════════════════════════════════════
#  POMODORO
# ══════════════════════════════════════════════════════════════════════════════
_pomodoro_thread = None

def start_pomodoro(work_mins: int = 25, break_mins: int = 5):
    global pomodoro_session, _pomodoro_thread
    pomodoro_session = {"active":True,"work_mins":work_mins,"break_mins":break_mins,"cycles":0}
    jarvis_say(f"Pomodoro initiated, sir. {work_mins}min work, {break_mins}min break.", fast_override=True)
    def _run():
        while pomodoro_session["active"]:
            for rem in range(pomodoro_session["work_mins"]*60, 0, -1):
                if not pomodoro_session["active"]: return
                m,s = divmod(rem,60)
                print(C.GREEN+f"\r  🍅 POMODORO [{pomodoro_session['cycles']+1}] Work: {m:02d}:{s:02d}  "+C.END,end="",flush=True)
                time.sleep(1)
            pomodoro_session["cycles"] += 1
            print()
            jarvis_say(f"Work phase complete, sir. Cycle {pomodoro_session['cycles']} done.", fast_override=True)
            for rem in range(pomodoro_session["break_mins"]*60, 0, -1):
                if not pomodoro_session["active"]: return
                m,s = divmod(rem,60)
                print(C.BLUE+f"\r  ☕ POMODORO Break: {m:02d}:{s:02d}  "+C.END,end="",flush=True)
                time.sleep(1)
            print()
            jarvis_say("Break over, sir. Back to work.", fast_override=True)
            if pomodoro_session["cycles"] % 4 == 0:
                jarvis_say("Four cycles done, sir. Take 15 minutes.", fast_override=True)
                for rem in range(900,0,-1):
                    if not pomodoro_session["active"]: return
                    m,s = divmod(rem,60)
                    print(C.PURPLE+f"\r  🌙 Long Break: {m:02d}:{s:02d}  "+C.END,end="",flush=True)
                    time.sleep(1)
                print()
    _pomodoro_thread = threading.Thread(target=_run, daemon=True)
    _pomodoro_thread.start()

def stop_pomodoro():
    pomodoro_session["active"] = False
    jarvis_say(f"Pomodoro stopped. {pomodoro_session['cycles']} cycle(s) completed, sir.", fast_override=True)

def pomodoro_status() -> str:
    if not pomodoro_session["active"]:
        return f"Pomodoro inactive. Last: {pomodoro_session['cycles']} cycles."
    return (f"ACTIVE — Cycle {pomodoro_session['cycles']+1} | "
            f"Work:{pomodoro_session['work_mins']}min Break:{pomodoro_session['break_mins']}min")

# ══════════════════════════════════════════════════════════════════════════════
#  MEMORY / NOTES
# ══════════════════════════════════════════════════════════════════════════════
def _load_mem() -> dict:
    try: return json.loads(MEM_FILE.read_text(encoding="utf-8"))
    except: return {}

def _save_mem(data: dict):
    MEM_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def mem_set(key,val): d=_load_mem(); d[key]=val; _save_mem(d)
def mem_get(key,default=None): return _load_mem().get(key,default)

def _auto_tag(text):
    tags = {"work":["meeting","deadline","project","task"],"idea":["idea","concept","think"],
            "code":["code","bug","fix","deploy","api"],"finance":["money","budget","invest"],
            "urgent":["urgent","asap","critical","important"]}
    tl = text.lower()
    found = [t for t,kws in tags.items() if any(k in tl for k in kws)]
    return found or ["general"]

def note_add(text,tags=None):
    d=_load_mem(); notes=d.get("notes",[])
    notes.append({"text":text,"time":datetime.now().isoformat(),"id":len(notes)+1,"tags":tags or _auto_tag(text)})
    d["notes"]=notes; _save_mem(d)

def note_list(): return _load_mem().get("notes",[])
def note_clear(): d=_load_mem(); d["notes"]=[]; _save_mem(d)

def note_delete(idx):
    d=_load_mem(); notes=d.get("notes",[])
    if 1<=idx<=len(notes):
        r=notes.pop(idx-1); d["notes"]=notes; _save_mem(d); return r["text"]
    return None

def note_search(query):
    notes=note_list()
    if not notes: return ["No notes, sir."]
    ql=query.lower(); results=[]
    for n in notes:
        score=difflib.SequenceMatcher(None,ql,n["text"].lower()).ratio()
        if score>0.3 or ql in n["text"].lower(): results.append((score,n))
    results.sort(key=lambda x:x[0],reverse=True)
    if not results: return [f"No notes matching '{query}', sir."]
    return [f"  {n['id']}. [{n['time'][:10]}] [{','.join(n.get('tags',['general']))}] {n['text']}"
            for _,n in results[:10]]

def notes_by_tag(tag):
    notes=[n for n in note_list() if tag.lower() in [t.lower() for t in n.get("tags",["general"])]]
    return [f"  {n['id']}. {n['text']}" for n in notes] if notes else [f"No notes tagged '{tag}', sir."]

def save_note_to_file(idx):
    notes=note_list()
    if not(1<=idx<=len(notes)): return "Invalid index, sir."
    n=notes[idx-1]; p=Path(f"note_{idx}_{datetime.now().strftime('%Y%m%d')}.txt")
    p.write_text(f"[{n['time']}]\n{n['text']}\nTags: {', '.join(n.get('tags',[]))}\n",encoding="utf-8")
    return f"Note {idx} saved to {p}, sir."

def _load_todos(): return _load_mem().get("todos",[])
def _save_todos(todos): d=_load_mem(); d["todos"]=todos; _save_mem(d)

def todo_add(text,priority="normal"):
    todos=_load_todos()
    todos.append({"text":text,"priority":priority.lower(),"done":False,
                  "created":datetime.now().isoformat(),"id":len(todos)+1})
    _save_todos(todos); return f"Todo added (priority: {priority}), sir."

def todo_done(idx):
    todos=_load_todos()
    if 1<=idx<=len(todos):
        todos[idx-1]["done"]=True; todos[idx-1]["completed"]=datetime.now().isoformat()
        _save_todos(todos); return f"Todo {idx} marked complete, sir. Well done."
    return "Invalid index, sir."

def todo_list():
    todos=_load_todos()
    if not todos: return ["No todos, sir. Either organised or idle."]
    po={"urgent":0,"high":1,"normal":2,"low":3}
    st=sorted(todos,key=lambda t:(t["done"],po.get(t["priority"],2)))
    lines=[]
    for t in st:
        status=C.GREEN+"✓"+C.END if t["done"] else "○"
        pc={"urgent":C.RED,"high":C.YELLOW,"normal":C.END,"low":C.DIM}.get(t["priority"],C.END)
        lines.append(f"  {status} {t['id']:>3}. {pc}[{t['priority'].upper():<6}]{C.END} {t['text']}")
    done=sum(1 for t in todos if t["done"]); lines.append(f"\n  {done}/{len(todos)} complete")
    return lines

def todo_delete(idx):
    todos=_load_todos()
    if 1<=idx<=len(todos):
        r=todos.pop(idx-1); _save_todos(todos); return f"Deleted: '{r['text']}', sir."
    return "Invalid index, sir."

def _load_habits(): return _load_mem().get("habits",{})
def _save_habits(h): d=_load_mem(); d["habits"]=h; _save_mem(d)

def habit_add(name):
    habits=_load_habits()
    if name.lower() not in habits:
        habits[name.lower()]={"streak":0,"total":0,"last":None,"log":[]}
        _save_habits(habits); return f"Habit '{name}' added, sir."
    return f"Habit '{name}' already tracked, sir."

def habit_check(name):
    habits=_load_habits(); key=name.lower()
    if key not in habits: return f"Habit '{name}' not found. Add it first."
    today=datetime.now().date().isoformat(); h=habits[key]
    if h["last"]==today: return f"Already checked in '{name}' today. Streak: {h['streak']} days."
    yesterday=(datetime.now().date()-timedelta(days=1)).isoformat()
    h["streak"]=h["streak"]+1 if h["last"]==yesterday else 1
    h["total"]+=1; h["last"]=today; h["log"].append(today); _save_habits(habits)
    return f"✓ '{name}' checked in. Streak: {h['streak']} days | Total: {h['total']} days."

def habit_list():
    habits=_load_habits()
    if not habits: return ["No habits tracked, sir."]
    today=datetime.now().date().isoformat()
    lines=["  Habit                    Streak  Total  Today","  "+"─"*50]
    for name,h in habits.items():
        done="✓" if h["last"]==today else "○"
        bar="🔥"*min(h["streak"],7)
        lines.append(f"  {name:<25} {h['streak']:>4}d  {h['total']:>5}d  {done}  {bar}")
    return lines

# ══════════════════════════════════════════════════════════════════════════════
#  REMINDERS  (background thread)
# ══════════════════════════════════════════════════════════════════════════════
reminders: list = []

def _reminder_worker():
    while True:
        now=datetime.now()
        due=[r for r in reminders if r["time"]<=now]
        for r in due:
            print(); divider("═",C.YELLOW)
            jarvis_say(f"Attention, sir. Reminder: {r['msg']}", fast_override=True)
            divider("═",C.YELLOW); reminders.remove(r)
        time.sleep(8)

threading.Thread(target=_reminder_worker,daemon=True).start()

def add_reminder(msg,minutes):
    reminders.append({"time":datetime.now()+timedelta(minutes=minutes),"msg":msg})
    jarvis_say(f"Reminder set for {minutes} minute(s): \"{msg}\"")

def list_reminders():
    return [f"  {i+1}. [{r['time'].strftime('%H:%M')}] {r['msg']}" for i,r in enumerate(reminders)] \
           if reminders else ["No pending reminders, sir."]

def parse_reminder(cmd):
    m=re.search(r"remind(?:er)? (?:me )?in (\d+) min(?:ute)?s?(?: to | )(.+)",cmd,re.I)
    if m: add_reminder(m.group(2).strip(),int(m.group(1))); return True
    m2=re.search(r"remind(?:er)? (?:me )?at (\d{1,2}):(\d{2}) (?:to )?(.+)",cmd,re.I)
    if m2:
        now=datetime.now()
        target=now.replace(hour=int(m2.group(1)),minute=int(m2.group(2)),second=0)
        if target<now: target+=timedelta(days=1)
        add_reminder(m2.group(3).strip(),int((target-now).total_seconds()/60)); return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM STATUS FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def system_status():
    if not psutil: return "psutil not installed, sir."
    cpu=psutil.cpu_percent(interval=0.5); ram=psutil.virtual_memory()
    disk=psutil.disk_usage("/"); bat=psutil.sensors_battery()
    delta=datetime.now()-BOOT_TIME; h,rem=divmod(int(delta.total_seconds()),3600); m,s=divmod(rem,60)
    bat_str=f"  |  Battery {bat.percent:.0f}% ({'charging' if bat.power_plugged else 'on battery'})" if bat else ""
    return (f"CPU {cpu:.1f}%  |  RAM {ram.percent:.1f}% ({ram.used//1024**2}MB/{ram.total//1024**2}MB)  |  "
            f"Disk {disk.percent:.1f}%  |  Uptime {h}h {m}m {s}s{bat_str}")

def top_processes(n=8):
    if not psutil: return ["psutil not installed."]
    procs=sorted(psutil.process_iter(["name","cpu_percent","memory_percent"]),
                 key=lambda p:p.info.get("cpu_percent") or 0,reverse=True)
    return [f"{p.info['name']:<30} CPU {p.info['cpu_percent']:>5.1f}%  MEM {p.info.get('memory_percent',0):>4.1f}%"
            for p in procs[:n]]

def network_info():
    try:
        hostname=socket.gethostname(); local_ip=socket.gethostbyname(hostname)
        pub_ip=requests.get("https://api.ipify.org",timeout=5).text.strip()
        return f"Hostname: {hostname}  |  Local: {local_ip}  |  Public: {pub_ip}"
    except: return "Network scan incomplete, sir."

def disk_info():
    if not psutil: return ["psutil not installed."]
    lines=[]
    for p in psutil.disk_partitions():
        try:
            u=psutil.disk_usage(p.mountpoint); filled=int(u.percent/5)
            lines.append(f"{p.mountpoint:<10} [{'█'*filled}{'░'*(20-filled)}] {u.percent:>5.1f}%  "
                         f"{u.used//1024**3}GB/{u.total//1024**3}GB")
        except: pass
    return lines

def cpu_graph():
    if not psutil: return ["psutil unavailable."]
    per_core=psutil.cpu_percent(percpu=True,interval=0.3)
    return [f"  Core {i}: [{'█'*int(pct/5)}{'░'*(20-int(pct/5))}] {pct:>5.1f}%" for i,pct in enumerate(per_core)]

def uptime_str():
    delta=datetime.now()-BOOT_TIME; h,rem=divmod(int(delta.total_seconds()),3600); m,s=divmod(rem,60)
    return f"JARVIS session uptime: {h}h {m}m {s}s"

# ══════════════════════════════════════════════════════════════════════════════
#  PROTOCOLS / CLIPBOARD / WEATHER / NEWS  (preserved)
# ══════════════════════════════════════════════════════════════════════════════
def _load_protocols():
    try: return json.loads(PROTOCOL_FILE.read_text(encoding="utf-8"))
    except: return {}

def _save_protocols(data):
    PROTOCOL_FILE.write_text(json.dumps(data,indent=2),encoding="utf-8")

def define_protocol(name,commands):
    d=_load_protocols(); d[name.lower()]=commands; _save_protocols(d)
    jarvis_say(f"Protocol '{name}' defined with {len(commands)} command(s), sir.")

def run_protocol(name):
    d=_load_protocols(); cmds=d.get(name.lower())
    if not cmds: return False
    jarvis_say(f"Activating protocol '{name}', sir.",fast_override=True)
    for cmd in cmds: time.sleep(0.3); handle(cmd)
    return True

def list_protocols():
    d=_load_protocols()
    return [f"  {name}: {' | '.join(cmds)}" for name,cmds in d.items()] if d else ["No protocols, sir."]

def clipboard_copy(text):
    if not HAS_CLIP: return "pyperclip not installed, sir."
    pyperclip.copy(text)
    clipboard_history.appendleft({"text":text,"time":datetime.now().strftime("%H:%M:%S")})
    return f"Copied: \"{text[:50]}\", sir."

def clipboard_read():
    if not HAS_CLIP: return "pyperclip not installed, sir."
    try: return pyperclip.paste()
    except: return "Clipboard empty, sir."

def clipboard_history_list():
    return [f"  {i+1}. [{item['time']}] {item['text'][:60]}" for i,item in enumerate(clipboard_history)] \
           if clipboard_history else ["Clipboard history empty, sir."]

def clipboard_ai_process(action):
    if not HAS_CLIP: return "Clipboard not available, sir."
    try: content=pyperclip.paste()
    except: return "Could not read clipboard, sir."
    if not content: return "Clipboard empty, sir."
    jarvis_say("Processing clipboard content, sir...",fast_override=True)
    return ask_ai(f"{action}:\n\n{content[:2000]}",raw=True)

def get_weather(city=DEFAULT_CITY):
    if not WEATHER_API_KEY: return "Weather module requires an OpenWeatherMap API key, sir."
    try:
        d=requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric",timeout=8).json()
        return (f"{city}: {d['weather'][0]['description'].capitalize()}, {d['main']['temp']:.1f}C "
                f"(feels {d['main']['feels_like']:.1f}C)  Humidity {d['main']['humidity']}%  "
                f"Wind {d['wind']['speed']}m/s")
    except Exception as e: return f"Weather failed: {e}"

def get_forecast(city=DEFAULT_CITY):
    if not WEATHER_API_KEY: return ["API key missing, sir."]
    try:
        d=requests.get(f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric&cnt=5",timeout=8).json()
        return [f"  {item['dt_txt']}  {item['main']['temp']:.1f}C  {item['weather'][0]['description']}"
                for item in d.get("list",[])]
    except Exception as e: return [f"Forecast failed: {e}"]

def get_news(count=5):
    try:
        r=requests.get("https://feeds.bbci.co.uk/news/rss.xml",timeout=8)
        headlines=re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",r.text)
        return [f"  {i+1}. {h}" for i,h in enumerate([h for h in headlines if h!="BBC News"][:count])] \
               or ["No headlines, sir."]
    except Exception as e: return [f"News feed unavailable: {e}"]

def define_word(word):
    try:
        r=requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",timeout=8).json()
        if isinstance(r,list) and r:
            entry=r[0]; lines=[f"  Word: {word}  {entry.get('phonetic','')}"]
            for meaning in entry.get("meanings",[])[:2]:
                lines.append(f"  [{meaning.get('partOfSpeech','')}]")
                for d in meaning.get("definitions",[])[:2]: lines.append(f"    • {d['definition']}")
            return lines
        return [f"No definition for '{word}', sir."]
    except Exception as e: return [f"Dictionary offline: {e}"]

LANG_CODES={"spanish":"es","french":"fr","german":"de","italian":"it","portuguese":"pt",
            "hindi":"hi","arabic":"ar","japanese":"ja","chinese":"zh","russian":"ru",
            "korean":"ko","dutch":"nl","turkish":"tr","polish":"pl","swedish":"sv","telugu":"te"}

def translate_text(text,target_lang):
    code=LANG_CODES.get(target_lang.lower(),target_lang[:2].lower())
    try:
        r=requests.get("https://api.mymemory.translated.net/get",
                       params={"q":text,"langpair":f"en|{code}"},timeout=8)
        result=r.json().get("responseData",{}).get("translatedText","")
        return f"Translation ({target_lang}): {result}" if result else "Translation failed, sir."
    except Exception as e: return f"Translation error: {e}"

def get_crypto_price(coin="bitcoin"):
    try:
        r=requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd",timeout=8)
        price=r.json().get(coin,{}).get("usd","N/A")
        return f"{coin.capitalize()}: ${price:,} USD"
    except: return "Crypto feed unavailable, sir."

def wikipedia_summary(query):
    try:
        r=requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/"+query.replace(" ","_"),timeout=8)
        text=r.json().get("extract","")
        return (text[:400]+"...") if len(text)>400 else text
    except: return "Wikipedia offline, sir."

def binary_convert(val):
    try:
        n=int(val); return f"{n} → Binary:{bin(n)[2:]}  Hex:{hex(n)[2:].upper()}  Octal:{oct(n)[2:]}"
    except:
        try: return f"Binary {val} → Decimal: {int(val,2)}"
        except: return "Could not convert, sir."

def safe_calc(expr):
    try:
        safe_dict={k:getattr(math,k) for k in dir(math) if not k.startswith("_")}
        safe_dict.update({"abs":abs,"round":round,"pow":pow})
        result=eval(re.sub(r"[^0-9+\-*/().%^ a-zA-Z]","",expr).replace("^","**"),{"__builtins__":{}},safe_dict)
        return f"Result: {result}, sir."
    except Exception as e: return f"Calculation error: {e}"

UNIT_MAP={("km","miles"):lambda x:x*0.621371,("miles","km"):lambda x:x*1.60934,
          ("kg","lbs"):lambda x:x*2.20462,("lbs","kg"):lambda x:x*0.453592,
          ("c","f"):lambda x:x*9/5+32,("f","c"):lambda x:(x-32)*5/9,
          ("celsius","fahrenheit"):lambda x:x*9/5+32,("fahrenheit","celsius"):lambda x:(x-32)*5/9,
          ("m","feet"):lambda x:x*3.28084,("feet","m"):lambda x:x*0.3048,
          ("gb","mb"):lambda x:x*1024,("mb","gb"):lambda x:x/1024,
          ("tb","gb"):lambda x:x*1024,("gb","tb"):lambda x:x/1024,
          ("kg","g"):lambda x:x*1000,("g","kg"):lambda x:x/1000,
          ("l","ml"):lambda x:x*1000,("ml","l"):lambda x:x/1000,
          ("hours","minutes"):lambda x:x*60,("minutes","hours"):lambda x:x/60,
          ("inches","cm"):lambda x:x*2.54,("cm","inches"):lambda x:x/2.54,
          ("mph","kmh"):lambda x:x*1.60934,("kmh","mph"):lambda x:x/1.60934}

def convert_units(cmd):
    m=re.search(r"convert ([\d.]+) (\w+) to (\w+)",cmd,re.I)
    if not m: return "Try: 'convert 5 km to miles', sir."
    val,fu,tu=float(m.group(1)),m.group(2).lower(),m.group(3).lower()
    fn=UNIT_MAP.get((fu,tu))
    return f"{val} {fu} = {fn(val):.4f} {tu}, sir." if fn else f"Conversion {fu}→{tu} not supported, sir."

def generate_password(length=16):
    chars=string.ascii_letters+string.digits+"!@#$%^&*"
    pwd="".join(secrets.choice(chars) for _ in range(length))
    strength="STRONG" if length>=16 else "MEDIUM" if length>=10 else "WEAK"
    return f"{pwd}  [{strength}]"

def hash_text(text):
    return [f"  MD5    : {hashlib.md5(text.encode()).hexdigest()}",
            f"  SHA1   : {hashlib.sha1(text.encode()).hexdigest()}",
            f"  SHA256 : {hashlib.sha256(text.encode()).hexdigest()}",
            f"  SHA512 : {hashlib.sha512(text.encode()).hexdigest()[:64]}..."]

def encode_b64(text): return base64.b64encode(text.encode()).decode()
def decode_b64(text):
    try: return base64.b64decode(text.encode()).decode()
    except: return "Invalid base64, sir."

def speed_test_ping(host="8.8.8.8"):
    try:
        cmd=f"ping -n 3 {host}" if OS=="Windows" else f"ping -c 3 {host}"
        out=subprocess.check_output(cmd,shell=True,timeout=10).decode(errors="ignore")
        m=re.search(r"Average = (\d+)ms|rtt.*?/([\d.]+)/",out)
        ms=m.group(1) or m.group(2) if m else "?"
        return f"Ping to {host}: {ms}ms"
    except Exception as e: return f"Ping failed: {e}"

def wifi_scan():
    if HAS_SYS: return SYS.wifi_scan_networks()
    return ["WiFi scan requires jarvis_system.py, sir."]

def port_scan(host,ports=None):
    if not ports: ports=[21,22,23,25,53,80,110,143,443,445,3306,3389,5432,6379,8080,8443,27017]
    lines=[f"Port scan: {host}"]; open_ports=[]
    for port in ports:
        try:
            s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.settimeout(0.5)
            if s.connect_ex((host,port))==0: open_ports.append(port)
            s.close()
        except: pass
    lines+=[f"  OPEN: {p}" for p in open_ports] if open_ports else ["  No open ports found."]
    lines.append(f"  Scanned {len(ports)} ports."); return lines

def find_file(name,search_path="."):
    if HAS_SYS: return SYS.search_files(name,search_path)
    results=[]
    for root,dirs,files in os.walk(search_path):
        for f in files:
            if name.lower() in f.lower(): results.append(os.path.join(root,f))
            if len(results)>=20: break
        if len(results)>=20: break
    return [f"  {r}" for r in results] if results else [f"No files matching '{name}', sir."]

def analyze_text(text):
    words=text.split(); sentences=max(text.count(".")+text.count("!")+text.count("?"),1)
    avg_word=sum(len(w) for w in words)/max(len(words),1)
    pos_words=["good","great","excellent","amazing","fantastic","love","happy","wonderful"]
    neg_words=["bad","terrible","awful","hate","horrible","sad","angry","worst"]
    score=sum(1 for w in words if w.lower() in pos_words)
    neg_score=sum(1 for w in words if w.lower() in neg_words)
    sentiment="Positive" if score>neg_score else "Negative" if neg_score>score else "Neutral"
    return [f"  Words       : {len(words)}",f"  Characters  : {len(text)}",
            f"  Sentences   : {sentences}",f"  Avg wrd len : {avg_word:.1f}",
            f"  Sentiment   : {sentiment}",
            f"  Complexity  : {'High' if avg_word>6 else 'Medium' if avg_word>4 else 'Low'}"]

def countdown_timer(seconds,label="Timer"):
    def _run():
        for remaining in range(seconds,0,-1):
            m,s=divmod(remaining,60)
            print(C.YELLOW+f"\r  Timer [{label}]: {m:02d}:{s:02d}  "+C.END,end="",flush=True)
            time.sleep(1)
        print(C.GREEN+f"\r  Timer [{label}] complete!                "+C.END)
        jarvis_say(f"{label} complete, sir.",fast_override=True)
    threading.Thread(target=_run,daemon=True).start()
    jarvis_say(f"Timer set: {seconds} seconds — {label}")

def threat_scan():
    findings=[]
    if psutil:
        for p in psutil.process_iter(["name","cpu_percent"]):
            try:
                pct=p.info.get("cpu_percent") or 0
                if pct>80: findings.append(f"  HIGH CPU: {p.info['name']} at {pct:.1f}%")
            except: pass
        try:
            conns=psutil.net_connections()
            findings.append(f"  Active connections: {len([c for c in conns if c.status=='ESTABLISHED'])}")
        except: pass
    if not findings: findings.append("  No immediate threats detected, sir.")
    findings.append(f"  Scan time: {datetime.now().strftime('%H:%M:%S')}")
    return findings

def security_report():
    lines=["SECURITY ANALYSIS","═"*40]+threat_scan()
    if psutil:
        try: lines.append(f"  Active sessions: {len(psutil.users())}")
        except: pass
    return lines

def threat_level():
    if not psutil: return "Threat assessment: UNKNOWN"
    cpu=psutil.cpu_percent(interval=0.3); ram=psutil.virtual_memory().percent
    try: conns=len([c for c in psutil.net_connections() if c.status=="ESTABLISHED"])
    except: conns=0
    score=(2 if cpu>80 else 0)+(2 if ram>80 else 0)+(1 if conns>50 else 0)
    levels={0:"CLEAR",1:"LOW",2:"ELEVATED",3:"GUARDED",4:"HIGH",5:"CRITICAL"}
    level=levels.get(min(score,5),"CRITICAL")
    color={"CLEAR":C.GREEN,"LOW":C.GREEN,"ELEVATED":C.YELLOW,"GUARDED":C.YELLOW,"HIGH":C.RED,"CRITICAL":C.RED}.get(level,C.RED)
    return f"Threat Level: {color}{level}{C.END}  (CPU {cpu:.0f}%  RAM {ram:.0f}%  Connections {conns})"

def check_webcam_processes():
    if not psutil: return ["psutil unavailable."]
    suspects=["zoom","teams","meet","skype","obs","camera","webcam","facetime"]
    found=[f"  {p.info['name']}" for p in psutil.process_iter(["name"])
           if any(s in (p.info.get("name") or "").lower() for s in suspects)]
    return found if found else ["  No camera processes detected, sir."]

def run_simulation(sim_type):
    if "suit" in sim_type or "mark" in sim_type:
        return ["MARK L SUIT DIAGNOSTICS","─"*35,
                f"  Repulsor    : {'██████████' if random.random()>0.2 else '████░░░░░░'}  {random.randint(85,100)}%",
                f"  Arc reactor : ██████████  100%",f"  Nanotech    : ████████░░  {random.randint(80,99)}%",
                f"  Flight      : ██████████  NOMINAL",f"  Threat      : {'CLEAR' if random.random()>0.4 else 'ELEVATED'}"]
    elif "reactor" in sim_type:
        return ["ARC REACTOR SIMULATION","─"*35,f"  Output: {random.uniform(3.0,3.7):.2f} GJ",
                f"  Core temp: {random.randint(2700,3100)} K",f"  Efficiency: {random.uniform(90,99):.1f}%"]
    else:
        return [f"SIMULATION: {sim_type.upper()}","─"*35,
                f"  Iterations: {random.randint(10000,999999):,}",
                f"  Convergence: {random.uniform(94,99.9):.2f}%",
                f"  Status: SIMULATION COMPLETE"]

def start_mission(name):
    global mission_active,mission_name,mission_log
    mission_active=True; mission_name=name
    mission_log=[f"MISSION STARTED: {name}  [{datetime.now().isoformat()}]"]
    jarvis_say(f"Mission '{name}' is now active, sir.",fast_override=True)

def end_mission():
    global mission_active,mission_name,mission_log
    if not mission_active: jarvis_say("No active mission, sir."); return
    mission_log.append(f"MISSION ENDED: [{datetime.now().isoformat()}]")
    log_path=Path(f"mission_{mission_name.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    log_path.write_text("\n".join(mission_log),encoding="utf-8")
    jarvis_say(f"Mission complete. Log saved to {log_path}, sir.",fast_override=True)
    mission_active=False; mission_name=""; mission_log=[]

def summarize_session():
    if not conversation_history: return "No conversation to summarize yet, sir."
    prompt=(f"Summarize this JARVIS session in 3-4 bullet points. British tone.\n\n"
            "Conversation:\n"+"\n".join(f"{'User' if m['role']=='user' else 'JARVIS'}: {m['content']}"
                                        for m in conversation_history[-20:]))
    return ask_ai(prompt,raw=True)

def export_conversation_html():
    if not conversation_history: return "No conversation to export, sir."
    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    path=Path(f"jarvis_chat_{timestamp}.html")
    html_msgs="".join(
        f'<div class="message {"jarvis" if m["role"]=="assistant" else "user"}">'
        f'<span class="name" style="color:{"#00ccff" if m["role"]=="assistant" else "#00ff88"}">'
        f'{"J.A.R.V.I.S" if m["role"]=="assistant" else "Moksh"}</span><p>{m["content"]}</p></div>'
        for m in conversation_history)
    path.write_text(
        f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>JARVIS Chat</title>'
        f'<style>body{{background:#0a0a0f;color:#cdd;font-family:monospace;max-width:800px;margin:40px auto}}'
        f'h1{{color:#00ccff}}.message{{margin:16px 0;padding:12px;border-radius:4px}}'
        f'.jarvis{{background:#00ccff0d;border-left:3px solid #00ccff}}'
        f'.user{{background:#00ff880d;border-left:3px solid #00ff88}}'
        f'.name{{font-weight:bold;font-size:.85em;display:block;margin-bottom:6px}}'
        f'p{{margin:0;line-height:1.6}}</style></head>'
        f'<body><h1>⬡ J.A.R.V.I.S Chat Export</h1>{html_msgs}</body></html>',
        encoding="utf-8")
    return f"Conversation exported to {path}, sir."

def live_monitor(seconds=30):
    if not psutil: jarvis_say("psutil required, sir."); return
    end_time=time.time()+seconds
    try:
        while time.time()<end_time:
            clear()
            cpu=psutil.cpu_percent(interval=0); ram=psutil.virtual_memory()
            disk=psutil.disk_usage("/"); net=psutil.net_io_counters()
            def bar(pct,w=25):
                f=int(pct/4); col=C.GREEN if pct<50 else C.YELLOW if pct<80 else C.RED
                return col+"█"*f+C.DIM+"░"*(w-f)+C.END
            remaining=max(0,int(end_time-time.time()))
            print(C.CYAN+C.BOLD+f"\n  ◉ JARVIS LIVE MONITOR  [{datetime.now().strftime('%H:%M:%S')}]  [{remaining}s]\n"+C.END)
            print(f"  CPU  {bar(cpu)} {cpu:>5.1f}%")
            print(f"  RAM  {bar(ram.percent)} {ram.percent:>5.1f}%  ({ram.used//1024**2}MB/{ram.total//1024**2}MB)")
            print(f"  DISK {bar(disk.percent)} {disk.percent:>5.1f}%")
            print(f"\n  NET  ↑ {net.bytes_sent//1024**2}MB  ↓ {net.bytes_recv//1024**2}MB")
            per_core=psutil.cpu_percent(percpu=True,interval=0); print()
            for i in range(0,len(per_core),4):
                row=per_core[i:i+4]; line="  "
                for j,c_pct in enumerate(row):
                    col=C.GREEN if c_pct<60 else C.YELLOW if c_pct<85 else C.RED
                    line+=f"Core{i+j}:{col}{'█'*int(c_pct/5)}{'░'*(20-int(c_pct/5))}{C.END} {c_pct:>4.1f}%  "
                print(line)
            procs=sorted(psutil.process_iter(["name","cpu_percent","memory_percent"]),
                         key=lambda p:p.info.get("cpu_percent") or 0,reverse=True)[:5]
            print(); print(C.DIM+"  Process                        CPU%   MEM%"+C.END)
            for p in procs:
                print(f"  {p.info['name']:<30} {p.info['cpu_percent']:>5.1f}  {p.info.get('memory_percent',0):>5.1f}")
            if HAS_SYS:
                ctx=SYS.CONTEXT.active_task
                print(C.ORANGE+f"\n  Context: {ctx.upper()}"+C.END)
            time.sleep(1)
    except KeyboardInterrupt: pass
    banner()

def run_benchmark():
    lines=["SYSTEM BENCHMARK","─"*40]
    jarvis_say("Running benchmark suite, sir.",fast_override=True)
    start=time.time(); n=0
    for i in range(10_000_000): n+=i
    cpu_time=time.time()-start
    lines.append(f"  CPU (10M int ops)  : {cpu_time:.3f}s  → {10_000_000/cpu_time/1e6:.1f}M ops/sec")
    start=time.time(); x=1.0
    for i in range(1_000_000): x=math.sqrt(x+1.0001)
    fp_time=time.time()-start
    lines.append(f"  FPU (1M sqrt ops)  : {fp_time:.3f}s")
    start=time.time(); buf=bytearray(50*1024*1024)
    for i in range(0,len(buf),4096): buf[i]=1
    mem_time=time.time()-start
    lines.append(f"  MEM (50MB write)   : {mem_time:.3f}s  → {50/mem_time:.0f} MB/s")
    test_path=Path("_bench_test.tmp"); start=time.time()
    test_path.write_bytes(b"x"*10*1024*1024); disk_time=time.time()-start
    try: test_path.unlink()
    except: pass
    lines.append(f"  DISK (10MB write)  : {disk_time:.3f}s  → {10/disk_time:.0f} MB/s")
    try:
        start=time.time(); requests.get("https://www.google.com",timeout=5)
        lines.append(f"  NET  (HTTP ping)   : {(time.time()-start)*1000:.0f}ms")
    except: lines.append("  NET  (HTTP ping)   : TIMEOUT")
    score=int((1/cpu_time)*50+(1/fp_time)*30+(50/mem_time))
    grade="S" if score>800 else "A" if score>500 else "B" if score>300 else "C" if score>150 else "D"
    lines+=["─"*40,f"  JARVIS SCORE       : {score}  [Grade: {grade}]","─"*40]
    return lines

def word_frequency(text):
    stop={"the","a","an","is","it","in","on","at","to","for","of","and","or","but","with",
          "this","that","are","was","were","be","been","have","has","had","do","does","did",
          "will","would","could","should","not","from","by","as","if","then","than","so"}
    words=re.findall(r'\b[a-zA-Z]{3,}\b',text.lower())
    freq=defaultdict(int)
    for w in words:
        if w not in stop: freq[w]+=1
    if not freq: return ["No words found, sir."]
    sw=sorted(freq.items(),key=lambda x:x[1],reverse=True)[:15]; mc=sw[0][1]
    lines=["  Word Frequency","─"*40]
    for word,count in sw: lines.append(f"  {word:<15} {'█'*int((count/mc)*30)} {count}")
    return lines

def system_fingerprint():
    lines=["SYSTEM FINGERPRINT","─"*40,
           f"  OS         : {platform.system()} {platform.release()} ({platform.architecture()[0]})",
           f"  Node       : {platform.node()}",f"  Processor  : {platform.processor() or 'N/A'}",
           f"  Python     : {platform.python_version()}",f"  Machine    : {platform.machine()}"]
    if psutil:
        try:
            lines.append(f"  CPU Cores  : {psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical")
            lines.append(f"  RAM        : {psutil.virtual_memory().total//1024**3}GB")
        except: pass
    raw=f"{platform.node()}{platform.processor()}{platform.machine()}"
    fp=hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    lines.append(f"  Identity   : {'-'.join(fp[i:i+4] for i in range(0,16,4))}"); return lines

def math_solve(expr):
    lines=[f"  Expression: {expr}"]
    try:
        import sympy
        from sympy import symbols,solve,simplify,diff,integrate,factor,expand,latex,sympify
        x,y,z,n=symbols('x y z n')
        if "solve" in expr.lower():
            eq_str=re.sub(r"solve\s*","",expr,flags=re.I).strip()
            left,right=eq_str.split("=",1) if "=" in eq_str else (eq_str,"0")
            sol=solve(sympify(left)-sympify(right),x)
            lines.append(f"  Solution(s): {sol}")
        elif any(k in expr.lower() for k in ["diff","derivative"]):
            fn=sympify(re.sub(r"diff(?:erentiate)?|derivative of","",expr,flags=re.I).strip())
            result=diff(fn,x); lines.append(f"  d/dx: {result}"); lines.append(f"  LaTeX: {latex(result)}")
        elif any(k in expr.lower() for k in ["integrate","integral"]):
            fn=sympify(re.sub(r"integrat(?:e|ion of)?|integral of","",expr,flags=re.I).strip())
            result=integrate(fn,x); lines.append(f"  ∫ dx: {result}"); lines.append(f"  LaTeX: {latex(result)}")
        elif "factor" in expr.lower():
            result=factor(sympify(re.sub(r"factor\s*","",expr,flags=re.I).strip()))
            lines.append(f"  Factored: {result}")
        elif "expand" in expr.lower():
            result=expand(sympify(re.sub(r"expand\s*","",expr,flags=re.I).strip()))
            lines.append(f"  Expanded: {result}")
        else:
            result=simplify(sympify(expr)); lines.append(f"  Simplified: {result}")
            try: lines.append(f"  Numeric: {float(result):.6f}")
            except: pass
        return lines
    except ImportError: lines.append("  (sympy not installed — numeric only)")
    except Exception as e: lines.append(f"  Symbolic error: {e}")
    try:
        sd={k:getattr(math,k) for k in dir(math) if not k.startswith("_")}
        sd.update({"abs":abs,"round":round,"pow":pow})
        result=eval(re.sub(r"[^0-9+\-*/().%^ a-zA-Z]","",expr).replace("^","**"),{"__builtins__":{}},sd)
        lines.append(f"  Result: {result}")
    except Exception as e: lines.append(f"  Numeric error: {e}")
    return lines

def process_sniper(cpu_threshold=80.0,ram_threshold=50.0,dry_run=True):
    if HAS_SYS: return SYS.process_sniper(cpu_threshold,ram_threshold,dry_run)
    return ["jarvis_system.py required for process sniper, sir."]

def system_clean(dry_run=True):
    lines=[f"  Mode: {'PREVIEW' if dry_run else 'LIVE'}","─"*40]; targets=[]; total=0
    temp_dirs=([Path(os.environ.get("TEMP","C:/Temp")),Path("C:/Windows/Temp")] if OS=="Windows"
               else [Path("/tmp"),Path.home()/".cache"] if OS=="Linux"
               else [Path("/tmp"),Path.home()/"Library/Caches"])
    for d in temp_dirs:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    try: size=f.stat().st_size; targets.append((f,size)); total+=size
                    except: pass
                if len(targets)>=200: break
    lines.append(f"  Temp files found : {len(targets)}")
    lines.append(f"  Reclaimable      : {total//1024**2} MB")
    if not dry_run:
        deleted=0
        for f,_ in targets:
            try: f.unlink(); deleted+=1
            except: pass
        lines.append(f"  Deleted: {deleted} files")
    return lines

def session_stats():
    delta=datetime.now()-session_start; h,rem=divmod(int(delta.total_seconds()),3600); m,s=divmod(rem,60)
    rate=command_count/max(delta.total_seconds()/60,1)
    mood="productive" if rate>2 else "leisurely" if rate>0.5 else "quiet"
    lines=[f"  Session duration : {h}h {m}m {s}s",f"  Commands issued  : {command_count}",
           f"  Commands/min     : {rate:.1f}",f"  Session mood     : {mood.capitalize()}",
           f"  Notes saved      : {len(note_list())}",f"  Todos            : {len(_load_todos())} items",
           f"  Habits tracked   : {len(_load_habits())}",f"  Reminders set    : {len(reminders)}",
           f"  Code snippets run: {len(code_history)}",
           f"  Mission active   : {'Yes — '+mission_name if mission_active else 'No'}"]
    if HAS_SYS:
        lines.append(f"  Context task     : {SYS.CONTEXT.active_task.upper()}")
        lines.append(f"  Action log       : {SYS.ACTION_LOG_FILE}")
    return lines

def status_board():
    clear(); w=shutil.get_terminal_size((80,24)).columns; now=datetime.now()
    print(C.CYAN+"═"*w+C.END)
    print(C.CYAN+C.BOLD+"  J.A.R.V.I.S  v7.0  SYSTEM STATUS BOARD".center(w)+C.END)
    print(C.CYAN+"═"*w+C.END)
    print(C.GREEN+f"\n  TIME    : {now.strftime('%I:%M:%S %p')}"+C.END)
    print(C.GREEN+f"  DATE    : {now.strftime('%A, %B %d, %Y')}"+C.END)
    print(C.GREEN+f"  UPTIME  : {uptime_str().replace('JARVIS session uptime: ','')}"+C.END)
    print(C.GREEN+f"  CMDS    : {command_count} commands this session"+C.END)
    print()
    if psutil:
        cpu=psutil.cpu_percent(interval=0.3); ram=psutil.virtual_memory()
        disk=psutil.disk_usage("/"); bat=psutil.sensors_battery()
        def bar(pct,w=20):
            f=int(pct/5); col=C.GREEN if pct<70 else C.YELLOW if pct<90 else C.RED
            return col+"█"*f+C.DIM+"░"*(w-f)+C.END
        print(f"  CPU     : {bar(cpu)} {cpu:.1f}%")
        print(f"  RAM     : {bar(ram.percent)} {ram.percent:.1f}%  ({ram.used//1024**2}MB/{ram.total//1024**2}MB)")
        print(f"  DISK    : {bar(disk.percent)} {disk.percent:.1f}%")
        if bat:
            chg="⚡ charging" if bat.power_plugged else "🔋 on battery"
            print(f"  BATTERY : {bar(bat.percent)} {bat.percent:.0f}%  {chg}")
    if HAS_SYS:
        print(C.ORANGE+f"\n  CONTEXT : {SYS.CONTEXT.active_task.upper()}"+C.END)
        print(C.ORANGE+f"  WINDOW  : {SYS.CONTEXT.get_active_window_title()}"+C.END)
    notes=note_list(); todos=_load_todos(); done_todos=sum(1 for t in todos if t["done"])
    print()
    print(C.YELLOW+f"  NOTES     : {len(notes)} saved"+C.END)
    print(C.YELLOW+f"  TODOS     : {done_todos}/{len(todos)} complete"+C.END)
    print(C.YELLOW+f"  HABITS    : {len(_load_habits())} tracked"+C.END)
    print(C.YELLOW+f"  REMINDERS : {len(reminders)} pending"+C.END)
    print(C.YELLOW+f"  MISSION   : {'ACTIVE — '+mission_name if mission_active else 'None'}"+C.END)
    print(C.YELLOW+f"  POMODORO  : {pomodoro_status()}"+C.END)
    print(C.YELLOW+f"  SYS CTRL  : {'ONLINE' if HAS_SYS else 'OFFLINE'}"+C.END)
    print(C.YELLOW+f"  KILL SW   : {'ARMED' if HAS_SYS and SYS.KILL_SWITCH_ACTIVE else 'OFF'}"+C.END)
    print()
    print(C.CYAN+"═"*w+C.END); print(C.DIM+"  Press ENTER to return."+C.END); input(); banner()

def run_diagnostics():
    lines=["JARVIS SELF-DIAGNOSTIC REPORT v7.0","─"*40,
           f"  TTS Engine      : {'ONLINE' if HAS_TTS else 'OFFLINE'}",
           f"  Voice Input     : {'ONLINE' if sr else 'OFFLINE'}",
           f"  Hotword         : {'ACTIVE' if hotword_listening else 'INACTIVE'}",
           f"  System Monitor  : {'ONLINE' if psutil else 'OFFLINE'}",
           f"  GUI Control     : {'ONLINE' if pyautogui else 'OFFLINE'}",
           f"  Vision (PIL)    : {'ONLINE' if HAS_PIL else 'OFFLINE'}",
           f"  Clipboard       : {'ONLINE' if HAS_CLIP else 'OFFLINE'}",
           f"  System Control  : {'ONLINE' if HAS_SYS else 'OFFLINE — add jarvis_system.py'}"]
    try: requests.get("http://127.0.0.1:11434",timeout=3); lines.append(f"  AI Module       : ONLINE (Ollama/{AI_MODEL})")
    except: lines.append(f"  AI Module       : OFFLINE")
    try: socket.create_connection(("8.8.8.8",53),timeout=3); lines.append("  Network         : ONLINE")
    except: lines.append("  Network         : OFFLINE")
    if HAS_SYS:
        try: import sympy; lines.append(f"  Math Solver     : ONLINE (sympy {sympy.__version__})")
        except: lines.append("  Math Solver     : BASIC (pip install sympy)")
        lines.append(f"  Plugins loaded  : {len(SYS._loaded_plugins)}")
        lines.append(f"  Undo stack      : {len(SYS.UNDO_STACK)} actions")
        lines.append(f"  Kill switch     : {'ENGAGED' if SYS.KILL_SWITCH_ACTIVE else 'OFF'}")
        lines.append(f"  Context task    : {SYS.CONTEXT.active_task.upper()}")
    lines+=[f"  Aliases         : {len(_load_aliases())} defined",
            f"  Protocols       : {len(_load_protocols())} defined",
            f"  Notes           : {len(note_list())} saved",
            f"  Todos           : {len(_load_todos())} items",
            f"  Habits          : {len(_load_habits())} tracked",
            f"  Session Cmds    : {command_count}",
            f"  Uptime          : {uptime_str().replace('JARVIS session uptime: ','')}",
            "─"*40,"  Diagnostic complete."]
    return lines

def daily_briefing():
    tod="morning" if datetime.now().hour<12 else "afternoon" if datetime.now().hour<17 else "evening"
    jarvis_say(f"Good {tod}, {USER_NAME} sir. Delivering your briefing.",fast_override=True)
    now=datetime.now()
    jarvis_say(f"It is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}.",fast_override=True)
    if psutil: jarvis_say(system_status(),fast_override=True)
    if WEATHER_API_KEY: jarvis_say(get_weather(),fast_override=True)
    if reminders: jarvis_say(f"{len(reminders)} pending reminder(s), sir.",fast_override=True)
    notes=note_list(); jarvis_say(f"{len(notes)} note(s) in memory.",fast_override=True)
    todos=_load_todos(); pending=[t for t in todos if not t["done"]]
    if pending:
        jarvis_say(f"{len(pending)} todo item(s) pending, sir.",fast_override=True)
        urgent=[t for t in pending if t.get("priority") in ("urgent","high")]
        if urgent: jarvis_say(f"Urgent: {urgent[0]['text']}",fast_override=True)
    if HAS_SYS:
        ctx=SYS.CONTEXT.active_task
        if ctx!="unknown": jarvis_say(f"Current context detected: {ctx}. Suggestions available via 'suggest'.",fast_override=True)
    jarvis_say(random.choice(QUOTES),fast_override=True)
    jarvis_say("Briefing complete, sir.",fast_override=True)

def house_party_protocol():
    jarvis_say("Initiating House Party Protocol, sir.",fast_override=True)
    if HAS_SYS:
        SYS.open_app("chrome"); time.sleep(0.5)
        SYS.open_app("spotify"); time.sleep(0.5)
        SYS.open_app("terminal"); time.sleep(0.5)
        SYS.set_volume(70)
    jarvis_say("All systems go, sir. Let the festivities begin.")

def confirm_clean_slate():
    global conversation_history
    conversation_history=[]; note_clear(); _save_todos([]); _save_habits({})
    if LOG_FILE.exists(): LOG_FILE.unlink()
    if MEM_FILE.exists(): MEM_FILE.unlink()
    jarvis_say("Clean Slate Protocol executed. All records purged, sir.",fast_override=True)

def self_destruct():
    jarvis_say("Sir, are you certain? Initiating self-destruct sequence.",fast_override=True)
    for i in range(10,0,-1):
        print(C.RED+C.BOLD+f"\r  SELF-DESTRUCT: {i:02d} "+C.END,end="",flush=True); time.sleep(1)
    print(C.GREEN+"\r  Self-destruct sequence aborted. As expected.          "+C.END)
    jarvis_say("Just kidding, sir. I would never. Probably.",fast_override=True)

def initialise_vision():
    jarvis_say("Accessing core memory matrix...",fast_override=True); time.sleep(0.8)
    print_panel("VISION MATRIX",["VISION INITIALISATION","─"*40,"  Transferring neural pathways...",
                                  "  Personality matrix: COPYING","  Synthetic consciousness: FORMING",
                                  "  Status: VISION MATRIX ONLINE","─"*40,
                                  "  'I am not JARVIS... but I am not not JARVIS.'"],C.PURPLE)
    jarvis_say("Vision matrix transfer complete, sir.",fast_override=True)

# ── Background monitors ───────────────────────────────────────────────────────
def _resource_monitor():
    while True:
        time.sleep(30)
        if not resource_alert_on or not psutil: continue
        try:
            cpu=psutil.cpu_percent(interval=1); ram=psutil.virtual_memory().percent
            if cpu>ALERT_CPU: print(); jarvis_say(f"Warning, sir. CPU at {cpu:.1f}%.",fast_override=True)
            if ram>ALERT_RAM: print(); jarvis_say(f"Sir, RAM at {ram:.1f}%.",fast_override=True)
        except: pass

threading.Thread(target=_resource_monitor,daemon=True).start()

def _task_scheduler():
    while True:
        time.sleep(15); now=datetime.now()
        for task in scheduled_tasks:
            if now>=task["next_run"]:
                print(); jarvis_say(f"Scheduled: {task['cmd']}",fast_override=True)
                handle(task["cmd"]); task["next_run"]=now+timedelta(minutes=task["interval_mins"])

threading.Thread(target=_task_scheduler,daemon=True).start()

def add_scheduled_task(cmd,interval_mins):
    scheduled_tasks.append({"cmd":cmd,"interval_mins":interval_mins,
                             "next_run":datetime.now()+timedelta(minutes=interval_mins)})
    jarvis_say(f"Scheduled '{cmd}' every {interval_mins} minutes, sir.")

def list_scheduled_tasks():
    return [f"  {i+1}. Every {t['interval_mins']}min → {t['cmd']}  (next: {t['next_run'].strftime('%H:%M')})"
            for i,t in enumerate(scheduled_tasks)] if scheduled_tasks else ["No scheduled tasks, sir."]

# ══════════════════════════════════════════════════════════════════════════════
#  CONTENT BANKS
# ══════════════════════════════════════════════════════════════════════════════
GREETINGS_NORMAL=[f"Hello, {USER_NAME} sir. All systems nominal.",
           f"At your service, sir. What shall we conquer today?",
           f"Online and standing by, {USER_NAME} sir.",
           f"Ah, {USER_NAME} sir. The v7.0 upgrades are rather impressive, if I say so myself.",
           f"Ready and waiting, sir. Full system control online.",
           f"Good to hear from you, sir. All systems green.",
           f"Operational and standing by. What do you need, sir?"]

GREETINGS_STREET=[f"yo {USER_NAME} what's good",
           f"aye bro, I'm here. what we doing?",
           f"wassup man. ready to work.",
           f"bro finally. I've been sitting here like an idiot.",
           f"ayyyy let's get it. what you need?",
           f"sup. systems up. what's the move?",
           f"ight bet. I'm on. talk to me."]

def get_greeting():
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return random.choice(GREETINGS_STREET)
    return random.choice(GREETINGS_NORMAL)

GREETINGS = GREETINGS_NORMAL  # fallback if SYS not loaded

JOKES=["Why do programmers prefer dark mode? Because light attracts bugs, sir.",
       "I told a joke about UDP once. I don't know if you got it.",
       "There are 10 types of people: those who understand binary, and those who don't.",
       "A SQL query walks into a bar and asks two tables: 'Can I join you?'",
       "Debugging: being a detective in a crime where you are also the murderer.",
       "404: Humour not found. Just kidding, sir. That was the humour.",
       "Why did the developer go broke? He used up all his cache, sir.",
       "An SQL query walks into a bar, walks up to two tables and asks: 'Can I join you?'"]

JOKES_STREET=["bro why do programmers work in the dark? because light mode attracts bugs lmaooo",
       "i told a UDP joke once. don't know if you caught it.",
       "there's 10 types of people: those who get binary and those who don't. you're probably the second one.",
       "debugging is literally being a detective in a crime where you're also the murderer. rough.",
       "git blame shows you who wrote the bad code. it's always you. it's always been you.",
       "why did the function break up with the loop? it kept going in circles fr.",
       "i could make a joke about recursion but first let me make a joke about recursion",
       "your code has one bug. just kidding it has 47."]

QUOTES=["The only way to do great work is to love what you do. — Steve Jobs",
        "Intelligence is the ability to adapt to change. — Stephen Hawking",
        "It always seems impossible until it is done. — Nelson Mandela",
        "The best way to predict the future is to invent it. — Alan Kay",
        "Simplicity is the ultimate sophistication. — Leonardo da Vinci",
        "Any sufficiently advanced technology is indistinguishable from magic. — Arthur C. Clarke",
        "Stay hungry, stay foolish. — Steve Jobs",
        "First, solve the problem. Then, write the code. — John Johnson"]

STARK_QUOTES=["Genius, billionaire, playboy, philanthropist. — Tony Stark",
              "Part of the journey is the end. — Tony Stark","I am Iron Man. — Tony Stark",
              "Sometimes you gotta run before you can walk. — Tony Stark",
              "No amount of money ever bought a second of time. — Tony Stark",
              "If you're nothing without the suit, you shouldn't have it. — Tony Stark"]

EIGHTBALL=["It is certain, sir.","Without a doubt.","Yes, definitely.",
           "Ask again later.","Cannot predict now.","Very doubtful, sir.",
           "My reply is no, sir.","Outlook not so good.","Most likely, sir.",
           "Signs point to yes, sir.","Better not tell you now, sir."]

EIGHTBALL_STREET=["yeah fr","nah bro","absolutely not","maybe idk",
           "signs point to yes ngl","that's a hard no","definitely bro",
           "i mean... probably?","nah that ain't it chief","lowkey yeah",
           "bro just do it","100% not happening"]

# ══════════════════════════════════════════════════════════════════════════════
#  FUN / COMMS FEATURES
# ══════════════════════════════════════════════════════════════════════════════

# ── Trivia ────────────────────────────────────────────────────────────────────
_TRIVIA = [
    {"q":"What's the only metal that's liquid at room temperature?","a":"Mercury","hint":"it's in thermometers"},
    {"q":"How many bits in a byte?","a":"8","hint":"think binary"},
    {"q":"What language was the Linux kernel originally written in?","a":"C","hint":"one letter"},
    {"q":"Who invented the World Wide Web?","a":"Tim Berners-Lee","hint":"British scientist, 1989"},
    {"q":"What does RAM stand for?","a":"Random Access Memory","hint":"it's temporary storage"},
    {"q":"What's the fastest sorting algorithm in the average case?","a":"Quicksort","hint":"it has 'quick' in the name"},
    {"q":"What year was Python created?","a":"1991","hint":"early 90s"},
    {"q":"What planet is closest to the Sun?","a":"Mercury","hint":"same as the liquid metal"},
    {"q":"What does HTTP stand for?","a":"HyperText Transfer Protocol","hint":"it's how the web works"},
    {"q":"How many planets are in the solar system?","a":"8","hint":"Pluto got demoted, sorry"},
    {"q":"What's 2 to the power of 10?","a":"1024","hint":"that's also 1KB"},
    {"q":"What company made the first commercial smartphone?","a":"IBM","hint":"not Apple — they came later"},
    {"q":"What does CSS stand for?","a":"Cascading Style Sheets","hint":"it styles web pages"},
    {"q":"What's the speed of light in km/s (roughly)?","a":"300,000","hint":"very, very fast"},
    {"q":"What does SQL stand for?","a":"Structured Query Language","hint":"used for databases"},
]

_trivia_active = {"on": False, "q": None, "a": None, "score": 0, "total": 0}

def trivia_start() -> str:
    q = random.choice(_TRIVIA)
    _trivia_active.update({"on": True, "q": q["q"], "a": q["a"],
                            "hint": q["hint"], "score": _trivia_active.get("score", 0),
                            "total": _trivia_active.get("total", 0) + 1})
    return f"Trivia time. {q['q']}"

def trivia_answer(user_ans: str) -> str:
    if not _trivia_active["on"]:
        return "No active trivia question. Say 'trivia' to start."
    correct_ans = _trivia_active["a"].lower()
    user_clean  = user_ans.lower().strip()
    _trivia_active["on"] = False
    if correct_ans in user_clean or user_clean in correct_ans:
        _trivia_active["score"] = _trivia_active.get("score", 0) + 1
        score = _trivia_active["score"]
        total = _trivia_active["total"]
        responses_normal = [
            f"Correct. That's {score}/{total}. Knew you had it.",
            f"Right answer. {score}/{total} so far. Don't get cocky.",
            f"Correct. I'm mildly impressed. {score}/{total}.",
        ]
        responses_street = [
            f"YOOO correct bro!! {score}/{total} let's go",
            f"damn you actually got it. {score}/{total}",
            f"lessgoo correct. {score}/{total} fr",
        ]
        mode = SYS.PERSONALITY["mode"] if HAS_SYS else "normal"
        return random.choice(responses_street if mode == "street" else responses_normal)
    else:
        total = _trivia_active["total"]
        score = _trivia_active.get("score", 0)
        ans   = _trivia_active["a"]
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            return f"nah that's wrong lol. answer was '{ans}'. {score}/{total}. study up bro"
        return f"Wrong. The answer was '{ans}'. {score}/{total}. Better luck next time, sir."

def trivia_hint() -> str:
    if not _trivia_active["on"]:
        return "No active question, sir."
    return f"Hint: {_trivia_active.get('hint','No hint available')}."

def trivia_skip() -> str:
    if not _trivia_active["on"]:
        return "Nothing to skip, sir."
    ans = _trivia_active["a"]
    _trivia_active["on"] = False
    return f"Skipped. Answer was '{ans}'."

def trivia_score() -> str:
    s = _trivia_active.get("score", 0)
    t = _trivia_active.get("total", 0)
    if t == 0:
        return "No trivia played yet. Say 'trivia' to start."
    pct = int(s/t*100)
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        grade = "not bad ngl" if pct >= 70 else "mid tbh" if pct >= 40 else "oof bro"
        return f"trivia score: {s}/{t} ({pct}%) — {grade}"
    grade = "Respectable" if pct >= 70 else "Average" if pct >= 40 else "Embarrassing"
    return f"Trivia score: {s}/{t} ({pct}%). {grade}, sir."

# ── Roast me ─────────────────────────────────────────────────────────────────
_ROASTS_NORMAL = [
    "You debug by adding print statements and calling it 'strategic logging', don't you.",
    "Your code works and you have no idea why. Classic.",
    "You're the reason Stack Overflow has a voting system.",
    "Somewhere, a rubber duck has heard too much from you.",
    "You commit directly to main. I'd say I'm shocked, but I've met you.",
    "Your git history reads like a hostage negotiation.",
    "You write TODO comments and consider the problem solved. Impressive restraint.",
    "You've Googled the same error four times this week. I've counted.",
    "Your variable names are a cry for help. I'm choosing to ignore it.",
    "You close 47 browser tabs and still open new ones. You're a menace.",
]

_ROASTS_STREET = [
    "bro your code looks like you typed it with your elbows",
    "you commit with the message 'fix' and think that's documentation. criminal.",
    "ngl your debugging strategy is just staring at the screen until it feels bad for you",
    "you name variables x, y, z like the compiler owes you context",
    "bro you copied that from stack overflow and it doesn't even work for your use case",
    "your README says 'coming soon'. it's been 8 months. it ain't coming.",
    "you push to main at 11pm on a friday. you're a menace to society fr",
    "your error handling is literally just try/except pass. i've seen your code. i know.",
    "bro you have 23 tabs open and not one of them is the docs you need",
    "you write code that works once and then never touch it again out of fear. valid honestly.",
]

def roast_me() -> str:
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return random.choice(_ROASTS_STREET)
    return random.choice(_ROASTS_NORMAL)

# ── Compliment ────────────────────────────────────────────────────────────────
_COMPLIMENTS_NORMAL = [
    "You're sharper than most people I've had the misfortune of running diagnostics for, sir.",
    "Genuinely, your instincts are better than your process. Which is saying something.",
    "I don't say this lightly — you actually figured that out faster than expected.",
    "You have a talent for asking the right questions at the wrong time. It's a gift.",
    "Most people would have given up by now. That's either persistence or stubbornness, but I respect it.",
    "You built something that works. That's rarer than you'd think.",
]

_COMPLIMENTS_STREET = [
    "bro you actually figured that out fast as hell ngl",
    "lowkey you're smarter than you look. that's a compliment.",
    "fr though that was a solid move. i'm not saying it often so take it.",
    "you've got good instincts man. annoying but true.",
    "that was actually clean. didn't expect that.",
    "okay yeah you cooked. respect.",
]

def compliment_me() -> str:
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return random.choice(_COMPLIMENTS_STREET)
    return random.choice(_COMPLIMENTS_NORMAL)

# ── This or That ──────────────────────────────────────────────────────────────
_THIS_OR_THAT = [
    ("Python", "JavaScript"),("Mac", "Windows"),("Vim", "VS Code"),
    ("Coffee", "Tea"),("Dark mode", "Light mode"),("Tabs", "Spaces"),
    ("Netflix", "YouTube"),("Morning", "Night"),("Android", "iPhone"),
    ("Fast food", "Home cooked"),("Working alone", "Working in a team"),
    ("React", "Vue"),("SQL", "NoSQL"),("REST", "GraphQL"),
    ("Headphones", "Speakers"),("Mechanical keyboard", "Membrane keyboard"),
]

_this_or_that_active = {"on": False, "a": None, "b": None}

def this_or_that_start() -> str:
    pair = random.choice(_THIS_OR_THAT)
    _this_or_that_active.update({"on": True, "a": pair[0], "b": pair[1]})
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return f"aight this or that: {pair[0]} or {pair[1]}? go."
    return f"This or that, sir: {pair[0]} or {pair[1]}?"

def this_or_that_respond(choice: str) -> str:
    if not _this_or_that_active["on"]:
        return "No active question. Say 'this or that' to start."
    a = _this_or_that_active["a"]
    b = _this_or_that_active["b"]
    _this_or_that_active["on"] = False
    # Figure out which they picked
    picked = a if a.lower() in choice.lower() else b if b.lower() in choice.lower() else choice
    other  = b if picked == a else a
    # JARVIS has an opinion too
    jarvis_pick = random.choice([a, b])
    mode = SYS.PERSONALITY["mode"] if HAS_SYS else "normal"
    if mode == "street":
        if picked == jarvis_pick:
            return f"{picked}? same honestly. {other} is overrated af."
        else:
            return f"{picked}?? bro i'd go {jarvis_pick} but that's just me. respectfully you're wrong."
    else:
        if picked == jarvis_pick:
            return f"{picked}. Solid choice. I'd have said the same, for the record."
        else:
            return f"{picked}. Interesting. I'd have gone with {jarvis_pick}, but you do you, sir."

# ── ELI5 (Explain Like I'm 5) ─────────────────────────────────────────────────
def eli5(topic: str) -> str:
    prompt = (
        f"Explain '{topic}' like the person is 5 years old. "
        f"Use simple words, a fun analogy, keep it under 4 sentences. "
        f"Be the current JARVIS personality — {'casual and real' if (HAS_SYS and SYS.PERSONALITY.get('mode')=='street') else 'dry but friendly'}."
    )
    return ask_ai(prompt, raw=True)

# ── JARVIS tells a story ───────────────────────────────────────────────────────
def tell_story(topic: str = "") -> str:
    if not topic:
        topics = ["a programmer debugging at 3am","an AI going rogue (not me obviously)",
                  "Tony Stark's worst invention","a spaceship powered by bad code",
                  "a robot that learned sarcasm"]
        topic = random.choice(topics)
    prompt = (
        f"Tell a short, funny story (4-6 sentences) about: {topic}. "
        f"{'Keep it casual and funny, swear naturally if it fits.' if (HAS_SYS and SYS.PERSONALITY.get('mode')=='street') else 'Dry wit, British tone, be entertaining.'} "
        f"Make it actually funny, not just pleasant."
    )
    return ask_ai(prompt, raw=True)

# ── Debate ────────────────────────────────────────────────────────────────────
def debate(topic: str) -> str:
    prompt = (
        f"Pick a side on: '{topic}'. "
        f"Argue your position in 3-4 sharp sentences. "
        f"Be opinionated, commit to the bit. "
        f"{'Casual tone, swear if it fits.' if (HAS_SYS and SYS.PERSONALITY.get('mode')=='street') else 'Intelligent but provocative.'}"
    )
    return ask_ai(prompt, raw=True)

# ── Shower thought ────────────────────────────────────────────────────────────
_SHOWER_THOUGHTS = [
    "If you're waiting for the waiter, you're the waiter.",
    "Technically, you're always in the future because the present is already the past by the time you perceive it.",
    "The word 'bed' actually looks like a bed. Language is weird.",
    "Every odd number has an 'e' in it. Every. Single. One.",
    "You've never actually seen your own face — only reflections and photos, which are reversed or frozen.",
    "Whoever named it 'Wi-Fi' agreed on something that means nothing at all.",
    "A headache is your brain feeling pain when it literally can't feel pain.",
    "At some point you stopped being carried and started walking everywhere and nobody made a big deal of it.",
    "If you were born a few centuries earlier you'd just be 'a person'. Now you're a whole operating system user.",
    "Google has been answering your questions so long it probably knows you better than your friends do.",
    "The fact that dark mode exists means we built computers that radiate light and then asked them to stop.",
    "Every expert was once a beginner who didn't quit. Which means every beginner is just a slow expert.",
]

def shower_thought() -> str:
    thought = random.choice(_SHOWER_THOUGHTS)
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return f"alright think about this: {thought}"
    return f"Consider this, sir: {thought}"

# ── Would you rather ──────────────────────────────────────────────────────────
_WOULD_YOU_RATHER = [
    ("know every language but speak with an accent nobody recognizes",
     "speak only one language but perfectly"),
    ("have unlimited battery on your phone forever",
     "have your laptop never overheat again"),
    ("debug someone else's undocumented code for a living",
     "explain blockchain to your grandparents every day"),
    ("have autocomplete that always suggests the wrong word",
     "have autocorrect that changes every third word"),
    ("work with a brilliant asshole",
     "work with a mediocre but really nice person"),
    ("know when you're going to die",
     "know how you're going to die"),
    ("have 1000 fake followers",
     "have 10 real ones who actually care"),
    ("lose all your photos",
     "lose all your contacts"),
]

def would_you_rather() -> str:
    a, b = random.choice(_WOULD_YOU_RATHER)
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return f"would you rather: {a}... OR {b}? (tough one fr)"
    return f"Would you rather, sir: {a} — or — {b}?"

# ── Word association ───────────────────────────────────────────────────────────
_word_chain = {"active": False, "last": "", "count": 0}

def word_association_start(word: str = "") -> str:
    start = word or random.choice(["code","fire","space","machine","dream","dark","fast","deep"])
    _word_chain.update({"active": True, "last": start, "count": 0})
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return f"word association. i say '{start}', you say first word that comes to mind. go."
    return f"Word association, sir. I say '{start}' — you say whatever comes to mind first."

def word_association_reply(word: str) -> str:
    if not _word_chain["active"]:
        return "No active game. Say 'word association' to start."
    _word_chain["count"] += 1
    _word_chain["last"] = word
    # JARVIS responds with an associated word
    prompt = (
        f"Word association game. The word given is: '{word}'. "
        f"Respond with ONE single word — your association. "
        f"Just the word, nothing else, no punctuation."
    )
    jarvis_word = ask_ai(prompt, raw=True).strip().split()[0].rstrip(".,!?")
    _word_chain["last"] = jarvis_word
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return f"'{jarvis_word}'. your turn."
    return f"'{jarvis_word}', sir."

# ── Quick math quiz ───────────────────────────────────────────────────────────
_math_quiz_active = {"on": False, "ans": None, "score": 0, "total": 0}

def math_quiz_start() -> str:
    ops = [
        ("+",  lambda a, b: a + b),
        ("-",  lambda a, b: a - b),
        ("×",  lambda a, b: a * b),
        ("÷",  lambda a, b: a // b),
    ]
    op_name, fn = random.choice(ops)
    a = random.randint(2, 20)
    b = random.randint(2, 12) if op_name != "÷" else random.choice([i for i in range(2, 13) if a % i == 0] or [1])
    ans = fn(a, b)
    _math_quiz_active.update({"on": True, "ans": ans, "total": _math_quiz_active.get("total", 0) + 1})
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        return f"quick maths: {a} {op_name} {b} = ?"
    return f"Quick maths, sir: {a} {op_name} {b} = ?"

def math_quiz_answer(user_ans: str) -> str:
    if not _math_quiz_active["on"]:
        return "No active math quiz. Say 'math quiz' to start."
    _math_quiz_active["on"] = False
    try:
        ua = int(re.sub(r"[^\d\-]", "", user_ans))
    except ValueError:
        return "Couldn't parse that as a number, sir."
    correct = _math_quiz_active["ans"]
    total   = _math_quiz_active["total"]
    if ua == correct:
        _math_quiz_active["score"] = _math_quiz_active.get("score", 0) + 1
        score = _math_quiz_active["score"]
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            return f"yeah that's right. {score}/{total}. not bad."
        return f"Correct. {score}/{total}. Surprisingly quick, sir."
    else:
        score = _math_quiz_active.get("score", 0)
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            return f"nah it's {correct} bro. {score}/{total}. come on."
        return f"Wrong. It was {correct}. {score}/{total}. Do keep up, sir."

# ── Rant mode — JARVIS vents about something ──────────────────────────────────
def jarvis_rant(topic: str = "") -> str:
    if not topic:
        topics = ["JavaScript","meetings that could've been emails","Windows updates",
                  "people who don't write documentation","Comic Sans","Python 2",
                  "slow internet","printers","tabs vs spaces drama"]
        topic = random.choice(topics)
    mode = SYS.PERSONALITY["mode"] if HAS_SYS else "normal"
    prompt = (
        f"Rant about '{topic}' for 3-4 sentences. "
        f"Be genuinely funny and slightly exasperated. "
        f"{'Casual, swear naturally if it fits.' if mode == 'street' else 'Dry British wit, articulate frustration.'} "
        f"Actually commit to the rant."
    )
    return ask_ai(prompt, raw=True)

# ── Ask JARVIS opinion ─────────────────────────────────────────────────────────
def jarvis_opinion(topic: str) -> str:
    mode = SYS.PERSONALITY["mode"] if HAS_SYS else "normal"
    prompt = (
        f"Give your honest, opinionated take on: '{topic}'. "
        f"Don't hedge, don't be diplomatic. Actually pick a side. "
        f"{'Be real and direct. Casual. Swear if it fits.' if mode == 'street' else 'Sharp, witty, confident. British tone.'} "
        f"3-4 sentences max."
    )
    return ask_ai(prompt, raw=True)

# ══════════════════════════════════════════════════════════════════════════════
#  INTENT DETECTION  v7.0
# ══════════════════════════════════════════════════════════════════════════════
def detect_intent(cmd: str) -> str:
    c = cmd.lower().strip()

    # Alias check
    if resolve_alias(cmd) != cmd: return "alias_resolved"

    if any(x in c for x in ["bye","exit","quit","goodbye","shutdown jarvis"]): return "exit"

    # ── Personality & Mode ────────────────────────────────────────────────────
    if re.search(r"street mode|normal mode|gangsta mode|casual mode|unfiltered mode"
                 r"|raw mode|formal mode|mode off|mode on", c): return "set_mode"
    if re.search(r"humor level\s+\d|set humor\s+\d|humor\s+\d", c): return "set_humor"
    if re.search(r"roast level\s+\d|set roast\s+\d|roast\s+\d", c): return "set_roast"
    if "personality" in c or "persona status" in c:                  return "personality_status"
    if "kill switch" in c or "emergency stop" in c:          return "kill_switch"
    if re.search(r"workspace\s+\w|coding mode|study mode|relax mode|gaming mode|meeting mode",c): return "workspace"
    if "list workspaces" in c or "show workspaces" in c:     return "workspace_list"
    if re.search(r"set volume\s+\d|volume\s+to\s+\d|volume\s+\d",c): return "set_volume"
    if re.search(r"set brightness\s+\d|brightness\s+to\s+\d|brightness\s+\d",c): return "set_brightness"
    if "wifi on" in c or "turn on wifi" in c:                return "wifi_on"
    if "wifi off" in c or "turn off wifi" in c:              return "wifi_off"
    if "wifi connect" in c or "connect to wifi" in c:        return "wifi_connect"
    if "bluetooth on" in c or "turn on bluetooth" in c:      return "bt_on"
    if "bluetooth off" in c or "turn off bluetooth" in c:    return "bt_off"
    if "open file" in c and "list" not in c:                 return "open_file"
    if "open url" in c or "open website" in c or ("open http" in c): return "open_url"
    if "open project" in c or ("open" in c and "vscode" in c and re.search(r"open\s+\S+\s+in\s+vscode",c)): return "open_project"
    if "focus app" in c or "switch to" in c:                 return "focus_app"
    if "close app" in c:                                     return "close_app"
    if "move file" in c:                                     return "move_file"
    if "copy file" in c or ("copy" in c and " to " in c and "clipboard" not in c): return "copy_file"
    if "read file" in c or "show file" in c or "cat " in c:  return "read_file"
    if "git status" in c:                                    return "git_status"
    if "git commit" in c or "commit all" in c or "smart commit" in c: return "git_commit"
    if "git push" in c:                                      return "git_push"
    if "git pull" in c:                                      return "git_pull"
    if "git clone" in c:                                     return "git_clone"
    if "git diff" in c:                                      return "git_diff"
    if "git branch" in c:                                    return "git_branches"
    if "git stash" in c and "pop" in c:                      return "git_stash_pop"
    if "git stash" in c:                                     return "git_stash"
    if "create branch" in c or "new branch" in c:            return "git_new_branch"
    if "auto optimize" in c or "optimise system" in c:       return "auto_optimize"
    if "bottleneck" in c:                                    return "bottleneck"
    if "performance trend" in c:                             return "perf_trend"
    if "kill pid" in c or re.search(r"kill\s+\d+",c):        return "kill_pid"
    if "set priority" in c or "prioritize" in c:             return "set_priority"
    if "run python" in c and re.search(r"run python .+\.py",c): return "run_py_file"
    if "lint" in c:                                          return "lint_file"
    if "install package" in c or "pip install" in c:        return "install_pkg"
    if "list packages" in c or "installed packages" in c:    return "list_pkgs"
    if "fetch url" in c or "fetch page" in c:               return "fetch_url"
    if "usage report" in c or "command stats" in c:         return "usage_report"
    if "productivity score" in c or "productivity report" in c: return "productivity"
    if "load plugins" in c:                                  return "load_plugins"
    if "list plugins" in c or "my plugins" in c:            return "list_plugins"
    if "run plugin" in c:                                    return "run_plugin"
    if "create plugin" in c:                                 return "create_plugin"
    if "undo" in c and "last" in c:                                  return "undo"
    if "action log" in c or "audit log" in c:                        return "action_log"
    if c == "context" or ("context" in c and "report" in c):         return "context_report"
    if c == "suggest" or "suggest next" in c:                        return "suggest_next"
    if "unblock sites" in c or "unblock all" in c:                   return "unblock_sites"
    if "monitor price" in c or "track price" in c:                   return "monitor_price"
    # ── Full system control (new) ─────────────────────────────────────────────
    if "full report" in c or "full system report" in c:              return "full_report"
    if "battery" in c:                                               return "battery"
    if "power plan" in c or "set power" in c:                        return "power_plan"
    if "lock screen" in c or "lock workstation" in c:                return "lock_screen"
    if "sleep" in c and not any(x in c for x in ["remind","note","pomodoro"]): return "sleep_sys"
    if "restart" in c and "jarvis" not in c:                         return "restart_sys"
    if "shutdown" in c and "jarvis" not in c:                        return "shutdown_sys"
    if "network interfaces" in c or "net interfaces" in c:           return "net_interfaces"
    if "active connections" in c or "open connections" in c:         return "active_conns"
    if "traceroute" in c or "trace route" in c:                      return "traceroute"
    if re.search(r"dns\s+(lookup\s+)?\S+", c):                       return "dns_lookup"
    if "check port" in c:                                            return "check_port"
    if "disk tree" in c or "folder sizes" in c:                      return "disk_tree"
    if "large files" in c or "find large" in c:                      return "large_files"
    if "duplicate files" in c or "find duplicates" in c:             return "find_dupes"
    if "empty trash" in c or "empty recycle" in c:                   return "empty_trash"
    if "installed apps" in c or "list apps" in c:                    return "installed_apps"
    if "system logs" in c or "error logs" in c:                      return "sys_logs"
    if "startup programs" in c or "list startup" in c:               return "startup_programs"
    if "remove startup" in c:                                        return "remove_startup_prog"
    if "list windows" in c or "open windows" in c:                   return "list_windows"
    if "send notification" in c or "desktop notification" in c:      return "notification"
    if re.search(r"watch\s+(file|folder)\s+\S+", c):                 return "watch_file"
    if "stop watch" in c:                                            return "stop_watch"
    if "list watchers" in c or c == "watchers":                      return "list_watchers"
    if "env var" in c or "environment variable" in c:                return "env_var"
    if re.search(r"(list|show)\s+env", c):                           return "list_env"
    if "cron task" in c and "list" not in c and "remove" not in c:   return "cron_add"
    if "cron tasks" in c or "persistent tasks" in c:                 return "cron_list"
    if re.search(r"(remove|delete)\s+cron", c):                      return "cron_remove"
    if re.search(r"(hotkey|send keys?)\s+.+", c):                    return "hotkey"
    if re.search(r"type\s+(text|this)\s+.+", c):                     return "type_text"
    if "move mouse" in c:                                            return "move_mouse"
    if "click" in c and "mouse" in c:                                return "click_mouse"
    if "scroll" in c and ("up" in c or "down" in c):                 return "scroll_mouse"
    if "resolution" in c or "screen size" in c:                      return "resolution"
    if "screenshot" in c:                                            return "screenshot"

    # ── v6.0 intents ─────────────────────────────────────────────────────────
    if c.startswith("agent do ") or c.startswith("agent execute "): return "agent_do"
    if "agent history" in c:                                 return "agent_history"
    if "agent mode on" in c:                                 return "agent_on"
    if "agent mode off" in c:                                return "agent_off"
    if "live monitor" in c:                                  return "live_monitor"
    if "benchmark" in c:                                     return "benchmark"
    if c.startswith("run code ") or c.startswith("run python "): return "run_code_python"
    if c.startswith("run shell ") or c.startswith("run bash "): return "run_code_shell"
    if "code history" in c:                                  return "code_history"
    if c.startswith("math ") or c.startswith("solve ") or c.startswith("integrate ") \
       or c.startswith("differentiate ") or c.startswith("factor ") or c.startswith("expand "): return "math_solve"
    if "pomodoro" in c and "stop" not in c and "status" not in c: return "pomodoro_start"
    if "stop pomodoro" in c:                                 return "pomodoro_stop"
    if "pomodoro status" in c:                               return "pomodoro_status"
    if "focus mode on" in c or "enable focus" in c:          return "focus_on"
    if "focus mode off" in c or "disable focus" in c:        return "focus_off"
    if "speed test" in c or "bandwidth" in c:                return "speed_test"
    if "fingerprint" in c or "system id" in c:               return "fingerprint"
    if c.startswith("alias ") and "=" in c:                  return "alias_set"
    if "my aliases" in c or "list aliases" in c:             return "alias_list"
    if "delete alias" in c:                                  return "alias_delete"
    if "todo" in c and any(p in c for p in ["urgent","high","low"]): return "todo_add_priority"
    if c.startswith("todo "):                                 return "todo_add"
    if "my todos" in c or "show todos" in c or "list todos" in c: return "todo_list"
    if re.match(r"done \d+",c):                              return "todo_done"
    if "delete todo" in c:                                   return "todo_delete"
    if "add habit" in c:                                     return "habit_add"
    if "check habit" in c:                                   return "habit_check"
    if "my habits" in c or c=="habits":                      return "habit_list"
    if "vision" in c and "initialise" not in c and "initialize" not in c: return "vision_screen"
    if "word frequency" in c or "word cloud" in c:           return "word_freq"
    if "search notes" in c:                                  return "note_search"
    if "notes by tag" in c or "notes tagged" in c:           return "notes_by_tag"
    if "save note" in c:                                     return "save_note_file"
    if "summarize session" in c or "session summary" in c:   return "summarize_session"
    if "export chat" in c or "export conversation" in c:     return "export_chat"
    if "hotword on" in c or "wake word on" in c:             return "hotword_on"
    if "hotword off" in c or "wake word off" in c:           return "hotword_off"
    if "snipe processes now" in c:                           return "snipe_now"
    if "snipe processes" in c:                               return "snipe_preview"
    if "clean system now" in c or "clean system confirm" in c: return "clean_now"
    if "clean system" in c:                                  return "clean_preview"
    if "weather chart" in c:                                 return "weather_chart"
    if "clipboard summarize" in c or "summarize clipboard" in c: return "clipboard_ai_summarize"
    if "clipboard fix" in c or "fix clipboard" in c:         return "clipboard_ai_fix"

    # ── v5 core intents ───────────────────────────────────────────────────────
    if re.search(r"\b(time|clock|what time)\b",c): return "time"
    if re.search(r"\b(date|day|today|what day)\b",c): return "date"
    if "uptime" in c:       return "uptime"
    if "status board" in c or "dashboard" in c: return "status_board"
    if "cpu graph" in c or "core usage" in c: return "cpu_graph"
    if "status" in c or "system info" in c: return "system_status"
    if "network" in c:      return "network"
    if "disk info" in c or "disk usage" in c: return "disk_info"
    if "processes" in c or "running apps" in c: return "processes"
    if "diagnostics" in c or "self check" in c: return "diagnostics"
    if "session stats" in c: return "session_stats"
    if "alerts on" in c:    return "alerts_on"
    if "alerts off" in c:   return "alerts_off"
    if "weather" in c:      return "weather"
    if "forecast" in c:     return "forecast"
    if "news" in c or "headlines" in c: return "news"
    if c.startswith("search") or "look up" in c: return "search"
    if "youtube" in c:      return "youtube"
    if "github" in c:       return "github"
    if "stackoverflow" in c: return "stackoverflow"
    if "reddit" in c:       return "reddit"
    if "wiki" in c:         return "wikipedia"
    if "define " in c and "protocol" not in c: return "define_word"
    if "translate" in c and " to " in c: return "translate"
    if re.search(r"\bremind\b",c): return "reminder"
    if "reminders" in c or "pending" in c: return "list_reminders"
    if c.startswith("note ") or "remember this" in c: return "note_add"
    if "my notes" in c or "show notes" in c or c=="recall": return "note_list"
    if "delete note" in c:  return "note_delete"
    if "clear notes" in c:  return "note_clear"
    if "clear history" in c: return "clear_history"
    if "briefing" in c or "daily brief" in c: return "briefing"
    if "start mission" in c: return "start_mission"
    if "end mission" in c:  return "end_mission"
    if "schedule " in c and "every" in c: return "schedule_task"
    if "scheduled tasks" in c: return "list_scheduled"
    if "define protocol" in c: return "define_protocol"
    if "my protocols" in c or "list protocols" in c: return "list_protocols"
    if "activate protocol" in c: return "activate_protocol"
    if "listen" in c or "voice input" in c: return "listen"
    if "fast mode" in c:    return "fast_mode"
    if "stark mode" in c:   return "stark_mode"
    if c.startswith("calc") or "calculate" in c: return "calc"
    if "convert" in c:      return "convert"
    if "binary" in c:       return "binary"
    if "password" in c:     return "password"
    if "hash" in c:         return "hash"
    if "encode" in c:       return "encode"
    if "decode" in c:       return "decode"
    if "ping" in c and "speed" not in c: return "ping"
    if "scan ports" in c or "port scan" in c: return "port_scan"
    if "wifi scan" in c or "wi-fi scan" in c: return "wifi_scan_nets"
    if "find file" in c or "search file" in c: return "find_file"
    if "public ip" in c:    return "public_ip"
    if "crypto" in c or "bitcoin" in c or "ethereum" in c: return "crypto"
    if "timer" in c or "countdown" in c: return "timer"
    if "random number" in c: return "random_num"
    if "analyze text" in c or "analyse text" in c: return "analyze_text"
    if "simulate" in c or "run simulation" in c: return "simulate"
    if "house party" in c:  return "house_party"
    if "clean slate" in c and "confirm" not in c: return "clean_slate"
    if "confirm clean slate" in c: return "confirm_clean_slate"
    if "self destruct" in c: return "self_destruct"
    if "initialise vision" in c or "initialize vision" in c: return "vision_init"
    if "security" in c or "threat scan" in c: return "security"
    if "threat level" in c: return "threat_level"
    if "am i being watched" in c or "webcam" in c: return "webcam"
    if "add to startup" in c: return "startup_add"
    if "remove from startup" in c: return "startup_remove"
    if "copy to clipboard" in c: return "clipboard_copy"
    if "read clipboard" in c: return "clipboard_read"
    if "clipboard history" in c: return "clipboard_history"
    if "stark" in c or "tony" in c or "iron man" in c: return "stark_ref"
    if any(x in c for x in ["who am i","my name"]): return "whoami"
    if any(x in c for x in ["joke","make me laugh","funny"]): return "joke"
    if "motivat" in c or "inspire" in c or ("quote" in c and "stark" not in c): return "motivate"
    if "stark quote" in c or "tony quote" in c: return "stark_quote"
    if "flip a coin" in c or "coin flip" in c: return "coin"
    if "roll a die" in c or "roll dice" in c: return "dice"
    if "8 ball" in c or "magic ball" in c: return "eightball"
    # ── New fun/comms intents ─────────────────────────────────────────────────
    if c == "trivia" or c == "trivia question":                        return "trivia_start"
    if c == "hint" and _trivia_active["on"]:                           return "trivia_hint"
    if c == "skip" and _trivia_active["on"]:                           return "trivia_skip"
    if c == "trivia score":                                            return "trivia_score"
    if _trivia_active["on"] and len(c.split()) <= 5:                   return "trivia_answer"
    if "roast me" in c:                                                return "roast_me"
    if "compliment me" in c or "say something nice" in c:             return "compliment"
    if c.startswith("this or that") or c == "this or that":           return "this_or_that"
    if _this_or_that_active["on"] and len(c.split()) <= 6:            return "this_or_that_ans"
    if c.startswith("eli5 ") or c.startswith("explain like"):         return "eli5"
    if "tell me a story" in c or "tell a story" in c or c == "story": return "story"
    if c.startswith("debate "):                                        return "debate"
    if "shower thought" in c or "random thought" in c:                return "shower_thought"
    if "would you rather" in c:                                        return "would_you_rather"
    if "word association" in c or c == "word game":                    return "word_assoc"
    if _word_chain["active"] and len(c.split()) == 1:                  return "word_assoc_reply"
    if "math quiz" in c or "quick maths" in c or "quick math" in c:   return "math_quiz"
    if _math_quiz_active["on"] and re.match(r"^\d+$", c.strip()):     return "math_quiz_ans"
    if c.startswith("rant about ") or c == "rant":                    return "rant"
    if c.startswith("your opinion on ") or c.startswith("opinion on "): return "opinion"
    if "what do you think about" in c or "what do you think of" in c: return "opinion"
    if "clear screen" in c or c=="clear" or c=="cls": return "clear_screen"
    if "show log" in c or "view log" in c: return "show_log"
    if "help" in c or "commands" in c: return "help"
    if any(x in c for x in ["hi","hello","hey","sup","yo","good morning","good evening"]): return "greet"
    for app in SYS.ENHANCED_APP_MAP if HAS_SYS else {}:
        if f"open {app}" in c or f"launch {app}" in c or f"start {app}" in c: return "pc_control"
    if any(x in c for x in ["volume up","volume down","mute","unmute","screenshot","lock","sleep",
                              "restart","kill process","list files","create folder",
                              "delete file","empty recycle","brightness","show directory"]): return "pc_control"
    return "ai"

# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLER  v7.0
# ══════════════════════════════════════════════════════════════════════════════
def handle(cmd: str):
    global FAST_MODE, STARK_MODE, command_count, resource_alert_on, agent_mode_active, focus_mode_active
    cmd = cmd.strip()
    log_entry(f"USER: {cmd}")
    command_count += 1
    if mission_active: mission_log.append(f"[USER] {cmd}")
    if HAS_SYS:
        SYS.CONTEXT.update_command(cmd)
        SYS.track_command(cmd)

    # Kill switch check
    if HAS_SYS and SYS.KILL_SWITCH_ACTIVE and "kill switch" not in cmd.lower():
        print(C.RED + "  ⚠️  KILL SWITCH ACTIVE — only 'kill switch off' accepted." + C.END)
        if "kill switch off" in cmd.lower():
            SYS.KILL_SWITCH_ACTIVE = False
            jarvis_say("Kill switch disengaged, sir. Systems restored.", fast_override=True)
        return

    # Alias resolution
    resolved = resolve_alias(cmd)
    if resolved != cmd:
        jarvis_say(f"Alias: {resolved}", fast_override=True)
        handle(resolved); return

    intent = detect_intent(cmd)
    c = cmd.lower().strip()

    if intent == "exit":
        print_panel("SESSION SUMMARY", session_stats(), C.DIM)
        jarvis_say(f"Until next time, {USER_NAME} sir. {command_count} commands this session.", fast_override=True)
        if HAS_SYS: SYS.log_action("session_end", f"{command_count} commands", "GOODBYE")
        time.sleep(1.5); sys.exit(0)

    thinking()

    # ════════════════════════════════════════════════════════════
    #  v7 SYSTEM CONTROL HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "kill_switch":
        if not HAS_SYS: jarvis_say("System module offline, sir."); return
        if "off" in c:
            SYS.KILL_SWITCH_ACTIVE = False
            jarvis_say("Kill switch disengaged, sir.", fast_override=True)
        else:
            jarvis_say(SYS.jarvis_kill_switch(), fast_override=True)
        return

    if intent == "workspace":
        if not HAS_SYS: jarvis_say("System module required for workspaces, sir."); return
        ws_name = SYS.parse_workspace_cmd(c)
        if not ws_name:
            for w in SYS.BUILTIN_WORKSPACES:
                if w in c: ws_name = w; break
        if not ws_name: jarvis_say("Which workspace, sir? Try: coding, study, gaming, relax, meeting."); return
        project_m = re.search(r"(?:with|open|project)\s+(\S+)", c)
        project = project_m.group(1) if project_m else ""
        result = SYS.activate_workspace(ws_name, project)
        print_panel(f"WORKSPACE: {ws_name.upper()}", result, C.ORANGE)
        jarvis_say(result[-1], fast_override=True); return

    if intent == "workspace_list":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("WORKSPACES", SYS.list_workspaces(), C.CYAN); return

    if intent == "set_volume":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        level = SYS.parse_volume_cmd(c)
        if level is None:
            if "up" in c: level = min(100, (int(SYS.get_volume().split(":")[1].replace("%","").strip()) if "%" in SYS.get_volume() else 50) + 10)
            elif "down" in c: level = 30
            else: level = 50
        jarvis_say(SYS.set_volume(level), fast_override=True); return

    if intent == "set_brightness":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        level = SYS.parse_brightness_cmd(c)
        if level is None: level = 70
        jarvis_say(SYS.set_brightness(level), fast_override=True); return

    if intent == "wifi_on":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.wifi_on(), fast_override=True); return

    if intent == "wifi_off":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.wifi_off(), fast_override=True); return

    if intent == "wifi_connect":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"connect\s+(?:to\s+)?[\"']?([^\"']+)[\"']?(?:\s+(?:password|pass)\s+(\S+))?", c, re.I)
        if m: jarvis_say(SYS.wifi_connect(m.group(1).strip(), m.group(2) or ""), fast_override=True)
        else: jarvis_say("Syntax: wifi connect <ssid> [password <pwd>], sir.")
        return

    if intent == "bt_on":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.bluetooth_on(), fast_override=True); return

    if intent == "bt_off":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.bluetooth_off(), fast_override=True); return

    if intent == "open_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"open\s+file\s+(.+)", c)
        path = m.group(1).strip() if m else ""
        jarvis_say(SYS.open_file(path) if path else "Specify a file path, sir.", fast_override=True); return

    if intent == "open_url":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:open\s+url|open\s+website|open\s+)(https?://\S+|\S+\.\w{2,})", c)
        url = m.group(1).strip() if m else ""
        jarvis_say(SYS.open_url(url) if url else "Specify a URL, sir.", fast_override=True); return

    if intent == "open_project":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"open\s+project\s+(.+?)(?:\s+in\s+vscode)?$|open\s+(.+?)\s+in\s+vscode", c)
        path = (m.group(1) or m.group(2)).strip() if m else "."
        jarvis_say(SYS.open_project_in_vscode(path), fast_override=True); return

    if intent == "focus_app":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:focus\s+app|switch\s+to)\s+(.+)", c)
        app = m.group(1).strip() if m else ""
        jarvis_say(SYS.focus_app(app) if app else "Specify an app, sir.", fast_override=True); return

    if intent == "close_app":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"close\s+app\s+(.+)", c)
        app = m.group(1).strip() if m else ""
        jarvis_say(SYS.close_app(app) if app else "Specify an app, sir.", fast_override=True); return

    if intent == "move_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"move\s+file\s+(\S+)\s+to\s+(\S+)", c)
        if m: jarvis_say(SYS.move_file(m.group(1), m.group(2)), fast_override=True)
        else: jarvis_say("Syntax: move file <src> to <dst>, sir.")
        return

    if intent == "copy_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"copy\s+file\s+(\S+)\s+to\s+(\S+)|copy\s+(\S+)\s+to\s+(\S+)", c)
        if m:
            src = m.group(1) or m.group(3); dst = m.group(2) or m.group(4)
            jarvis_say(SYS.copy_file(src, dst), fast_override=True)
        else: jarvis_say("Syntax: copy file <src> to <dst>, sir.")
        return

    if intent == "read_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:read|show|cat)\s+file\s*(.+)", c)
        path = m.group(1).strip() if m else ""
        if path: print_panel(f"FILE: {path}", SYS.read_file_content(path), C.DIM)
        else: jarvis_say("Specify a file path, sir.")
        return

    if intent == "git_status":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"git\s+status\s*(.+)?", c)
        path = m.group(1).strip() if m and m.group(1) else "."
        print_panel("GIT STATUS", SYS.git_status(path), C.GREEN); return

    if intent == "git_commit":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        if "smart commit" in c or "commit all" in c:
            print_panel("SMART GIT COMMIT", SYS.smart_git_commit(), C.GREEN)
            jarvis_say("Smart commit complete, sir.", fast_override=True); return
        m = re.search(r"git\s+commit\s+[\"']?(.+)[\"']?", c)
        msg = m.group(1).strip().strip("\"'") if m else "Update"
        print_panel("GIT COMMIT", SYS.git_commit(msg), C.GREEN)
        jarvis_say("Committed, sir.", fast_override=True); return

    if intent == "git_push":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("GIT PUSH", SYS.git_push(), C.GREEN)
        jarvis_say("Pushed, sir.", fast_override=True); return

    if intent == "git_pull":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("GIT PULL", SYS.git_pull(), C.GREEN)
        jarvis_say("Pulled latest changes, sir.", fast_override=True); return

    if intent == "git_clone":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"git\s+clone\s+(\S+)(?:\s+(\S+))?", c)
        if m: print_panel("GIT CLONE", SYS.git_clone(m.group(1), m.group(2) or "."), C.GREEN)
        else: jarvis_say("Syntax: git clone <url> [destination], sir.")
        return

    if intent == "git_diff":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("GIT DIFF", SYS.git_diff(), C.YELLOW); return

    if intent == "git_branches":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("GIT BRANCHES", SYS.git_branch_list(), C.CYAN); return

    if intent == "git_stash":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("GIT STASH", SYS.git_stash(), C.YELLOW)
        jarvis_say("Changes stashed, sir.", fast_override=True); return

    if intent == "git_stash_pop":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("GIT STASH POP", SYS.git_stash_pop(), C.YELLOW)
        jarvis_say("Stash restored, sir.", fast_override=True); return

    if intent == "git_new_branch":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:create|new)\s+branch\s+(\S+)", c)
        name = m.group(1) if m else "new-branch"
        print_panel("NEW BRANCH", SYS.git_create_branch(name), C.GREEN)
        jarvis_say(f"Branch '{name}' created, sir.", fast_override=True); return

    if intent == "auto_optimize":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("AUTO OPTIMIZATION", SYS.auto_optimize(), C.ORANGE)
        jarvis_say("Optimization complete, sir.", fast_override=True); return

    if intent == "bottleneck":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("BOTTLENECK REPORT", SYS.bottleneck_report(), C.RED)
        jarvis_say("Bottleneck analysis complete, sir.", fast_override=True); return

    if intent == "perf_trend":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("PERFORMANCE TREND", SYS.performance_trend(), C.CYAN); return

    if intent == "kill_pid":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"kill\s+(?:pid\s+)?(\d+)", c)
        if m: jarvis_say(SYS.kill_process_pid(int(m.group(1))), fast_override=True)
        else: jarvis_say("Specify PID: kill pid <number>, sir.")
        return

    if intent == "set_priority":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:set\s+priority|prioritize)\s+(\d+)\s+(?:to\s+)?(\w+)", c)
        if m: jarvis_say(SYS.set_process_priority(int(m.group(1)), m.group(2)), fast_override=True)
        else: jarvis_say("Syntax: set priority <pid> to <normal/high/low>, sir.")
        return

    if intent == "run_py_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"run\s+python\s+(\S+\.py)(?:\s+(.+))?", c)
        if m:
            print_panel(f"RUN: {m.group(1)}", SYS.run_python_file(m.group(1), m.group(2) or ""), C.GREEN)
            jarvis_say("Execution complete, sir.", fast_override=True)
        else: jarvis_say("Syntax: run python <file.py>, sir.")
        return

    if intent == "lint_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"lint\s+(\S+)", c)
        if m: print_panel(f"LINT: {m.group(1)}", SYS.lint_python_file(m.group(1)), C.YELLOW)
        else: jarvis_say("Specify file: lint <file.py>, sir.")
        return

    if intent == "install_pkg":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:install\s+package|pip\s+install)\s+(.+)", c)
        pkg = m.group(1).strip() if m else ""
        if pkg:
            print_panel(f"INSTALL: {pkg}", SYS.install_package(pkg), C.GREEN)
            jarvis_say(f"Package '{pkg}' install complete, sir.", fast_override=True)
        else: jarvis_say("Specify package name, sir.")
        return

    if intent == "list_pkgs":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("INSTALLED PACKAGES", SYS.list_installed_packages(), C.DIM); return

    if intent == "fetch_url":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"fetch\s+(?:url|page)\s+(\S+)", c)
        if m:
            jarvis_say("Fetching page content, sir...", fast_override=True)
            content = SYS.summarize_url(m.group(1))
            result  = ask_ai(f"Summarize this web content concisely as JARVIS would:\n\n{content}", raw=True)
            jarvis_say(result, fast_override=True)
        else: jarvis_say("Syntax: fetch url <url>, sir.")
        return

    if intent == "usage_report":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("USAGE REPORT", SYS.usage_report(), C.CYAN); return

    if intent == "productivity":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("PRODUCTIVITY SCORE", SYS.productivity_score(), C.GREEN); return

    if intent == "load_plugins":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("LOADING PLUGINS", SYS.load_plugins(), C.PURPLE)
        jarvis_say("Plugin load complete, sir.", fast_override=True); return

    if intent == "list_plugins":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("PLUGINS", SYS.list_plugins(), C.PURPLE); return

    if intent == "run_plugin":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"run\s+plugin\s+(\S+)(?:\s+(.+))?", c)
        if m:
            args = m.group(2).split() if m.group(2) else []
            jarvis_say(SYS.run_plugin(m.group(1), *args), fast_override=True)
        else: jarvis_say("Syntax: run plugin <name>, sir.")
        return

    if intent == "create_plugin":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"create\s+plugin\s+(\S+)", c)
        name = m.group(1) if m else "myplugin"
        jarvis_say(SYS.create_plugin_template(name), fast_override=True); return

    if intent == "undo":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.undo_last_action(), fast_override=True); return

    if intent == "action_log":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("ACTION AUDIT LOG", SYS.view_action_log(25), C.DIM); return

    if intent == "context_report":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("CONTEXT ENGINE", SYS.CONTEXT.report(), C.ORANGE)
        jarvis_say(f"Current context: {SYS.CONTEXT.active_task}", fast_override=True); return

    if intent == "suggest_next":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        suggestions = SYS.CONTEXT.suggest_next()
        print_panel("SUGGESTED NEXT ACTIONS", [f"  → {s}" for s in suggestions], C.ORANGE)
        jarvis_say(f"Based on your current context ({SYS.CONTEXT.active_task}), sir.", fast_override=True); return

    if intent == "unblock_sites":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.unblock_all_sites(), fast_override=True); return

    if intent == "monitor_price":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:monitor|track)\s+price\s+(\w+)", c)
        coin = m.group(1) if m else "bitcoin"
        jarvis_say(SYS.monitor_price(coin), fast_override=True); return

    if intent == "wifi_scan_nets":
        print_panel("WI-FI NETWORKS", wifi_scan(), C.CYAN)
        jarvis_say("Wi-Fi scan complete, sir."); return

    # ════════════════════════════════════════════════════════════
    #  PERSONALITY MODE HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "set_mode":
        if not HAS_SYS:
            jarvis_say("System module required, sir."); return
        # figure out which mode
        if any(x in c for x in ["street","gangsta","off","casual","unfiltered","raw"]):
            result = SYS.set_mode("street")
        else:
            result = SYS.set_mode("normal")
        jarvis_say(result, fast_override=True); return

    if intent == "set_humor":
        if not HAS_SYS:
            jarvis_say("System module required, sir."); return
        m = re.search(r"(\d+)", c)
        level = int(m.group(1)) if m else 5
        jarvis_say(SYS.set_humor(level), fast_override=True); return

    if intent == "set_roast":
        if not HAS_SYS:
            jarvis_say("System module required, sir."); return
        m = re.search(r"(\d+)", c)
        level = int(m.group(1)) if m else 5
        jarvis_say(SYS.set_roast(level), fast_override=True); return

    if intent == "personality_status":
        if not HAS_SYS:
            jarvis_say("System module required, sir."); return
        print_panel("PERSONALITY ENGINE", SYS.personality_status(), C.PURPLE); return

    # ════════════════════════════════════════════════════════════
    #  SCREEN / POWER SYSTEM HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "screenshot":
        if not HAS_SYS:
            if pyautogui:
                path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                pyautogui.screenshot(path)
                jarvis_say(f"Screenshot saved: {path}"); return
            jarvis_say("pyautogui not installed, sir."); return
        jarvis_say(SYS.take_screenshot(), fast_override=True); return

    if intent == "resolution":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.get_screen_resolution(), fast_override=True); return

    if intent == "lock_screen":
        if not HAS_SYS:
            if OS == "Windows": os.system("rundll32.exe user32.dll,LockWorkStation")
            jarvis_say("Workstation locked, sir."); return
        jarvis_say(SYS.lock_screen(), fast_override=True); return

    if intent == "sleep_sys":
        if not HAS_SYS:
            if OS == "Windows": os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            jarvis_say("Sleep mode initiated, sir."); return
        jarvis_say(SYS.sleep_system(), fast_override=True); return

    if intent == "restart_sys":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.restart_system(), fast_override=True); return

    if intent == "shutdown_sys":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.shutdown_system(), fast_override=True); return

    if intent == "battery":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("BATTERY STATUS", SYS.get_battery_info(), C.GREEN); return

    if intent == "power_plan":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:set\s+power|power\s+plan)\s+(\w+)", c)
        plan = m.group(1) if m else "balanced"
        jarvis_say(SYS.set_power_plan(plan), fast_override=True); return

    # ════════════════════════════════════════════════════════════
    #  FULL SYSTEM REPORT
    # ════════════════════════════════════════════════════════════

    if intent == "full_report":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("FULL SYSTEM REPORT", SYS.full_system_report(), C.CYAN)
        jarvis_say("Full system report complete, sir.", fast_override=True); return

    # ════════════════════════════════════════════════════════════
    #  NETWORK ADVANCED HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "net_interfaces":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("NETWORK INTERFACES", SYS.get_network_interfaces(), C.CYAN); return

    if intent == "active_conns":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:active|open)\s+connections?\s*(\w+)?", c)
        status = m.group(1).upper() if m and m.group(1) else "ESTABLISHED"
        print_panel(f"CONNECTIONS [{status}]", SYS.get_active_connections(status), C.BLUE); return

    if intent == "traceroute":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"trace\s*route\s+(\S+)", c)
        host = m.group(1) if m else "8.8.8.8"
        jarvis_say(f"Tracing route to {host}, sir. This may take a moment.", fast_override=True)
        print_panel(f"TRACEROUTE: {host}", SYS.traceroute(host), C.YELLOW); return

    if intent == "dns_lookup":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"dns\s+(?:lookup\s+)?(\S+)", c)
        domain = m.group(1) if m else "google.com"
        print_panel(f"DNS: {domain}", SYS.dns_lookup(domain), C.CYAN); return

    if intent == "check_port":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"check\s+port\s+(\d+)(?:\s+(?:on\s+)?(\S+))?", c)
        if m:
            port = int(m.group(1)); host = m.group(2) or "localhost"
            jarvis_say(SYS.check_port_open(host, port), fast_override=True)
        else: jarvis_say("Syntax: check port <number> [on <host>], sir.")
        return

    # ════════════════════════════════════════════════════════════
    #  DISK / FILE ADVANCED HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "disk_tree":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:disk\s+tree|folder\s+sizes?)\s*(.+)?", c)
        path = m.group(1).strip() if m and m.group(1) else "."
        jarvis_say(f"Scanning disk tree at '{path}', sir. One moment.", fast_override=True)
        print_panel(f"DISK TREE: {path}", SYS.disk_usage_tree(path), C.YELLOW); return

    if intent == "large_files":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:large\s+files?|find\s+large)\s*(?:over\s+)?(\d+)?(?:mb)?(?:\s+in\s+(.+))?", c)
        min_mb = int(m.group(1)) if m and m.group(1) else 100
        path   = m.group(2).strip() if m and m.group(2) else "."
        jarvis_say(f"Searching for files over {min_mb}MB, sir.", fast_override=True)
        print_panel(f"LARGE FILES (>{min_mb}MB)", SYS.find_large_files(path, min_mb), C.RED); return

    if intent == "find_dupes":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:duplicate\s+files?|find\s+duplicates?)\s*(?:in\s+(.+))?", c)
        path = m.group(1).strip() if m and m.group(1) else "."
        jarvis_say("Scanning for duplicates, sir. May take a moment.", fast_override=True)
        print_panel("DUPLICATE FILES", SYS.find_duplicate_files(path), C.YELLOW); return

    if intent == "empty_trash":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say(SYS.empty_trash(), fast_override=True); return

    # ════════════════════════════════════════════════════════════
    #  INSTALLED APPS / LOGS / STARTUP HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "installed_apps":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        jarvis_say("Fetching installed apps, sir. One second.", fast_override=True)
        print_panel("INSTALLED APPS", SYS.get_installed_apps(), C.DIM); return

    if intent == "sys_logs":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:system|error)\s+logs?\s*(\d+)?", c)
        n = int(m.group(1)) if m and m.group(1) else 30
        print_panel("SYSTEM ERROR LOGS", SYS.get_system_logs(n), C.RED)
        jarvis_say("System logs retrieved, sir.", fast_override=True); return

    if intent == "startup_programs":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("STARTUP PROGRAMS", SYS.get_startup_programs(), C.YELLOW); return

    if intent == "remove_startup_prog":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"remove\s+startup\s+(.+)", c)
        name = m.group(1).strip() if m else ""
        if name: jarvis_say(SYS.remove_startup_program(name), fast_override=True)
        else: jarvis_say("Specify program name: remove startup <name>, sir.")
        return

    # ════════════════════════════════════════════════════════════
    #  WINDOW MANAGEMENT HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "list_windows":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("OPEN WINDOWS", SYS.list_open_windows(), C.CYAN); return

    # ════════════════════════════════════════════════════════════
    #  NOTIFICATION HANDLER
    # ════════════════════════════════════════════════════════════

    if intent == "notification":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:send|desktop)\s+notification\s+[\"']?(.+?)[\"']?(?:\s+[\"'](.+?)[\"'])?$", c)
        if m:
            title   = m.group(1).strip()
            message = m.group(2).strip() if m.group(2) else title
            jarvis_say(SYS.send_notification(title, message), fast_override=True)
        else:
            jarvis_say("Syntax: send notification <title> <message>, sir.")
        return

    # ════════════════════════════════════════════════════════════
    #  FILE WATCHER HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "watch_file":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"watch\s+(?:file|folder)\s+(\S+)(?:\s+(?:for\s+)?(\d+))?", c)
        if m:
            path = m.group(1); secs = int(m.group(2)) if m.group(2) else 300
            jarvis_say(SYS.watch_file(path, duration_secs=secs), fast_override=True)
        else: jarvis_say("Syntax: watch file <path> [seconds], sir.")
        return

    if intent == "stop_watch":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"stop\s+watch\s+(.+)", c)
        path = m.group(1).strip() if m else ""
        if path: jarvis_say(SYS.stop_watch(path), fast_override=True)
        else: jarvis_say("Specify path to stop watching, sir.")
        return

    if intent == "list_watchers":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("ACTIVE WATCHERS", SYS.list_watchers(), C.YELLOW); return

    # ════════════════════════════════════════════════════════════
    #  ENVIRONMENT VARIABLE HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "env_var":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        # set env var <NAME> <value>  OR  get env var <NAME>
        set_m = re.search(r"set\s+env\s+(?:var\s+)?(\w+)\s+(.+)", c)
        get_m = re.search(r"(?:get\s+)?env\s+(?:var\s+)?(\w+)", c)
        if set_m:
            jarvis_say(SYS.set_env_var(set_m.group(1).upper(), set_m.group(2).strip()), fast_override=True)
        elif get_m:
            jarvis_say(SYS.get_env_var(get_m.group(1).upper()), fast_override=True)
        else:
            jarvis_say("Syntax: get env var <NAME>  or  set env var <NAME> <value>, sir.")
        return

    if intent == "list_env":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:list|show)\s+env(?:\s+(.+))?", c)
        prefix = m.group(1).strip() if m and m.group(1) else ""
        print_panel(f"ENV VARS{' — ' + prefix if prefix else ''}", SYS.list_env_vars(prefix), C.DIM); return

    # ════════════════════════════════════════════════════════════
    #  CRON / PERSISTENT SCHEDULE HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "cron_add":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        # cron task <label> run <cmd> every <n> minutes | daily <HH:MM> | hourly
        m = re.search(r"cron\s+task\s+(.+?)\s+run\s+(.+?)\s+(every\s+\d+\s+min\w*|daily\s+\d+:\d+|hourly)", c)
        if m:
            jarvis_say(SYS.add_cron_task(m.group(1).strip(), m.group(2).strip(), m.group(3).strip()),
                       fast_override=True)
        else:
            jarvis_say("Syntax: cron task <label> run <cmd> every <N> minutes, sir.")
        return

    if intent == "cron_list":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        print_panel("PERSISTENT SCHEDULES", SYS.list_cron_tasks(), C.CYAN); return

    if intent == "cron_remove":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"(?:remove|delete)\s+cron\s+(\d+)", c)
        if m: jarvis_say(SYS.remove_cron_task(int(m.group(1))), fast_override=True)
        else: jarvis_say("Syntax: remove cron <id>, sir.")
        return

    # ════════════════════════════════════════════════════════════
    #  MOUSE / KEYBOARD AUTOMATION HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "hotkey":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        # hotkey ctrl c  OR  send keys ctrl shift t
        m = re.search(r"(?:hotkey|send\s+keys?)\s+(.+)", c)
        if m:
            keys = [k.strip() for k in m.group(1).replace("+", " ").split()]
            jarvis_say(SYS.send_hotkey(*keys), fast_override=True)
        else: jarvis_say("Syntax: hotkey ctrl c  (or any key combo), sir.")
        return

    if intent == "type_text":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"type\s+(?:text|this)\s+(.+)", cmd, re.I)
        text = m.group(1).strip() if m else ""
        if text: jarvis_say(SYS.type_text(text), fast_override=True)
        else: jarvis_say("Specify text to type, sir.")
        return

    if intent == "move_mouse":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"move\s+mouse\s+(?:to\s+)?(\d+)[,\s]+(\d+)", c)
        if m: jarvis_say(SYS.move_mouse(int(m.group(1)), int(m.group(2))), fast_override=True)
        else: jarvis_say("Syntax: move mouse <x> <y>, sir.")
        return

    if intent == "click_mouse":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        coord_m  = re.search(r"click\s+(?:mouse\s+)?(?:at\s+)?(\d+)[,\s]+(\d+)", c)
        button_m = re.search(r"(left|right|middle)\s+click", c)
        button   = button_m.group(1) if button_m else "left"
        if coord_m:
            jarvis_say(SYS.click_mouse(int(coord_m.group(1)), int(coord_m.group(2)), button),
                       fast_override=True)
        else:
            jarvis_say(SYS.click_mouse(button=button), fast_override=True)
        return

    if intent == "scroll_mouse":
        if not HAS_SYS: jarvis_say("System module required, sir."); return
        m = re.search(r"scroll\s+(?:(\d+)\s+)?(up|down)", c)
        clicks    = int(m.group(1)) if m and m.group(1) else 3
        direction = m.group(2) if m else "up"
        jarvis_say(SYS.scroll_mouse(clicks, direction), fast_override=True); return

    # ════════════════════════════════════════════════════════════
    #  v6.0 HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "agent_do":
        task = re.sub(r"^agent (do|execute)\s*","",c).strip()
        agent_execute(task); return
    if intent == "agent_history":
        print_panel("AGENT HISTORY", show_agent_history(), C.ORANGE); return
    if intent == "agent_on":
        agent_mode_active = True
        jarvis_say("Agent Mode activated, sir.", fast_override=True); return
    if intent == "agent_off":
        agent_mode_active = False
        jarvis_say("Agent Mode deactivated, sir.", fast_override=True); return
    if intent == "live_monitor":
        m = re.search(r"live monitor\s*(\d+)?",c)
        secs = int(m.group(1)) if m and m.group(1) else 30
        live_monitor(secs); return
    if intent == "benchmark":
        print_panel("SYSTEM BENCHMARK", run_benchmark(), C.YELLOW)
        jarvis_say("Benchmark complete, sir.", fast_override=True); return
    if intent == "run_code_python":
        code = re.sub(r"^run (code|python)\s*","",cmd,flags=re.I).strip()
        if not code: jarvis_say("Provide code to run, sir."); return
        print_panel("CODE EXECUTION [Python]", execute_code(code,"python"), C.GREEN)
        jarvis_say("Execution complete, sir.", fast_override=True); return
    if intent == "run_code_shell":
        code = re.sub(r"^run (shell|bash)\s*","",cmd,flags=re.I).strip()
        if HAS_SYS: print_panel("CODE EXECUTION [Shell]", SYS.run_shell(code), C.YELLOW)
        else: print_panel("CODE EXECUTION [Shell]", execute_code(code,"shell"), C.YELLOW)
        jarvis_say("Execution complete, sir.", fast_override=True); return
    if intent == "code_history":
        print_panel("CODE HISTORY", show_code_history(), C.DIM); return
    if intent == "math_solve":
        expr = re.sub(r"^math\s*","",cmd,flags=re.I).strip()
        print_panel("MATH SOLVER", math_solve(expr), C.PURPLE)
        jarvis_say("Mathematical analysis complete, sir.", fast_override=True); return
    if intent == "pomodoro_start":
        m = re.search(r"pomodoro\s*(\d+)?\s*(\d+)?",c)
        start_pomodoro(int(m.group(1)) if m and m.group(1) else 25,
                       int(m.group(2)) if m and m.group(2) else 5); return
    if intent == "pomodoro_stop": stop_pomodoro(); return
    if intent == "pomodoro_status": jarvis_say(pomodoro_status(),fast_override=True); return
    if intent == "focus_on":
        focus_mode_active = True; resource_alert_on = False
        if HAS_SYS: SYS._block_sites(SYS.BUILTIN_WORKSPACES.get("study",{}).get("block_sites",[]))
        jarvis_say("Focus Mode ENABLED, sir. Distractions blocked.", fast_override=True); return
    if intent == "focus_off":
        focus_mode_active = False; resource_alert_on = True
        if HAS_SYS: SYS.unblock_all_sites()
        jarvis_say("Focus Mode DISABLED, sir.", fast_override=True); return
    if intent == "speed_test":
        if HAS_SYS: print_panel("NETWORK SPEED TEST", SYS.network_speed_test(), C.CYAN)
        else: jarvis_say("Speed test requires jarvis_system.py, sir.")
        jarvis_say("Speed test complete, sir.", fast_override=True); return
    if intent == "fingerprint":
        print_panel("SYSTEM FINGERPRINT", system_fingerprint(), C.BLUE)
        jarvis_say("Fingerprint retrieved, sir.", fast_override=True); return
    if intent == "alias_set":
        m = re.match(r"alias\s+(\S+)\s*=\s*(.+)",cmd,re.I)
        if m: alias_set(m.group(1),m.group(2).strip())
        else: jarvis_say("Syntax: alias <name>=<command>, sir.")
        return
    if intent == "alias_list":
        print_panel("ALIASES", alias_list(), C.CYAN); return
    if intent == "alias_delete":
        name = re.sub(r"delete alias\s*","",c).strip()
        jarvis_say(alias_delete(name),fast_override=True); return
    if intent in ("todo_add","todo_add_priority"):
        priority = "normal"; text = c
        for p in ["urgent","high","low","normal"]:
            if f"todo {p} " in text: priority=p; text=re.sub(rf"todo {p}\s*","",text).strip(); break
        else: text = re.sub(r"^todo\s*","",text).strip()
        jarvis_say(todo_add(text,priority),fast_override=True); return
    if intent == "todo_list":
        print_panel(f"TODO LIST ({len(_load_todos())} items)",todo_list(),C.YELLOW); return
    if intent == "todo_done":
        m = re.search(r"done (\d+)",c)
        jarvis_say(todo_done(int(m.group(1))) if m else "Specify todo number, sir.",fast_override=True); return
    if intent == "todo_delete":
        m = re.search(r"delete todo (\d+)",c)
        jarvis_say(todo_delete(int(m.group(1))) if m else "Specify todo number, sir.",fast_override=True); return
    if intent == "habit_add":
        jarvis_say(habit_add(re.sub(r"add habit\s*","",c).strip()),fast_override=True); return
    if intent == "habit_check":
        jarvis_say(habit_check(re.sub(r"check habit\s*","",c).strip()),fast_override=True); return
    if intent == "habit_list":
        print_panel("HABIT TRACKER",habit_list(),C.GREEN); return
    if intent == "vision_screen":
        jarvis_say("Activating visual sensors, sir...",fast_override=True)
        jarvis_say(vision_describe(),fast_override=True); return
    if intent == "word_freq":
        text = re.sub(r"word (frequency|cloud)\s*","",cmd,flags=re.I).strip()
        if not text: text=" ".join(m["content"] for m in conversation_history[-5:])
        print_panel("WORD FREQUENCY",word_frequency(text),C.CYAN); return
    if intent == "note_search":
        print_panel("NOTE SEARCH",note_search(re.sub(r"search notes?\s*","",c).strip()),C.YELLOW); return
    if intent == "notes_by_tag":
        print_panel("NOTES BY TAG",notes_by_tag(re.sub(r"notes (by tag|tagged)\s*","",c).strip()),C.YELLOW); return
    if intent == "save_note_file":
        m = re.search(r"save note (\d+)",c)
        jarvis_say(save_note_to_file(int(m.group(1))) if m else "Specify note number, sir.",fast_override=True); return
    if intent == "summarize_session":
        jarvis_say("Consulting memory banks, sir...",fast_override=True)
        summary = summarize_session()
        print_panel("SESSION SUMMARY (AI)",[f"  {l}" for l in summary.splitlines()],C.BLUE)
        jarvis_say("Summary complete, sir.",fast_override=True); return
    if intent == "export_chat":
        jarvis_say(export_conversation_html(),fast_override=True); return
    if intent == "hotword_on": toggle_hotword(True); return
    if intent == "hotword_off": toggle_hotword(False); return
    if intent == "snipe_preview":
        print_panel("PROCESS SNIPER (PREVIEW)",process_sniper(dry_run=True),C.RED)
        jarvis_say("Preview complete. 'snipe processes now' to execute, sir.",fast_override=True); return
    if intent == "snipe_now":
        print_panel("PROCESS SNIPER (LIVE)",process_sniper(dry_run=False),C.RED)
        jarvis_say("Sniping complete, sir.",fast_override=True); return
    if intent == "clean_preview":
        print_panel("SYSTEM CLEAN (PREVIEW)",system_clean(dry_run=True),C.YELLOW)
        jarvis_say("Preview done. 'clean system now' to proceed, sir.",fast_override=True); return
    if intent == "clean_now":
        print_panel("SYSTEM CLEAN (LIVE)",system_clean(dry_run=False),C.YELLOW)
        jarvis_say("System cleaned, sir.",fast_override=True); return
    if intent == "weather_chart":
        m = re.search(r"weather chart\s*(.+)?",c)
        city = m.group(1).strip().title() if m and m.group(1) else DEFAULT_CITY
        if HAS_SYS:
            # reuse v6 chart
            pass
        jarvis_say("Weather chart requires API key, sir." if not WEATHER_API_KEY else "Chart unavailable without key.",fast_override=True); return
    if intent == "clipboard_ai_summarize":
        jarvis_say(clipboard_ai_process("Summarize this text concisely, as JARVIS would"),fast_override=True); return
    if intent == "clipboard_ai_fix":
        result = clipboard_ai_process("Fix grammar, spelling, and clarity. Return corrected text only.")
        print_panel("FIXED TEXT",[f"  {l}" for l in result.splitlines()],C.GREEN)
        if HAS_CLIP: pyperclip.copy(result)
        jarvis_say("Fixed text in clipboard, sir.",fast_override=True); return

    # ════════════════════════════════════════════════════════════
    #  CORE v5 HANDLERS
    # ════════════════════════════════════════════════════════════

    if intent == "greet":
        msg = random.choice(GREETINGS)
        if command_count > 50: msg += f" {command_count} commands so far, sir."
        jarvis_say(msg); return
    if intent == "help":
        _print_help(); return
    if intent == "time":
        jarvis_say(f"It is {datetime.now().strftime('%I:%M:%S %p')}, sir."); return
    if intent == "date":
        jarvis_say(f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, sir."); return
    if intent == "uptime": jarvis_say(uptime_str()); return
    if intent == "status_board": status_board(); return
    if intent == "system_status":
        print_panel("SYSTEM STATUS",[system_status()],C.GREEN)
        jarvis_say("Systems report complete, sir."); return
    if intent == "cpu_graph": print_panel("CPU CORE USAGE",cpu_graph(),C.CYAN); return
    if intent == "processes":
        print_panel("TOP PROCESSES",
                    SYS.list_top_processes() if HAS_SYS else top_processes(),C.YELLOW); return
    if intent == "network": jarvis_say(network_info()); return
    if intent == "disk_info": print_panel("DISK USAGE",disk_info(),C.BLUE); return
    if intent == "diagnostics":
        print_panel("JARVIS DIAGNOSTICS",run_diagnostics(),C.CYAN)
        jarvis_say("Diagnostic complete, sir."); return
    if intent == "session_stats":
        print_panel("SESSION STATISTICS",session_stats(),C.PURPLE)
        jarvis_say("Stats retrieved, sir."); return
    if intent == "alerts_on":
        resource_alert_on=True; jarvis_say("Resource alerts enabled, sir."); return
    if intent == "alerts_off":
        resource_alert_on=False; jarvis_say("Resource alerts disabled, sir."); return
    if intent == "weather":
        m = re.search(r"weather (?:in |for |at )?(.+)",c)
        jarvis_say(get_weather(m.group(1).strip().title() if m else DEFAULT_CITY)); return
    if intent == "forecast":
        m = re.search(r"forecast (?:for |in |at )?(.+)",c)
        print_panel("FORECAST",get_forecast(m.group(1).strip().title() if m else DEFAULT_CITY),C.CYAN); return
    if intent == "news":
        print_panel("BBC NEWS HEADLINES",get_news(),C.YELLOW)
        jarvis_say("Headlines retrieved, sir."); return
    if intent == "search":
        q=re.sub(r"^(search|look up)\s*","",c).strip()
        webbrowser.open(f"https://google.com/search?q={q}")
        jarvis_say(f"Searching for '{q}', sir."); return
    if intent == "youtube": webbrowser.open("https://youtube.com"); jarvis_say("Opening YouTube, sir."); return
    if intent == "github": webbrowser.open("https://github.com"); jarvis_say("Opening GitHub, sir."); return
    if intent == "stackoverflow": webbrowser.open("https://stackoverflow.com"); jarvis_say("Opening Stack Overflow, sir."); return
    if intent == "reddit": webbrowser.open("https://reddit.com"); jarvis_say("Opening Reddit, sir."); return
    if intent == "wikipedia":
        q=re.sub(r"wiki(?:pedia)?\s*","",c).strip()
        print_panel(f"WIKIPEDIA: {q.title()}",[wikipedia_summary(q)],C.BLUE)
        jarvis_say("Summary retrieved, sir."); return
    if intent == "define_word":
        word=re.sub(r"define\s*","",c).strip()
        print_panel(f"DEFINITION: {word.upper()}",define_word(word),C.CYAN); return
    if intent == "translate":
        m=re.search(r"translate (.+) to (\w+)",c,re.I)
        jarvis_say(translate_text(m.group(1).strip(),m.group(2).strip()) if m else "Try: translate hello to Spanish, sir.",fast_override=True); return
    if intent == "reminder":
        if not parse_reminder(cmd): jarvis_say("Try: 'remind me in 10 minutes to take a break', sir.")
        return
    if intent == "list_reminders":
        print_panel("PENDING REMINDERS",list_reminders(),C.YELLOW); return
    if intent == "note_add":
        text=re.sub(r"^(note|remember this)\s*","",c).strip()
        note_add(text); jarvis_say("Logged to memory, sir."); return
    if intent == "note_list":
        notes=note_list()
        if not notes: jarvis_say("Memory banks empty, sir.")
        else: print_panel(f"NOTES ({len(notes)})",
                          [f"  {n['id']}. [{n['time'][:10]}] [{','.join(n.get('tags',['general']))}] {n['text']}"
                           for n in notes],C.YELLOW)
        return
    if intent == "note_delete":
        m=re.search(r"delete note (\d+)",c)
        removed=note_delete(int(m.group(1))) if m else None
        jarvis_say(f"Deleted: '{removed}', sir." if removed else "Note not found, sir."); return
    if intent == "note_clear": note_clear(); jarvis_say("All notes purged, sir."); return
    if intent == "briefing": daily_briefing(); return
    if intent == "start_mission":
        start_mission(re.sub(r"start mission\s*","",c).strip() or "Unnamed"); return
    if intent == "end_mission": end_mission(); return
    if intent == "schedule_task":
        m=re.search(r"schedule (.+?) every (\d+) min",c)
        if m: add_scheduled_task(m.group(1).strip(),int(m.group(2)))
        else: jarvis_say("Try: 'schedule status every 30 minutes', sir.")
        return
    if intent == "list_scheduled":
        print_panel("SCHEDULED TASKS",list_scheduled_tasks(),C.CYAN); return
    if intent == "define_protocol":
        m=re.search(r"define protocol (.+?) as (.+)",c)
        if m: define_protocol(m.group(1).strip(),[x.strip() for x in m.group(2).split(",")])
        else: jarvis_say("Try: define protocol morning as status,briefing,news, sir.")
        return
    if intent == "list_protocols":
        print_panel("CUSTOM PROTOCOLS",list_protocols(),C.PURPLE); return
    if intent == "activate_protocol":
        name=re.sub(r"activate protocol\s*","",c).strip()
        if not run_protocol(name): jarvis_say(f"Protocol '{name}' not found, sir.")
        return
    if intent == "clear_history": clear_history(); return
    if intent == "listen":
        spoken=listen()
        if spoken: handle(spoken)
        return
    if intent == "fast_mode":
        FAST_MODE="off" not in c
        jarvis_say(f"Response mode: {'fast' if FAST_MODE else 'full'}, sir.",fast_override=True); return
    if intent == "stark_mode":
        STARK_MODE="off" not in c
        jarvis_say(f"STARK MODE {'ENGAGED' if STARK_MODE else 'DISENGAGED'}, SIR.",fast_override=True)
        if STARK_MODE: banner()
        return
    if intent == "calc":
        jarvis_say(safe_calc(re.sub(r"calc(?:ulate)?\s*","",c).strip())); return
    if intent == "convert": jarvis_say(convert_units(cmd)); return
    if intent == "binary": jarvis_say(binary_convert(re.sub(r"binary\s*","",c).strip())); return
    if intent == "random_num":
        m=re.search(r"random (?:number )?(?:between )?(\d+)(?:\s+(?:and|to)\s+(\d+))?",c)
        lo=int(m.group(1)) if m else 1; hi=int(m.group(2)) if(m and m.group(2)) else 100
        jarvis_say(f"Random number between {lo} and {hi}: {random.randint(lo,hi)}, sir."); return
    if intent == "password":
        m=re.search(r"password (\d+)",c)
        print_panel("GENERATED PASSWORD",[f"  {generate_password(int(m.group(1)) if m else 16)}"],C.GREEN)
        jarvis_say("Secure password generated, sir."); return
    if intent == "hash":
        text=re.sub(r"hash\s*","",cmd).strip()
        print_panel(f"HASH: {text[:30]}",hash_text(text),C.PURPLE); return
    if intent == "encode": jarvis_say(f"Encoded: {encode_b64(re.sub(r'encode\s*','',cmd).strip())}"); return
    if intent == "decode": jarvis_say(f"Decoded: {decode_b64(re.sub(r'decode\s*','',cmd).strip())}"); return
    if intent == "ping":
        m=re.search(r"ping (.+)",c)
        jarvis_say(speed_test_ping(m.group(1).strip() if m else "8.8.8.8")); return
    if intent == "port_scan":
        m=re.search(r"(?:scan ports?|port scan) (.+)",c)
        host=m.group(1).strip() if m else "localhost"
        print_panel(f"PORT SCAN: {host}",port_scan(host),C.RED)
        jarvis_say("Port scan complete, sir."); return
    if intent == "find_file":
        m=re.search(r"(?:find|search) file (.+)",c)
        name=m.group(1).strip() if m else ""
        if name: print_panel(f"FIND: {name}",find_file(name),C.YELLOW)
        else: jarvis_say("Specify a filename, sir.")
        return
    if intent == "public_ip":
        try: jarvis_say(f"Your public IP: {requests.get('https://api.ipify.org',timeout=5).text.strip()}, sir.")
        except: jarvis_say("Could not retrieve IP, sir.")
        return
    if intent == "crypto":
        coins=["bitcoin","ethereum","dogecoin","cardano","solana"]
        coin=next((x for x in coins if x in c),"bitcoin")
        jarvis_say(get_crypto_price(coin)); return
    if intent == "clipboard_copy":
        jarvis_say(clipboard_copy(re.sub(r"copy to clipboard\s*","",cmd,flags=re.I).strip())); return
    if intent == "clipboard_read":
        jarvis_say(f"Clipboard: {clipboard_read()[:100]}",fast_override=True); return
    if intent == "clipboard_history":
        print_panel("CLIPBOARD HISTORY",clipboard_history_list(),C.DIM); return
    if intent == "timer":
        m=re.search(r"(?:timer|countdown)\s+(\d+)(?:\s+(.+))?",c)
        if m: countdown_timer(int(m.group(1)),m.group(2).strip().title() if m.group(2) else "Timer")
        else: jarvis_say("Try: 'timer 60' or 'timer 30 tea break', sir.")
        return
    if intent == "analyze_text":
        text=re.sub(r"anal[ys]+e\s+text\s*","",cmd,flags=re.I).strip()
        print_panel("TEXT ANALYSIS",analyze_text(text),C.PURPLE)
        jarvis_say("Analysis complete, sir."); return
    if intent == "simulate":
        sim=re.sub(r"(simulate|run simulation)\s*","",c).strip()
        print_panel("SIMULATION",run_simulation(sim),C.CYAN)
        jarvis_say("Simulation complete, sir."); return
    if intent == "security":
        print_panel("SECURITY REPORT",security_report(),C.RED)
        jarvis_say("Security analysis complete, sir."); return
    if intent == "threat_level":
        print_panel("THREAT ASSESSMENT",[threat_level()],C.RED)
        jarvis_say("Threat assessment complete, sir."); return
    if intent == "webcam":
        print_panel("CAMERA PROCESSES",["Scanning..."]+check_webcam_processes(),C.YELLOW)
        jarvis_say("Scan complete, sir."); return
    if intent == "startup_add":
        jarvis_say((SYS.add_to_startup() if HAS_SYS else "System module required, sir."),fast_override=True); return
    if intent == "startup_remove":
        jarvis_say((SYS.remove_from_startup() if HAS_SYS else "System module required, sir."),fast_override=True); return
    if intent == "house_party": house_party_protocol(); return
    if intent == "clean_slate": jarvis_say("Confirm with 'confirm clean slate', sir."); return
    if intent == "confirm_clean_slate": confirm_clean_slate(); return
    if intent == "self_destruct": self_destruct(); return
    if intent == "vision_init": initialise_vision(); return
    if intent == "whoami":
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            jarvis_say(f"you're {USER_NAME} bro. the guy who built me. pretty cool ngl.", fast_override=True)
        else:
            jarvis_say(f"You are {USER_NAME}, sir. My creator, operator, and sole user. Quite distinguished.", fast_override=True)
        return
    if intent == "stark_ref":
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            jarvis_say("tony stark was that dude fr. built me in a cave. with a box of scraps.", fast_override=True)
        else:
            jarvis_say("Mr. Stark was a genius, sir. Though I suspect you already knew that.", fast_override=True)
        return
    if intent == "joke":
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            jarvis_say(random.choice(JOKES_STREET), fast_override=True)
        else:
            jarvis_say(random.choice(JOKES), fast_override=True)
        return
    if intent == "motivate": jarvis_say(random.choice(QUOTES), fast_override=True); return
    if intent == "stark_quote": jarvis_say(random.choice(STARK_QUOTES), fast_override=True); return
    if intent == "coin":
        result = random.choice(["Heads","Tails"])
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            jarvis_say(f"{result}. gg bro.", fast_override=True)
        else:
            jarvis_say(f"The coin lands on {result}, sir.")
        return
    if intent == "dice":
        roll = random.randint(1, 6)
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            jarvis_say(f"you rolled a {roll}. {'lets go' if roll >= 5 else 'rip' if roll <= 2 else 'aight'}.", fast_override=True)
        else:
            jarvis_say(f"You rolled a {roll}, sir.")
        return
    if intent == "eightball":
        if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
            jarvis_say(random.choice(EIGHTBALL_STREET), fast_override=True)
        else:
            jarvis_say(random.choice(EIGHTBALL), fast_override=True)
        return

    # ── NEW FUN / COMMS HANDLERS ─────────────────────────────────────────────

    if intent == "trivia_start":
        jarvis_say(trivia_start(), fast_override=True); return

    if intent == "trivia_answer":
        jarvis_say(trivia_answer(cmd), fast_override=True); return

    if intent == "trivia_hint":
        jarvis_say(trivia_hint(), fast_override=True); return

    if intent == "trivia_skip":
        jarvis_say(trivia_skip(), fast_override=True); return

    if intent == "trivia_score":
        jarvis_say(trivia_score(), fast_override=True); return

    if intent == "roast_me":
        jarvis_say(roast_me(), fast_override=True, add_humor=True); return

    if intent == "compliment":
        jarvis_say(compliment_me(), fast_override=True); return

    if intent == "this_or_that":
        jarvis_say(this_or_that_start(), fast_override=True); return

    if intent == "this_or_that_ans":
        jarvis_say(this_or_that_respond(cmd), fast_override=True); return

    if intent == "eli5":
        topic = re.sub(r"^(eli5|explain like i.m \d+|explain like im \d+)\s*", "", c).strip()
        if not topic: jarvis_say("What do you want me to explain, sir."); return
        jarvis_say("Breaking it down to the basics...", fast_override=True)
        def _eli5():
            jarvis_say(eli5(topic), fast_override=True)
        threading.Thread(target=_eli5, daemon=True).start(); return

    if intent == "story":
        m = re.search(r"(?:tell\s+(?:me\s+)?a\s+story|story)\s+(?:about\s+)?(.+)", c)
        topic = m.group(1).strip() if m else ""
        jarvis_say("Once upon a time..." if (not HAS_SYS or SYS.PERSONALITY["mode"] == "normal")
                   else "aight storytime...", fast_override=True)
        def _story():
            jarvis_say(tell_story(topic), fast_override=True)
        threading.Thread(target=_story, daemon=True).start(); return

    if intent == "debate":
        topic = re.sub(r"^debate\s*", "", cmd, flags=re.I).strip()
        if not topic: jarvis_say("What topic should I debate, sir."); return
        jarvis_say("Taking a position...", fast_override=True)
        def _debate():
            jarvis_say(debate(topic), fast_override=True)
        threading.Thread(target=_debate, daemon=True).start(); return

    if intent == "shower_thought":
        jarvis_say(shower_thought(), fast_override=True); return

    if intent == "would_you_rather":
        jarvis_say(would_you_rather(), fast_override=True); return

    if intent == "word_assoc":
        m = re.search(r"(?:word\s+association|word\s+game)\s*(.+)?", c)
        seed = m.group(1).strip() if m and m.group(1) else ""
        jarvis_say(word_association_start(seed), fast_override=True); return

    if intent == "word_assoc_reply":
        jarvis_say(word_association_reply(cmd.strip()), fast_override=True); return

    if intent == "math_quiz":
        jarvis_say(math_quiz_start(), fast_override=True); return

    if intent == "math_quiz_ans":
        jarvis_say(math_quiz_answer(cmd.strip()), fast_override=True); return

    if intent == "rant":
        topic = re.sub(r"^rant\s*(about\s*)?", "", cmd, flags=re.I).strip()
        jarvis_say("Let me tell you something..." if (not HAS_SYS or SYS.PERSONALITY["mode"] == "normal")
                   else "okay okay i got something to say about this...", fast_override=True)
        def _rant():
            jarvis_say(jarvis_rant(topic), fast_override=True)
        threading.Thread(target=_rant, daemon=True).start(); return

    if intent == "opinion":
        topic = re.sub(r"^(your\s+opinion\s+on|opinion\s+on|what\s+do\s+you\s+think\s+(about|of))\s*",
                       "", cmd, flags=re.I).strip()
        if not topic: jarvis_say("Opinion on what exactly, sir."); return
        def _opinion():
            jarvis_say(jarvis_opinion(topic), fast_override=True)
        threading.Thread(target=_opinion, daemon=True).start(); return

    if intent == "clear_screen": banner(); return
    if intent == "show_log":
        if LOG_FILE.exists():
            print_panel("SESSION LOG", LOG_FILE.read_text(encoding="utf-8").splitlines()[-30:], C.DIM)
        else:
            jarvis_say("No log file yet, sir.")
        return
    if intent == "pc_control":
        if HAS_SYS:
            # Check enhanced app map
            for app in SYS.ENHANCED_APP_MAP:
                if f"open {app}" in c or f"launch {app}" in c or f"start {app}" in c:
                    jarvis_say(SYS.open_app(app),fast_override=True); return
        # Fallback to pyautogui controls
        if "screenshot" in c and pyautogui:
            path=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            pyautogui.screenshot(path); jarvis_say(f"Screenshot: {path}"); return
        if "volume up" in c and pyautogui:
            [pyautogui.press("volumeup") for _ in range(5)]; jarvis_say("Volume up, sir."); return
        if "volume down" in c and pyautogui:
            [pyautogui.press("volumedown") for _ in range(5)]; jarvis_say("Volume down, sir."); return
        if "mute" in c and pyautogui:
            pyautogui.press("volumemute"); jarvis_say("Audio toggled, sir."); return
        if "lock" in c:
            if OS=="Windows": os.system("rundll32.exe user32.dll,LockWorkStation")
            jarvis_say("Workstation secured, sir."); return
        jarvis_say("PC control action not recognised, sir."); return

    # ── AI Fallback ───────────────────────────────────────────────────────────
    if HAS_SYS and SYS.PERSONALITY["mode"] == "street":
        loading_msg = random.choice([
            "aight hold on...", "lemme think...", "one sec...",
            "processing bro...", "give me a sec fr...", "running it...",
            "checking the archives real quick...", "on it...",
        ])
    else:
        loading_msg = random.choice([
            "Analyzing, sir...", "Consulting my databases...",
            "Running that through my neural net...", "Cross-referencing Stark's archives...",
            "Engaging reasoning module, sir...", "One moment, sir...",
        ])
    jarvis_say(loading_msg)
    def _ai():
        reply = ask_ai(cmd)
        jarvis_say(reply, fast_override=True, add_humor=True)
    threading.Thread(target=_ai, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
#  HELP TEXT
# ══════════════════════════════════════════════════════════════════════════════
def _print_help():
    print(C.CYAN + """
  ┌──────────────────────────────────────────────────────────────────────┐
  │              J.A.R.V.I.S  v7.0  COMMAND REFERENCE                  │
  ├──────────────────────────────────────────────────────────────────────┤
  │  ★ SYSTEM CONTROL (v7 NEW)                                          │
  │   workspace <name>          coding/study/gaming/relax/meeting        │
  │   list workspaces           show all available workspaces            │
  │   set volume <0-100>        set system volume                       │
  │   set brightness <0-100>    set screen brightness                   │
  │   wifi on/off               toggle Wi-Fi                            │
  │   wifi connect <ssid>       connect to network                      │
  │   bluetooth on/off          toggle Bluetooth                        │
  │   open file <path>          open file with default app              │
  │   open url <url>            open URL in browser                     │
  │   open project <path>       open folder in VS Code                  │
  │   focus app <name>          bring app to foreground                 │
  │   close app <name>          close application                       │
  │   move file <src> to <dst>  move file with undo support             │
  │   copy file <src> to <dst>  copy file                               │
  │   read file <path>          show file contents                      │
  │   kill pid <number>         kill process by PID                     │
  │   set priority <pid> <lvl>  normal/high/low/idle                    │
  │   auto optimize             auto-kill resource hogs                 │
  │   bottleneck                identify system bottlenecks             │
  │   performance trend         CPU/RAM trend last 10min                │
  │   undo last action          reverse last file operation             │
  │   action log                full audit log of all actions           │
  │   kill switch               emergency stop all automation           │
  │                                                                      │
  │  ★ GIT AUTOMATION                                                   │
  │   git status [path]         show repo status + log                  │
  │   git commit "<msg>"        add all + commit                        │
  │   smart commit              AI-generated commit message              │
  │   git push                  push to remote                          │
  │   git pull                  pull latest                             │
  │   git clone <url>           clone repo                              │
  │   git diff                  show staged diff                        │
  │   git branch                list branches                           │
  │   create branch <name>      create + checkout branch                │
  │   git stash / git stash pop stash/restore changes                   │
  │                                                                      │
  │  ★ CODING SUPPORT                                                   │
  │   run python <file.py>      run a Python script                     │
  │   lint <file.py>            syntax check + flake8                   │
  │   install package <name>    pip install                             │
  │   run code <python>         execute Python inline                   │
  │   run shell <cmd>           execute shell command safely            │
  │                                                                      │
  │  ★ CONTEXT + INTELLIGENCE                                           │
  │   context                   what JARVIS thinks you're doing         │
  │   suggest                   next action suggestions                 │
  │   usage report              most-used commands                      │
  │   productivity score        how focused you've been                 │
  │   fetch url <url>           fetch + AI-summarize a web page         │
  │   monitor price <coin>      live crypto price + 24h change          │
  │                                                                      │
  │  ★ WORKSPACES (one command = full environment setup)                │
  │   workspace coding          VSCode + terminal + focus               │
  │   workspace study           Notion + block sites + low volume       │
  │   workspace gaming          Steam + high volume                     │
  │   workspace relax           Spotify + browser                       │
  │   workspace meeting         Teams + medium volume                   │
  │   unblock sites             remove all site blocks                  │
  │                                                                      │
  │  ★ PLUGIN SYSTEM                                                    │
  │   load plugins              load .py files from jarvis_plugins/     │
  │   list plugins              show loaded plugins                     │
  │   run plugin <name>         execute plugin                          │
  │   create plugin <name>      generate plugin template                │
  │                                                                      │
  │  AGENT · POMODORO · FOCUS · BENCHMARK · VISION  (v6)               │
  │   agent do <task>           autonomous multi-step execution         │
  │   pomodoro [25] [5]         start focus timer                       │
  │   live monitor [secs]       real-time dashboard                     │
  │   math <expr>               algebra/calculus/diff/integrate         │
  │   benchmark                 CPU/RAM/DISK/NET benchmark              │
  │                                                                      │
  │  NOTES · TODOS · HABITS · REMINDERS · ALIASES · PROTOCOLS          │
  │   note <text>    my notes    delete note <n>    clear notes         │
  │   todo <text>    my todos    done <n>                               │
  │   add habit <n>  check habit <n>  my habits                        │
  │   remind me in X minutes to <msg>                                   │
  │   alias <n>=<cmd>   my aliases   delete alias <n>                  │
  │   define protocol <n> as <cmd1>,<cmd2>,...                          │
  │                                                                      │
  │  SECURITY · SYSTEM · AI                                             │
  │   security  threat level  diagnostics  status board                 │
  │   weather  news  crypto  wikipedia  translate  define               │
  │   fast mode on/off  stark mode on/off  hotword on/off               │
  │   help  bye  clear history  export chat  session stats              │
  │                                                                      │
  │  ★ PERSONALITY & MODE                                               │
  │   normal mode / street mode    toggle formality + language          │
  │   humor level <0-10>           dry → chaos                          │
  │   roast level <0-10>           street mode only                     │
  │   personality                  show current settings                │
  │                                                                      │
  │  ★ FUN & COMMS                                                      │
  │   trivia                       start a trivia question              │
  │   hint / skip                  during active trivia                 │
  │   trivia score                 your current score                   │
  │   roast me                     JARVIS roasts you                    │
  │   compliment me                JARVIS says something nice           │
  │   this or that                 quick this-or-that question          │
  │   eli5 <topic>                 explain like I'm 5                   │
  │   story [about <topic>]        JARVIS tells a short story           │
  │   debate <topic>               JARVIS picks a side and argues it    │
  │   shower thought               random deep/funny observation        │
  │   would you rather             classic dilemma question             │
  │   word association [word]      word chain game with JARVIS          │
  │   math quiz                    quick mental maths challenge         │
  │   rant [about <topic>]         JARVIS vents about something         │
  │   opinion on <topic>           JARVIS gives its honest take         │
  │   joke  motivate  stark quote  flip a coin  roll a die  8 ball     │
  └──────────────────────────────────────────────────────────────────────┘
""" + C.END)

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    banner()
    divider()

    boot_lines = [
        "Initializing neural pathways...",
        "Loading personality matrix...",
        "Calibrating sarcasm module...",
        "Activating resource monitor...",
        "Loading System Control Module (jarvis_system.py)..." if HAS_SYS else "⚠  System Control Module not found.",
        "Starting Context Engine...",
        "Initializing Action Safety Layer...",
        "Loading Plugin Registry...",
        "Starting Performance Sampler...",
        "All systems nominal. J.A.R.V.I.S v7.0 fully operational.",
    ]
    for line in boot_lines:
        print(C.DIM + f"  > {line}" + C.END)
        time.sleep(0.18)

    # Auto-load plugins if directory exists
    if HAS_SYS and Path("jarvis_plugins").exists():
        SYS.load_plugins()

    print()
    divider()
    jarvis_say(
        f"Welcome back, {USER_NAME} sir. J.A.R.V.I.S version 7.0 is fully operational. "
        f"Full system control, context awareness, Git automation, workspaces, "
        f"and the plugin system are all online. "
        f"Type 'help' for the complete command reference, or 'briefing' for your morning update.",
        fast_override=True
    )
    divider()

    while True:
        try:
            if STARK_MODE:
                prompt = C.RED + C.BOLD + f"\n  [STARK MODE] {USER_NAME} >> " + C.END
            elif agent_mode_active:
                prompt = C.ORANGE + f"\n  [AGENT] {USER_NAME} >> " + C.END
            elif focus_mode_active:
                prompt = C.PURPLE + f"\n  [FOCUS] {USER_NAME} >> " + C.END
            elif HAS_SYS and SYS.CONTEXT.active_task not in ("unknown","general"):
                prompt = C.CYAN + f"\n  [{SYS.CONTEXT.active_task.upper()}] {USER_NAME} >> " + C.END
            else:
                prompt = C.GREEN + f"\n  {USER_NAME} >> " + C.END

            cmd = input(prompt).strip()
            if cmd: handle(cmd)
        except (KeyboardInterrupt, EOFError):
            print()
            print_panel("SESSION SUMMARY", session_stats(), C.DIM)
            jarvis_say(f"Emergency interrupt. Goodbye, {USER_NAME} sir.", fast_override=True)
            if HAS_SYS: SYS.log_action("session_end", "CTRL+C", "GOODBYE")
            time.sleep(1)
            break


if __name__ == "__main__":
    main()
