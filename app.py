"""Hugging Face Gradio/Streamlit SDK Entrypoint (No Docker Required!)
When you create a Free 'Gradio' Space on Hugging Face (16 GB RAM, 2 vCPU, Free, No Credit Card),
Hugging Face automatically runs `python app.py` and exposes port 7860 over HTTPS.
This launches the full Linework AI SaaS + Built-in Multi-Core Worker on port 7860!
"""
import os
import uvicorn

if __name__ == "__main__":
    os.environ.setdefault("HF_SPACE", "1")
    port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", 7860)))
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
