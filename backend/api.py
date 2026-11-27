"""REST API（/api/v1）。所有业务逻辑在服务层，路由只做参数校验与响应组装。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import config
from .errors import reject
from .providers import image as image_provider
from .providers import llm as llm_provider
from .providers import video as video_provider
from .services import catalog, generation, imports, planning, runs, tenants
from .services import extractions as extraction_service
from .services import issues as issue_service

router = APIRouter(prefix="/api/v1")


# ---------- 请求模型 ----------
class ProductIn(BaseModel):
    id: str
    name: str
    category_id: str = "BAG"
    brand: str = ""
    origin: str = ""
    model: str = ""
    description: str = ""


class ProductPatch(BaseModel):
    name: str | None = None
    category_id: str | None = None
    brand: str | None = None
    origin: str | None = None
    model: str | None = None
    description: str | None = None


class CategoryIn(BaseModel):
    category_id: str
    category_name: str
    attributes: list[dict[str, Any]]


class SkuIn(BaseModel):
    sku_code: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class SourcePatch(BaseModel):
    view_angle: str | None = None
    purpose: str | None = None
    review_status: str | None = None
    sku_id: str | None = None
    asset_type: str | None = None
    tags: list[str] | None = None


class ExtractIn(BaseModel):
    category_id: str
    source_ids: list[str] = Field(min_length=1)
    manual: bool = False


class Resolution(BaseModel):
    issue_id: str
    resolution: str


class ConfirmIn(BaseModel):
    fields: dict[str, Any]
    base_version_id: int | None = None
    sku: str = ""
    note: str = ""
    manual_basis: dict[str, str] = Field(default_factory=dict)
    resolutions: list[Resolution] = Field(default_factory=list)


class NoteIn(BaseModel):
    note: str


class BatchIn(BaseModel):
    rows: list[dict[str, Any]] = Field(min_length=1)


class PlanIn(BaseModel):
    scene: str
    channel: str = "抖音"
    audience: str = ""
    content_type: str = "商品主图+短视频"
    source_ids: list[str] = Field(default_factory=list)
    version_id: int | None = None
    manual: bool = False
    content: dict[str, Any] | None = None


class PlanContentIn(BaseModel):
    content: dict[str, Any]
    note: str = ""


class ReuseIn(BaseModel):
    scene: str
    channel: str = "抖音"
    audience: str = ""
    content_type: str = "日常商品展示"
    output_ids: list[str] = Field(default_factory=list)
    manual: bool = False
    content: dict[str, Any] | None = None


class ImageIn(BaseModel):
    prompt: str = ""
    ratio: str = "3:4"
    count: int = Field(default=1, ge=1, le=4)
    reference_ids: list[str] | None = Field(default=None, min_length=1, max_length=4)
    source_output_id: str = ""


class VideoIn(BaseModel):
    materials: list[str] = Field(default_factory=list)
    provider: str = "ffmpeg"
    duration: int | None = None


class ReviewIn(BaseModel):
    approved: bool
    note: str = ""


class ReviseIn(BaseModel):
    prompt: str = ""
    ratio: str = "3:4"
    materials: list[str] = Field(default_factory=list)


# ---------- 健康检查与模型状态 ----------
@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": config.db_path().exists(),
        "models": config.model_status(),
        "version": "v0.3-local",
    }


@router.get("/models/status")
def models_status() -> dict[str, Any]:
    return {
        "llm": llm_provider.connectivity(),
        "image": image_provider.connectivity(),
        "video": video_provider.connectivity(),
        "ffmpeg": {
            "available": bool(config.ffmpeg_path()),
            "ffprobe": bool(config.ffprobe_path()),
            "font": config.ffmpeg_font(),
        },
        "ocr": {
            "available": bool(__import__("shutil").which("tesseract")),
            "note": "未安装 tesseract 时，图片资料会保留原件并提示人工补充字段",
        },
        "note": "模型状态只检查环境变量是否存在，不发送真实请求，也不返回密钥。",
    }


# ---------- 租户 ----------
class TenantIn(BaseModel):
    name: str
    id: str = ""


@router.get("/tenants")
def list_tenants() -> list[dict[str, Any]]:
    return tenants.list_tenants()


@router.post("/tenants", status_code=201)
def create_tenant(body: TenantIn) -> dict[str, Any]:
    return tenants.create_tenant(body.name, body.id)


# ---------- 品类模板 ----------
@router.get("/categories")
def categories() -> list[dict[str, Any]]:
    return catalog.list_categories()


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn) -> dict[str, Any]:
    return catalog.create_category(body.model_dump())


@router.put("/categories/{category_id}")
def update_category(category_id: str, body: CategoryIn) -> dict[str, Any]:
    payload = body.model_dump()
    if payload.get("category_id") != category_id:
        raise reject("品类编号不可修改")
    return catalog.update_category(category_id, payload)


@router.get("/categories/{category_id}/versions")
def category_versions(category_id: str) -> list[dict[str, Any]]:
    return catalog.category_versions(category_id)


# ---------- 商品与版本 ----------
@router.get("/products")
def products(search: str = "", category_id: str = "") -> dict[str, Any]:
    items = catalog.list_products(search.strip(), category_id.strip().upper())
    return {"items": items, "total": len(items)}


@router.post("/products", status_code=201)
def create_product(body: ProductIn) -> dict[str, Any]:
    return catalog.create_product(body.model_dump())


@router.get("/products/{product_id}")
def product_detail(product_id: str) -> dict[str, Any]:
    return catalog.get_product(product_id)


@router.put("/products/{product_id}")
def update_product(product_id: str, body: ProductPatch) -> dict[str, Any]:
    return catalog.update_product(product_id, {key: value for key, value in body.model_dump().items() if value is not None})


@router.get("/products/{product_id}/versions")
def versions(product_id: str) -> list[dict[str, Any]]:
    return catalog.list_versions(product_id)


@router.get("/products/{product_id}/versions/diff")
def version_diff(product_id: str, from_version: int | None = None, to_version: int | None = None) -> dict[str, Any]:
    return catalog.version_diff(product_id, from_version, to_version)


@router.post("/products/{product_id}/versions/{version_id}/restore")
def restore_version(product_id: str, version_id: int) -> dict[str, Any]:
    return catalog.restore_version(product_id, version_id)


@router.get("/products/{product_id}/impact")
def impact(product_id: str) -> dict[str, Any]:
    return catalog.impact(product_id)


@router.post("/products/{product_id}/regenerate-affected")
def regenerate_affected(product_id: str) -> dict[str, Any]:
    return generation.regenerate_affected(product_id)


@router.get("/products/{product_id}/skus")
def skus(product_id: str) -> list[dict[str, Any]]:
    return catalog.list_skus(product_id)


@router.post("/products/{product_id}/skus", status_code=201)
def create_sku(product_id: str, body: SkuIn) -> dict[str, Any]:
    return catalog.create_sku(product_id, body.model_dump())


@router.put("/products/{product_id}/skus/{sku_id}")
def update_sku(product_id: str, sku_id: str, body: SkuIn) -> dict[str, Any]:
    return catalog.update_sku(product_id, sku_id, body.model_dump())


@router.delete("/products/{product_id}/skus/{sku_id}")
def delete_sku(product_id: str, sku_id: str) -> dict[str, Any]:
    return catalog.delete_sku(product_id, sku_id)


# ---------- 原始资料 ----------
@router.post("/products/{product_id}/sources", status_code=201)
async def upload_source(
    product_id: str,
    file: UploadFile = File(...),
    sku_id: str = Form(""),
    purpose: str = Form("reference"),
    view_angle: str = Form(""),
    review_status: str = Form("pending"),
    asset_type: str = Form("raw"),
    tags: str = Form(""),
) -> dict[str, Any]:
    content = await file.read(config.MAX_UPLOAD_BYTES + 1)
    tags_list = [tag for tag in tags.split(",") if tag.strip()] if tags else []
    return catalog.upload_source(product_id, file.filename or "原始资料", content, sku_id=sku_id,
                                 purpose=purpose, view_angle=view_angle, review_status=review_status,
                                 asset_type=asset_type, tags=tags_list)


@router.get("/products/{product_id}/sources/{source_id}")
def source_file(product_id: str, source_id: str) -> FileResponse:
    source, path = catalog.source_file(product_id, source_id)
    return FileResponse(path, media_type=source["mime"], filename=source["name"],
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.put("/products/{product_id}/sources/{source_id}")
def update_source(product_id: str, source_id: str, body: SourcePatch) -> dict[str, Any]:
    payload = {key: value for key, value in body.model_dump().items() if value is not None}
    return catalog.update_source(product_id, source_id, payload)


@router.delete("/products/{product_id}/sources/{source_id}")
def delete_source(product_id: str, source_id: str) -> dict[str, Any]:
    return catalog.delete_source(product_id, source_id)


@router.post("/products/{product_id}/sources/{source_id}/suggest-angle")
def suggest_angle(product_id: str, source_id: str) -> dict[str, Any]:
    source = catalog.get_source(product_id, source_id)
    return catalog.suggest_angle(source["name"])


# ---------- 数据导入 ----------
@router.post("/products/{product_id}/imports/extract", status_code=201)
def extract(product_id: str, body: ExtractIn) -> dict[str, Any]:
    return imports.extract(product_id, body.category_id.strip().upper(), body.source_ids, body.manual)


@router.get("/products/{product_id}/imports")
def list_imports(product_id: str) -> list[dict[str, Any]]:
    return imports.list_imports(product_id)


@router.get("/imports/{import_id}")
def import_detail(import_id: str) -> dict[str, Any]:
    return imports.detail(import_id)


@router.post("/imports/{import_id}/reject")
def reject_import(import_id: str, body: NoteIn) -> dict[str, Any]:
    return imports.reject_import(import_id, body.note)


@router.post("/imports/{import_id}/confirm")
def confirm_import(import_id: str, body: ConfirmIn) -> dict[str, Any]:
    return imports.confirm(import_id, body.model_dump())


@router.post("/imports/batch", status_code=201)
def batch_import(body: BatchIn) -> dict[str, Any]:
    return imports.batch_import(body.rows)


@router.get("/imports/batch/{job_id}")
def get_batch(job_id: str) -> dict[str, Any]:
    return imports.get_batch(job_id)


# ---------- 提取记录与数据异常 ----------
class ResolveIn(BaseModel):
    resolution: str


@router.get("/imports/{import_id}/extractions")
def import_extractions(import_id: str) -> list[dict[str, Any]]:
    return extraction_service.list_for_import(import_id)


@router.get("/products/{product_id}/issues")
def product_issues(product_id: str, resolution_status: str = "") -> list[dict[str, Any]]:
    return issue_service.list_for_product(product_id, resolution_status)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(issue_id: str, body: ResolveIn) -> dict[str, Any]:
    return issue_service.resolve(issue_id, body.resolution)


# ---------- 素材与资产 ----------
@router.get("/assets/sources")
def assets(product_id: str = "", angle: str = "", review_status: str = "", asset_type: str = "",
           search: str = "") -> dict[str, Any]:
    items = catalog.list_all_sources(product_id=product_id, angle=angle,
                                     review_status=review_status, asset_type=asset_type, search=search)
    return {"items": items, "total": len(items)}


@router.get("/library/outputs")
def library(status: str = "", kind: str = "", product_id: str = "", search: str = "") -> dict[str, Any]:
    items = generation.library_outputs(status=status, kind=kind, product_id=product_id, search=search)
    return {"items": items, "total": len(items)}


# ---------- 内容策划 ----------
@router.get("/products/{product_id}/plans")
def plans(product_id: str) -> list[dict[str, Any]]:
    return planning.list_plans(product_id)


@router.post("/products/{product_id}/plans", status_code=201)
def create_plan(product_id: str, body: PlanIn) -> dict[str, Any]:
    return planning.create_plan(product_id, body.model_dump())


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: str) -> dict[str, Any]:
    return planning.get_plan(plan_id)


@router.put("/plans/{plan_id}")
def update_plan(plan_id: str, body: PlanContentIn) -> dict[str, Any]:
    return planning.update_plan(plan_id, body.model_dump())


@router.post("/plans/{plan_id}/confirm")
def confirm_plan(plan_id: str) -> dict[str, Any]:
    return planning.confirm_plan(plan_id)


@router.post("/plans/{plan_id}/reuse", status_code=201)
def reuse_plan(plan_id: str, body: ReuseIn) -> dict[str, Any]:
    return planning.reuse_plan(plan_id, body.model_dump())


# ---------- 内容生产、审核与交付 ----------
@router.post("/plans/{plan_id}/outputs/image", status_code=201)
def generate_image(plan_id: str, body: ImageIn) -> dict[str, Any]:
    return generation.generate_image(plan_id, body.model_dump())


@router.post("/plans/{plan_id}/outputs/video", status_code=201)
def generate_video(plan_id: str, body: VideoIn) -> dict[str, Any]:
    return generation.generate_video(plan_id, body.model_dump())


@router.get("/products/{product_id}/outputs")
def outputs(product_id: str) -> list[dict[str, Any]]:
    return generation.list_outputs(product_id)


@router.get("/outputs/{output_id}")
def output_file(output_id: str) -> FileResponse:
    path, mime, _ = generation.output_file(output_id, download=False)
    return FileResponse(path, media_type=mime, content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/outputs/{output_id}/download")
def download_output(output_id: str) -> FileResponse:
    path, mime, name = generation.output_file(output_id, download=True)
    return FileResponse(path, media_type=mime, filename=name,
                        content_disposition_type="attachment")


@router.put("/outputs/{output_id}/review")
def review_output(output_id: str, body: ReviewIn) -> dict[str, Any]:
    return generation.review_output(output_id, body.approved, body.note)


@router.post("/outputs/{output_id}/revise", status_code=201)
def revise_output(output_id: str, body: ReviseIn) -> dict[str, Any]:
    return generation.revise_output(output_id, body.model_dump())


# ---------- 任务记录、概览与统计 ----------
@router.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    return runs.get(run_id)


@router.get("/products/{product_id}/runs")
def product_runs(product_id: str) -> list[dict[str, Any]]:
    return runs.list_for_product(product_id)


@router.get("/products/{product_id}/workflow")
def workflow(product_id: str) -> dict[str, Any]:
    detail = catalog.get_product(product_id)
    sources = detail["sources"]
    return {
        "product": detail["product"],
        "sources": sources,
        "skus": detail["skus"],
        "versions": detail["versions"],
        "latest_version": detail["latest_version"],
        "completeness": detail["completeness"],
        "imports": imports.list_imports(product_id),
        "plans": planning.list_plans(product_id),
        "outputs": generation.list_outputs(product_id),
        "runs": runs.list_for_product(product_id),
        "tags": {source["id"]: source["view_angle"] for source in sources if source["view_angle"]},
        "impact": catalog.impact(product_id),
    }


@router.get("/stats")
def stats() -> dict[str, Any]:
    return generation.stats()
