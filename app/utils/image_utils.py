import os
import uuid
import logging
from io import BytesIO

import requests
from PIL import Image
from flask import current_app

logger = logging.getLogger(__name__)

ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp', 'image/tiff'}
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'tiff'}


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS


def _download_image(url: str, timeout: int = 10) -> BytesIO:
    headers = {'User-Agent': 'FredVunjabei/1.0'}
    resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
    resp.raise_for_status()

    content_type = resp.headers.get('Content-Type', '')
    if content_type and content_type not in ALLOWED_MIMES:
        raise ValueError(f"Unsupported image format: {content_type}")

    buf = BytesIO()
    for chunk in resp.iter_content(chunk_size=8192):
        buf.write(chunk)
    buf.seek(0)
    return buf


def convert_to_webp(source, upload_subfolder: str = 'products', quality: int = 82) -> str:
    upload_root = os.path.join(current_app.root_path, 'static', 'uploads', upload_subfolder)
    os.makedirs(upload_root, exist_ok=True)

    if hasattr(source, 'read'):
        if not _allowed_file(source.filename):
            raise ValueError('Unsupported file type')
        img = Image.open(source)
    else:
        buf = _download_image(source)
        img = Image.open(buf)

    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
    else:
        img = img.convert('RGB')

    out_name = f"{uuid.uuid4().hex}.webp"
    out_path = os.path.join(upload_root, out_name)

    save_kwargs = {'quality': quality, 'method': 6}
    if img.mode == 'RGBA':
        save_kwargs['lossless'] = False

    try:
        img.save(out_path, 'webp', **save_kwargs)
    except Exception as exc:
        logger.exception("Failed saving WebP")
        raise RuntimeError(f"Could not save image: {exc}") from exc

    return f"/static/uploads/{upload_subfolder}/{out_name}"