"""Legacy entry point — delegates to the sanctuary package CLI.

Run via:  uv run cc <args>
Or:       python scripts/cc.py <args>  (this shim)
"""
from sanctuary.client.cc import main

if __name__ == "__main__":
    main()
