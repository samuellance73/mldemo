# platforms/colab/README.md
# Run these cells in order in a Google Colab notebook.

# ── Cell 1: Install uv + clone repo ──────────────────────────────────────────
# !pip install -q uv
# !git clone https://github.com/your-username/sanctuary.git /content/sanctuary
# %cd /content/sanctuary
# !uv sync

# ── Cell 2: Build obfuscated dist/ ───────────────────────────────────────────
# !uv run python main/scripts/build.py

# ── Cell 3: Launch orchestrator in background ─────────────────────────────────
# import subprocess, os
# os.chdir("/content/sanctuary/dist")
# proc = subprocess.Popen(["uv", "run", "python", "core/orchestrator.py"])
# print(f"[+] Sanctuary booting. PID: {proc.pid}")
