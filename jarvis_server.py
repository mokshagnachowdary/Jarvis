"""
J.A.R.V.I.S WEB SERVER v8.0
FastAPI + WebSocket streaming + REST API
Run: python jarvis_server.py
Open: http://localhost:5000
"""
from __future__ import annotations
import os, sys, json, time, re, random, base64, hashlib, string, secrets
import subprocess, threading, platform, socket, webbrowser, traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import requests as _req
import psutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))
from jarvis_core import (
    CFG, save_config, build_system_prompt,
    ask_ai, ask_ai_stream, clear_history, get_ai_stats,
    conversation, ollama, router, cache,
    note_add, note_list, note_delete, note_clear, note_search, notes_by_tag,
    todo_add, todo_done, todo_delete, todo_list,
    habit_add, habit_check, habit_list,
    reminder_add, reminder_list, reminder_on_due,
    alias_set, alias_delete, alias_list, alias_get, resolve_alias,
    get_snapshot, get_perf_history, get_top_processes,
    log_action, get_action_log,
    get_session_stats, increment_command,
    PERSONALITY, set_personality_mode, set_humor_level,
    get_roast, get_compliment,
    alert_on_resource, log,
)

try:
    import jarvis_system as SYS
    HAS_SYS = True
except ImportError:
    HAS_SYS = False
    SYS = None

OS = platform.system()

