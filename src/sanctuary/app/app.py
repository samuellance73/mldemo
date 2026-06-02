import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path


app = FastAPI(title="Sanctuary Gateway Core")



@app.get("/api/hello")
def api_hello():
    return {"message": "Success! React frontend is talking to FastAPI backend on port 7861."}


# 2. Dynamic React Production Routing
# Looks for assets folder in /home/user/frontend_dist
static_dir = Path("/home/user/frontend_dist")

if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Fallback path routing to index.html (supports React Router routing client-side)
    @app.get("/{catchall:path}")
    def serve_react(catchall: str):
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse(
            status_code=404,
            content={"error": "index.html not found inside frontend_dist."}
        )
else:
    # Local fallback for debugging if React hasn't been compiled yet
    @app.get("/{catchall:path}")
    def dev_fallback(catchall: str):
        return JSONResponse(
            status_code=200,
            content={
                "status": "warning",
                "message": "FastAPI is running, but React frontend assets are missing. Run 'npm run build' inside frontend/."
            }
        )
    
if __name__ == "__main__":
    # Binds to 7861 so Caddy reverse-proxies it as the default fallback route
    uvicorn.run(app, host="127.0.0.1", port=7861)