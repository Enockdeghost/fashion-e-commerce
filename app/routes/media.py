"""
Media service — image & video upload / deletion via Cloudinary.
Supports compression, transformation, CDN delivery.
"""
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app
from PIL import Image
import io


def _init_cloudinary():
    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )


# ─── Image Upload ─────────────────────────────────────────────────────────────

def upload_product_image(file_obj, product_id: str, is_primary: bool = False) -> dict:
    """
    Upload a product image to Cloudinary.
    Returns {"url", "thumbnail_url", "public_id"}.
    """
    _init_cloudinary()

    folder = f"fashion/products/{product_id}"
    result = cloudinary.uploader.upload(
        file_obj,
        folder=folder,
        transformation=[
            {"width": 1200, "height": 1500, "crop": "limit", "quality": "auto:good"},
        ],
        format="webp",
        overwrite=False,
        resource_type="image",
    )

    # Generate a thumbnail URL via Cloudinary transformations
    thumbnail_url = cloudinary.CloudinaryImage(result["public_id"]).build_url(
        width=400, height=500, crop="fill", quality="auto", format="webp"
    )

    return {
        "url": result["secure_url"],
        "thumbnail_url": thumbnail_url,
        "public_id": result["public_id"],
    }


def upload_banner_image(file_obj, position: str = "homepage") -> dict:
    _init_cloudinary()
    folder = f"fashion/banners/{position}"
    result = cloudinary.uploader.upload(
        file_obj,
        folder=folder,
        transformation=[{"width": 1920, "height": 800, "crop": "limit", "quality": "auto:good"}],
        format="webp",
    )
    mobile_url = cloudinary.CloudinaryImage(result["public_id"]).build_url(
        width=768, height=500, crop="fill", quality="auto", format="webp"
    )
    return {
        "url": result["secure_url"],
        "mobile_url": mobile_url,
        "public_id": result["public_id"],
    }


def upload_brand_logo(file_obj, brand_name: str) -> dict:
    _init_cloudinary()
    result = cloudinary.uploader.upload(
        file_obj,
        folder="fashion/brands",
        transformation=[{"width": 300, "height": 150, "crop": "limit", "quality": "auto"}],
        format="webp",
    )
    return {"url": result["secure_url"], "public_id": result["public_id"]}


def upload_blog_cover(file_obj, post_slug: str) -> dict:
    _init_cloudinary()
    result = cloudinary.uploader.upload(
        file_obj,
        folder=f"fashion/blog",
        public_id=post_slug,
        transformation=[{"width": 1200, "height": 630, "crop": "fill", "quality": "auto"}],
        format="webp",
        overwrite=True,
    )
    return {"url": result["secure_url"], "public_id": result["public_id"]}


# ─── Video Upload ─────────────────────────────────────────────────────────────

def upload_product_video(file_obj, product_id: str) -> dict:
    _init_cloudinary()
    folder = f"fashion/products/{product_id}/videos"
    result = cloudinary.uploader.upload(
        file_obj,
        folder=folder,
        resource_type="video",
        transformation=[{"quality": "auto", "width": 1280, "crop": "limit"}],
    )
    # Generate a video thumbnail
    thumbnail_url = cloudinary.CloudinaryImage(result["public_id"]).build_url(
        resource_type="video", format="jpg", transformation=[
            {"width": 640, "height": 360, "crop": "fill"}
        ]
    )
    return {
        "url": result["secure_url"],
        "thumbnail_url": thumbnail_url,
        "public_id": result["public_id"],
        "duration_seconds": int(result.get("duration", 0)),
    }


# ─── Delete Media ─────────────────────────────────────────────────────────────

def delete_media(public_id: str, resource_type: str = "image") -> bool:
    _init_cloudinary()
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return result.get("result") == "ok"
    except Exception:
        return False


# ─── Bulk delete ──────────────────────────────────────────────────────────────

def delete_product_all_media(product_id: str):
    _init_cloudinary()
    try:
        cloudinary.api.delete_resources_by_prefix(f"fashion/products/{product_id}")
    except Exception:
        pass


# ─── File validation ──────────────────────────────────────────────────────────

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024    # 10MB
MAX_VIDEO_BYTES = 200 * 1024 * 1024   # 200MB


def validate_image(file_obj) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
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