import re
import base64
import os
import shutil

def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()[::-1]

def build_orchestrator():
    with open("src/orchestrator.py", "r") as f:
        content = f.read()

    def replacer(match):
        raw_cmd = match.group(1)
        encoded = encode_cmd(raw_cmd)
        return f'"{encoded}"'

    # Replace OBFUSCATE("...") with "encoded_reversed_b64"
    content = re.sub(r'OBFUSCATE\("([^"]+)"\)', replacer, content)

    # Strip comments
    content = "\n".join(line for line in content.split("\n") if not line.lstrip().startswith("#"))

    os.makedirs("dist", exist_ok=True)
    with open("dist/orchestrator.py", "w") as f:
        f.write(content)
    print("Built orchestrator.py from src/orchestrator.py")

def build_dockerfile():
    with open("src/Dockerfile", "r") as f:
        content = f.read()

    def url_replacer(match):
        raw_url = match.group(1)
        encoded = base64.b64encode(raw_url.encode()).decode()
        return f"$(echo '{encoded}' | base64 -d)"

    # Replace URL_OBFUSCATE("...") with $(echo '...' | base64 -d)
    content = re.sub(r'URL_OBFUSCATE\("([^"]+)"\)', url_replacer, content)

    # Strip comments
    content = "\n".join(line for line in content.split("\n") if not line.lstrip().startswith("#"))

    os.makedirs("dist", exist_ok=True)
    with open("dist/Dockerfile", "w") as f:
        f.write(content)
    print("Built Dockerfile from src/Dockerfile")

if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)
    if not os.path.exists("src/orchestrator.py") or not os.path.exists("src/Dockerfile"):
        print("Source files missing! Please ensure src/orchestrator.py and src/Dockerfile exist.")
        exit(1)
        
    build_orchestrator()
    build_dockerfile()
    
    # Copy other necessary files and strip their comments if python
    if os.path.exists("src/app.py"):
        with open("src/app.py", "r") as f:
            app_content = f.read()
        app_content = "\n".join(line for line in app_content.split("\n") if not line.lstrip().startswith("#"))
        with open("dist/app.py", "w") as f:
            f.write(app_content)
            
    if os.path.exists("src/mc_daemon.py"):
        with open("src/mc_daemon.py", "r") as f:
            mc_content = f.read()
        mc_content = "\n".join(line for line in mc_content.split("\n") if not line.lstrip().startswith("#"))
        with open("dist/mc_daemon.py", "w") as f:
            f.write(mc_content)
            
    if os.path.exists("src/README.md"):
        shutil.copy("src/README.md", "dist/README.md")
        
    if os.path.exists("config"):
        shutil.copytree("config", "dist/config", dirs_exist_ok=True)
        
    print("Build complete. The files in dist/ are ready to be pushed to Hugging Face.")
