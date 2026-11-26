"""内容生产、审核、交付、复用与统计。"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .. import config
from ..db import dumps, loads, now, one, rows, session
from ..errors import ApiError, conflict, not_found, reject
from ..providers import image
from ..providers import video as seedance
from ..video import compose_video
from . import catalog, planning, runs, tenants

RETRYABLE = {"provider_timeout", "provider_connection", "provider_http"}
STEPS_IMAGE = ["load_plan", "check_version", "load_references", "provider", "store", "verify"]
STEPS_VIDEO = ["load_plan", "check_version", "select_materials", "compose", "verify"]
STEPS_VIDEO_AI = ["load_plan", "check_version", "select_materials", "provider", "store", "verify"]


def _plan_row(plan_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM plans WHERE id=?", (plan_id,))
        if row is None:
            raise not_found("策划不存在")
        return row


def _guard(plan_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _plan_row(plan_id)
    if plan.get("status") != "confirmed":
        raise conflict("请先人工确认内容策划，再开始生产", code="plan_not_confirmed")
    with session() as db:
        latest = one(db, "SELECT id FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC LIMIT 1",
                     (plan["product_id"],))
        product = one(db, "SELECT * FROM products WHERE id=?", (plan["product_id"],))
        version = one(db, "SELECT * FROM product_versions WHERE id=?", (plan["version_id"],))
    if latest and latest["id"] != plan["version_id"]:
        raise conflict("商品已有更新版本，该策划不能继续生产，请重新策划", code="stale_version")
    if product is None or version is None:
        raise not_found("策划关联的商品或版本不存在")
    return plan, {"product": product, "version": version}


def _attempt(plan_id: str, kind: str, attempt: int, status: str, prompt: str,
             params: dict[str, Any], error_code: str = "", error: str = "", output_id: str = "",
             provider: str = "", model: str = "") -> None:
    with session() as db:
        db.execute(
            "INSERT INTO generation_attempts(id,plan_id,kind,attempt,status,prompt,params_json,provider,model,"
            "error_code,error,request_id,output_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uuid4().hex, plan_id, kind, attempt, status, prompt[:3000], dumps(params),
             provider or ("volcengine-ark" if kind == "image" else "ffmpeg"), model, error_code, error[:300], "", output_id, now()),
        )


def _output(row: dict[str, Any]) -> dict[str, Any]:
    with session() as db:
        plan = one(db, "SELECT p.*, v.version FROM plans p LEFT JOIN product_versions v ON v.id=p.version_id "
                       "WHERE p.id=?", (row["plan_id"],))
        latest = one(db, "SELECT id FROM product_versions WHERE product_id=? ORDER BY version DESC, id DESC LIMIT 1",
                     (plan["product_id"],)) if plan else None
        product = one(db, "SELECT id,name FROM products WHERE id=?", (plan["product_id"],)) if plan else None
        sources = []
        if plan:
            for source_id in loads(plan["source_ids"], []):
                source = one(db, "SELECT id,name,mime,view_angle,purpose FROM sources WHERE id=?", (source_id,))
                if source:
                    purpose = source.get("purpose") or "reference"
                    sources.append({**dict(source),
                                    "role": "style" if purpose == "marketing" else "fact"})
    stale = False
    if plan and latest and plan["version_id"] != latest["id"]:
        content = loads(plan.get("content_json") or plan.get("script"), {})
        if catalog.content_depends_on(content, catalog.changed_fields(plan["product_id"])):
            stale = True
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "kind": row["kind"],
        "asset_type": "video" if row["kind"] == "video" else "ai_generated",
        "status": row["status"],
        "note": row["note"],
        "filename": row.get("filename") or "",
        "mime": row.get("mime") or "",
        "size": row.get("size") or 0,
        "provider": row.get("provider") or "",
        "model": row.get("model") or "",
        "prompt": row.get("prompt") or "",
        "params": loads(row.get("params_json"), {}),
        "error": row.get("error") or "",
        "attempt": row.get("attempt") or 1,
        "source_output_id": row.get("source_output_id") or "",
        "created_at": row.get("created_at") or "",
        "url": f"/api/v1/outputs/{row['id']}",
        "download_url": f"/api/v1/outputs/{row['id']}/download",
        "needs_review": stale,
        "stale_reason": "商品版本已更新且内容引用了变更字段，成品暂停交付并等待复审" if stale else "",
        "product_id": product["id"] if product else "",
        "product_name": product["name"] if product else "",
        "plan": {"id": plan["id"], "scene": plan["scene"], "version_id": plan["version_id"],
                 "version": plan.get("version") if isinstance(plan, dict) else None} if plan else None,
        "sources": sources,
    }


def get_output(output_id: str) -> dict[str, Any]:
    with session() as db:
        row = one(db, "SELECT * FROM outputs WHERE id=?", (output_id,))
        if row is None:
            raise not_found("成品不存在")
        return _output(row)


def list_outputs(product_id: str) -> list[dict[str, Any]]:
    with session() as db:
        if one(db, "SELECT 1 FROM products WHERE id=?", (product_id,)) is None:
            raise not_found("找不到该商品")
        return [_output(row) for row in rows(
            db, "SELECT o.* FROM outputs o JOIN plans p ON p.id=o.plan_id WHERE p.product_id=? "
                "ORDER BY o.created_at DESC", (product_id,))]


def library_outputs(*, status: str = "", kind: str = "", product_id: str = "",
                    search: str = "") -> list[dict[str, Any]]:
    query = "SELECT o.* FROM outputs o JOIN plans p ON p.id=o.plan_id JOIN products pr ON pr.id=p.product_id WHERE 1=1"
    params: list[Any] = []
    if status:
        query += " AND o.status=?"
        params.append(status)
    if kind:
        query += " AND o.kind=?"
        params.append(kind)
    if product_id:
        query += " AND p.product_id=?"
        params.append(product_id)
    if search:
        query += " AND (pr.name LIKE ? OR p.scene LIKE ? OR o.prompt LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    query += " ORDER BY o.created_at DESC"
    with session() as db:
        return [_output(row) for row in rows(db, query, params)]


def _save(content: bytes, mime: str) -> tuple[Path, str]:
    suffix = ".png" if mime == "image/png" else ".jpg"
    name = uuid4().hex + suffix
    path = config.generated_dir() / name
    path.write_bytes(content)
    return path, name


def generate_image(plan_id: str, body: dict[str, Any]) -> dict[str, Any]:
    plan, _ = _guard(plan_id)
    run_id = runs.start(plan_id, "image_generation", plan["product_id"], STEPS_IMAGE)
    prompt = str(body.get("prompt") or loads(plan.get("content_json"), {}).get("image_prompt") or "").strip()
    if not prompt:
        runs.finish(run_id, "failed", "提示词为空", "invalid_input")
        raise reject("请填写图片提示词")
    ratio = str(body.get("ratio") or "3:4")
    count = max(1, min(int(body.get("count") or 1), 4))
    references = []
    try:
        runs.step(run_id, "load_plan", "success", plan["scene"])
        runs.step(run_id, "check_version", "success", f"商品版本 {plan['version_id']}")
        with session() as db:
            source_ids = loads(plan["source_ids"], [])
        for source_id in source_ids[:4]:
            source, path = catalog.source_file(plan["product_id"], source_id)
            references.append({"content": path.read_bytes(), "mime": source["mime"]})
        if not references:
            raise reject("策划没有可用的参考图")
        runs.step(run_id, "load_references", "success", f"{len(references)} 张")
        last_error: ApiError | None = None
        for attempt in range(1, 4):
            try:
                results = image.generate(prompt, references, ratio=ratio, count=count)
                break
            except ApiError as error:
                last_error = error
                _attempt(plan_id, "image", attempt, "failed", prompt,
                         {"ratio": ratio, "count": count}, error.code, error.message)
                runs.step(run_id, "provider", "failed",
                          f"第 {attempt} 次：{error.message}")
                if error.code not in RETRYABLE or attempt >= 3:
                    raise
        else:  # pragma: no cover - 循环必然 break 或 raise
            raise last_error or ApiError(502, "生图失败", "provider_http")
        runs.step(run_id, "provider", "success", f"{len(results)} 张候选（共尝试 {attempt} 次）")
        created = []
        for item in results:
            path, name = _save(item["content"], item["mime"])
            output_id = uuid4().hex
            params = {**item.get("params", {}), "width": item["width"], "height": item["height"],
                      "request_id": item.get("request_id", "")}
            try:
                with session() as db:
                    db.execute(
                        "INSERT INTO outputs(id,plan_id,kind,filename,status,note,mime,size,provider,model,prompt,"
                        "params_json,error,attempt,source_output_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (output_id, plan_id, "image", name, "pending", "", item["mime"], len(item["content"]),
                         item.get("provider") or "volcengine-ark", item.get("model") or "",
                         prompt, dumps(params), "", attempt, str(body.get("source_output_id") or ""), now()),
                    )
            except Exception:
                path.unlink(missing_ok=True)
                raise
            _attempt(plan_id, "image", attempt, "success", prompt,
                     {"ratio": ratio, "count": count}, output_id=output_id)
            created.append(get_output(output_id))
        runs.step(run_id, "store", "success", f"{len(created)} 个候选已保存")
        runs.step(run_id, "verify", "success", "图片格式与尺寸已校验")
        runs.finish(run_id, "success")
        return {"outputs": created, "run_id": run_id, "attempts": attempt}
    except ApiError as error:
        runs.finish(run_id, "failed", error.message, error.code)
        raise
    except Exception as error:  # noqa: BLE001
        runs.finish(run_id, "failed", str(error)[:300], "unexpected")
        raise


def _material(plan: dict[str, Any], value: str) -> tuple[Path, str]:
    kind, _, identifier = value.partition(":")
    if kind == "source":
        source, path = catalog.source_file(plan["product_id"], identifier)
        if not source["mime"].startswith("image/"):
            raise reject("视频镜头素材必须是图片")
        return path, source["mime"]
    if kind == "output":
        with session() as db:
            output = one(db, "SELECT o.* FROM outputs o JOIN plans p ON p.id=o.plan_id "
                             "WHERE o.id=? AND p.product_id=? AND o.kind='image'", (identifier, plan["product_id"]))
        if output is None:
            raise reject("镜头成品不属于该商品")
        if output["status"] != "approved":
            raise reject("只能使用审核通过的商品图作为镜头素材", code="material_not_approved")
        path = config.generated_dir() / output["filename"]
        if not path.is_file():
            raise not_found("镜头成品文件缺失")
        return path, output["mime"] or "image/png"
    raise reject("镜头素材格式应为 source:<id> 或 output:<id>")


def _generate_ffmpeg(plan_id: str, prompt: str, paths: list[Path],
                     shots: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    output_id = uuid4().hex
    output_path = config.generated_dir() / (output_id + ".mp4")
    info = compose_video(output_path, paths, shots)
    runs.step(run_id, "compose", "success", f"{info['duration']} 秒")
    runs.step(run_id, "verify", "success", f"{info['width']}x{info['height']} {info['codec']} {info['pix_fmt']}")
    with session() as db:
        db.execute(
            "INSERT INTO outputs(id,plan_id,kind,filename,status,note,mime,size,provider,model,prompt,"
            "params_json,error,attempt,source_output_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (output_id, plan_id, "video", output_path.name, "pending", "", "video/mp4",
             output_path.stat().st_size, "ffmpeg", "libx264", prompt[:3000],
             dumps(info), "", 1, "", now()),
        )
    _attempt(plan_id, "video", 1, "success", prompt, info, output_id=output_id)
    return [get_output(output_id)]


def _generate_seedance(plan_id: str, prompt: str,
                       pairs: list[tuple[Path, str]], body: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    references = [{"content": path.read_bytes(), "mime": mime} for path, mime in pairs[:1]]
    duration = int(body.get("duration") or 12)
    last_error: ApiError | None = None
    for attempt in range(1, 4):
        try:
            results = seedance.generate(prompt, references, duration=duration)
            break
        except ApiError as error:
            last_error = error
            _attempt(plan_id, "video", attempt, "failed", prompt, {"duration": duration},
                     error.code, error.message, provider="volcengine-ark")
            runs.step(run_id, "provider", "failed", f"第 {attempt} 次：{error.message}")
            if error.code not in RETRYABLE or attempt >= 3:
                raise
    else:  # pragma: no cover - 循环必然 break 或 raise
        raise last_error or ApiError(502, "视频生成失败", "provider_http")
    runs.step(run_id, "provider", "success", f"共尝试 {attempt} 次")
    created: list[dict[str, Any]] = []
    for item in results:
        output_id = uuid4().hex
        name = output_id + ".mp4"
        path = config.generated_dir() / name
        path.write_bytes(item["content"])
        params = item.get("params", {})
        try:
            with session() as db:
                db.execute(
                    "INSERT INTO outputs(id,plan_id,kind,filename,status,note,mime,size,provider,model,prompt,"
                    "params_json,error,attempt,source_output_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (output_id, plan_id, "video", name, "pending", "", "video/mp4", len(item["content"]),
                     "volcengine-ark", item.get("model") or "", prompt, dumps(params), "", attempt, "", now()),
                )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        _attempt(plan_id, "video", attempt, "success", prompt, params, output_id=output_id,
                 provider="volcengine-ark", model=item.get("model") or "")
        created.append(get_output(output_id))
    runs.step(run_id, "store", "success", f"{len(created)} 个视频已保存")
    runs.step(run_id, "verify", "success",
              f"{params.get('resolution', '')} {params.get('duration', '')}s")
    return created


def generate_video(plan_id: str, body: dict[str, Any]) -> dict[str, Any]:
    plan, _ = _guard(plan_id)
    provider = str(body.get("provider") or "ffmpeg").strip().lower()
    if provider not in {"ffmpeg", "seedance"}:
        raise reject("视频生成方式只支持 ffmpeg 或 seedance")
    steps = STEPS_VIDEO_AI if provider == "seedance" else STEPS_VIDEO
    run_id = runs.start(plan_id, "video_generation", plan["product_id"], steps)
    content = loads(plan.get("content_json"), {})
    shots = content.get("shots") or []
    if not shots:
        runs.finish(run_id, "failed", "策划没有分镜", "invalid_input")
        raise reject("策划没有分镜，无法生成视频")
    materials = body.get("materials") or [f"source:{source_id}" for source_id in loads(plan["source_ids"], [])]
    if not isinstance(materials, list) or not materials:
        runs.finish(run_id, "failed", "缺少镜头素材", "invalid_input")
        raise reject("请选择至少一个镜头素材")
    prompt = str(content.get("image_prompt") or "").strip()
    provider_label = "volcengine-ark" if provider == "seedance" else "ffmpeg"
    try:
        runs.step(run_id, "load_plan", "success", f"{len(shots)} 个镜头")
        runs.step(run_id, "check_version", "success", f"商品版本 {plan['version_id']}")
        pairs = [_material(plan, str(item)) for item in materials]
        runs.step(run_id, "select_materials", "success", f"{len(pairs)} 个素材")
        if provider == "seedance":
            created = _generate_seedance(plan_id, prompt, pairs, body, run_id)
        else:
            paths = [path for path, _ in pairs]
            created = _generate_ffmpeg(plan_id, prompt, paths, shots, run_id)
        runs.finish(run_id, "success")
        return {"outputs": created, "run_id": run_id, "attempts": 1}
    except ApiError as error:
        _attempt(plan_id, "video", 1, "failed", prompt, {"materials": materials, "provider": provider},
                 error.code, error.message, provider=provider_label)
        runs.finish(run_id, "failed", error.message, error.code)
        raise
    except Exception as error:  # noqa: BLE001
        runs.finish(run_id, "failed", str(error)[:300], "unexpected")
        raise


def review_output(output_id: str, approved: bool, note: str) -> dict[str, Any]:
    row = get_output(output_id)
    if not approved and not note.strip():
        raise reject("驳回时请填写原因")
    if approved and not note.strip():
        note = "人工审核通过"
    if row["needs_review"]:
        raise conflict("商品版本已更新，成品暂停交付，请重新生成后再审核", code="stale_output")
    if row["status"] == "approved" and not approved:
        raise conflict("已通过的成品不能直接驳回，请创建修订任务", code="already_approved")
    stamp = now()
    with session() as db:
        db.execute("UPDATE outputs SET status=?, note=? WHERE id=?",
                   ("approved" if approved else "rejected", note[:500], output_id))
        db.execute(
            "INSERT INTO reviews(id,target_type,target_id,action,note,payload_json,reviewer,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (uuid4().hex, "output", output_id, "approve" if approved else "reject", note[:500], "{}", "user", stamp),
        )
    return get_output(output_id)


def output_file(output_id: str, download: bool) -> tuple[Path, str, str]:
    row = get_output(output_id)
    if download:
        if row["status"] != "approved":
            raise conflict("成品尚未审核通过，不能下载正式文件", code="not_approved")
        if row["needs_review"]:
            raise conflict("商品版本已更新，旧成品暂停交付", code="stale_output")
    path = config.generated_dir() / Path(row["filename"]).name
    if not path.is_file():
        raise not_found("成品文件缺失")
    return path, row["mime"] or "application/octet-stream", row["filename"]


def revise_output(output_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source = get_output(output_id)
    if source["attempt"] >= 5:
        raise conflict("该成品修订次数已达上限，请人工处理", code="revision_limit")
    prompt = str(body.get("prompt") or source["prompt"]).strip()
    if not prompt:
        raise reject("请填写修订后的提示词")
    payload = {"prompt": prompt, "source_output_id": output_id}
    if source["kind"] == "image":
        payload.update({"ratio": body.get("ratio") or "3:4", "count": 1})
        result = generate_image(source["plan_id"], payload)
    else:
        payload["materials"] = body.get("materials") or []
        result = generate_video(source["plan_id"], payload)
    created = result["outputs"][0]
    with session() as db:
        db.execute("UPDATE outputs SET attempt=?, source_output_id=? WHERE id=?",
                   (source["attempt"] + 1, output_id, created["id"]))
    return get_output(created["id"])


def regenerate_affected(product_id: str) -> dict[str, Any]:
    """定向更新：精确列出受字段变更影响的成品，并记录更新请求；未受影响成品继续交付。"""
    result = catalog.impact(product_id)
    with session() as db:
        db.execute(
            "INSERT INTO reviews(id,tenant_id,target_type,target_id,action,note,payload_json,reviewer,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (uuid4().hex, tenants.current(), "product", product_id, "regenerate_requested",
             f"请求定向更新 {result['affected_outputs']} 个受影响成品", dumps(result["changed_fields"]), "user", now()),
        )
    result["note"] = "已记录定向更新请求；受影响成品需基于最新版本重新策划后再生产，未受影响成品可继续交付"
    return result


def stats() -> dict[str, Any]:
    with session() as db:
        def count(sql: str, params: tuple | list = ()) -> int:
            return one(db, sql, params)["n"]

        products = count("SELECT COUNT(*) AS n FROM products")
        confirmed = count("SELECT COUNT(*) AS n FROM products WHERE status='confirmed'")
        sources = count("SELECT COUNT(*) AS n FROM sources")
        plans = count("SELECT COUNT(*) AS n FROM plans")
        outputs = {
            "image": count("SELECT COUNT(*) AS n FROM outputs WHERE kind='image'"),
            "video": count("SELECT COUNT(*) AS n FROM outputs WHERE kind='video'"),
        }
        review = {
            "pending": count("SELECT COUNT(*) AS n FROM outputs WHERE status='pending'"),
            "approved": count("SELECT COUNT(*) AS n FROM outputs WHERE status='approved'"),
            "rejected": count("SELECT COUNT(*) AS n FROM outputs WHERE status='rejected'"),
        }
        reviewed = review["approved"] + review["rejected"]
        # 首轮通过：首次送审即通过；修订任务有 source_output_id 视为非首轮
        first_pass = count("SELECT COUNT(*) AS n FROM outputs WHERE status='approved' AND source_output_id=''")
        first_pass_denominator = count("SELECT COUNT(*) AS n FROM outputs WHERE source_output_id='' AND status IN ('approved','rejected')")
        reuse = count("SELECT COUNT(*) AS n FROM plans WHERE parent_plan_id<>''")
        manual = count("SELECT COUNT(*) AS n FROM imports WHERE status='confirmed'")
        imports_total = count("SELECT COUNT(*) AS n FROM imports")
        durations = rows(db, "SELECT created_at, finished_at FROM workflow_runs WHERE finished_at<>''")
        total_seconds = 0.0
        measured = 0
        from datetime import datetime

        for item in durations:
            try:
                start = datetime.fromisoformat(item["created_at"])
                end = datetime.fromisoformat(item["finished_at"])
                total_seconds += max(0.0, (end - start).total_seconds())
                measured += 1
            except (TypeError, ValueError):
                continue
        failure = {row["error_code"] or "unknown": row["n"] for row in rows(
            db, "SELECT error_code, COUNT(*) AS n FROM workflow_runs WHERE status='failed' GROUP BY error_code")}
    return {
        "products": products,
        "confirmed_products": confirmed,
        "sources": sources,
        "plans": plans,
        "outputs": outputs,
        "review": review,
        "first_pass_approval": {
            "value": round(first_pass / first_pass_denominator, 3) if first_pass_denominator else None,
            "numerator": first_pass,
            "denominator": first_pass_denominator,
            "definition": "首轮送审即通过的成品数 / 已出审核结论的首轮成品数",
            "sample_size": first_pass_denominator,
        },
        "manual_intervention": {
            "count": manual,
            "definition": "完成人工确认入库的导入任务数",
            "sample_size": imports_total,
        },
        "avg_task_seconds": {
            "value": round(total_seconds / measured, 2) if measured else None,
            "sample_size": measured,
            "definition": "工作流从创建到结束的平均耗时（秒）",
        },
        "failure_categories": failure,
        "reuse": {
            "plans_with_parent": reuse,
            "total_plans": plans,
            "rate": round(reuse / plans, 3) if plans else None,
            "definition": "复用历史素材创建的新策划数 / 策划总数",
            "sample_size": plans,
        },
        "cost": {"status": "未采集", "note": "尚未接入服务商计费数据，不展示成本估算"},
        "note": "以上指标来自本地真实任务记录；样本量不足时返回 null，不编造数据。",
    }
