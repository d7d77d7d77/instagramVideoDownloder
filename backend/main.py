import os
import ssl
import glob
import uuid
import asyncio
import certifi
from pathlib import Path
from typing import Optional

# ── SSL Fix for Railway/Nix environment ─────────────────────────────────────
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
ssl.create_default_context = lambda *a, **kw: ssl.create_default_context(
    *a, cafile=certifi.where(), **kw
)

import urllib.parse
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
import yt_dlp

# ── Rate limiter ────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Constants ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp_downloads"
TEMP_DIR.mkdir(exist_ok=True)
COOKIES_FILE = BASE_DIR / "cookies.txt"


# ── Helpers ──────────────────────────────────────────────────────────────────
def delete_file_after_delay(file_path: str, delay: int = 600):
    async def _delete():
        await asyncio.sleep(delay)
        p = Path(file_path)
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                print(f"[CLEANUP] Error deleting {file_path}: {e}")
    asyncio.create_task(_delete())


def download_video_sync(url: str, proxy: Optional[str] = None) -> dict:
    random_id = uuid.uuid4().hex[:10]
    filename_prefix = f'insta_{random_id}'

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': filename_prefix + '.%(ext)s',
        'paths': {'home': str(TEMP_DIR)},
        'restrictfilenames': True,
        'quiet': False,
        'no_warnings': False,
        # ── Block-proof headers ──────────────────────────────────────────
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': '*/*',
        },
        # ── Anti-ban pacing ──────────────────────────────────────────────
        'sleep_interval': 1,
        'max_sleep_interval': 3,
        'nocheckcertificate': True,
    }

    # Use the saved cookies.txt file for Instagram auth
    if COOKIES_FILE.exists():
        print(f"[AUTH] Using cookies file: {COOKIES_FILE}")
        ydl_opts['cookiefile'] = str(COOKIES_FILE)
    else:
        print("[AUTH] No cookies.txt found. Attempting anonymous download (may fail).")

    if proxy:
        ydl_opts['proxy'] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"[DOWNLOAD] URL: {url}")
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'instagram_video')

            pattern = str(TEMP_DIR / (filename_prefix + '.*'))
            matches = glob.glob(pattern)
            print(f"[DOWNLOAD] Glob matches: {matches}")

            if not matches:
                raise Exception("Download succeeded but output file not found on disk.")

            file_path = next((m for m in matches if m.endswith('.mp4')), matches[0])
            print(f"[DOWNLOAD] Resolved path: {file_path}")
            return {"file_path": file_path, "title": title}
    except Exception as e:
        print(f"[ERROR] {e}")
        raise Exception(str(e))


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/api/upload-cookies")
async def upload_cookies(file: UploadFile = File(...)):
    """Saves an uploaded cookies.txt (Netscape format) for use in downloads."""
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Please upload a .txt file in Netscape cookie format.")
    content = await file.read()
    COOKIES_FILE.write_bytes(content)
    return {"message": f"Cookies saved successfully ({len(content)} bytes). You can now download videos."}


@app.get("/api/cookies-status")
async def cookies_status():
    """Check if a cookies file is currently loaded."""
    if COOKIES_FILE.exists():
        size = COOKIES_FILE.stat().st_size
        return {"loaded": True, "size_bytes": size}
    return {"loaded": False}


@app.post("/api/download")
@limiter.limit("5/minute")
async def download_instagram_video(
    request: Request,
    bg_tasks: BackgroundTasks,
    url: str = Form(...),
):
    if "instagram.com" not in url:
        raise HTTPException(status_code=400, detail="Not a valid Instagram URL.")

    try:
        result = await asyncio.to_thread(download_video_sync, url)
        file_path = result['file_path']
        title = result['title']

        if not Path(file_path).exists():
            raise HTTPException(status_code=500, detail="Download failed, file not found.")

        delete_file_after_delay(file_path, 600)

        safe_title = (
            "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            or "instagram_video"
        )

        file_data = Path(file_path).read_bytes()
        encoded_name = urllib.parse.quote(f"{safe_title}.mp4")
        headers = {
            "Content-Disposition": f"attachment; filename=\"{safe_title}.mp4\"; filename*=UTF-8''{encoded_name}",
            "Content-Type": "video/mp4",
        }
        return Response(content=file_data, headers=headers, media_type="video/mp4")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")


# ── JSON download endpoint (for JSON body requests from JS) ──────────────────
class DownloadRequest(BaseModel):
    url: str
    proxy: Optional[str] = None

@app.post("/api/download-json")
@limiter.limit("5/minute")
async def download_instagram_video_json(
    request: Request,
    bg_tasks: BackgroundTasks,
    payload: DownloadRequest,
):
    if "instagram.com" not in payload.url:
        raise HTTPException(status_code=400, detail="Not a valid Instagram URL.")

    try:
        result = await asyncio.to_thread(download_video_sync, payload.url, payload.proxy)
        file_path = result['file_path']
        title = result['title']

        if not Path(file_path).exists():
            raise HTTPException(status_code=500, detail="Download failed, file not found.")

        delete_file_after_delay(file_path, 600)

        safe_title = (
            "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            or "instagram_video"
        )

        return FileResponse(
            path=file_path,
            filename=f"{safe_title}.mp4",
            media_type="video/mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")


# ── Serve frontend (must be last) ─────────────────────────────────────────────
frontend_path = BASE_DIR.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
