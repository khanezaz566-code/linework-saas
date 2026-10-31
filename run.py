"""Start the Linework server:  python run.py  (then open http://localhost:8000)"""
import os, sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    cur = os.path.abspath(os.path.dirname(__file__))
    reload_env = os.environ.get("RELOAD", "1")
    use_reload = reload_env.lower() in ("1", "true", "yes")

    reload_dirs = [
        os.path.join(cur, "linework"),
        os.path.join(cur, "server")
    ] if use_reload else None

    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=use_reload,
        reload_dirs=reload_dirs,
        log_level="info"
    )
