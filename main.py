"""
LogPulse — Entry Point
Run with: python main.py  or  uvicorn main:app --reload
"""

import uvicorn
from api.app import app

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
