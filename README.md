# Local Stream - YouTube Video Downloader

A premium YouTube video downloader with a modern glassmorphism UI.

## Tech Stack
- **Frontend**: React (Vite) + TypeScript
- **Backend**: Python FastAPI + yt-dlp

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+
- `yt-dlp` installed (`pip install yt-dlp` or via package manager)

### Setup
```bash
# Install all dependencies
npm run setup
```

### Run Development Servers
```bash
npm run dev
```

This starts both:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000

### Run Separately
```bash
# Backend only
npm run backend

# Frontend only
npm run frontend
```

## Project Structure
```
├── backend/
│   ├── main.py          # FastAPI app
│   ├── requirements.txt # Python deps
│   └── venv/            # Python virtual env
├── frontend/
│   ├── src/
│   │   ├── App.tsx      # Main component
│   │   ├── App.css      # Component styles
│   │   └── index.css    # Global styles
│   └── package.json
└── package.json         # Root scripts
```
