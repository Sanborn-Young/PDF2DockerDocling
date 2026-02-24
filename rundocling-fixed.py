import subprocess
import sys

# ============================================================
# AUTO-INSTALL MISSING DEPENDENCIES
# ============================================================
REQUIRED_PACKAGES = ["requests", "python-dotenv", "Pillow"]
for _pkg in REQUIRED_PACKAGES:
    try:
        __import__(_pkg)
    except ImportError:
        print(f"[SETUP] Installing missing package: {_pkg}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", _pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[SETUP] {_pkg} installed successfully.")

import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import shutil
import json
import time
import re
import threading
import requests
import logging
import argparse
import base64
import io
import zipfile

# ============================================================
# DOCLING PDF TO MARKDOWN PROCESSOR
# VERSION: 2026-02-23-v6 | WebP recompression + .env config
# VERSION: 2026-02-23-v6 | WebP recompression + .env config
# Optimized for AnythingLLM RAG Ingestion
# ============================================================

# ============================================================
# CONFIGURATION — adjust these values to suit your environment
# ============================================================
MAX_FILE_SIZE_MB      = 500    # warn (but proceed) if PDF exceeds this size in MB
MAX_RETRIES           = 3      # retry attempts per file on API failure

PS1_TIMEOUT_SEC       = 300    # max seconds to wait for PowerShell to output a port
HEALTH_CHECK_TIMEOUT  = 180    # max seconds to wait for Docker /health to return 200
HEALTH_CHECK_INTERVAL = 3      # seconds between each /health probe
CONVERSION_TIMEOUT    = 10800  # max seconds per PDF conversion request (default: 3 hrs)


# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("docling_convert.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)
# ============================================================
# .ENV CONFIGURATION
# ============================================================
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docling_settings.env")
    load_dotenv(_env_path)
except Exception:
    pass

def _env(key, default):
    return os.environ.get(key, str(default))

SINGLE_PDF_OUTPUT_DIR = _env("SINGLE_PDF_OUTPUT_DIR", "")
WEBP_ENABLED          = _env("WEBP_ENABLED", "true").lower() == "true"
WEBP_QUALITY          = int(_env("WEBP_QUALITY", "65"))
WEBP_METHOD           = int(_env("WEBP_METHOD", "6"))
WEBP_MAX_WIDTH        = int(_env("WEBP_MAX_WIDTH", "1920"))
WEBP_MAX_HEIGHT       = int(_env("WEBP_MAX_HEIGHT", "1080"))

# ============================================================
# WEBP RECOMPRESSOR
# ============================================================
def recompress_to_webp(markdown, image_paths=None):
    if not WEBP_ENABLED:
        return markdown
    try:
        from PIL import Image
        import io as _io
    except ImportError:
        log.warning("Pillow not available — skipping WebP recompression")
        return markdown
    def _to_webp_b64(img_bytes):
        img = Image.open(_io.BytesIO(img_bytes)).convert("RGB")
        if WEBP_MAX_WIDTH and img.width > WEBP_MAX_WIDTH:
            ratio = WEBP_MAX_WIDTH / img.width
            img = img.resize((WEBP_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
        if WEBP_MAX_HEIGHT and img.height > WEBP_MAX_HEIGHT:
            ratio = WEBP_MAX_HEIGHT / img.height
            img = img.resize((int(img.width * ratio), WEBP_MAX_HEIGHT), Image.LANCZOS)
        buf = _io.BytesIO()
        img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    if image_paths:
        name_to_path = {}
        for p in image_paths:
            stem = os.path.splitext(os.path.basename(p))[0]
            name_to_path[stem] = p
        def _fill(m):
            stem = os.path.splitext(m.group(1))[0]
            disk = name_to_path.get(stem)
            if disk and os.path.isfile(disk):
                with open(disk, "rb") as fh: raw = fh.read()
                b64 = _to_webp_b64(raw)
                log.info("  Embedded from disk: %s", os.path.basename(disk))
                return "![" + stem + "](data:image/webp;base64," + b64 + ")"
            return m.group(0)
        markdown = re.sub(
            r"\*\[Slide ([^:]+): image with no extractable text\]\*",
            _fill, markdown)
    def _reencode(m):
        raw = base64.b64decode(m.group(2))
        return "![" + m.group(1) + "](data:image/webp;base64," + _to_webp_b64(raw) + ")"
    markdown = re.sub(
        r"!\[([^\]]*)\]\(data:image/(?:jpeg|png|jpg);base64,([A-Za-z0-9+/=]+)\)",
        _reencode, markdown)
    return markdown




# ============================================================
# GUI DIALOGS
# ============================================================

def _center_window(win: tk.Tk | tk.Toplevel, w: int, h: int) -> None:
    """Center a tkinter window on screen."""
    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


def ask_mode_dialog() -> str:
    """
    Show a dialog asking the user to choose between single-file or folder mode.
    Returns 'file', 'folder', or '' if cancelled.
    """
    result = {"choice": ""}

    root = tk.Tk()
    root.title("Docling Converter — Select Mode")
    root.resizable(False, False)
    # Force window to front so it isn't missed behind other windows
    root.lift()
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    _center_window(root, 460, 220)

    tk.Label(
        root, text="What would you like to convert?",
        font=("Segoe UI", 11, "bold"), pady=12
    ).pack()
    tk.Label(
        root, text="Choose a conversion mode to continue:",
        font=("Segoe UI", 9), fg="#555"
    ).pack()

    btn_frame = tk.Frame(root, pady=16)
    btn_frame.pack()

    def choose(val):
        result["choice"] = val
        root.destroy()

    tk.Button(
        btn_frame, text="📄 One PDF", width=13, height=2,
        command=lambda: choose("file"),
        bg="#4A90E2", fg="white", font=("Segoe UI", 9, "bold"), relief="flat"
    ).grid(row=0, column=0, padx=8)

    tk.Button(
        btn_frame, text="📁 PDF Folder", width=13, height=2,
        command=lambda: choose("folder"),
        bg="#5CB85C", fg="white", font=("Segoe UI", 9, "bold"), relief="flat"
    ).grid(row=0, column=1, padx=8)

    tk.Button(
        btn_frame, text="🖼️ JPEG Slides", width=13, height=2,
        command=lambda: choose("images"),
        bg="#8E44AD", fg="white", font=("Segoe UI", 9, "bold"), relief="flat"
    ).grid(row=0, column=2, padx=8)

    tk.Button(
        btn_frame, text="Cancel", width=8, height=2,
        command=root.destroy,
        bg="#D9534F", fg="white", font=("Segoe UI", 9), relief="flat"
    ).grid(row=1, column=0, columnspan=3, pady=(6, 0))

    root.mainloop()
    return result["choice"]

def ask_image_mode_dialog() -> str:
    """
    Ask the user how to handle images in the converted Markdown.
    Returns 'strip', 'placeholder', or 'embedded'. Defaults to 'strip' if cancelled.
    """
    result = {"choice": "strip"}

    root = tk.Tk()
    root.title("Image Handling Mode")
    root.resizable(False, False)
    root.lift()
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    _center_window(root, 620, 270)

    tk.Label(
        root, text="How should images be handled?",
        font=("Segoe UI", 11, "bold"), pady=10
    ).pack()

    descriptions = {
        "strip":         "🗑️  Strip Images       — Remove all images (best for RAG / AnythingLLM)",
        "placeholder":   "📌  Placeholder        — Replace images with <picture> tag (clean Markdown)",
        "embedded_text": "📝  Embed Text Images — Embed charts/diagrams only (no plain photos)",
        "embedded_full": "🖼️  Embed All Images  — Embed everything at native PDF resolution",
    }

    btn_frame = tk.Frame(root, pady=10)
    btn_frame.pack()

    def choose(val):
        result["choice"] = val
        root.destroy()

    colors = {
        "strip":         "#D9534F",
        "placeholder":   "#F0AD4E",
        "embedded_text": "#4A90E2",
        "embedded_full": "#5CB85C",
    }

    for i, (val, label) in enumerate(descriptions.items()):
        tk.Button(
            btn_frame, text=label, width=60, height=2,
            command=lambda v=val: choose(v),
            bg=colors[val], fg="white",
            font=("Segoe UI", 9), relief="flat", anchor="w", padx=10
        ).grid(row=i, column=0, pady=3, padx=8)

    root.mainloop()
    return result["choice"]



def select_pdfs_from_folder_dialog(folder_path: str) -> list[str]:
    """
    Display a scrollable checklist of all PDFs found in folder_path.
    User can select all, none, or individual files.
    Returns a list of fully-qualified normalized paths for the selected PDFs.
    """
    folder_path = os.path.normpath(folder_path)

    all_pdfs = sorted([
        f for f in os.listdir(folder_path)
        if f.lower().endswith(".pdf")
    ])

    if not all_pdfs:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "No PDFs Found",
            f"No PDF files were found in:\n{folder_path}"
        )
        root.destroy()
        return []

    result = {"selected": []}

    root = tk.Tk()
    root.title("Select PDFs to Convert")
    root.resizable(True, True)
    root.minsize(440, 320)
    _center_window(root, 600, 480)

    # ── Header ────────────────────────────────────────────────────────────
    header = tk.Frame(root, bg="#2C3E50", pady=10)
    header.pack(fill="x")
    tk.Label(
        header, text=f"📁  {os.path.basename(folder_path)}",
        font=("Segoe UI", 10, "bold"), bg="#2C3E50", fg="white"
    ).pack()
    tk.Label(
        header,
        text=f"{len(all_pdfs)} PDF(s) found — check the files you want to convert",
        font=("Segoe UI", 9), bg="#2C3E50", fg="#BDC3C7"
    ).pack()

    # ── Select All / None ─────────────────────────────────────────────────
    check_vars: list[tk.BooleanVar] = []

    ctrl_row = tk.Frame(root, pady=6)
    ctrl_row.pack(fill="x", padx=12)

    def select_all():
        for v in check_vars:
            v.set(True)

    def select_none():
        for v in check_vars:
            v.set(False)

    tk.Button(
        ctrl_row, text="✅  Select All", command=select_all, width=13,
        bg="#5CB85C", fg="white", relief="flat", font=("Segoe UI", 9)
    ).pack(side="left", padx=4)
    tk.Button(
        ctrl_row, text="❌  Select None", command=select_none, width=13,
        bg="#D9534F", fg="white", relief="flat", font=("Segoe UI", 9)
    ).pack(side="left", padx=4)

    # ── Scrollable Checklist ──────────────────────────────────────────────
    list_outer = tk.Frame(root, bd=1, relief="sunken")
    list_outer.pack(fill="both", expand=True, padx=12, pady=4)

    canvas = tk.Canvas(list_outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(list_outer, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas)

    inner.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    canvas.bind_all(
        "<MouseWheel>",
        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    )

    for i, fname in enumerate(all_pdfs):
        var = tk.BooleanVar(value=True)
        check_vars.append(var)
        bg = "#F8F9FA" if i % 2 == 0 else "#FFFFFF"
        row_frame = tk.Frame(inner, bg=bg)
        row_frame.pack(fill="x")
        tk.Checkbutton(row_frame, variable=var, bg=bg, activebackground=bg).pack(side="left", padx=(6, 0))
        tk.Label(
            row_frame, text=fname, anchor="w", bg=bg, font=("Segoe UI", 9)
        ).pack(side="left", fill="x", expand=True)
        size_kb = os.path.getsize(os.path.join(folder_path, fname)) // 1024
        tk.Label(
            row_frame, text=f"{size_kb:,} KB", anchor="e",
            bg=bg, fg="#888", font=("Segoe UI", 8)
        ).pack(side="right", padx=8)

    # ── Footer ────────────────────────────────────────────────────────────
    foot = tk.Frame(root, pady=8)
    foot.pack(fill="x", padx=12)

    def on_ok():
        result["selected"] = [
            os.path.normpath(os.path.join(folder_path, fname))
            for fname, var in zip(all_pdfs, check_vars)
            if var.get()
        ]
        if not result["selected"]:
            messagebox.showwarning("Nothing Selected", "Please select at least one PDF.")
            return
        root.destroy()

    tk.Button(
        foot, text="Convert Selected  →", command=on_ok,
        bg="#4A90E2", fg="white", width=20, font=("Segoe UI", 9, "bold"), relief="flat"
    ).pack(side="right", padx=4)
    tk.Button(
        foot, text="Cancel", command=root.destroy,
        bg="#888", fg="white", width=10, font=("Segoe UI", 9), relief="flat"
    ).pack(side="right", padx=4)

    root.mainloop()
    return result["selected"]

def ask_output_directory_dialog(parent_folder: str) -> str:
    """
    Ask the user where to save the converted .md files.
    Default suggestion is a 'folder_md' subdirectory inside parent_folder.
    Returns an absolute normalized path, or '' if cancelled.
    """
    # Normalize incoming path to fix any mixed forward/back slash issues
    parent_folder = os.path.normpath(parent_folder)
    default_path = os.path.join(parent_folder, "folder_md")

    result = {"path": ""}

    root = tk.Tk()
    root.title("Choose Output Directory")
    root.resizable(False, False)
    _center_window(root, 540, 250)

    tk.Label(
        root, text="Output Directory for Markdown Files",
        font=("Segoe UI", 11, "bold"), pady=10
    ).pack()
    tk.Label(
        root,
        text="Converted .md files will be saved here. Edit the path or browse to change it.",
        font=("Segoe UI", 9), fg="#555", wraplength=500
    ).pack()

    path_var = tk.StringVar(value=default_path)

    # ── Path Entry + Browse ───────────────────────────────────────────────
    entry_frame = tk.Frame(root, pady=10)
    entry_frame.pack(fill="x", padx=16)

    tk.Entry(
        entry_frame, textvariable=path_var,
        font=("Segoe UI", 9), width=54
    ).pack(side="left", fill="x", expand=True, padx=(0, 6))

    def browse():
        chosen = filedialog.askdirectory(
            title="Select output folder",
            initialdir=parent_folder
        )
        if chosen:
            # Normalize to fix mixed slashes from tkinter dialog
            path_var.set(os.path.normpath(chosen))

    tk.Button(
        entry_frame, text="Browse…", command=browse,
        bg="#4A90E2", fg="white", relief="flat", font=("Segoe UI", 9)
    ).pack(side="left")

    # ── Shortcut name buttons ─────────────────────────────────────────────
    hint_frame = tk.Frame(root, pady=2)
    hint_frame.pack(fill="x", padx=16)
    tk.Label(
        hint_frame, text="Quick names:", font=("Segoe UI", 8), fg="#888"
    ).pack(side="left")
    for name in ["folder_md", "markdown_output", "converted", "rag_ready"]:
        tk.Button(
            hint_frame, text=name,
            command=lambda n=name: path_var.set(os.path.normpath(os.path.join(parent_folder, n))),
            relief="flat", bg="#E9ECEF", font=("Segoe UI", 8), padx=5
        ).pack(side="left", padx=3)

    # ── OK / Cancel ───────────────────────────────────────────────────────
    foot = tk.Frame(root, pady=14)
    foot.pack()

    def on_ok():
        p = path_var.get().strip()
        if not p:
            messagebox.showwarning("No Path", "Please enter or select an output directory.")
            return
        # Normalize final path to ensure clean backslashes on Windows
        result["path"] = os.path.normpath(os.path.abspath(p))
        root.destroy()

    tk.Button(
        foot, text="Use This Folder  →", command=on_ok,
        bg="#5CB85C", fg="white", width=18, font=("Segoe UI", 9, "bold"), relief="flat"
    ).grid(row=0, column=0, padx=8)
    tk.Button(
        foot, text="Cancel", command=root.destroy,
        bg="#D9534F", fg="white", width=10, font=("Segoe UI", 9), relief="flat"
    ).grid(row=0, column=1, padx=8)

    root.mainloop()
    return result["path"]


# ============================================================
# CORE FUNCTIONS
# ============================================================

def run_pull_script_and_get_port(
    ps1_path: str = "pull-updated.ps1",
    timeout_sec: int = PS1_TIMEOUT_SEC
) -> int:
    """
    Run the PowerShell script via Popen and stream output line-by-line.
    Extracts the port as soon as it appears — does NOT wait for the script to finish,
    which prevents hanging when Docker runs in foreground/attached mode.
    """
    log.info("=" * 70)
    log.info("[STEP 1] Starting Docling Serve via PowerShell")
    log.info("=" * 70)

    try:
        proc = subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", ps1_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        log.error("Failed to launch PowerShell script: %s", e)
        return 0

    selected_port = 0
    deadline = time.time() + timeout_sec

    log.info("[INFO] Streaming PowerShell output...")

    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log.info("  [PS] %s", line)

        match = re.search(r"Using port:\s*(\d+)", line)
        if match:
            selected_port = int(match.group(1))
            log.info("Detected Docling Serve port: %d", selected_port)
            break

        if time.time() > deadline:
            log.error("Timed out after %ds waiting for port in PowerShell output.", timeout_sec)
            proc.kill()
            return 0

    # Leave process running — Docker container must stay alive in background
    return selected_port


def wait_for_docling(
    base_url: str,
    timeout: int = HEALTH_CHECK_TIMEOUT
) -> bool:
    """Poll /health until Docling is ready — avoids blind sleep."""
    log.info("Waiting for Docling container to become ready (up to %ds)...", timeout)
    deadline = time.time() + timeout
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        remaining = int(deadline - time.time())
        try:
            r = requests.get(
                f"{base_url}/health",
                timeout=3,
                proxies={"http": None, "https": None}
            )
            if r.status_code == 200:
                log.info("✅ Docling is ready! (after %d probe(s))", attempt)
                return True
            else:
                log.info(
                    "  [Health] Probe %d — HTTP %d, retrying... (%ds left)",
                    attempt, r.status_code, remaining
                )
        except requests.ConnectionError:
            log.info(
                "  [Health] Probe %d — container not yet up, retrying... (%ds left)",
                attempt, remaining
            )
        except Exception as e:
            log.info("  [Health] Probe %d — %s (%ds left)", attempt, e, remaining)

        time.sleep(HEALTH_CHECK_INTERVAL)

    log.error("❌ Docling did not become ready within %ds after %d probes.", timeout, attempt)
    return False


def prepare_single_file_directories(pdf_path: str) -> tuple[str, str, str]:
    """Stage a PDF into documents/ and prepare the outputs/ folder (single-file mode)."""
    log.info("[STEP] Preparing directories")
    base_name = os.path.basename(pdf_path)
    docs_dir = os.path.join(os.getcwd(), "documents")
    out_dir = os.path.join(os.getcwd(), "outputs")

    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    dest_pdf = os.path.join(docs_dir, base_name)
    if os.path.abspath(pdf_path) != os.path.abspath(dest_pdf):
        shutil.copy(pdf_path, dest_pdf)
        log.info("Staged PDF to %s", docs_dir)

    return base_name, os.path.abspath(docs_dir), os.path.abspath(out_dir)


def send_pdf_to_docling(
    api_base_url: str,
    pdf_path: str,
    output_dir: str,
    cleanup: bool = False,
    image_mode: str = "strip",
) -> str | None:
    """
    POST a PDF to Docling's /v1/convert/file endpoint, extract the Markdown
    from the JSON response, and write a .md file to output_dir.
    Returns the output path on success, or None on failure.
    """
    if not os.path.isfile(pdf_path):
        log.error("File not found, skipping: %s", pdf_path)
        return None

    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        log.warning(
            "%.1f MB — exceeds %d MB threshold, proceeding anyway: %s",
            size_mb, MAX_FILE_SIZE_MB, os.path.basename(pdf_path)
        )
    else:
        log.info("  File: %s  (%.1f MB)", os.path.basename(pdf_path), size_mb)

    url = f"{api_base_url.rstrip('/')}/v1/convert/file"
    base_name = os.path.basename(pdf_path)
    output_md_path = os.path.join(output_dir, os.path.splitext(base_name)[0] + ".md")

    # Map your internal label to what the Docling API actually accepts
    if image_mode == "strip":
        api_image_mode = "placeholder"
    elif image_mode == "placeholder":
        api_image_mode = "placeholder"
    else:
        api_image_mode = "embedded"


    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(pdf_path, "rb") as f:
                files = {"files": (base_name, f, "application/pdf")}
                data = {
                    "to_formats": "md",
                    "image_export_mode": api_image_mode,
                    "include_images": "true" if image_mode in ("embedded_text", "embedded_full") else "false",
                    "images_scale": "2" if image_mode == "embedded_full" else "1",
                    "table_mode": "fast",
                    "abort_on_error": "false",
                }


                stop_spinner = threading.Event()

                def spinner(stop: threading.Event = stop_spinner) -> None:
                    chars = ["|", "/", "-", "\\"]   # FIX: was \\\\ — only need one backslash
                    idx, start = 0, time.time()
                    while not stop.is_set():
                        elapsed = int(time.time() - start)
                        print(
                            f"\r[INFO] Processing... {chars[idx % 4]} ({elapsed}s)",  # FIX: was \\\r
                            end="", flush=True
                        )
                        idx += 1
                        time.sleep(0.3)

                t = threading.Thread(target=spinner, daemon=True)
                t.start()
                try:
                    response = requests.post(
                        url, files=files, data=data,
                        timeout=CONVERSION_TIMEOUT,
                        proxies={"http": None, "https": None},
                    )
                finally:
                    stop_spinner.set()
                    t.join(timeout=1)
                    print()   # newline after spinner

                log.info("DEBUG sent data: %s", data)
                log.info("DEBUG HTTP status: %s | content-type: %s",
                     response.status_code, response.headers.get("Content-Type", "?"))

            if response.status_code == 200:
                resp_data = response.json()

                status = resp_data.get("status", "unknown")
                errors = resp_data.get("errors", [])
                if errors:
                    for err in errors:
                        log.warning("Docling warning: %s", err)
                if status == "failure":
                    log.error("Docling reported failure: %s", errors)
                    return None

                markdown_content = resp_data.get("document", {}).get("md_content", "")
                if markdown_content:
                    # Belt-and-suspenders: scrub any base64 that leaked through
                    if image_mode == "strip":
                        markdown_content = re.sub(
                            r'!\[.*?\]\(data:image\/[^;]+;base64,[A-Za-z0-9+/=]+\)',  # FIX: was over-escaped
                            '',
                            markdown_content
                        )
                    markdown_content = recompress_to_webp(markdown_content)
                    os.makedirs(output_dir, exist_ok=True)
                    with open(output_md_path, "w", encoding="utf-8") as md_f:
                        md_f.write(markdown_content)
                    log.info("✅ Saved: %s", output_md_path)

                    if cleanup:
                        try:
                            os.remove(pdf_path)
                            log.info("Cleaned up temp copy: %s", pdf_path)
                        except OSError as e:
                            log.warning("Could not remove temp file: %s", e)

                    return output_md_path
                else:
                    log.error("No Markdown content in API response.")
                    log.debug("Full response: %s", resp_data)
                    return None

            else:
                log.error(
                    "Attempt %d/%d — HTTP %d: %s",
                    attempt, MAX_RETRIES, response.status_code, response.text[:300]
                )

        except Exception as e:
            log.error("Attempt %d/%d — Exception: %s", attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            log.info("Retrying in 5 seconds...")
            time.sleep(5)
            # FIX: health check before retry — detect container crash immediately
            try:
                health = requests.get(
                    f"{api_base_url}/health",
                    timeout=3,
                    proxies={"http": None, "https": None}
                )
                if health.status_code != 200:
                    log.error("❌ Container health check failed before retry — container may have crashed.")
                    log.error("   Restart Docker or re-run the program to restart the container.")
                    return None
            except requests.ConnectionError:
                log.error("❌ Container is unreachable before retry — it has likely crashed.")
                log.error("   Restart Docker or re-run the program to restart the container.")
                return None
            log.info("  [Health] Container still alive, proceeding with retry %d...", attempt + 1)

    return None


def send_images_to_docling(
    api_base_url: str,
    image_paths: list[str],
    output_dir: str,
    output_name: str,
    image_mode: str = "embedded_full",
) -> str | None:
    """
    POST multiple JPEG/PNG files to Docling in a single request.
    Returns one combined .md file with all slides in order.
    """
    url = f"{api_base_url.rstrip('/')}/v1/convert/file"
    output_md_path = os.path.join(output_dir, output_name + ".md")

    if image_mode in ("strip", "placeholder"):
        api_image_mode = "placeholder"
    else:
        api_image_mode = "embedded"

    data = {
        "to_formats": "md",
        "target_type": "inbody",
        "image_export_mode": api_image_mode,
        "include_images": "true" if image_mode in ("embedded_text", "embedded_full") else "false",
        "images_scale": "2" if image_mode == "embedded_full" else "1",
        "table_mode": "fast",
        "abort_on_error": "false",
        "force_ocr": "true",
    }


    log.info("[BATCH] Sending %d image(s) to Docling as one document...", len(image_paths))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            file_handles = []
            files = []
            for path in sorted(image_paths):
                ext = os.path.splitext(path)[1].lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                fh = open(path, "rb")
                file_handles.append(fh)
                files.append(("files", (os.path.basename(path), fh, mime)))

            stop_spinner = threading.Event()
            def spinner(stop: threading.Event = stop_spinner) -> None:
                chars = ["|", "/", "-", "\\"]
                idx, start = 0, time.time()
                while not stop.is_set():
                    elapsed = int(time.time() - start)
                    print(f"\r[INFO] Processing... {chars[idx % 4]} ({elapsed}s)", end="", flush=True, file=sys.stderr)
                    idx += 1
                    time.sleep(0.3)

            t = threading.Thread(target=spinner, daemon=True)
            t.start()

            try:
                response = requests.post(
                    url, files=files, data=data,
                    timeout=CONVERSION_TIMEOUT,
                    proxies={"http": None, "https": None},
                )
            finally:
                stop_spinner.set()
                t.join(timeout=1)
                print(file=sys.stderr)
                for fh in file_handles:
                    fh.close()

            log.info("DEBUG sent data: %s", data)
            log.info("DEBUG HTTP status: %s", response.status_code)
            log.info("DEBUG HTTP status: %s | content-type: %s",
                     response.status_code, response.headers.get("Content-Type", "?"))

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")

                if "zip" in content_type or response.content[:2] == b"PK":
                    combined_md = []
                    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                        for name in sorted(zf.namelist()):
                            if name.endswith(".md"):
                                text = zf.read(name).decode("utf-8", errors="replace").strip()
                                if not text or text in ["{", "}", "{}", "{ }"]:
                                    text = "*[Slide " + name + ": image with no extractable text]*"
                                combined_md.append("<!-- " + name + " -->\n" + text)
                    markdown_content = "\n\n---\n\n".join(combined_md)
                else:
                    resp_data = response.json()
                    if resp_data.get("status") == "failure":
                        log.error("Docling reported failure: %s", resp_data.get("errors"))
                        return None
                    markdown_content = resp_data.get("document", {}).get("md_content", "")

                if markdown_content:
                    markdown_content = recompress_to_webp(markdown_content, image_paths)
                    os.makedirs(output_dir, exist_ok=True)
                    with open(output_md_path, "w", encoding="utf-8") as md_f:
                        md_f.write(markdown_content)
                    log.info("✅ Saved: %s", output_md_path)
                    return output_md_path

                log.error("No Markdown content in response.")
                return None

            else:
                log.error("Attempt %d/%d — HTTP %d: %s",
                          attempt, MAX_RETRIES, response.status_code, response.content[:300])

        except Exception as e:
            log.error("Attempt %d/%d — Exception: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(5)

    return None


# ============================================================
# CLI ARGUMENT PARSER
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Docling PDF-to-Markdown converter for AnythingLLM"
    )
    parser.add_argument(
        "--input", nargs="+", metavar="PDF",
        help="Path(s) to PDF file(s); bypasses GUI dialogs"
    )
    parser.add_argument(
        "--ps1", default="pull-updated.ps1",
        help="PowerShell script to start the Docker container (default: pull-updated.ps1)"
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Delete temporary PDF copies from documents/ after successful conversion"
    )
    parser.add_argument(
        "--no-docker", action="store_true",
        help="Skip PowerShell/Docker startup and connect to an already-running server"
    )
    parser.add_argument(
        "--port", type=int, default=0,
        help="Port to use when --no-docker is set"
    )
    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    args = parse_args()

    print("\n" + "=" * 70)
    print("  DOCLING TO MARKDOWN CONVERTER FOR ANYTHINGLLM")
    print("=" * 70)

    # ── Start Docling once — stays running for all conversions ────────────
    if args.no_docker:
        if not args.port:
            log.error("--no-docker requires --port to be specified.")
            sys.exit(1)
        port = args.port
        log.info("Skipping Docker startup. Using port %d.", port)
    else:
        port = run_pull_script_and_get_port(args.ps1)
        if not port:
            sys.exit(1)

    base_url = f"http://localhost:{port}"
    if not wait_for_docling(base_url):
        sys.exit(1)

    # ── Main loop — repeats until user chooses to quit ────────────────────
    while True:
        pdf_files: list[str] = []
        output_dir: str = ""
        use_staging = False

        if args.input:
            # CLI mode — skip all dialogs
            pdf_files = args.input
            output_dir = os.path.normpath(os.path.abspath(os.path.join(os.getcwd(), "outputs")))
            os.makedirs(output_dir, exist_ok=True)

        else:
            mode = ask_mode_dialog()
            if not mode:
                log.info("Cancelled by user — exiting.")
                break   # exits the while loop cleanly

            if mode == "file":
                root = tk.Tk()
                root.withdraw()
                chosen = filedialog.askopenfilenames(
                    title="Select PDF file(s) to convert",
                    filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
                )
                root.destroy()

                if not chosen:
                    log.error("No file selected — returning to menu.")
                    continue   # back to top of loop, show mode dialog again

                pdf_files = list(chosen)
                use_staging = True
                output_dir = os.path.normpath(os.path.abspath(
                    SINGLE_PDF_OUTPUT_DIR if SINGLE_PDF_OUTPUT_DIR
                    else os.path.join(os.getcwd(), "outputs")
                ))
                os.makedirs(output_dir, exist_ok=True)

            elif mode == "folder":
                root = tk.Tk()
                root.withdraw()
                folder = filedialog.askdirectory(title="Select folder containing PDFs")
                root.destroy()

                if not folder:
                    log.error("No folder selected — returning to menu.")
                    continue   # back to top of loop

                folder = os.path.normpath(folder)
                log.info("[STEP] Scanning folder: %s", folder)

                pdf_files = select_pdfs_from_folder_dialog(folder)
                if not pdf_files:
                    log.info("No PDFs selected — returning to menu.")
                    continue   # back to top of loop

                output_dir = ask_output_directory_dialog(folder)
                if not output_dir:
                    log.info("Output directory selection cancelled — returning to menu.")
                    continue   # back to top of loop

                os.makedirs(output_dir, exist_ok=True)
                log.info("Output directory: %s", output_dir)

            elif mode == "images":
                root = tk.Tk()
                root.withdraw()
                folder = filedialog.askdirectory(title="Select folder containing JPEG Slides")
                root.destroy()
                if not folder:
                    log.error("No folder selected — returning to menu.")
                    continue
                folder = os.path.normpath(folder)
                image_files = sorted([
                    os.path.join(folder, f) for f in os.listdir(folder)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ])
                if not image_files:
                    log.error("No images found in folder — returning to menu.")
                    continue
                log.info("[BATCH] Found %d image(s) in: %s", len(image_files), folder)
                output_dir = ask_output_directory_dialog(folder)
                if not output_dir:
                    log.info("Output directory selection cancelled — returning to menu.")
                    continue
                os.makedirs(output_dir, exist_ok=True)
                image_mode = ask_image_mode_dialog()
                log.info("Image mode selected: %s", image_mode)
                output_name = os.path.basename(folder)
                out = send_images_to_docling(
                    base_url, image_files, output_dir,
                    output_name=output_name,
                    image_mode=image_mode,
                )
                if out:
                    print(f"\n✅ Saved: {out}")
                else:
                    print("\n❌ Failed to convert image folder.")
                continue

        # ── Image Mode Selection ──────────────────────────────────────────
        image_mode = ask_image_mode_dialog()
        log.info("Image mode selected: %s", image_mode)

        # ── Conversion Loop ───────────────────────────────────────────────
        log.info("=" * 70)
        log.info("[STEP] Converting %d PDF(s)...", len(pdf_files))
        log.info("=" * 70)

        results_ok: list[str] = []
        results_fail: list[str] = []

        for i, pdf_file in enumerate(pdf_files, 1):
            log.info("[%d/%d]  %s", i, len(pdf_files), os.path.basename(pdf_file))

            if not os.path.isfile(pdf_file):
                log.error("File not found, skipping: %s", pdf_file)
                results_fail.append(pdf_file)
                continue

            if use_staging:
                base_name, _, cur_output_dir = prepare_single_file_directories(pdf_file)
                pdf_to_send = os.path.join(os.getcwd(), "documents", base_name)
            else:
                pdf_to_send = pdf_file
                cur_output_dir = output_dir

            out = send_pdf_to_docling(
                base_url, pdf_to_send, cur_output_dir,
                cleanup=args.cleanup,
                image_mode=image_mode,
            )
            if out:
                results_ok.append(out)
            else:
                results_fail.append(pdf_file)

        # ── Summary ───────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print(f"[DONE]  {len(results_ok)}/{len(pdf_files)} file(s) converted successfully.")
        print("=" * 70)

        if results_ok:
            print("\n✅  Successfully converted:")
            for r in results_ok:
                print(f"      → {r}")

        if results_fail:
            print("\n❌  Failed / skipped:")
            for r in results_fail:
                print(f"      ✗  {r}")

        print(f"\n📤  Upload the .md file(s) from:  {output_dir}")
        print("=" * 70 + "\n")

        # ── Ask to continue or quit ───────────────────────────────────────
        # CLI mode never loops — exit after one run
        if args.input:
            break

        root = tk.Tk()
        root.withdraw()
        again = messagebox.askyesno(
            "Convert More?",
            "Conversion complete!\n\nWould you like to convert more files?",
        )
        root.destroy()

        if not again:
            log.info("User chose to exit.")
            break
        # else loop back to top — show mode dialog again

    print("\n" + "=" * 70)
    print("  All done. Docling container remains running in background.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()