app = FastAPI(title="J.A.R.V.I.S", version="8.0.0", docs_url="/api/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── WebSocket Manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
        self._lock = threading.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self.active.append(ws)

    async def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self.active:
                self.active.remove(ws)

    async def broadcast(self, data: dict):
        msg  = json.dumps(data)
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def send(self, ws: WebSocket, data: dict):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            pass

ws_manager = ConnectionManager()

import asyncio

def _on_reminder(r: dict):
    async def _push():
        await ws_manager.broadcast({"type": "reminder", "message": r["msg"], "id": r["id"]})
    try:
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(_push(), loop)
    except Exception:
        pass

reminder_on_due(_on_reminder)

def _on_alert(resource: str, value: float):
    async def _push():
        await ws_manager.broadcast({"type": "alert", "resource": resource,
                                    "value": round(value, 1),
                                    "message": f"{'CPU' if resource=='cpu' else 'RAM'} at {value:.1f}%"})
    try:
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(_push(), loop)
    except Exception:
        pass

alert_on_resource(_on_alert)

# ── Trivia / Fun data ─────────────────────────────────────────────────────────
_TRIVIA = [
    {"q": "What metal is liquid at room temperature?",        "a": "mercury",  "hint": "in thermometers"},
    {"q": "How many bits in a byte?",                          "a": "8",        "hint": "think binary"},
    {"q": "What language was Linux written in?",               "a": "c",        "hint": "one letter"},
    {"q": "Who invented the World Wide Web?",                  "a": "tim berners-lee", "hint": "British, 1989"},
    {"q": "What does RAM stand for?",                          "a": "random access memory", "hint": "temporary storage"},
    {"q": "What year was Python created?",                     "a": "1991",     "hint": "early 90s"},
    {"q": "What's 2 to the power of 10?",                     "a": "1024",     "hint": "also 1KB"},
    {"q": "What does CSS stand for?",                          "a": "cascading style sheets", "hint": "styles web pages"},
    {"q": "How many planets in the solar system?",             "a": "8",        "hint": "Pluto got demoted"},
    {"q": "What does API stand for?",                          "a": "application programming interface", "hint": "how apps talk"},
    {"q": "What year was the first iPhone released?",          "a": "2007",     "hint": "mid 2000s"},
    {"q": "What does JSON stand for?",                         "a": "javascript object notation", "hint": "common data format"},
]
_THIS_OR_THAT = [
    ("Python","JavaScript"),("Mac","Windows"),("Vim","VS Code"),
    ("Coffee","Tea"),("Dark mode","Light mode"),("Tabs","Spaces"),
    ("React","Vue"),("SQL","NoSQL"),("Android","iPhone"),
]
_WOULD_YOU_RATHER = [
    ("debug someone else's undocumented code for a living",
     "explain blockchain to your grandparents every day"),
    ("lose all your photos","lose all your contacts"),
    ("have unlimited phone battery","have laptop that never overheats"),
    ("work with a brilliant asshole","work with a nice but mediocre person"),
]
_SHOWER_THOUGHTS = [
    "If you're waiting for the waiter, you're the waiter.",
    "Every expert was once a beginner who didn't quit.",
    "The word 'bed' actually looks like a bed.",
    "Dark mode exists because we built computers that emit light and then asked them to stop.",
    "Google has answered your questions so long it probably knows you better than your friends.",
    "Every odd number has the letter 'e' in it. Every single one.",
]

_active_trivia:    dict = {}
_active_tot:       dict = {}
_active_math_quiz: dict = {}
_active_word_chain:dict = {}

# ── Command Processor ─────────────────────────────────────────────────────────
async def process_command(cmd: str, ws: WebSocket) -> dict:
    increment_command()
    c = cmd.lower().strip()
    log_action("command", cmd[:80])

    resolved = resolve_alias(cmd)
    if resolved != cmd:
        return await process_command(resolved, ws)

    # Personality
    if re.search(r"street mode|gangsta mode|unfiltered", c):
        return {"type":"message","text":set_personality_mode("street"),"mode_changed":"street"}
    if re.search(r"normal mode|formal mode", c):
        return {"type":"message","text":set_personality_mode("normal"),"mode_changed":"normal"}
    if m := re.search(r"humor level\s*(\d+)", c):
        return {"type":"message","text":set_humor_level(int(m.group(1)))}
    if "personality" in c:
        return {"type":"personality","data":PERSONALITY}

    # Time/date
    if re.search(r"\b(time|what time)\b", c):
        return {"type":"message","text":f"It's {datetime.now().strftime('%I:%M:%S %p')}, sir."}
    if re.search(r"\b(date|what day|today)\b", c):
        return {"type":"message","text":f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, sir."}
    if "uptime" in c:
        from jarvis_core import SESSION_START
        d = datetime.now()-SESSION_START; h,r=divmod(int(d.total_seconds()),3600); m2,s=divmod(r,60)
        return {"type":"message","text":f"JARVIS session uptime: {h}h {m2}m {s}s."}

    # System
    if c in ("status","system status","system info"):
        snap = get_snapshot()
        return {"type":"system_stats","data":snap.to_dict() if snap else {}}
    if c in ("processes","top processes"):
        return {"type":"processes","data":get_top_processes(10)}
    if c in ("session stats","stats","session"):
        return {"type":"session_stats","data":get_session_stats()}
    if c in ("ai stats","model stats"):
        return {"type":"ai_stats","data":get_ai_stats()}
    if c in ("action log","audit log"):
        return {"type":"action_log","data":get_action_log(30)}

    # Notes
    if c.startswith("note ") or c.startswith("remember "):
        text = re.sub(r"^(note|remember)\s+","",cmd,flags=re.I).strip()
        n = note_add(text)
        return {"type":"note_added","note":n,"text":f"Logged. Tagged: {', '.join(n['tags'])}."}
    if c in ("my notes","notes","show notes","recall"):
        return {"type":"notes","data":note_list()}
    if m := re.search(r"delete note (\d+)",c):
        removed = note_delete(int(m.group(1)))
        return {"type":"message","text":f"Deleted: '{removed}'" if removed else "Not found, sir."}
    if "clear notes" in c:
        note_clear(); return {"type":"message","text":"All notes purged, sir."}
    if m := re.search(r"search notes?\s+(.+)",c):
        return {"type":"notes","data":note_search(m.group(1).strip())}
    if m := re.search(r"notes (?:by tag|tagged)\s+(\w+)",c):
        return {"type":"notes","data":notes_by_tag(m.group(1))}

    # Todos
    if m := re.match(r"^todo\s+(urgent|high|low)?\s*(.+)",c):
        t = todo_add(m.group(2).strip(), m.group(1) or "normal")
        return {"type":"todo_added","todo":t,"text":f"Todo added [{t['priority']}]."}
    if c in ("my todos","todos","show todos"):
        return {"type":"todos","data":todo_list()}
    if m := re.search(r"done (\d+)",c):
        ok = todo_done(int(m.group(1)))
        return {"type":"message","text":"Marked complete, sir." if ok else "Invalid index, sir."}
    if m := re.search(r"delete todo (\d+)",c):
        ok = todo_delete(int(m.group(1)))
        return {"type":"message","text":"Deleted, sir." if ok else "Not found, sir."}

    # Habits
    if m := re.search(r"add habit\s+(.+)",c):
        ok = habit_add(m.group(1).strip())
        return {"type":"message","text":f"Habit '{m.group(1).strip()}' added." if ok else "Already tracked."}
    if m := re.search(r"check habit\s+(.+)",c):
        result = habit_check(m.group(1).strip())
        if not result: return {"type":"message","text":"Habit not found. Add it first."}
        if result.get("already_done"):
            return {"type":"message","text":f"Already done today. Streak: {result['streak']} days."}
        return {"type":"habit_checked","data":result,
                "text":f"✓ Checked in. Streak: {result['streak']}d | Total: {result['total']}d."}
    if c in ("my habits","habits"):
        return {"type":"habits","data":habit_list()}

    # Reminders
    if m := re.search(r"remind(?:er)? (?:me )?in (\d+) min(?:ute)?s?(?: to | )(.+)",cmd,re.I):
        r = reminder_add(m.group(2).strip(), int(m.group(1)))
        return {"type":"reminder_set","reminder":r,"text":f"Reminder set for {m.group(1)} min: '{m.group(2).strip()}'."}
    if m := re.search(r"remind(?:er)? (?:me )?at (\d{1,2}):(\d{2}) (?:to )?(.+)",cmd,re.I):
        now = datetime.now()
        target = now.replace(hour=int(m.group(1)),minute=int(m.group(2)),second=0)
        if target < now: target += timedelta(days=1)
        mins = int((target-now).total_seconds()/60)
        r = reminder_add(m.group(3).strip(), mins)
        return {"type":"reminder_set","reminder":r,"text":f"Reminder set for {target.strftime('%H:%M')}."}
    if c in ("reminders","my reminders"):
        return {"type":"reminders","data":reminder_list()}

    # Aliases
    if m := re.match(r"alias\s+(\S+)\s*=\s*(.+)",cmd,re.I):
        alias_set(m.group(1),m.group(2).strip())
        return {"type":"message","text":f"Alias '{m.group(1)}' → '{m.group(2).strip()}' saved."}
    if c in ("my aliases","aliases"):
        return {"type":"aliases","data":alias_list()}
    if m := re.search(r"delete alias\s+(\S+)",c):
        ok = alias_delete(m.group(1))
        return {"type":"message","text":f"Alias '{m.group(1)}' {'removed' if ok else 'not found'}, sir."}

    # Model switching
    if m := re.search(r"switch model\s+(.+)",c):
        CFG["primary_model"] = m.group(1).strip(); save_config(CFG)
        return {"type":"message","text":f"Model switched to '{m.group(1).strip()}', sir."}
    if c in ("list models","available models"):
        return {"type":"models","data":ollama.list_models(),"current":CFG["primary_model"]}
    if "clear history" in c:
        clear_history(); return {"type":"message","text":"Conversation cleared, sir."}

    # System control
    if HAS_SYS:
        if m := re.search(r"set volume\s+(\d+)",c):
            return {"type":"message","text":SYS.set_volume(int(m.group(1)))}
        if m := re.search(r"set brightness\s+(\d+)",c):
            return {"type":"message","text":SYS.set_brightness(int(m.group(1)))}
        if "wifi on" in c:  return {"type":"message","text":SYS.wifi_on()}
        if "wifi off" in c: return {"type":"message","text":SYS.wifi_off()}
        if "bluetooth on" in c:  return {"type":"message","text":SYS.bluetooth_on()}
        if "bluetooth off" in c: return {"type":"message","text":SYS.bluetooth_off()}
        if "screenshot" in c: return {"type":"message","text":SYS.take_screenshot()}
        if "lock screen" in c: return {"type":"message","text":SYS.lock_screen()}
        if m := re.search(r"kill pid\s+(\d+)",c):
            return {"type":"message","text":SYS.kill_process_pid(int(m.group(1)),confirm=False)}
        if "auto optimize" in c:
            result = SYS.auto_optimize()
            return {"type":"optimize_result","data":result,"text":result[-1] if result else "Done."}
        if "bottleneck" in c:
            return {"type":"bottleneck","data":SYS.bottleneck_report()}
        if "battery" in c:
            return {"type":"battery","data":SYS.get_battery_info()}
        if m := re.search(r"workspace\s+(\w+)",c):
            result = SYS.activate_workspace(m.group(1))
            return {"type":"workspace","data":result,"text":result[-1] if result else "Done."}
        if c in ("list workspaces","workspaces"):
            return {"type":"workspaces","data":SYS.list_workspaces()}
        if "git status" in c:
            mp = re.search(r"git status\s*(.+)?",c)
            return {"type":"git","data":SYS.git_status(mp.group(1).strip() if mp and mp.group(1) else ".")}
        if "git push" in c:   return {"type":"git","data":SYS.git_push()}
        if "git pull" in c:   return {"type":"git","data":SYS.git_pull()}
        if "git diff" in c:   return {"type":"git","data":SYS.git_diff()}
        if "git branch" in c: return {"type":"git","data":SYS.git_branch_list()}
        if "smart commit" in c or "commit all" in c:
            return {"type":"git","data":SYS.smart_git_commit()}
        if m := re.search(r"git commit\s+[\"']?(.+)[\"']?",c):
            return {"type":"git","data":SYS.git_commit(m.group(1).strip())}
        if m := re.search(r"run shell\s+(.+)",cmd,re.I):
            return {"type":"shell_output","data":SYS.run_shell(m.group(1).strip(),confirm_if_danger=False)}
        if m := re.search(r"find file\s+(.+)",c):
            return {"type":"files","data":SYS.search_files(m.group(1).strip())}
        if m := re.search(r"open file\s+(.+)",c):
            return {"type":"message","text":SYS.open_file(m.group(1).strip())}
        if m := re.search(r"open (?:url|website)\s+(.+)",c):
            return {"type":"message","text":SYS.open_url(m.group(1).strip())}
        if m := re.search(r"install package\s+(.+)",c):
            return {"type":"shell_output","data":SYS.install_package(m.group(1).strip())}
        if c in ("network interfaces","net interfaces"):
            return {"type":"network","data":SYS.get_network_interfaces()}
        if m := re.search(r"dns\s+(?:lookup\s+)?(\S+)",c):
            return {"type":"dns","data":SYS.dns_lookup(m.group(1))}
        if "large files" in c:
            return {"type":"files","data":SYS.find_large_files()}
        if "duplicate files" in c:
            return {"type":"files","data":SYS.find_duplicate_files()}
        if "startup programs" in c:
            return {"type":"startup","data":SYS.get_startup_programs()}
        if "system logs" in c or "error logs" in c:
            return {"type":"logs","data":SYS.get_system_logs()}
        if "speed test" in c or "bandwidth" in c:
            return {"type":"speed_test","data":SYS.network_speed_test()}
        if m := re.search(r"power plan\s+(\w+)",c):
            return {"type":"message","text":SYS.set_power_plan(m.group(1))}
        if "list windows" in c or "open windows" in c:
            return {"type":"windows","data":SYS.list_open_windows()}
        if m := re.search(r"send notification\s+(.+)",c):
            return {"type":"message","text":SYS.send_notification("JARVIS",m.group(1).strip())}
        for app_name in SYS.ENHANCED_APP_MAP:
            if f"open {app_name}" in c or f"launch {app_name}" in c:
                return {"type":"message","text":SYS.open_app(app_name)}

    # Code execution
    if m := re.search(r"^run code\s+(.+)",cmd,re.I|re.DOTALL):
        import io, contextlib
        code = m.group(1).strip(); buf = io.StringIO(); lines = []
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, {"__builtins__": __builtins__})
            lines = ["STATUS: OK"] + [f"  {l}" for l in (buf.getvalue() or "(no output)").splitlines()[:20]]
        except Exception as e:
            lines = [f"STATUS: ERROR", f"  {e}"]
        return {"type":"code_output","data":lines}

    # Web search
    if m := re.search(r"^(?:search|look up)\s+(.+)",c):
        q = m.group(1).strip()
        webbrowser.open(f"https://google.com/search?q={q}")
        return {"type":"message","text":f"Searching '{q}' in your browser, sir."}

    # Calc
    import math as _math
    if m := re.search(r"^calc(?:ulate)?\s+(.+)",c):
        try:
            sd = {k:getattr(_math,k) for k in dir(_math) if not k.startswith("_")}
            sd.update({"abs":abs,"round":round,"pow":pow})
            result = eval(re.sub(r"[^0-9+\-*/().%^ a-zA-Z]","",m.group(1)).replace("^","**"),{"__builtins__":{}},sd)
            return {"type":"message","text":f"Result: {result}"}
        except Exception as e:
            return {"type":"message","text":f"Calc error: {e}"}

    # Password
    if "generate password" in c or re.match(r"^password\b",c):
        pm = re.search(r"(\d+)",c); length = int(pm.group(1)) if pm else 16
        chars = string.ascii_letters+string.digits+"!@#$%^&*"
        pwd = "".join(secrets.choice(chars) for _ in range(length))
        return {"type":"password","password":pwd,"length":length,"text":f"Generated {length}-char password."}

    # Hash
    if m := re.search(r"hash\s+(.+)",cmd,re.I):
        text = m.group(1).strip()
        return {"type":"hash","data":{
            "md5":    hashlib.md5(text.encode()).hexdigest(),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "sha512": hashlib.sha512(text.encode()).hexdigest(),
        }}

    if m := re.search(r"encode\s+(.+)",cmd,re.I):
        return {"type":"message","text":f"Encoded: {base64.b64encode(m.group(1).encode()).decode()}"}
    if m := re.search(r"decode\s+(.+)",cmd,re.I):
        try: return {"type":"message","text":f"Decoded: {base64.b64decode(m.group(1)).decode()}"}
        except: return {"type":"message","text":"Invalid base64, sir."}

    # Public IP
    if "public ip" in c:
        try: ip = _req.get("https://api.ipify.org",timeout=5).text.strip(); return {"type":"message","text":f"Public IP: {ip}"}
        except: return {"type":"message","text":"Could not retrieve IP, sir."}

    # Crypto
    if any(x in c for x in ["crypto","bitcoin","ethereum","dogecoin"]):
        coins = ["bitcoin","ethereum","dogecoin","cardano","solana"]
        coin = next((x for x in coins if x in c),"bitcoin")
        try:
            r = _req.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true",timeout=8)
            data = r.json().get(coin,{}); price=data.get("usd","N/A"); change=data.get("usd_24h_change",0)
            arrow = "▲" if change>0 else "▼"
            return {"type":"crypto","coin":coin,"price":price,"change":round(change,2),
                    "text":f"{coin.capitalize()}: ${price:,} {arrow} {abs(change):.2f}% (24h)"}
        except: return {"type":"message","text":"Crypto feed unavailable, sir."}

    # Wikipedia
    if m := re.search(r"wiki(?:pedia)?\s+(.+)",c):
        try:
            r = _req.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{m.group(1).replace(' ','_')}",timeout=8)
            return {"type":"wikipedia","query":m.group(1),"text":r.json().get("extract","Not found.")[:500]}
        except: return {"type":"message","text":"Wikipedia offline, sir."}

    # News
    if "news" in c or "headlines" in c:
        try:
            r = _req.get("https://feeds.bbci.co.uk/news/rss.xml",timeout=8)
            headlines = [h for h in re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",r.text) if h!="BBC News"][:6]
            return {"type":"news","headlines":headlines}
        except: return {"type":"message","text":"News feed unavailable, sir."}

    # Translation
    if m := re.search(r"translate\s+(.+?)\s+to\s+(\w+)",cmd,re.I):
        codes = {"spanish":"es","french":"fr","german":"de","hindi":"hi","telugu":"te",
                 "japanese":"ja","chinese":"zh","russian":"ru","arabic":"ar"}
        code = codes.get(m.group(2).lower(), m.group(2)[:2].lower())
        try:
            r = _req.get("https://api.mymemory.translated.net/get",
                         params={"q":m.group(1),"langpair":f"en|{code}"},timeout=8)
            result = r.json().get("responseData",{}).get("translatedText","")
            return {"type":"message","text":f"Translation ({m.group(2)}): {result}"}
        except: return {"type":"message","text":"Translation unavailable, sir."}

    # Fun
    if "roast me" in c: return {"type":"message","text":get_roast()}
    if "compliment me" in c or "say something nice" in c: return {"type":"message","text":get_compliment()}
    if "flip a coin" in c or "coin flip" in c:
        result = random.choice(["Heads","Tails"])
        return {"type":"coin_flip","result":result,"text":f"The coin lands on {result}."}
    if "roll a die" in c or "roll dice" in c:
        result = random.randint(1,6)
        return {"type":"dice_roll","result":result,"text":f"You rolled a {result}."}
    if "shower thought" in c or "random thought" in c:
        return {"type":"message","text":random.choice(_SHOWER_THOUGHTS)}
    if "would you rather" in c:
        a,b = random.choice(_WOULD_YOU_RATHER)
        return {"type":"would_you_rather","a":a,"b":b,"text":f"Would you rather: {a} — or — {b}?"}
    if "this or that" in c:
        a,b = random.choice(_THIS_OR_THAT)
        _active_tot.update({"a":a,"b":b,"active":True})
        return {"type":"this_or_that","a":a,"b":b,"text":f"This or that: {a} or {b}?"}
    if "trivia" in c and "score" not in c:
        q = random.choice(_TRIVIA)
        _active_trivia.update({"q":q,"active":True})
        return {"type":"trivia","question":q["q"],"text":q["q"]}
    if _active_trivia.get("active") and not any(x in c for x in ["trivia","hint","skip"]):
        ans=_active_trivia["q"]["a"].lower(); _active_trivia["active"]=False
        correct = ans in c or c in ans
        return {"type":"trivia_result","correct":correct,
                "text":"Correct! Well done, sir." if correct else f"Wrong. Answer was '{_active_trivia['q']['a']}', sir."}
    if "hint" in c and _active_trivia.get("active"):
        return {"type":"message","text":f"Hint: {_active_trivia['q']['hint']}."}
    if "math quiz" in c or "quick math" in c:
        ops = [("+",lambda a,b:a+b),("-",lambda a,b:a-b),("×",lambda a,b:a*b)]
        op,fn = random.choice(ops); a,b = random.randint(2,20),random.randint(2,12)
        _active_math_quiz.update({"ans":fn(a,b),"active":True})
        return {"type":"math_quiz","question":f"{a} {op} {b} = ?","text":f"Quick maths: {a} {op} {b} = ?"}
    if _active_math_quiz.get("active"):
        m2 = re.search(r"\d+",c)
        if m2:
            _active_math_quiz["active"] = False
            correct = int(m2.group()) == _active_math_quiz["ans"]
            return {"type":"math_result","correct":correct,
                    "text":"Correct!" if correct else f"Nope. Answer was {_active_math_quiz['ans']}."}
    if "word association" in c:
        seed = random.choice(["code","fire","space","dream","dark","machine"])
        _active_word_chain.update({"active":True,"last":seed})
        return {"type":"word_chain","word":seed,"text":f"Word association — I say: '{seed}'. Your turn."}
    if _active_word_chain.get("active") and len(c.split())==1:
        ai_word = ask_ai(f"Word association. Word: '{c}'. Respond with ONE word only.",
                         raw=True, force_model=CFG.get("fast_model",CFG["primary_model"]))
        ai_word = ai_word.strip().split()[0].rstrip(".,!?")
        _active_word_chain["last"] = ai_word
        return {"type":"word_chain","word":ai_word,"text":f"'{ai_word}'. Your turn."}
    if m := re.search(r"^(?:eli5|explain like)\s+(.+)",c):
        reply = ask_ai(f"Explain '{m.group(1)}' like the user is 5. Simple, fun analogy, 3 sentences max.",raw=True)
        return {"type":"message","text":reply}
    if "tell" in c and "story" in c or c=="story":
        sm = re.search(r"story(?:\s+about\s+)?(.+)?",c)
        topic = sm.group(1).strip() if sm and sm.group(1) else random.choice(["a programmer debugging at 3am","Tony Stark's worst invention","a robot that learned sarcasm"])
        reply = ask_ai(f"Tell a short funny story (4-6 sentences) about: {topic}. {'Casual, swear if it fits.' if PERSONALITY['mode']=='street' else 'Dry wit, British tone.'}",raw=True)
        return {"type":"message","text":reply}
    if m := re.search(r"^debate\s+(.+)",c):
        reply = ask_ai(f"Pick a side on: '{m.group(1)}'. Argue in 3-4 sharp sentences. Be opinionated.",raw=True)
        return {"type":"message","text":reply}
    if "rant" in c:
        topic = re.sub(r"^rant\s*(about\s*)?","",cmd,flags=re.I).strip() or random.choice(["JavaScript","meetings","Windows updates","slow internet"])
        reply = ask_ai(f"Rant about '{topic}' for 3-4 sentences. Be funny and exasperated.",raw=True)
        return {"type":"message","text":reply}
    if m := re.search(r"(?:your\s+)?opinion\s+(?:on\s+)?(.+)|what do you think (?:about|of)\s+(.+)",c):
        topic=(m.group(1) or m.group(2)).strip()
        reply = ask_ai(f"Give your honest opinionated take on: '{topic}'. Don't hedge. 3-4 sentences.",raw=True)
        return {"type":"message","text":reply}

    # Jokes/quotes
    if any(x in c for x in ["joke","make me laugh","funny"]):
        jokes_n=["Why do programmers prefer dark mode? Light attracts bugs.","Debugging: being a detective in a crime where you're also the murderer.","There are 10 types of people: those who understand binary, and those who don't."]
        jokes_s=["bro why do programmers work in the dark? light attracts bugs lmaooo","debugging is literally being a detective where you're also the murderer. rough.","bro you really named your variable 'x'. criminally lazy."]
        return {"type":"message","text":random.choice(jokes_s if PERSONALITY["mode"]=="street" else jokes_n)}
    if any(x in c for x in ["motivate","inspire"]) or ("quote" in c and "stark" not in c):
        return {"type":"message","text":random.choice(["The only way to do great work is to love what you do. — Jobs","Intelligence is the ability to adapt to change. — Hawking","It always seems impossible until it is done. — Mandela"])}
    if "stark quote" in c or "tony quote" in c:
        return {"type":"message","text":random.choice(["I am Iron Man. — Tony Stark","Part of the journey is the end. — Tony Stark","No amount of money ever bought a second of time. — Tony Stark"])}
    if any(x in c for x in ["8 ball","magic ball"]):
        return {"type":"message","text":random.choice(["It is certain, sir.","Very doubtful, sir.","Most likely, sir.","Ask again later, sir.","My reply is no, sir."])}

    # Briefing
    if "briefing" in c or "daily brief" in c:
        snap=get_snapshot(); notes=note_list(); todos=[t for t in todo_list() if not t["done"]]; rems=reminder_list()
        tod="morning" if datetime.now().hour<12 else "afternoon" if datetime.now().hour<17 else "evening"
        parts=[f"Good {tod}, {CFG['user_name']}.",f"It's {datetime.now().strftime('%I:%M %p')} on {datetime.now().strftime('%A, %B %d')}."]
        if snap: parts.append(f"System: CPU {snap.cpu:.0f}%, RAM {snap.ram:.0f}%.")
        parts.append(f"{len(notes)} note(s). {len(todos)} todo(s) pending. {len(rems)} reminder(s).")
        if todos:
            urgent=[t for t in todos if t["priority"] in ("urgent","high")]
            if urgent: parts.append(f"Urgent: {urgent[0]['text']}")
        return {"type":"briefing","text":" ".join(parts),"data":{"notes":len(notes),"todos":len(todos),"reminders":len(rems),"snapshot":snap.to_dict() if snap else {}}}

    # Help
    if c in ("help","commands","what can you do"):
        return {"type":"help"}

    # Goodbye
    if any(x in c for x in ["bye","exit","goodbye"]):
        stats=get_session_stats()
        return {"type":"goodbye","data":stats,"text":f"Until next time, {CFG['user_name']} sir. {stats['commands']} commands this session."}

    # AI fallback with streaming
    mode = PERSONALITY["mode"]
    loading = random.choice(
        ["aight hold on...","lemme think...","one sec...","on it..."] if mode=="street"
        else ["Analyzing, sir...","One moment...","Consulting the archives...","Processing..."]
    )
    await ws_manager.send(ws, {"type":"thinking","text":loading})
    full_reply = []
    await ws_manager.send(ws, {"type":"stream_start"})
    for token in ask_ai_stream(cmd):
        full_reply.append(token)
        await ws_manager.send(ws, {"type":"stream_token","token":token})
        await asyncio.sleep(0)
    return {"type":"stream_end","text":"".join(full_reply)}

# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    snap = get_snapshot()
    await ws_manager.send(ws, {
        "type": "init",
        "config": {k: CFG[k] for k in ("user_name","primary_model","personality_mode","humor_level","fast_mode")},
        "personality": PERSONALITY,
        "snapshot": snap.to_dict() if snap else {},
        "ai_online": ollama.available,
        "sys_online": HAS_SYS,
        "notes": note_list(),
        "todos": todo_list(),
        "habits": habit_list(),
        "reminders": reminder_list(),
        "stats": get_session_stats(),
    })
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                cmd = msg.get("command","").strip()
            except json.JSONDecodeError:
                cmd = data.strip()
            if not cmd:
                continue
            try:
                response = await process_command(cmd, ws)
                await ws_manager.send(ws, response)
            except Exception as e:
                log.error(f"Command error [{cmd!r}]: {e}")
                await ws_manager.send(ws, {
                    "type": "error",
                    "text": f"shit broke: {e}" if PERSONALITY["mode"]=="street" else f"Something went wrong, sir: {e}"
                })
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception as e:
        log.error(f"WS error: {e}")
        await ws_manager.disconnect(ws)

# ── REST endpoints ────────────────────────────────────────────────────────────
@app.get("/api/status")
async def api_status():
    snap = get_snapshot()
    return JSONResponse({"online":True,"ai_online":ollama.available,"sys_online":HAS_SYS,
                         "snapshot":snap.to_dict() if snap else {},"session":get_session_stats(),"ai":get_ai_stats()})

@app.get("/api/snapshot")
async def api_snapshot():
    snap = get_snapshot()
    return JSONResponse(snap.to_dict() if snap else {})

@app.get("/api/processes")
async def api_processes():
    return JSONResponse({"processes":get_top_processes(12)})

@app.get("/api/perf_history")
async def api_perf_history():
    return JSONResponse({"history":get_perf_history()})

@app.get("/api/notes")
async def api_notes():
    return JSONResponse({"notes":note_list()})

@app.post("/api/notes")
async def api_note_add(body: dict):
    n = note_add(body.get("text",""), body.get("tags"))
    await ws_manager.broadcast({"type":"notes","data":note_list()})
    return JSONResponse({"note":n})

@app.delete("/api/notes/{idx}")
async def api_note_delete(idx: int):
    removed = note_delete(idx)
    if removed is None: raise HTTPException(404,"Note not found")
    await ws_manager.broadcast({"type":"notes","data":note_list()})
    return JSONResponse({"deleted":removed})

@app.get("/api/todos")
async def api_todos():
    return JSONResponse({"todos":todo_list()})

@app.post("/api/todos")
async def api_todo_add(body: dict):
    t = todo_add(body.get("text",""), body.get("priority","normal"))
    await ws_manager.broadcast({"type":"todos","data":todo_list()})
    return JSONResponse({"todo":t})

@app.patch("/api/todos/{idx}/done")
async def api_todo_done(idx: int):
    ok = todo_done(idx)
    await ws_manager.broadcast({"type":"todos","data":todo_list()})
    return JSONResponse({"done":ok})

@app.delete("/api/todos/{idx}")
async def api_todo_delete(idx: int):
    ok = todo_delete(idx)
    if not ok: raise HTTPException(404,"Todo not found")
    await ws_manager.broadcast({"type":"todos","data":todo_list()})
    return JSONResponse({"deleted":ok})

@app.get("/api/habits")
async def api_habits():
    return JSONResponse({"habits":habit_list()})

@app.get("/api/reminders")
async def api_reminders():
    return JSONResponse({"reminders":reminder_list()})

@app.get("/api/aliases")
async def api_aliases():
    return JSONResponse({"aliases":alias_list()})

@app.get("/api/config")
async def api_config():
    safe = {k:v for k,v in CFG.items() if "key" not in k.lower()}
    return JSONResponse(safe)

@app.patch("/api/config")
async def api_config_update(body: dict):
    for k,v in body.items():
        if k in CFG: CFG[k]=v
    save_config(CFG)
    return JSONResponse({"updated":list(body.keys())})

@app.get("/api/ai/stats")
async def api_ai_stats():
    return JSONResponse(get_ai_stats())

@app.get("/api/models")
async def api_models():
    return JSONResponse({"models":ollama.list_models(),"current":CFG["primary_model"]})

@app.post("/api/models/switch")
async def api_model_switch(body: dict):
    model = body.get("model","")
    if not model: raise HTTPException(400,"model required")
    CFG["primary_model"]=model; save_config(CFG)
    await ws_manager.broadcast({"type":"model_changed","model":model})
    return JSONResponse({"model":model})

@app.get("/api/action_log")
async def api_action_log():
    return JSONResponse({"log":get_action_log(50)})

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = content.decode("utf-8",errors="ignore")
        summary = ask_ai(f"File: {file.filename}\n\nContent:\n{text[:3000]}\n\nSummarize this file and note anything important.",raw=True)
        return JSONResponse({"filename":file.filename,"summary":summary,"size":len(content)})
    except Exception as e:
        raise HTTPException(500,f"File error: {e}")

# ── Real-time push ────────────────────────────────────────────────────────────
async def push_stats():
    while True:
        try:
            if ws_manager.active:
                snap = get_snapshot()
                if snap:
                    await ws_manager.broadcast({"type":"snapshot","data":snap.to_dict()})
        except Exception as e:
            log.debug(f"Push: {e}")
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    asyncio.create_task(push_stats())
    log.info("JARVIS server started.")

# ── Serve UI ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    ui = Path(__file__).parent / "jarvis_ui.html"
    if ui.exists():
        return HTMLResponse(ui.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>jarvis_ui.html not found — place it in the same folder.</h1>", status_code=404)

if __name__ == "__main__":
    port = 5000
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"
    print(f"""
  J.A.R.V.I.S v8.0 starting...
  Local:   http://localhost:{port}
  Network: http://{local_ip}:{port}
  API:     http://localhost:{port}/api/docs
  Press Ctrl+C to stop.
""")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", access_log=False)
