import hashlib
import mimetypes
import posixpath
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from defusedxml import ElementTree
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter
from PIL import Image, UnidentifiedImageError

from app.core.errors import BadRequestError
from app.schemas.imports import ImportMappingConfig, ImportTransform, is_column_reference
from app.services.document_parser.base import BaseImporter
from app.services.document_parser.markitdown_service import MarkItDownService

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
DRAWING_MAIN_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

MAX_ARCHIVE_ENTRIES = 20_000
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_SINGLE_ENTRY_BYTES = 128 * 1024 * 1024
MAX_WORKSHEET_ROWS = 50_000
MAX_WORKSHEET_COLUMNS = 500
MAX_SAMPLE_ROWS = 20


def _image_pixel_size(payload: bytes, extent: Any | None) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
            return max(int(width), 1), max(int(height), 1)
    except (OSError, UnidentifiedImageError):
        width = int(int(extent.attrib.get("cx", "0")) / 9525) if extent is not None else 0
        height = int(int(extent.attrib.get("cy", "0")) / 9525) if extent is not None else 0
        return max(width, 1), max(height, 1)


@dataclass(frozen=True, slots=True)
class ExtractedImage:
    original_filename: str
    source_sheet: str
    source_row: int
    source_column: int
    width: int
    height: int
    mime_type: str
    sha256: str
    payload: bytes


def _resolve_part(base_part: str, target: str) -> str:
    normalized_target = target.replace("\\", "/")
    return posixpath.normpath(
        posixpath.join(posixpath.dirname(base_part), normalized_target)
    ).lstrip("/")


def _relationship_map(archive: zipfile.ZipFile, rels_part: str) -> dict[str, dict[str, str]]:
    if rels_part not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read(rels_part))
    return {
        node.attrib["Id"]: node.attrib
        for node in root.findall(f"{{{REL_NS}}}Relationship")
        if "Id" in node.attrib
    }


def _rels_part(part: str) -> str:
    directory, filename = posixpath.split(part)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


HEADER_ALIASES: tuple[tuple[tuple[str, ...], str, float], ...] = (
    (("supplier sku", "supplier sku #", "sku", "item sku", "item number"), "sku", 0.99),
    (("product name", "item name", "item descriptions with specifications"), "product_name", 0.96),
    (("description", "product description", "specification"), "description", 0.94),
    (("material",), "material", 0.99),
    (("buyer notes", "notes", "remark", "remarks"), "remark", 0.96),
    (("retail packaging", "packing", "package"), "packing", 0.95),
    (("master qty", "carton qty", "master quantity"), "carton_qty", 0.94),
    (("moq", "minimum order quantity"), "moq", 0.99),
    (("fob us", "fob", "supplier cost", "purchase price"), "supplier_cost", 0.93),
    (("price", "selling price"), "selling_price", 0.92),
    (("hts", "hts #", "hs code", "hs"), "hs_code", 0.97),
    (("country of origin", "origin"), "country_of_origin", 0.96),
    (("brand",), "brand", 0.99),
    (("category",), "category", 0.99),
    (("size", "dimensions", "dimension"), "size", 0.97),
    (("color", "colour"), "color", 0.99),
)


