# Phase 6：输出模板中心

## 范围

本阶段实现 PPTX/XLSX 输出模板的上传、结构验证、版本管理和字段绑定，不实现 Canva 类在线编辑器，也不执行最终文件生成。

业务链路：

上传 PPTX/XLSX 模板
→ 保存 SHA256 与版本
→ 解析模板对象
→ 展示支持与不支持对象
→ 用户显式绑定客户字段或图片来源
→ 保存 Mapping

## 数据模型

### `output_templates`

- 租户内模板名称不区分大小写唯一。
- 记录 `pptx` 或 `xlsx` 类型、状态和当前版本号。

### `output_template_versions`

- 每次上传创建不可变版本号和 `template_sha256`。
- 保存原始文件、验证报告、Mapping 及映射状态。
- 同一模板不允许重复上传相同 SHA256。
- 新文件版本不继承旧 Mapping，并返回“模板文件发生变化，请重新验证字段映射”。

两张表均启用并强制执行 PostgreSQL RLS。

## Template Validation

PPTX 第一版识别：

- Slide
- Text Shape
- Image Shape
- Table
- Shape position / size
- 基础字体属性

XLSX 第一版识别：

- Sheet
- Cell / Merged Cell
- Image
- Table
- Cell position / size
- 基础字体和数字格式

验证报告会明确列出暂不支持对象，包括 SmartArt、复杂图表、组合图形、动画编辑、VBA、复杂母版编辑和任意 Office 对象编辑。

## Mapping

每条绑定包含：

- `object_key`
- `source`
- `visible`
- `label`
- `formatter`
- `default_value`
- `fallback`
- `transform`
- `fit`
- `position`

图片来源支持 `image.main`、`image.white_background`、`image.lifestyle`、`image.detail`、`image.packaging` 和 `image.other`，并保存 fallback 顺序。

保存 Mapping 时后端重新验证：

- 请求中的 SHA256 必须等于模板版本指纹。
- 模板对象必须存在且可参数化。
- 图片来源只能绑定图片对象。
- 字段必须存在、有效且属于客户字段。
- 内部字段即使 `visible=false` 也禁止进入客户模板 Mapping。
- 未绑定字段不会默认进入输出上下文。

## API

- `GET /api/v1/output-templates`
- `POST /api/v1/output-templates`
- `GET /api/v1/output-templates/{template_id}`
- `PATCH /api/v1/output-templates/{template_id}`
- `POST /api/v1/output-templates/{template_id}/versions`
- `PUT /api/v1/output-templates/versions/{version_id}/mapping`
- `GET /api/v1/output-templates/versions/{version_id}/content`

模板创建、更新、版本上传和 Mapping 修改仅允许 Tenant Owner 或 Admin。普通成员可以查看模板及验证结果。
