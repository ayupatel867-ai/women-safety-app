from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import sqlite3, hashlib, secrets, time, os

app = FastAPI(title="Women Safety Companion API", version="1.0.0")

# ── CORS (allow your HTML app / phone to call this) ──────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
DB = os.getenv("DB_PATH", "safety.db")

# ── DATABASE SETUP ────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name     TEXT,
            token    TEXT
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name    TEXT NOT NULL,
            phone   TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sos_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            latitude  REAL,
            longitude REAL,
            message   TEXT,
            timestamp INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)
    db.commit()
    db.close()

init_db()

# ── HELPERS ──────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_token(token: str):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()
    db.close()
    return user

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return dict(user)

# ── MODELS ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = "User"

class LoginRequest(BaseModel):
    email: str
    password: str

class ContactModel(BaseModel):
    name: str
    phone: str

class SOSRequest(BaseModel):
    latitude: float
    longitude: float
    message: Optional[str] = "SOS! I need help!"

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float

# ── AUTH ROUTES ───────────────────────────────────────────────────────────────
@app.post("/auth/register", summary="Register a new user")
def register(req: RegisterRequest):
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (req.email,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    token = secrets.token_hex(32)
    db.execute(
        "INSERT INTO users (email, password, name, token) VALUES (?, ?, ?, ?)",
        (req.email, hash_password(req.password), req.name, token)
    )
    db.commit()
    db.close()
    return {"message": "Registration successful", "token": token, "name": req.name}

@app.post("/auth/login", summary="Login and get token")
def login(req: LoginRequest):
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (req.email, hash_password(req.password))
    ).fetchone()
    if not user:
        db.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # Refresh token on each login
    new_token = secrets.token_hex(32)
    db.execute("UPDATE users SET token = ? WHERE id = ?", (new_token, user["id"]))
    db.commit()
    db.close()
    return {"message": "Login successful", "token": new_token, "name": user["name"]}

@app.get("/auth/me", summary="Get logged-in user info")
def me(user=Depends(require_auth)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}

# ── CONTACTS ROUTES ───────────────────────────────────────────────────────────
@app.get("/contacts", summary="Get all emergency contacts")
def get_contacts(user=Depends(require_auth)):
    db = get_db()
    rows = db.execute("SELECT * FROM contacts WHERE user_id = ?", (user["id"],)).fetchall()
    db.close()
    return [{"id": r["id"], "name": r["name"], "phone": r["phone"]} for r in rows]

@app.post("/contacts", summary="Add an emergency contact")
def add_contact(contact: ContactModel, user=Depends(require_auth)):
    db = get_db()
    db.execute(
        "INSERT INTO contacts (user_id, name, phone) VALUES (?, ?, ?)",
        (user["id"], contact.name, contact.phone)
    )
    db.commit()
    db.close()
    return {"message": f"{contact.name} added as emergency contact"}

@app.delete("/contacts/{contact_id}", summary="Remove an emergency contact")
def delete_contact(contact_id: int, user=Depends(require_auth)):
    db = get_db()
    result = db.execute(
        "DELETE FROM contacts WHERE id = ? AND user_id = ?", (contact_id, user["id"])
    )
    db.commit()
    db.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact removed"}

# ── SOS ROUTES ────────────────────────────────────────────────────────────────
@app.post("/sos", summary="Trigger SOS alert (logs it + returns WhatsApp links)")
def trigger_sos(req: SOSRequest, user=Depends(require_auth)):
    db = get_db()

    # Log the SOS event
    db.execute(
        "INSERT INTO sos_logs (user_id, latitude, longitude, message, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user["id"], req.latitude, req.longitude, req.message, int(time.time()))
    )
    db.commit()

    # Get contacts to alert
    contacts = db.execute(
        "SELECT name, phone FROM contacts WHERE user_id = ?", (user["id"],)
    ).fetchall()
    db.close()

    maps_link = f"https://maps.google.com/?q={req.latitude},{req.longitude}"
    sos_message = (
        f"🚨 SOS ALERT from {user['name']}!\n"
        f"{req.message}\n"
        f"📍 Location: {maps_link}"
    )

    # Build WhatsApp links for each contact
    wa_links = []
    for c in contacts:
        phone = "".join(filter(str.isdigit, c["phone"]))
        wa_links.append({
            "name": c["name"],
            "phone": phone,
            "whatsapp_url": f"https://wa.me/91{phone}?text={sos_message}"
        })

    return {
        "message": "SOS triggered",
        "location": {"lat": req.latitude, "lon": req.longitude, "maps_link": maps_link},
        "contacts_alerted": len(wa_links),
        "whatsapp_links": wa_links,
        "sos_message": sos_message
    }

@app.get("/sos/history", summary="Get past SOS logs")
def sos_history(user=Depends(require_auth)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM sos_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20",
        (user["id"],)
    ).fetchall()
    db.close()
    return [
        {
            "id": r["id"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "message": r["message"],
            "timestamp": r["timestamp"],
            "maps_link": f"https://maps.google.com/?q={r['latitude']},{r['longitude']}"
        }
        for r in rows
    ]

# ── LOCATION ROUTE ────────────────────────────────────────────────────────────
@app.post("/location/share", summary="Share live location with all contacts")
def share_location(loc: LocationUpdate, user=Depends(require_auth)):
    db = get_db()
    contacts = db.execute(
        "SELECT name, phone FROM contacts WHERE user_id = ?", (user["id"],)
    ).fetchall()
    db.close()

    maps_link = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
    msg = (
        f"📍 Live location shared by {user['name']}:\n"
        f"{maps_link}\n"
        f"(Via Women Safety Companion)"
    )

    wa_links = []
    for c in contacts:
        phone = "".join(filter(str.isdigit, c["phone"]))
        wa_links.append({
            "name": c["name"],
            "whatsapp_url": f"https://wa.me/91{phone}?text={msg}"
        })

    return {
        "maps_link": maps_link,
        "share_message": msg,
        "whatsapp_links": wa_links
    }

# ── HEALTH CHECK ──────────────────────────────────────────────────────────────
@app.get("/", summary="Health check")
def root():
    return {"status": "ok", "app": "Women Safety Companion API", "version": "1.0.0"}
