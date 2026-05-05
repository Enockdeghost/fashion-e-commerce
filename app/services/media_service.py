import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename
from PIL import Image
import io

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024      
MAX_VIDEO_BYTES = 200 * 1024 * 1024     #


def _local_upload_dir(subfolder=""):
    """Return the absolute path to the local upload directory."""
    base = os.path.join(current_app.root_path, "static", "uploads")
    if subfolder:
        base = os.path.join(base, subfolder)
    os.makedirs(base, exist_ok=True)
    return base


def _save_file(file_obj, subfolder, is_image=True):

    ext = secure_filename(file_obj.filename).rsplit(".", 1)[-1].lower()
    if is_image and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Invalid image extension .{ext}")
    if not is_image and ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError(f"Invalid video extension .{ext}")

    filename = f"{uuid.uuid4().hex}.{ext}"
    folder = _local_upload_dir(subfolder)
    filepath = os.path.join(folder, filename)
    file_obj.seek(0)
    file_obj.save(filepath)

    rel_path = os.path.join("uploads", subfolder, filename).replace("\\", "/")
    url = f"/static/{rel_path}"

    thumbnail_url = url
    if is_image:
        try:
            thumb_dir = _local_upload_dir(os.path.join(subfolder, "thumbnails"))
            thumb_path = os.path.join(thumb_dir, filename)
            img = Image.open(filepath)
            img.thumbnail((400, 500))
            img.save(thumb_path, format="WEBP" if ext == "webp" else img.format)
            thumbnail_url = f"/static/uploads/{subfolder}/thumbnails/{filename}"
        except Exception:
            pass  # thumbnail generation failed – use original

    return {
        "url": url,
        "thumbnail_url": thumbnail_url,
        "public_id": filename,          # used for deletion
    }



def upload_product_image(file_obj, product_id: str, is_primary: bool = False) -> dict:
    return _save_file(file_obj, f"products/{product_id}")


def upload_banner_image(file_obj, position: str = "homepage") -> dict:
    return _save_file(file_obj, f"banners/{position}")


def upload_brand_logo(file_obj, brand_name: str) -> dict:
    return _save_file(file_obj, "brands")


def upload_blog_cover(file_obj, post_slug: str) -> dict:
    return _save_file(file_obj, f"blog/{post_slug}")


def upload_product_video(file_obj, product_id: str) -> dict:
    result = _save_file(file_obj, f"products/{product_id}/videos", is_image=False)
    # Thumbnail not generated for videos – keep URL as placeholder
    result["duration_seconds"] = 0
    return result


def delete_media(public_id: str, resource_type: str = "image") -> bool:
    """Delete a file by its public_id (filename)."""
    try:
        
        base = os.path.join(current_app.root_path, "static", "uploads")
        for root, dirs, files in os.walk(base):
            if public_id in files:
                os.remove(os.path.join(root, public_id))
                return True
        return False
    except Exception:
        return False


def delete_product_all_media(product_id: str):
    """Remove the entire product media folder."""
    folder = os.path.join(current_app.root_path, "static", "uploads", "products", product_id)
    try:
        import shutil
        shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass



def validate_image(file_obj) -> tuple[bool, str]:
    if not file_obj:
        return False, "No file provided"
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > MAX_IMAGE_BYTES:
        return False, f"File too large (max {MAX_IMAGE_BYTES // 1024 // 1024}MB)"
    try:
        img = Image.open(file_obj)
        img.verify()
        file_obj.seek(0)
    except Exception:
        return False, "Invalid image file"
    return True, ""


def validate_video(file_obj) -> tuple[bool, str]:
    if not file_obj:
        return False, "No file provided"
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)
    if size > MAX_VIDEO_BYTES:
        return False, f"File too large (max {MAX_VIDEO_BYTES // 1024 // 1024}MB)"
    return True, ""