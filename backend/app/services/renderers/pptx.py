import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from app.core.errors import BadRequestError
from app.services.renderers.base import (
    RenderRequest,
    as_png,
    format_text,
    render_text_runs,
    resolve_image,
    resolve_value,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"p": P_NS, "a": A_NS, "r": R_NS}


def _shape_by_id(root, shape_id: int):
    for tag in ("sp", "pic", "graphicFrame"):
        for shape in root.findall(f".//p:{tag}", NS):
            marker = shape.find(".//p:cNvPr", NS)
            if marker is not None and marker.get("id") == str(shape_id):
                return shape
    return None


def _replace_text(shape, text: str) -> None:
    nodes = shape.findall(".//a:t", NS)
    if not nodes:
        raise BadRequestError("映射的 PowerPoint 对象不包含可写文本。")
    nodes[0].text = text
    for node in nodes[1:]:
        node.text = ""


def _replace_text_runs(shape, replacements: list[tuple[int, str]]) -> None:
    nodes = shape.findall(".//a:t", NS)
    if not nodes:
        raise BadRequestError("映射的 PowerPoint 对象不包含可写文本。")
    for run_index, text in replacements:
        if run_index >= len(nodes):
            raise BadRequestError("模板文本 Run 已经发生变化，请重新验证模板映射。")
        nodes[run_index].text = text


def _int_attr(node, name: str) -> int:
    return int(node.get(name) or 0)


def _positioned_offset(extra: int, position: str | None, axis: str) -> int:
    if extra <= 0:
        return 0
    if axis == "x":
        if position == "left":
            return 0
        if position == "right":
            return extra
    else:
        if position == "top":
            return 0
        if position == "bottom":
            return extra
    return extra // 2


def _apply_image_fit(shape, image_width: int, image_height: int, binding: dict) -> None:
    xfrm = shape.find(".//p:spPr/a:xfrm", NS)
    if xfrm is None:
        return
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return
    box_width = _int_attr(ext, "cx")
    box_height = _int_attr(ext, "cy")
    if not box_width or not box_height or not image_width or not image_height:
        return
    fit = binding.get("fit") or "contain"
    position = binding.get("position") or "center"
    blip_fill = shape.find("p:blipFill", NS)
    if blip_fill is not None:
        for crop in list(blip_fill.findall("a:srcRect", NS)):
            blip_fill.remove(crop)
    if fit == "stretch":
        return
    image_ratio = image_width / image_height
    box_ratio = box_width / box_height
    if fit == "contain":
        if image_ratio >= box_ratio:
            target_width = box_width
            target_height = max(1, round(box_width / image_ratio))
        else:
            target_height = box_height
            target_width = max(1, round(box_height * image_ratio))
        offset_x = _positioned_offset(box_width - target_width, position, "x")
        offset_y = _positioned_offset(box_height - target_height, position, "y")
        off.set("x", str(_int_attr(off, "x") + offset_x))
        off.set("y", str(_int_attr(off, "y") + offset_y))
        ext.set("cx", str(target_width))
        ext.set("cy", str(target_height))
        return
    if fit == "cover" and blip_fill is not None:
        crop = ET.Element(f"{{{A_NS}}}srcRect")
        if image_ratio > box_ratio:
            visible = box_ratio / image_ratio
            crop_total = round((1 - visible) * 100000)
            before = _positioned_offset(crop_total, position, "x")
            crop.set("l", str(before))
            crop.set("r", str(crop_total - before))
        elif image_ratio < box_ratio:
            visible = image_ratio / box_ratio
            crop_total = round((1 - visible) * 100000)
            before = _positioned_offset(crop_total, position, "y")
            crop.set("t", str(before))
            crop.set("b", str(crop_total - before))
        blip_fill.insert(0, crop)


def _ensure_png_content_type(members: dict[str, bytes]) -> None:
    root = ET.fromstring(members["[Content_Types].xml"])
    exists = any(
        item.get("Extension", "").lower() == "png"
        for item in root.findall(f"{{{CT_NS}}}Default")
    )
    if not exists:
        node = ET.Element(f"{{{CT_NS}}}Default")
        node.set("Extension", "png")
        node.set("ContentType", "image/png")
        root.append(node)
        members["[Content_Types].xml"] = ET.tostring(
            root, encoding="utf-8", xml_declaration=True
        )


