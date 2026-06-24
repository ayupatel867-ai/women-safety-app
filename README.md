# 🛡️ Women Safety Companion — API & Deployment Guide

## 📁 Project Structure
```
women-safety-api/
├── main.py           ← FastAPI backend (all routes)
├── requirements.txt  ← Python dependencies
├── render.yaml       ← Render auto-deploy config
└── README.md         ← This file
```

---

## 🚀 Deploy on Render (Free) — Step by Step

### Step 1: Push to GitHub
1. Go to https://github.com and create a **new repository** (e.g. `women-safety-api`)
2. Upload all 3 files: `main.py`, `requirements.txt`, `render.yaml`
   - Click **"Add file" → "Upload files"** and drag all 3 files
   - Click **"Commit changes"**

### Step 2: Deploy on Render
1. Go to https://render.com and **sign up / log in**
2. Click **"New +"** → **"Web Service"**
3. Click **"Connect a repository"** → select your GitHub repo
4. Render will auto-detect `render.yaml` and fill everything in
5. Click **"Create Web Service"**
6. Wait ~2 minutes for build to finish ✅
7. Your API URL will be: `https://women-safety-api.onrender.com`

> ⚠️ Free tier sleeps after 15 min of inactivity. First request after sleep takes ~30 sec.

---

## 📡 API Endpoints

Base URL after deploy: `https://YOUR-APP.onrender.com`

### 🔐 Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, get token |
| GET | `/auth/me` | Get logged-in user info |

**Register:**
```json
POST /auth/register
{
  "email": "priya@example.com",
  "password": "mypassword",
  "name": "Priya"
}
→ { "token": "abc123...", "name": "Priya" }
```

**Login:**
```json
POST /auth/login
{
  "email": "priya@example.com",
  "password": "mypassword"
}
→ { "token": "abc123..." }
```

> Save the token! Use it in all future requests as:
> `Authorization: Bearer abc123...`

---

### 📞 Contacts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contacts` | Get all emergency contacts |
| POST | `/contacts` | Add a contact |
| DELETE | `/contacts/{id}` | Remove a contact |

**Add contact:**
```json
POST /contacts
Authorization: Bearer YOUR_TOKEN
{
  "name": "Mom",
  "phone": "9876543210"
}
```

---

### 🚨 SOS

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sos` | Trigger SOS alert |
| GET | `/sos/history` | View past SOS events |

**Trigger SOS:**
```json
POST /sos
Authorization: Bearer YOUR_TOKEN
{
  "latitude": 21.2514,
  "longitude": 81.6296,
  "message": "Help! I'm being followed."
}
→ Returns WhatsApp links to open for each contact
```

---

### 📍 Location

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/location/share` | Share live location with contacts |

```json
POST /location/share
Authorization: Bearer YOUR_TOKEN
{
  "latitude": 21.2514,
  "longitude": 81.6296
}
→ Returns WhatsApp links with Google Maps link
```

---

## 📱 Use on Phone

After deploying, test on your phone with **Postman** (free app):
1. Download Postman from Play Store
2. Create a POST request to `https://YOUR-APP.onrender.com/auth/register`
3. Set Body → Raw → JSON, paste your details
4. Hit Send → copy the token
5. Use that token in all other requests

Or open `https://YOUR-APP.onrender.com/docs` in your phone browser —
FastAPI gives you a **free interactive API tester** built-in! 🎉

---

## 🔗 Connect your HTML app to this API

In your `women-safety-companion.html`, replace localStorage calls with:
```javascript
const API = "https://YOUR-APP.onrender.com";
const TOKEN = localStorage.getItem("token"); // saved after login

// Example: fetch contacts from API
const res = await fetch(`${API}/contacts`, {
  headers: { "Authorization": `Bearer ${TOKEN}` }
});
const contacts = await res.json();
```
