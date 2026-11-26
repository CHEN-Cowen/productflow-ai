"""原始资料解析：PDF、Excel、Word、图片 OCR。

每个文本块都带定位信息：PDF 页码、表格工作表/行/列、Word 段落或表格行列、OCR 图片。
解析失败或扫描件降级时给出明确提示，不伪造提取结果。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .. import config
from ..errors import reject
from .catalog import DOCX_MIME, XLSX_MIME

MAX_PDF_PAGES = 30
MAX_SHEET_ROWS = 400
MAX_BLOCKS = 400


@dataclass
class Parsed:
    blocks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def text(self, block_id: int) -> str:
        for block in self.blocks:
            if block["id"] == block_id:
                return block["text"]
        return ""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def parse_pdf(path: Path, name: str) -> Parsed:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    parsed = Parsed()
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise reject("PDF 已加密，无法解析，请上传未加密资料", code="pdf_encrypted") from None
        for index, page in enumerate(reader.pages):
            if index >= MAX_PDF_PAGES:
                parsed.warnings.append(f"PDF 超过 {MAX_PDF_PAGES} 页，仅解析前 {MAX_PDF_PAGES} 页")
                break
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            parsed.blocks.append({
                "id": len(parsed.blocks),
                "locator": {"kind": "pdf", "page": index + 1},
                "text": text[:4000],
            })
    except (PdfReadError, OSError, ValueError) as error:
        raise reject("PDF 无法解析，请确认文件完整且带文字层", code="pdf_invalid") from error
    if not parsed.blocks:
        parsed.warnings.append(
            "未提取到文字：该 PDF 可能是扫描件或图片版。已保留原件，请在字段区域人工补充并填写依据。"
        )
    return parsed


def parse_xlsx(path: Path, name: str) -> Parsed:
    from openpyxl import load_workbook

    parsed = Parsed()
    try:
        workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception as error:  # noqa: BLE001 - openpyxl 异常类型较多
        raise reject("Excel 无法解析，请另存为 .xlsx 后重试", code="xlsx_invalid") from error
    try:
        for sheet in workbook.worksheets[:10]:
            rows = list(sheet.iter_rows(max_row=MAX_SHEET_ROWS, values_only=True))
            if not rows:
                continue
            header = [f"列{index + 1}" for index in range(len(rows[0]))]
            start = 0
            if any(isinstance(cell, str) and cell.strip() for cell in rows[0]):
                header = []
                for index, cell in enumerate(rows[0]):
                    label = _clean(cell)
                    header.append(label or f"列{index + 1}")
                start = 1
            for row_index, values in enumerate(rows[start:], start=start + 1):
                cells = {}
                parts = []
                for column, value in enumerate(values):
                    text = _clean(value)
                    if not text:
                        continue
                    key = chr(65 + column) if column < 26 else f"C{column + 1}"
                    cells[key] = text
                    parts.append(f"{header[column] if column < len(header) else key}: {text}")
                if not parts:
                    continue
                parsed.blocks.append({
                    "id": len(parsed.blocks),
                    "locator": {"kind": "xlsx", "sheet": sheet.title, "row": row_index, "cells": cells},
                    "text": " | ".join(parts)[:2000],
                })
                if len(parsed.blocks) >= MAX_BLOCKS:
                    parsed.warnings.append("表格行数较多，仅解析前 400 行")
                    return parsed
    finally:
        workbook.close()
    if not parsed.blocks:
        parsed.warnings.append("Excel 未找到可解析的表格行，请检查工作表内容。")
    return parsed


def parse_docx(path: Path, name: str) -> Parsed:
    try:
        from docx import Document
    except ImportError:  # pragma: no cover - 依赖缺失时明确提示
        raise reject("服务器未安装 python-docx，无法解析 Word", code="docx_unavailable") from None

    parsed = Parsed()
    try:
        document = Document(str(path))
    except Exception as error:  # noqa: BLE001
        raise reject("Word 无法解析，请另存为 .docx 后重试", code="docx_invalid") from error
    for index, paragraph in enumerate(document.paragraphs):
        text = (paragraph.text or "").strip()
        if text:
            parsed.blocks.append({
                "id": len(parsed.blocks),
                "locator": {"kind": "docx", "paragraph": index + 1},
                "text": text[:2000],
            })
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows):
            cells = [_clean(cell.text) for cell in row.cells]
            if not any(cells):
                continue
            parsed.blocks.append({
                "id": len(parsed.blocks),
                "locator": {"kind": "docx", "table": table_index + 1, "row": row_index + 1},
                "text": " | ".join(cell for cell in cells if cell)[:2000],
            })
    if not parsed.blocks:
        parsed.warnings.append("Word 未找到文字内容，请检查文档。")
    return parsed


def tesseract_path() -> str:
    return os.environ.get("TESSERACT_CMD", "").strip() or (shutil.which("tesseract") or "")


def parse_image(path: Path, name: str) -> Parsed:
    parsed = Parsed()
    binary = tesseract_path()
    if not binary:
        parsed.warnings.append(
            "当前环境未安装 OCR 引擎（tesseract），图片已保留但未提取文字。"
            "请人工补充字段并填写依据，或安装带中文语言包的 tesseract 后重新提取。"
        )
        return parsed
    try:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [binary, str(path), "stdout", "-l", "chi_sim+eng", "--psm", "3"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=60, cwd=directory,
            )
        text = (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        parsed.warnings.append("OCR 执行失败，请检查 tesseract 安装或语言包，之后可人工补充字段。")
        return parsed
    if result.returncode != 0 or not text:
        detail = (result.stderr or "").strip().splitlines()
        reason = detail[-1][:160] if detail else "未识别出文字"
        parsed.warnings.append(f"OCR 未提取到文字（{reason}），可人工补充字段。")
        return parsed
    parsed.blocks.append({
        "id": 0,
        "locator": {"kind": "image", "page": 1, "ocr": "tesseract"},
        "text": text[:4000],
    })
    parsed.warnings.append("OCR 结果为机器识别，定位精度有限，确认时请核对原图。")
    return parsed


def parse_source(source: dict[str, Any], path: Path) -> Parsed:
    mime = source["mime"]
    if mime == "application/pdf":
        return parse_pdf(path, source["name"])
    if mime == XLSX_MIME:
        return parse_xlsx(path, source["name"])
    if mime == DOCX_MIME:
        return parse_docx(path, source["name"])
    if mime.startswith("image/"):
        return parse_image(path, source["name"])
    raise reject("该资料类型暂不支持解析", code="unsupported_file")
