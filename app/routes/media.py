from flask import Blueprint, request
from app.utils.security import admin_required, ok, err
from app.services.media_service import (
    upload_banner_image,
    upload_blog_cover,
    upload_brand_logo,
    upload_product_video,
    validate_image,
    validate_video,
)

media_bp = Blueprint("media", __name__, url_prefix="/media")


@media_bp.route("/upload-image", methods=["POST"])
@admin_required
def upload_image():
    if "file" not in request.files:
        return err("No file provided")
    file = request.files["file"]

    valid, msg = validate_image(file)
    if not valid:
        return err(msg)

    upload_type = request.form.get("type", "banner")
    if upload_type == "blog":
        slug = request.form.get("slug", "post")
        result = upload_blog_cover(file, slug)
    elif upload_type == "brand":
        name = request.form.get("name", "brand")
        result = upload_brand_logo(file, name)
    else:
        position = request.form.get("position", "homepage")
        result = upload_banner_image(file, position)

    return ok(result, "Image uploaded", 201)


@media_bp.route("/upload-video", methods=["POST"])
@admin_required
def upload_video():
    if "file" not in request.files:
        return err("No file provided")
    file = request.files["file"]

    valid, msg = validate_video(file)
    if not valid:
        return err(msg)

    product_id = request.form.get("product_id", "lookbook")
    result = upload_product_video(file, product_id)
    return ok(result, "Video uploaded", 201)