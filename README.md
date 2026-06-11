# Expense Intelligence

An AI-powered credit card statement analyzer. Upload a PDF or CSV statement from HDFC, ICICI, SBI, or Axis Bank — get back a fully categorized Excel file with spending breakdowns by category, merchant, and month.

No login. No database. No data stored. Upload → Analyze → Download.

---

## What It Does

- Parses credit card statements (PDF, CSV, Excel) from major Indian banks
- Categorizes every transaction using rule-based matching + local AI (Ollama)
- Generates a formatted Excel file with 4 sheets:
  - **Transactions** — every transaction with date, merchant, category, amount
  - **Category Summary** — total spent per category with % breakdown
  - **Merchant Summary** — top merchants ranked by spend
  - **Monthly Summary** — month-by-month income vs expense

---

## Supported Banks

| Bank | PDF | CSV | Excel |
|------|-----|-----|-------|
| HDFC | ✅ | ✅ | ✅ |
| ICICI | ✅ | ✅ | ✅ |
| SBI | ✅ | ✅ | ✅ |
| Axis | ✅ | ✅ | ✅ |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS, TypeScript |
| Backend | FastAPI (Python 3.12), Uvicorn |
| AI / Categorization | Ollama (qwen3:8b) — runs locally on your machine |
| PDF Parsing | pdfplumber, PyMuPDF |
| Excel Generation | pandas, openpyxl |
| Containerization | Docker, Docker Compose |

---

## Prerequisites

You need three things installed before running the project:

### 1. Docker & Docker Compose

Docker is used to run the frontend and backend in containers — no need to install Python or Node.js manually.

**Ubuntu / Debian:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```
Log out and log back in after running these commands.

**Verify:**
```bash
docker --version
docker compose version
```

> **Note for Ubuntu 24.04+ (Noble/Resolute):** If `docker compose` is not found, add Docker's official repo manually:
> ```bash
> sudo apt-get install -y ca-certificates curl
> sudo install -m 0755 -d /etc/apt/keyrings
> curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
> echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu noble stable" | sudo tee /etc/apt/sources.list.d/docker.list
> sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
> ```

---

### 2. Ollama (Local AI)

Ollama runs the AI model on your machine. The backend calls it to categorize transactions it doesn't recognize from the built-in rules.

**Install:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Download the AI model** (~5 GB, one-time):
```bash
ollama pull qwen3:8b
```

**Verify Ollama is running:**
```bash
curl http://localhost:11434/api/tags
```
You should see `qwen3:8b` listed in the response.

> Ollama must be running on the host machine when you use the app. It starts automatically on install, but if it ever stops, run `ollama serve`.

---

### 3. Git (to clone the repo)

```bash
sudo apt-get install git   # Ubuntu/Debian
```

---

## Installation & Running

### Step 1 — Clone the repository

```bash
git clone https://github.com/ABISEK2003/Expense-Analyser.git
cd Expense-Analyser
```

### Step 2 — Create the environment file

```bash
cp .env.example .env
```

Or create `.env` manually with this content:

```env
APP_NAME=Expense Intelligence
DEBUG=false

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_PRIMARY_MODEL=qwen3:8b
OLLAMA_FALLBACK_MODEL=qwen3:4b
OLLAMA_TIMEOUT=120
OLLAMA_MAX_RETRIES=3

MAX_UPLOAD_SIZE_MB=50
```

> `host.docker.internal` is how Docker containers reach the host machine. Ollama runs on the host, not inside Docker, so this is how the backend talks to it.

### Step 3 — Build and start

```bash
docker compose up -d
```

**First run takes ~10–15 minutes** — Docker needs to download base images and install all dependencies. Subsequent starts take only a few seconds.

Watch the build progress:
```bash
docker compose logs -f
```

### Step 4 — Open the app

```
http://localhost:3000
```

---

## How Docker Compose Works

The project has two containers defined in `docker-compose.yml`:

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│   ei_frontend               │     │   ei_backend                │
│   Next.js (port 3000)       │────▶│   FastAPI (port 8000)       │
│                             │     │                             │
│   Serves the UI             │     │   Parses statements         │
│   Handles file upload       │     │   Calls Ollama for AI       │
│                             │     │   Generates Excel           │
└─────────────────────────────┘     └──────────────┬──────────────┘
                                                   │
                                                   ▼
                                    ┌─────────────────────────────┐
                                    │   Ollama (host machine)     │
                                    │   qwen3:8b model            │
                                    │   port 11434                │
                                    └─────────────────────────────┘
```

