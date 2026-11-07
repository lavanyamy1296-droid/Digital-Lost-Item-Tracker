from pathlib import Path
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "lost_items.db"
WEB_DIR = ROOT / "frontend"

app = FastAPI(title="FindIt - Digital Lost Item Tracker", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Lost', 'Found')),
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                event_date TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if count == 0:
            samples = [
                ("Black water bottle", "Accessories", "Lost", "Black insulated bottle with a small silver sticker.", "Central Library", "2026-11-04", "Aarav", "aarav@example.com", datetime.now().isoformat(timespec="seconds")),
                ("Blue backpack", "Bags", "Found", "Navy blue backpack found near the cafeteria. No contents listed.", "College Cafeteria", "2026-11-05", "Meera", "meera@example.com", datetime.now().isoformat(timespec="seconds")),
                ("Wireless earbuds case", "Electronics", "Lost", "White charging case for wireless earbuds.", "Computer Science Block", "2026-11-06", "Rohan", "rohan@example.com", datetime.now().isoformat(timespec="seconds")),
            ]
            db.executemany("""
                INSERT INTO items (item_name, category, status, description, location, event_date, contact_name, contact_email, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, samples)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FindIt API"}

@app.get("/api/items")
def get_items(status: Optional[str] = None, category: Optional[str] = None, q: Optional[str] = None):
    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if status and status in ("Lost", "Found"):
        sql += " AND status = ?"
        params.append(status)
    if category and category != "All":
        sql += " AND category = ?"
        params.append(category)
    if q:
        term = f"%{q.strip()}%"
        sql += " AND (item_name LIKE ? OR description LIKE ? OR location LIKE ? OR category LIKE ?)"
        params.extend([term, term, term, term])
    sql += " ORDER BY created_at DESC, id DESC"
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(row) for row in rows]

@app.post("/api/items")
def create_item(
    item_name: str = Form(...),
    category: str = Form(...),
    status: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    event_date: str = Form(...),
    contact_name: str = Form(...),
    contact_email: str = Form(...),
):
    values = [item_name.strip(), category, status, description.strip(), location.strip(),
              event_date, contact_name.strip(), contact_email.strip()]
    if not all(values):
        raise HTTPException(status_code=400, detail="Please complete all fields.")
    if status not in ("Lost", "Found"):
        raise HTTPException(status_code=400, detail="Status must be Lost or Found.")
    with connect() as db:
        cur = db.execute("""
            INSERT INTO items (item_name, category, status, description, location, event_date,
                               contact_name, contact_email, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*values, datetime.now().isoformat(timespec="seconds")))
        row = db.execute("SELECT * FROM items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@app.get("/api/items/{item_id}")
def get_item(item_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found.")
    return dict(row)

@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    with connect() as db:
        cur = db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found.")
    return {"message": "Report deleted."}

app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")
