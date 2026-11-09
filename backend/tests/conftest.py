import os
import tempfile
from pathlib import Path

# Must be set before the app (and its engine) is imported.
_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db.as_posix()}"
os.environ["SIMULATE"] = "false"
