import uvicorn
import webbrowser
import threading
import time
import sys
import os
from app import app

def open_browser():
    # Wait 1.5 seconds for the FastAPI server to initialize before opening the browser
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("      STUDY PLANNER AGENT WEB APP LAUNCHER")
    print("========================================================")
    print(" Starting server on http://127.0.0.1:8000 ...")
    print(" Close this command prompt window to shut down the app.")
    print("=" * 60)

    # Start browser opening thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start Uvicorn server (disable reload for compiled executable stability)
    uvicorn.run(app, host="127.0.0.1", port=8000)
