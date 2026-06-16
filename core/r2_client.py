import os, logging, requests

logger = logging.getLogger(__name__)

WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL", "").rstrip("/")
ENABLED = bool(WORKER_URL)


def upload_video(file_path: str) -> str | None:
    """Upload MP4 to Cloudflare R2 via Worker, return public URL."""
    if not ENABLED:
        return None
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                f"{WORKER_URL}/r2/upload",
                files={"file": (os.path.basename(file_path), f, "video/mp4")},
                timeout=120,
            )
        if r.status_code == 200:
            url = r.text.strip()
            if url.startswith("http"):
                logger.info(f"uploaded to R2: {url}")
                return url
        logger.warning(f"R2 upload failed ({r.status_code}): {r.text[:100]}")
    except Exception as e:
        logger.warning(f"R2 upload exception: {e}")
    return None


def delete_video(url: str):
    """Delete video from R2 by its public URL."""
    if not ENABLED or not url:
        return
    filename = url.rsplit("/", 1)[-1]
    try:
        r = requests.post(
            f"{WORKER_URL}/r2/delete",
            json={"filename": filename},
            timeout=10,
        )
        if r.status_code == 200:
            logger.info(f"deleted from R2: {filename}")
    except Exception as e:
        logger.warning(f"R2 delete exception: {e}")