class ExcelImporter(BaseImporter):
    def __init__(self, *, markitdown: MarkItDownService | None = None) -> None:
        self.markitdown = markitdown or MarkItDownService()

    @staticmethod
    def validate_archive(path: Path) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ARCHIVE_ENTRIES:
                    raise BadRequestError("Excel 文件包含过多内部对象，无法安全解析。")
                total_size = sum(entry.file_size for entry in entries)
                if total_size > MAX_UNCOMPRESSED_BYTES:
                    raise BadRequestError("Excel 解压后体积过大，无法安全解析。")
                if any(entry.file_size > MAX_SINGLE_ENTRY_BYTES for entry in entries):
                    raise BadRequestError("Excel 包含体积过大的内部对象。")
                names = {entry.filename for entry in entries}
                if "xl/workbook.xml" not in names or "[Content_Types].xml" not in names:
                    raise BadRequestError("上传文件不是有效的 XLSX 工作簿。")
                if any(name.lower().endswith("vbaproject.bin") for name in names):
                    raise BadRequestError("第一版不支持包含 VBA 的工作簿，请另存为普通 XLSX。")
        except (zipfile.BadZipFile, OSError) as exc:
            raise BadRequestError(
                "文件无法正常读取，请确认该文件已经解除企业文档保护，"
                "并另存为普通 Excel 文件后重新上传。"
            ) from exc

    def _extract_ooxml_images(self, path: Path) -> list[ExtractedImage]:
        images: list[ExtractedImage] = []
        with zipfile.ZipFile(path) as archive:
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            workbook_rels = _relationship_map(archive, "xl/_rels/workbook.xml.rels")
            sheets = workbook.find(f"{{{SHEET_NS}}}sheets")
            if sheets is None:
                return images
            for sheet in list(sheets):
                sheet_name = sheet.attrib.get("name", "Sheet")
                relation_id = sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
                relation = workbook_rels.get(relation_id or "")
                if relation is None or relation.get("TargetMode") == "External":
                    continue
                sheet_part = _resolve_part("xl/workbook.xml", relation["Target"])
                if sheet_part not in archive.namelist():
                    continue
                sheet_xml = ElementTree.fromstring(archive.read(sheet_part))
                sheet_rels = _relationship_map(archive, _rels_part(sheet_part))
                for drawing_ref in sheet_xml.findall(f"{{{SHEET_NS}}}drawing"):
                    drawing_id = drawing_ref.attrib.get(f"{{{DOC_REL_NS}}}id")
                    drawing_relation = sheet_rels.get(drawing_id or "")
                    if drawing_relation is None or drawing_relation.get("TargetMode") == "External":
                        continue
                    drawing_part = _resolve_part(sheet_part, drawing_relation["Target"])
                    if drawing_part not in archive.namelist():
                        continue
                    drawing_xml = ElementTree.fromstring(archive.read(drawing_part))
                    drawing_rels = _relationship_map(archive, _rels_part(drawing_part))
                    for anchor in list(drawing_xml):
                        origin = anchor.find(f"{{{DRAWING_NS}}}from")
                        blip = anchor.find(f".//{{{DRAWING_MAIN_NS}}}blip")
                        if origin is None or blip is None:
                            continue
                        embed_id = blip.attrib.get(f"{{{DOC_REL_NS}}}embed")
                        media_relation = drawing_rels.get(embed_id or "")
                        if media_relation is None or media_relation.get("TargetMode") == "External":
                            continue
                        media_part = _resolve_part(drawing_part, media_relation["Target"])
                        if media_part not in archive.namelist():
                            continue
                        row_node = origin.find(f"{{{DRAWING_NS}}}row")
                        column_node = origin.find(f"{{{DRAWING_NS}}}col")
                        if row_node is None or column_node is None:
                            continue
                        extent = anchor.find(f"{{{DRAWING_NS}}}ext")
                        if extent is None:
                            extent = anchor.find(f".//{{{DRAWING_MAIN_NS}}}ext")
                        payload = archive.read(media_part)
                        width, height = _image_pixel_size(payload, extent)
                        original_filename = Path(media_part).name
                        mime_type = (
                            mimetypes.guess_type(original_filename)[0]
                            or "application/octet-stream"
                        )
                        images.append(
                            ExtractedImage(
                                original_filename=original_filename,
                                source_sheet=sheet_name,
                                source_row=int(row_node.text or "0") + 1,
                                source_column=int(column_node.text or "0") + 1,
                                width=width,
                                height=height,
                                mime_type=mime_type,
                                sha256=hashlib.sha256(payload).hexdigest(),
                                payload=payload,
                            )
                        )
        return images

    @staticmethod
    def _suggest_mapping(headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        used_targets: set[str] = set()
        for header in headers:
            normalized = _normalize_header(header["value"])
            if not normalized:
                continue
            for aliases, target, confidence in HEADER_ALIASES:
                if target in used_targets:
                    continue
                if normalized in aliases or any(alias in normalized for alias in aliases):
                    suggestions.append(
                        {
                            "source": header["column"],
                            "source_header": header["value"],
                            "target": target,
                            "transform": (
                                "trim"
                                if target
                                not in {
                                    "supplier_cost",
                                    "selling_price",
                                    "moq",
                                    "carton_qty",
                                }
                                else "decimal"
                            ),
                            "required": target in {"sku", "product_name"},
                            "confidence": confidence,
                            "method": "header_alias",
                        }
                    )
                    used_targets.add(target)
                    break
        return suggestions

    def analyze(
        self, path: Path, *, original_filename: str, sha256: str
    ) -> tuple[dict, list[ExtractedImage]]:
        self.validate_archive(path)
        try:
            workbook = load_workbook(
                path, read_only=False, data_only=False, keep_links=False
            )
        except Exception as exc:
            raise BadRequestError(
                "文件无法正常读取，请确认该文件已经解除企业文档保护，"
                "并另存为普通 Excel 文件后重新上传。"
            ) from exc

        try:
            extracted_images = self._extract_ooxml_images(path)
            images_by_sheet: dict[str, list[ExtractedImage]] = {}
            for image in extracted_images:
                images_by_sheet.setdefault(image.source_sheet, []).append(image)

            sheets: list[dict[str, Any]] = []
            for worksheet in workbook.worksheets:
                if (
                    worksheet.max_row > MAX_WORKSHEET_ROWS
                    or worksheet.max_column > MAX_WORKSHEET_COLUMNS
                ):
                    raise BadRequestError(
                        f"工作表 {worksheet.title} 超出第一版支持的 50000 行或 500 列限制。"
                    )
                headers = [
                    {
                        "column": get_column_letter(column),
                        "column_index": column,
                        "value": _json_value(worksheet.cell(1, column).value),
                    }
                    for column in range(1, worksheet.max_column + 1)
                    if worksheet.cell(1, column).value not in (None, "")
                ]
                sample_rows: list[dict[str, Any]] = []
                for row_number in range(1, min(worksheet.max_row, MAX_SAMPLE_ROWS) + 1):
                    cells: dict[str, Any] = {}
                    formats: dict[str, Any] = {}
                    for column in range(1, worksheet.max_column + 1):
                        cell = worksheet.cell(row_number, column)
                        if cell.value in (None, ""):
                            continue
                        letter = get_column_letter(column)
                        cells[letter] = _json_value(cell.value)
                        formats[letter] = {
                            "style_id": cell.style_id,
                            "number_format": cell.number_format,
                            "bold": bool(cell.font.bold),
                            "horizontal": cell.alignment.horizontal,
                        }
                    if cells:
                        sample_rows.append(
                            {"row": row_number, "cells": cells, "formats": formats}
                        )
                sheet_images = images_by_sheet.get(worksheet.title, [])
                sheets.append(
                    {
                        "name": worksheet.title,
                        "max_row": worksheet.max_row,
                        "max_column": worksheet.max_column,
                        "merged_cells": [str(item) for item in worksheet.merged_cells.ranges],
                        "headers": headers,
                        "sample_rows": sample_rows,
                        "images": [
                            {
                                "source_filename": image.original_filename,
                                "source_sheet": image.source_sheet,
                                "source_row": image.source_row,
                                "source_column": image.source_column,
                                "width": image.width,
                                "height": image.height,
                                "mime_type": image.mime_type,
                                "sha256": image.sha256,
                            }
                            for image in sheet_images
                        ],
                        "suggested_mapping": self._suggest_mapping(headers),
                    }
                )
            analysis = {
                "workbook_filename": original_filename,
                "workbook_sha256": sha256,
                "sheets": sheets,
                "markitdown": self.markitdown.convert_local(path),
            }
            return analysis, extracted_images
        finally:
            workbook.close()

    @staticmethod
    def _source_columns(worksheet, mapping: ImportMappingConfig) -> dict[str, int]:
        headers: dict[str, int] = {}
        for column in range(1, worksheet.max_column + 1):
            value = worksheet.cell(mapping.header_row, column).value
            normalized = _normalize_header(value)
            if normalized and normalized not in headers:
                headers[normalized] = column
        resolved: dict[str, int] = {}
        for field in mapping.fields:
            if is_column_reference(field.source):
                column = column_index_from_string(field.source.upper())
            else:
                column = headers.get(_normalize_header(field.source), 0)
            if column < 1 or column > worksheet.max_column:
                raise BadRequestError(
                    f"工作表 {worksheet.title} 中找不到映射来源：{field.source}"
                )
            resolved[field.target] = column
        return resolved

    @staticmethod
    def _transform(value: Any, transform: ImportTransform | None) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None
        if transform is None:
            return _json_value(value)
        if transform in {ImportTransform.TEXT, ImportTransform.TRIM}:
            return str(value).strip()
        if transform == ImportTransform.UPPERCASE:
            return str(value).strip().upper()
        if transform == ImportTransform.LOWERCASE:
            return str(value).strip().lower()
        if transform in {ImportTransform.DECIMAL, ImportTransform.INTEGER}:
            try:
                number = Decimal(str(value).replace(",", ""))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("必须是数字") from exc
            if transform == ImportTransform.INTEGER:
                if number != number.to_integral_value():
                    raise ValueError("必须是整数")
                return int(number)
            return int(number) if number == number.to_integral_value() else float(number)
        if transform == ImportTransform.BOOLEAN:
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"true", "yes", "y", "1", "是"}:
                return True
            if normalized in {"false", "no", "n", "0", "否"}:
                return False
            raise ValueError("必须是布尔值")
        if transform == ImportTransform.DATE:
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            try:
                return date.fromisoformat(str(value).strip()).isoformat()
            except ValueError as exc:
                raise ValueError("必须是 ISO 日期") from exc
        if transform == ImportTransform.NORMALIZE_DIMENSION:
            text = str(value).strip()
            text = re.sub(r"\s*[×X*]\s*", " x ", text)
            return re.sub(r"\s+", " ", text)
        return _json_value(value)

    @staticmethod
    def _validate(value: Any, rules: dict[str, Any]) -> list[str]:
        if value is None:
            return []
        errors: list[str] = []
        text = str(value)
        pattern = rules.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, text) is None:
            errors.append("格式不符合 validation.pattern")
        max_length = rules.get("max_length")
        if isinstance(max_length, int) and len(text) > max_length:
            errors.append(f"长度不能超过 {max_length}")
        choices = rules.get("choices")
        if isinstance(choices, list) and value not in choices:
            errors.append("不在允许值范围内")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = rules.get("min")
            maximum = rules.get("max")
            if isinstance(minimum, (int, float)) and value < minimum:
                errors.append(f"不能小于 {minimum}")
            if isinstance(maximum, (int, float)) and value > maximum:
                errors.append(f"不能大于 {maximum}")
        return errors

    def preview(self, path: Path, mapping: ImportMappingConfig) -> list[dict]:
        self.validate_archive(path)
        try:
            workbook = load_workbook(path, read_only=False, data_only=True, keep_links=False)
        except Exception as exc:
            raise BadRequestError("Excel 文件无法读取。") from exc
        try:
            selected = set(mapping.sheet_names or workbook.sheetnames)
            missing_sheets = selected - set(workbook.sheetnames)
            if missing_sheets:
                raise BadRequestError(
                    f"工作簿中不存在这些 Sheet：{', '.join(sorted(missing_sheets))}"
                )
            rows: list[dict[str, Any]] = []
            for worksheet in workbook.worksheets:
                if worksheet.title not in selected:
                    continue
                source_columns = self._source_columns(worksheet, mapping)
                found_product_row = False
                for row_number in range(mapping.data_start_row, worksheet.max_row + 1):
                    source_data: dict[str, Any] = {}
                    mapped_data: dict[str, Any] = {}
                    errors: list[str] = []
                    for field in mapping.fields:
                        column = source_columns[field.target]
                        raw_value = worksheet.cell(row_number, column).value
                        source_data[get_column_letter(column)] = _json_value(raw_value)
                        value = raw_value if raw_value not in (None, "") else field.default_value
                        try:
                            value = self._transform(value, field.transform)
                        except ValueError as exc:
                            errors.append(f"{field.target}: {exc}")
                            value = None
                        if field.required and value in (None, ""):
                            errors.append(f"{field.target}: 必填")
                        errors.extend(
                            f"{field.target}: {error}"
                            for error in self._validate(value, field.validation)
                        )
                        if value is not None:
                            mapped_data[field.target] = value
                    if not any(value not in (None, "") for value in source_data.values()):
                        continue
                    # Supplier workbooks often place a note or instruction row
                    # between the header and the first product.  A value in the
                    # product-name column alone must not turn that leading note into
                    # an invalid product.  Once the first SKU has been found, rows
                    # missing either core field remain visible for validation.
                    if not found_product_row and mapped_data.get("sku") in (None, ""):
                        continue
                    if all(
                        mapped_data.get(core_field) in (None, "")
                        for core_field in ("sku", "product_name")
                    ):
                        continue
                    if mapped_data.get("sku") not in (None, ""):
                        found_product_row = True
                    for core_field in ("sku", "product_name"):
                        if mapped_data.get(core_field) in (None, ""):
                            errors.append(f"{core_field}: 核心字段不能为空")
                    rows.append(
                        {
                            "source_sheet": worksheet.title,
                            "source_row": row_number,
                            "source_data": source_data,
                            "mapped_data": mapped_data,
                            "errors": sorted(set(errors)),
                        }
                    )
            return rows
        finally:
            workbook.close()
