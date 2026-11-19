#!/usr/bin/env python3
"""
J.A.R.V.I.S v8.0 LAUNCHER
Usage:
  python launch.py          -> start web server
  python launch.py --setup  -> install deps + config wizard
  python launch.py --cli    -> terminal mode (jarvis_v7.py)
  python launch.py --check  -> check system only
  python launch.py --models 6  -> model recommendations for 6GB VRAM
"""
import sys, os, json, subprocess, argparse, socket
from pathlib import Path

# Windows consoles default to cp1252, which cannot print the Unicode banner.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

R="\033[91m";G="\033[92m";Y="\033[93m";C="\033[96m";D="\033[2m";E="\033[0m"

BANNER=f"""{C}
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝{E}
{C}  J.A.R.V.I.S v8.0  —  Just A Rather Very Intelligent System{E}
"""

REQUIRED = {
    "fastapi":   "fastapi",
    "uvicorn":   "uvicorn[standard]",
    "requests":  "requests",
    "psutil":    "psutil",
    "aiofiles":  "aiofiles",
    "multipart": "python-multipart",
}

OPTIONAL = {
    "speech_recognition": ("SpeechRecognition", "Voice input"),
    "pyautogui":          ("pyautogui",          "Mouse/keyboard automation"),
    "pyperclip":          ("pyperclip",           "Clipboard access"),
    "PIL":                ("Pillow",              "Screen vision"),
    "playsound":          ("playsound",           "TTS audio playback"),
    "sympy":              ("sympy",               "Advanced math solver"),
}

FILES_NEED = ["jarvis_core.py", "jarvis_server.py", "jarvis_ui.html"]
FILES_OPT  = ["jarvis_system.py", "jarvis_v7.py", "jarvis.wav"]

def imp(name):
    try: __import__(name); return True
    except ImportError: return False

def check_ollama():
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"  {G}✓{E}  Ollama running — {len(models)} model(s): {', '.join(models[:4]) or 'none'}")
            return True, models
    except Exception:
        pass
    print(f"  {Y}⚠{E}  Ollama not running — start with: ollama serve")
    return False, []

def model_recs(vram):
    recs = {
        6:  [("qwen2.5:7b","Best all-around, fits clean"),
             ("qwen2.5-coder:7b","Best for coding"),
             ("llava:7b","Vision support"),
             ("mistral:7b","Alternative all-rounder")],
        8:  [("qwen2.5:7b","Fast with headroom"),
             ("llava:13b","Better vision"),
             ("qwen2.5-coder:7b","Code specialist")],
        10: [("qwen2.5:14b","Best quality at this VRAM"),
             ("phi4:14b","Very smart"),
             ("llava:13b","High quality vision")],
        12: [("qwen2.5:14b","Runs comfortably"),
             ("mixtral:8x7b","Very capable MoE")],
    }
    bucket = min([k for k in recs if k >= vram], default=10)
    print(f"\n  {C}Recommended models for {vram}GB VRAM:{E}")
    for model, desc in recs.get(bucket, recs[10]):
        print(f"  {G}→{E}  ollama pull {model:<30} {D}{desc}{E}")
    print()

def full_check():
    print(BANNER)
    print(f"  {C}=== SYSTEM CHECK ==={E}\n")
    v = sys.version_info
    if v >= (3,10): print(f"  {G}✓{E}  Python {v.major}.{v.minor}.{v.micro}")
    else: print(f"  {R}✗{E}  Python 3.10+ required, you have {v.major}.{v.minor}")

    print(f"\n  {C}Required packages:{E}")
    all_ok = True
    for name, pkg in REQUIRED.items():
        if imp(name): print(f"  {G}✓{E}  {name}")
        else: print(f"  {R}✗{E}  {name}  →  pip install {pkg}"); all_ok = False

    print(f"\n  {C}Optional packages:{E}")
    for name, (pkg, desc) in OPTIONAL.items():
        if imp(name): print(f"  {G}✓{E}  {desc}")
        else: print(f"  {Y}○{E}  {desc} (pip install {pkg})")

    print(f"\n  {C}Files:{E}")
    files_ok = True
    for f in FILES_NEED:
        if Path(f).exists(): print(f"  {G}✓{E}  {f}")
        else: print(f"  {R}✗{E}  {f} MISSING"); files_ok = False
    for f in FILES_OPT:
        if Path(f).exists(): print(f"  {G}✓{E}  {f} (optional)")
        else: print(f"  {Y}○{E}  {f} (optional)")

    print(f"\n  {C}Ollama:{E}")
    check_ollama()

    if all_ok and files_ok:
        print(f"\n  {G}All checks passed. JARVIS is ready.{E}\n")
    else:
        print(f"\n  {R}Issues found. Run: python launch.py --setup{E}\n")
    return all_ok and files_ok