class PptxRenderer:
    output_type = "pptx"

    def render(self, request: RenderRequest) -> None:
        try:
            with ZipFile(request.template_path) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
        except (BadZipFile, OSError) as exc:
            raise BadRequestError("PPTX 模板无法读取。") from exc
        _ensure_png_content_type(members)
        slide_roots: dict[int, object] = {}
        relation_roots: dict[int, object] = {}
        changed_slides: set[int] = set()
        changed_relations: set[int] = set()

        for binding in request.mapping.get("bindings", []):
            if not binding.get("visible", True):
                continue
            matched = re.fullmatch(r"pptx:s(\d+):shape:(\d+)", binding["object_key"])
            if not matched:
                continue
            slide_index, shape_id = (int(value) for value in matched.groups())
            slide_name = f"ppt/slides/slide{slide_index}.xml"
            if slide_name not in members:
                raise BadRequestError("模板映射引用了不存在的幻灯片。")
            root = slide_roots.setdefault(slide_index, ET.fromstring(members[slide_name]))
            shape = _shape_by_id(root, shape_id)
            if shape is None:
                raise BadRequestError("模板文件已经发生变化，请重新验证模板后再生成。")
            source = binding["source"]
            if source.startswith("image.") or source == "customer.logo":
                blip = shape.find(".//a:blip", NS)
                if blip is None:
                    raise BadRequestError("映射的 PowerPoint 图片对象结构无效。")
                image = resolve_image(binding, request.products, request.customer)
                png, image_width, image_height = as_png(image.payload)
                media_name = f"generated-s{slide_index}-shape{shape_id}.png"
                members[f"ppt/media/{media_name}"] = png
                rel_name = f"ppt/slides/_rels/slide{slide_index}.xml.rels"
                if rel_name not in members:
                    raise BadRequestError("PPTX 图片关系文件缺失。")
                rel_root = relation_roots.setdefault(
                    slide_index, ET.fromstring(members[rel_name])
                )
                existing_ids = {
                    item.get("Id") for item in rel_root.findall(f"{{{REL_NS}}}Relationship")
                }
                rel_id = f"rIdProductFlow{shape_id}"
                suffix = 1
                while rel_id in existing_ids:
                    suffix += 1
                    rel_id = f"rIdProductFlow{shape_id}_{suffix}"
                relationship = ET.Element(f"{{{REL_NS}}}Relationship")
                relationship.set("Id", rel_id)
                relationship.set(
                    "Type",
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                )
                relationship.set("Target", f"../media/{media_name}")
                rel_root.append(relationship)
                blip.set(f"{{{R_NS}}}embed", rel_id)
                _apply_image_fit(shape, image_width, image_height, binding)
                changed_relations.add(slide_index)
            else:
                if binding.get("text_runs"):
                    _replace_text_runs(
                        shape,
                        render_text_runs(
                            binding,
                            request.products,
                            request.customer,
                            request.parameters,
                        ),
                    )
                else:
                    value = resolve_value(binding, request.products, request.customer)
                    _replace_text(
                        shape,
                        format_text(
                            binding,
                            value,
                            customer=request.customer,
                            parameters=request.parameters,
                        ),
                    )
            changed_slides.add(slide_index)

        for slide_index in changed_slides:
            members[f"ppt/slides/slide{slide_index}.xml"] = ET.tostring(
                slide_roots[slide_index], encoding="utf-8", xml_declaration=True
            )
        for slide_index in changed_relations:
            members[f"ppt/slides/_rels/slide{slide_index}.xml.rels"] = ET.tostring(
                relation_roots[slide_index], encoding="utf-8", xml_declaration=True
            )
        request.destination.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(request.destination, "w", ZIP_DEFLATED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        self.validate(request.destination, changed_slides)

    @staticmethod
    def validate(path: Path, changed_slides: set[int] | None = None) -> None:
        try:
            with ZipFile(path) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
                    raise BadRequestError("生成的 PPTX 基础结构不完整。")
                ET.fromstring(archive.read("ppt/presentation.xml"))
                for slide_index in changed_slides or set():
                    ET.fromstring(archive.read(f"ppt/slides/slide{slide_index}.xml"))
        except (BadZipFile, KeyError, ET.ParseError) as exc:
            raise BadRequestError("生成的 PPTX 未通过结构验证。") from exc