### Backend Dockerfile
- Base image: `python:3.12-slim`
- Installs system libraries needed for PDF parsing (`libmupdf-dev`, `mupdf-tools`)
- Installs all Python packages from `requirements.txt`
- Runs with `--reload` so code changes apply automatically without rebuilding

### Frontend Dockerfile
- Multi-stage build to keep the final image small:
  1. **deps** stage — installs npm packages
  2. **builder** stage — runs `next build` to compile the app
  3. **runner** stage — serves the compiled output with `node server.js`

---

## Common Commands

| Action | Command |
|--------|---------|
| Start the app | `docker compose up -d` |
| Stop the app | `docker compose down` |
| View live logs | `docker compose logs -f` |
| View backend logs only | `docker compose logs -f backend` |
| Restart after code change | `docker compose restart backend` |
| Rebuild after code change | `docker compose build && docker compose up -d` |
| Check running containers | `docker compose ps` |

---

## Project Structure

```
expense-intelligence/
├── docker-compose.yml          # Defines both containers
├── .env                        # Environment variables (not committed)
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app entry point
│       ├── core/
│       │   └── config.py       # Settings (reads from .env)
│       ├── api/
│       │   └── analyze.py      # POST /api/analyze endpoint
│       ├── services/
│       │   └── analyze_service.py  # Core logic: parse → categorize → Excel
│       └── parsers/
│           ├── base.py         # Abstract base parser
│           ├── factory.py      # Auto-detects bank from file content
│           ├── hdfc.py         # HDFC parser
│           ├── icici.py        # ICICI parser
│           ├── sbi.py          # SBI parser
│           └── axis.py         # Axis parser
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── app/
        │   ├── layout.tsx      # Root layout
        │   ├── page.tsx        # Home page
        │   └── globals.css     # Tailwind base styles
        ├── components/
        │   └── UploadPage.tsx  # Main UI component
        └── lib/
            ├── api.ts          # Fetch wrapper for backend calls
            └── utils.ts        # Helper utilities
```

---

## How the Analysis Works

1. **Upload** — User drops a PDF/CSV/Excel file on the UI
2. **Detect bank** — `factory.py` reads the first page and matches keywords to identify HDFC/ICICI/SBI/Axis
3. **Parse** — The matching parser extracts: date, merchant name, amount, debit/credit
4. **Categorize** — For each unique merchant:
   - First checks 50+ built-in rules (e.g. `SWIGGY` → Food & Dining, `NETFLIX` → Subscriptions)
   - If no rule matches, asks Ollama AI to classify it
   - Results are cached so the same merchant isn't sent to AI twice
5. **Generate Excel** — pandas + openpyxl builds the 4-sheet workbook in memory
6. **Download** — The Excel file is returned directly as a download, nothing is saved on the server

---

## Troubleshooting

**"No transactions found"**
The parser didn't recognize the statement format. Make sure the file is a genuine bank statement PDF (not a scanned image). Try downloading it again from net banking.

**"Could not parse statement"**
The bank format may be slightly different from what the parser expects. Check `docker compose logs backend` for the detailed error.

**Ollama not responding / AI categorization fails**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve

# Check if the model is downloaded
ollama list
```

**Port already in use**
```bash
# Find what's using port 3000 or 8000
sudo lsof -i :3000
sudo lsof -i :8000
```

**Docker permission denied**
```bash
sudo usermod -aG docker $USER
# Then log out and log back in
```

---

## Access from Other Devices (Same Network)

Find your machine's IP:
```bash
hostname -I | awk '{print $1}'
```

Then on any device on the same WiFi, open:
```
http://<your-ip>:3000
```

If it doesn't connect, allow the ports through the firewall:
```bash
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp
```

---

## License

MIT
