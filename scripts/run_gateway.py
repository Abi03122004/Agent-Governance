import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_SRC = BASE_DIR / "backend" / "src"
DB_PATH = BASE_DIR / "backend" / "agent_governance.db"

os.environ["PYTHONPATH"] = str(BACKEND_SRC)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"
os.environ["ALLOW_DEV_HEADER_AUTH"] = "true"
sys.path.insert(0, str(BACKEND_SRC))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("agent_security.main:app", host="127.0.0.1", port=8000, log_level="info")

