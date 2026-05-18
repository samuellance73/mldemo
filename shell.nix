{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    gradio
    huggingface-hub
    pyyaml
    requests
  ]);
in
pkgs.mkShell {
  name = "mldemo-env";
  
  packages = [
    pythonEnv
  ];

  shellHook = ''
    echo "================================================="
    echo "🤖 Welcome to the MLDEMO development environment!"
    echo "================================================="
    echo "Available CLI tools:"
    echo "  - huggingface-cli : Hugging Face Hub Client"
    echo "  - python          : Python with Gradio & HF Hub"
    echo ""
    echo "To authenticate with Hugging Face Hub, run:"
    echo "  huggingface-cli login"
    echo "================================================="
  '';
}
