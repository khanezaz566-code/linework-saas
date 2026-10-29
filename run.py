"""Start the Linework server:  python run.py  (then open http://localhost:8000)"""
import os, sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))
    uvicorn.run("server.app:app", host=os.environ.get("HOST", "0.0.0.0"), port=port, log_level="info")
