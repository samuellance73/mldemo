import re
import base64
import os
import shutil

def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()[::-1]

def build_wrapper():
    with open("src/wrapper.py", "r") as f:
        content = f.read()

    def replacer(match):
        raw_cmd = match.group(1)
        encoded = encode_cmd(raw_cmd)
        return f'"{encoded}"'

    # Replace OBFUSCATE("...") with "encoded_reversed_b64"
    content = re.sub(r'OBFUSCATE\("([^"]+)"\)', replacer, content)

    # Strip comments
    content = "\n".join(line for line in content.split("\n") if not line.lstrip().startswith("#"))

    os.makedirs("hf_deploy", exist_ok=True)
    with open("hf_deploy/wrapper.py", "w") as f:
        f.write(content)
    print("Built wrapper.py from src/wrapper.py")

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

    os.makedirs("hf_deploy", exist_ok=True)
    with open("hf_deploy/Dockerfile", "w") as f:
        f.write(content)
    print("Built Dockerfile from src/Dockerfile")

if __name__ == "__main__":
    if not os.path.exists("src/wrapper.py") or not os.path.exists("src/Dockerfile"):
        print("Source files missing! Please ensure src/wrapper.py and src/Dockerfile exist.")
        exit(1)
        
    build_wrapper()
    build_dockerfile()
    
    # Copy other necessary files and strip their comments if python
    if os.path.exists("src/app.py"):
        with open("src/app.py", "r") as f:
            app_content = f.read()
        app_content = "\n".join(line for line in app_content.split("\n") if not line.lstrip().startswith("#"))
        with open("hf_deploy/app.py", "w") as f:
            f.write(app_content)
            
    if os.path.exists("src/mc_daemon.py"):
        with open("src/mc_daemon.py", "r") as f:
            mc_content = f.read()
        mc_content = "\n".join(line for line in mc_content.split("\n") if not line.lstrip().startswith("#"))
        with open("hf_deploy/mc_daemon.py", "w") as f:
            f.write(mc_content)
            
    if os.path.exists("src/README.md"):
        shutil.copy("src/README.md", "hf_deploy/README.md")
        
    print("Build complete. The files in hf_deploy/ are ready to be pushed to Hugging Face.")
