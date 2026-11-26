"""测试辅助：生成带文字层的 PDF、Excel、Word 与最小 PNG。"""
from __future__ import annotations

import base64
import io
from typing import Any

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def make_png(rgb: tuple[int, int, int] = (250, 248, 245), size: int = 64) -> bytes:
    """生成不同颜色的合法 PNG，避免测试中内容哈希重复。"""
    import struct
    import zlib

    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def make_pdf(lines: list[str]) -> bytes:
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content = "BT\n/F1 12 Tf\n72 720 Td\n"
    for index, line in enumerate(lines):
        if index:
            content += "0 -22 Td\n"
        content += f"({esc(line)}) Tj\n"
    content += "ET\n"
    stream = content.encode("latin-1", "replace")
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n" + content + "endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = b"%PDF-1.4\n"
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets:
        data += f"{offset:010d} 00000 n \n".encode("ascii")
    data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return data


def make_xlsx(rows: list[list[Any]]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "商品参数"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_docx(lines: list[str]) -> bytes:
    from docx import Document

    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def upload(client, product_id: str, name: str, content: bytes, **form: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/products/{product_id}/sources",
        files={"file": (name, content)},
        data=form,
    )
    assert response.status_code == 201, response.text
    return response.json()


def error_code(response) -> str:
    detail = response.json().get("detail")
    if isinstance(detail, dict):
        return str(detail.get("code") or "")
    return ""


def create_product(client, product_id: str = "TP01", category_id: str = "BAG",
                   name: str = "测试女士双肩包") -> dict[str, Any]:
    response = client.post("/api/v1/products", json={
        "id": product_id, "name": name, "category_id": category_id,
    })
    assert response.status_code == 201, response.text
    return response.json()


def confirm_fields(client, import_id: str, fields: dict[str, str],
                   manual_basis: dict[str, str] | None = None, sku: str = "") -> dict[str, Any]:
    response = client.post(f"/api/v1/imports/{import_id}/confirm", json={
        "fields": fields,
        "sku": sku,
        "note": "测试人工确认",
        "manual_basis": manual_basis or {},
        "resolutions": [],
    })
    assert response.status_code == 200, response.text
    return response.json()
