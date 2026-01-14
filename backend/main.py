import os
import re
import asyncio
import uuid
from pathlib import Path
from typing import Generator, List, Dict
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp
import json
from cache import RedisCache

app = FastAPI(title="Local Stream API")

# CORS configuration
def get_allowed_origins():
    """Get allowed origins from env or use defaults for local dev."""
    env_origins = os.getenv("ALLOWED_ORIGINS")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",")]
    return ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Create downloads directory
DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Initialize Redis Cache
# Use "redis" as hostname because inside docker-compose network they can see each other usually,
# BUT here we are running uvicorn likely on host (as user env) but redis in docker.
# The user's requested Redis setup is docker mapped to localhost:6379, so default localhost works.
cache = RedisCache()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_progress(self, client_id: str, data: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(data)
            except Exception as e:
                print(f"Error sending progress to {client_id}: {e}")

manager = ConnectionManager()

@app.websocket("/api/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)

def extract_video_id(url: str) -> str | None:
    """Try to extract video ID from URL without network call."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_yt_dlp_opts(format_id: str = "best") -> dict:
    """Base yt-dlp options with optional cookies support."""
    opts = {
        "format": format_id,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    
    # Check for cookies file in env or common locations
    cookies_path = os.getenv("COOKIES_FILE_PATH", "cookies.txt")
    if os.path.exists(cookies_path):
        opts["cookiefile"] = cookies_path
        
    return opts


@app.get("/api/info")
async def get_video_info(url: str = Query(..., description="YouTube URL")):
    """Fetch video metadata."""
    try:
        # Try to extract ID and check cache first
        video_id = extract_video_id(url)
        if video_id:
            cached_info = cache.get(video_id, "info")
            if cached_info:
                return cached_info

        ydl_opts = get_yt_dlp_opts()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Run in executor to avoid blocking event loop
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
        
        if info is None:
            raise HTTPException(status_code=400, detail="Could not extract video info")
        
        # Filter and format the response
        formats = []
        if info.get("formats"):
            for f in info["formats"]:
                if f.get("vcodec") != "none":  # Only video formats
                    formats.append({
                        "format_id": f.get("format_id"),
                        "format_note": f.get("format_note", ""),
                        "ext": f.get("ext", "mp4"),
                        "resolution": f.get("resolution", f"{f.get('width', '?')}x{f.get('height', '?')}"),
                        "filesize": f.get("filesize"),
                        "acodec": f.get("acodec", "none"),
                        "vcodec": f.get("vcodec", "none"),
                    })
        
        result = {
            "id": info.get("id"),
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", info.get("channel", "Unknown")),
            "formats": formats[:15],  # Limit to 15 formats
        }
        
        # Cache the result
        if result.get("id"):
            cache.set(result["id"], "info", result)
            
        return result
        
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Info Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/download")
async def download_video(
    url: str = Query(..., description="YouTube URL"),
    format_id: str = Query("best", description="Format ID"),
    client_id: str = Query(None, description="Client ID for WebSocket progress")
):
    """Stream video download."""
    
    # Sanitize format_id
    safe_format = re.sub(r'[^a-zA-Z0-9+]', '', format_id) if format_id != "best" else "best"
    
    try:
        # OPTIMIZATION: Try to check cache BEFORE fetching info from YouTube
        # This prevents blocking on yt-dlp for files we already have
        video_id = extract_video_id(url)
        
        if video_id:
            # If we successfully extracted ID, check cache immediately
            cached_metadata = cache.get(video_id, safe_format)
            
            if cached_metadata:
                # CACHE HIT
                cached_filename = cached_metadata.get("filename")
                if cached_filename and (DOWNLOADS_DIR / cached_filename).exists():
                    if client_id:
                        await manager.send_progress(client_id, {"status": "finished", "percent": 100})
                    
                    return JSONResponse({
                        "status": "success",
                        "filename": cached_filename,
                        "download_url": cached_metadata.get("download_url")
                    })
                else:
                    cache.delete(video_id, safe_format)

        # First get video title for filename
        def get_info():
            opts = get_yt_dlp_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await asyncio.to_thread(get_info)
        video_id = info.get("id") # Ensure video_id is set from source of truth
        title = info.get("title", "video")
        sanitized_title = re.sub(r'[^\w\s-]', '', title)[:50].strip()
        
        # If format_id is "best", resolve it to the specific ID
        # When extract_info is called with download=False, 'format_id' contains the selected format(s) string
        target_format_id = safe_format
        if safe_format == "best":
             target_format_id = info.get("format_id", "best")
        
        # Deterministic filename for caching
        # Format: {video_id}_{format_id}.{ext}
        # Use the resolved target_format_id for the cache key
        
        cached_metadata = cache.get(video_id, target_format_id)
        
        if cached_metadata:
            # CACHE HIT
            # Verify file actually exists
            cached_filename = cached_metadata.get("filename")
            if cached_filename and (DOWNLOADS_DIR / cached_filename).exists():
                
                # Immediately notify progress 100%
                if client_id:
                    await manager.send_progress(client_id, {
                        "status": "finished",
                        "percent": 100
                    })
                
                return JSONResponse({
                    "status": "success",
                    "filename": cached_filename,
                    "download_url": cached_metadata.get("download_url")
                })
            else:
                # File missing, clean cache
                cache.delete(video_id, target_format_id)

        # CACHE MISS - Start Download
        output_template = str(DOWNLOADS_DIR / f"{video_id}_{target_format_id}.%(ext)s")
        
        # Capture the event loop before entering the thread
        loop = asyncio.get_running_loop()
        
        def progress_hook(d):
            if d['status'] == 'downloading' and client_id:
                # Calculate progress
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes', 0)
                
                if total_bytes:
                    percent = (downloaded / total_bytes) * 100
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    # Schedule coroutine on the captured main loop
                    asyncio.run_coroutine_threadsafe(
                        manager.send_progress(client_id, {
                            "status": "downloading",
                            "percent": percent,
                            "speed": speed,
                            "eta": eta
                        }),
                        loop
                    )

            elif d['status'] == 'finished' and client_id:
                asyncio.run_coroutine_threadsafe(
                    manager.send_progress(client_id, {
                        "status": "finished",
                        "percent": 100
                    }),
                    loop
                )

                )

        ydl_opts = get_yt_dlp_opts(target_format_id)
        ydl_opts.update({
            "outtmpl": output_template,
            "progress_hooks": [progress_hook]
        })
        
        def run_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
        await asyncio.to_thread(run_download)
        
        # Find the downloaded file (matches the pattern we used)
        # Re-check for the file we just downloaded
        cache_pattern = f"{video_id}_{target_format_id}.*"
        downloaded_files = list(DOWNLOADS_DIR.glob(cache_pattern))
        if not downloaded_files:
            raise HTTPException(status_code=500, detail="Download failed - no file created")
        
        downloaded_file = downloaded_files[0]
        filename = downloaded_file.name
        safe_suffix = downloaded_file.suffix
        
        final_filename = f"{sanitized_title}{safe_suffix}"
        download_url = f"/api/files/{filename}?name={final_filename}"
        
        # Store in Redis
        metadata = {
            "filename": filename, # Store raw filename
            "download_url": download_url,
            "title": title
        }
        cache.set(video_id, target_format_id, metadata)
        
        # If user asked for "best", also cache under "best" key so next time we find it efficiently
        if safe_format == "best" and target_format_id != "best":
            cache.set(video_id, "best", metadata)
        
        return JSONResponse({
            "status": "success",
            "filename": final_filename,
            "download_url": download_url
        })
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "403" in error_msg:
            raise HTTPException(status_code=403, detail="YouTube blocked the download. Try a different format or video.")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")


@app.get("/api/files/{filename}")
async def serve_file(filename: str, name: str = None):
    """Serve a downloaded file."""
    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name
    file_path = DOWNLOADS_DIR / safe_filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type from extension
    ext = file_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    
    # Use the provided friendly name if available, otherwise use storage filename
    download_filename = name if name else safe_filename
    # Basic sanitization of the friendly name to be safe in header
    download_filename = re.sub(r'[^\w\s\-\.]', '', download_filename)
    
    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type=media_type
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}
