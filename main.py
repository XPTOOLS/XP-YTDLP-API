from fastapi import FastAPI, Query, Header, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
import yt_dlp
import os
import uvicorn
from loguru import logger
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import requests

app = FastAPI(title="YouTube Downloader API", version="1.0")

# Configure Loguru
logger.add("logs.txt", rotation="1 MB", level="DEBUG")

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Serve all files in DOWNLOADS_DIR via /files route
app.mount("/files", StaticFiles(directory=DOWNLOADS_DIR), name="files")

# Static API key
API_KEY = "XPTOOLSTEAM-YTKEY"

# Dependency to verify API key
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
# Define the header for OpenAPI
api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

def verify_api_key(x_api_key: str = Security(api_key_header)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# -------------------- Routes --------------------

@app.get("/download", dependencies=[Depends(verify_api_key)])
def download_video(url: str = Query(..., description="YouTube video URL")):
    logger.info(f"Download request received for URL: {url}")
    
    ydl_opts = {
        'outtmpl': f'{DOWNLOADS_DIR}/%(title)s.%(ext)s',
        'format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        logger.success(f"Downloaded video: {info.get('title')}")

        # Return video file directly
        return FileResponse(
            path=filename,
            filename=os.path.basename(filename),
            media_type='video/mp4'
        )

    except Exception as e:
        logger.exception(f"Error downloading video: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/download/audio", dependencies=[Depends(verify_api_key)])
def download_audio(url: str = Query(..., description="YouTube video URL (audio only)")):
    logger.info(f"Audio download requested for URL: {url}")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOADS_DIR}/%(title)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            mp3_path = base + ".mp3"

        logger.success(f"Audio extracted: {info.get('title')} -> {mp3_path}")
        return FileResponse(
            path=mp3_path,
            filename=os.path.basename(mp3_path),
            media_type="audio/mpeg"
        )

    except Exception as e:
        logger.exception("Audio download failed")
        return {"status": "error", "message": str(e)}

@app.get("/thumbnail", dependencies=[Depends(verify_api_key)])
def get_thumbnail(url: str = Query(..., description="YouTube video URL")):
    logger.info(f"Thumbnail request received for URL: {url}")

    try:
        ydl_opts = {"skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        thumbnail_url = info.get("thumbnail")
        title = info.get("title", "thumbnail").replace("/", "_").replace("\\", "_")
        file_path = f"{DOWNLOADS_DIR}/{title}.jpg"

        r = requests.get(thumbnail_url, stream=True)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            logger.success(f"Thumbnail downloaded: {file_path}")
            return FileResponse(
                file_path,
                filename=os.path.basename(file_path),
                media_type="image/jpeg"
            )
        else:
            logger.error(f"Failed to fetch thumbnail (status code: {r.status_code})")
            return {"status": "error", "message": "Failed to fetch thumbnail."}

    except Exception as e:
        logger.exception("Error extracting thumbnail")
        return {"status": "error", "message": str(e)}

@app.get("/info", dependencies=[Depends(verify_api_key)])
def get_video_info(url: str = Query(..., description="YouTube video URL")):
    logger.info(f"Metadata request received for URL: {url}")

    try:
        ydl_opts = {"skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        base_filename = os.path.splitext(ydl.prepare_filename(info))[0]
        video_file = base_filename + ".mp4"
        file_url = f"http://127.0.0.1:8000/files/{os.path.basename(video_file)}" \
            if os.path.exists(video_file) else None

        return {
            "status": "success",
            "title": info.get("title"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
            "views": info.get("view_count"),
            "thumbnail": info.get("thumbnail"),
            "download_url": file_url
        }

    except Exception as e:
        logger.exception("Error fetching video info")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Render sets PORT
    uvicorn.run(
        "main:app",  # <filename>:<app instance>
        host="0.0.0.0",  # bind to all interfaces
        port=port,
        reload=False  # must be False in production
    )