def setup():
    print(f"\n  {C}Installing required packages...{E}\n")
    for name, pkg in REQUIRED.items():
        if not imp(name):
            print(f"  Installing {pkg}...")
            r = subprocess.run([sys.executable,"-m","pip","install",pkg,"--quiet"],
                               capture_output=True, text=True)
            if r.returncode == 0: print(f"  {G}✓{E}  {pkg}")
            else: print(f"  {R}✗{E}  {pkg} failed")
        else:
            print(f"  {G}✓{E}  {name} already installed")

    print(f"\n  {C}=== CONFIG WIZARD ==={E}\n")
    cfg = {}
    cfg["user_name"]    = input(f"  Your name [{Y}Moksh{E}]: ").strip() or "Moksh"
    cfg["default_city"] = input(f"  City [{Y}Dharmavaram{E}]: ").strip() or "Dharmavaram"

    _, models = check_ollama()
    if models:
        print(f"\n  Available models:")
        for i, m in enumerate(models): print(f"    {i+1}. {m}")
        choice = input(f"  Choose model [1]: ").strip()
        try:
            idx = int(choice) - 1
            cfg["primary_model"] = models[idx] if 0 <= idx < len(models) else "qwen2.5:7b"
        except ValueError:
            cfg["primary_model"] = "qwen2.5:7b"
    else:
        cfg["primary_model"] = input(f"  Primary model [{Y}qwen2.5:7b{E}]: ").strip() or "qwen2.5:7b"

    cfg["weather_api_key"] = input(f"  OpenWeatherMap API key (optional): ").strip()

    defaults = {
        "ollama_url":"http://127.0.0.1:11434",
        "fast_model":"llama3:latest",
        "vision_model":"llava:7b",
        "code_model":"qwen2.5-coder:7b",
        "max_history_tokens":4000,
        "fast_mode":True,"stream_responses":True,
        "response_cache_ttl":300,"personality_mode":"normal",
        "humor_level":5,"roast_level":3,
        "alert_cpu":90,"alert_ram":85,
        "tts_url":"http://127.0.0.1:8000/tts","tts_voice_file":"jarvis.wav",
    }
    final = {**defaults, **cfg}
    Path("jarvis_config.json").write_text(json.dumps(final, indent=2))
    print(f"\n  {G}Config saved to jarvis_config.json{E}")
    print(f"  {G}Setup complete. Run: python launch.py{E}\n")

def start(port=5000):
    # Check port free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        if s.connect_ex(("localhost", port)) == 0:
            print(f"  {Y}Port {port} in use — trying {port+1}{E}")
            port += 1

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"

    print(f"""
  {C}╔══════════════════════════════════════════════╗
  ║     J.A.R.V.I.S v8.0  —  STARTING          ║
  ╠══════════════════════════════════════════════╣
  ║  Local  →  http://localhost:{port}            ║
  ║  Net    →  http://{local_ip}:{port}      ║
  ║  API    →  http://localhost:{port}/api/docs   ║
  ╚══════════════════════════════════════════════╝{E}
  {D}Ctrl+C to stop{E}
""")
    import uvicorn
    from jarvis_server import app
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", access_log=False)

def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S v8.0")
    parser.add_argument("--setup",  action="store_true")
    parser.add_argument("--check",  action="store_true")
    parser.add_argument("--cli",    action="store_true")
    parser.add_argument("--port",   type=int, default=5000)
    parser.add_argument("--models", type=int, metavar="VRAM_GB")
    args = parser.parse_args()

    print(BANNER)

    if args.models:
        model_recs(args.models); return
    if args.setup:
        setup(); return
    if args.check:
        full_check(); return
    if args.cli:
        if not Path("jarvis_v7.py").exists():
            print(f"  {R}jarvis_v7.py not found{E}"); sys.exit(1)
        os.execv(sys.executable, [sys.executable, "jarvis_v7.py"]); return

    # Quick pre-flight
    missing_pkg = [pkg for name, pkg in REQUIRED.items() if not imp(name)]
    if missing_pkg:
        print(f"  {R}Missing packages: {', '.join(missing_pkg)}{E}")
        print(f"  Run: python launch.py --setup\n"); sys.exit(1)

    missing_files = [f for f in FILES_NEED if not Path(f).exists()]
    if missing_files:
        print(f"  {R}Missing files: {', '.join(missing_files)}{E}\n"); sys.exit(1)

    if not Path("jarvis_config.json").exists():
        print(f"  {Y}First run — running quick setup...{E}\n")
        try: setup()
        except KeyboardInterrupt: print(f"  {Y}Skipping setup — using defaults{E}")

    check_ollama()
    print()
    start(port=args.port)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n  {Y}JARVIS stopped. Goodbye, sir.{E}\n")
