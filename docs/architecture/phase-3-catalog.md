# Phase 3：产品数据库、自定义字段与图片库

## 完成范围

Phase 3 建立可供 Excel 导入、客户模板和生成快照复用的产品资料域：

- 产品核心字段与租户内大小写不敏感的 SKU 唯一性
- 标准字段和自定义字段的统一 Field Definition
- 类型化 Product Field Value
- 客户报价字段与内部字段边界
- 产品图片、原始文件元数据和 SHA256 去重
- 产品、字段与图片的管理 API 和响应式 Web UI
- 全部新增业务表的 PostgreSQL 强制 RLS

Excel 解析、自动图片匹配和人工匹配工作台属于 Phase 4，本阶段只建立它们需要的数据结构。

## 数据模型

### field_definitions

每个字段包含：

- `tenant_id`、`code`、`label`
- `data_type`：`text | number | money | date | boolean | select | multi_select | image`
- `scope`：`customer | internal`
- `is_system`、`is_core`、`is_required`
- `options JSONB`、`sort_order`、`status`

系统为每个租户建立标准产品字段。`supplier_cost`、`purchase_price`、`margin` 和 `supplier` 固定为内部字段，API 禁止将系统内部字段改为客户字段。

### products

核心字段直接保存在产品表中：`sku`、`product_name`、`description`、`category`、`brand` 和 `status`。`(tenant_id, lower(sku))` 唯一，避免仅大小写不同的重复 SKU。

### product_field_values

扩展值采用规范化表，而不是把所有数据放进一个无约束 JSON 对象。该表通过以下复合外键同时约束租户边界：

- `(tenant_id, product_id) -> products(tenant_id, id)`
- `(tenant_id, field_definition_id) -> field_definitions(tenant_id, id)`

服务层根据 Field Definition 校验并规范化金额、数字、日期、布尔和选项值。未知字段、已停用字段和无效选项直接拒绝，不做名称猜测。

### stored_files 与 product_images

`stored_files` 保存实际文件身份：

- 原始文件名、安全文件名和租户内存储键
- SHA256、MIME、字节数、宽度和高度
- 同租户相同 SHA256 只保存一份实际文件

`product_images` 保存产品关联和业务语义：

- 图片类型、排序、主图标记
- `source_sheet`、`source_row`、`source_column`
- `match_method`、`match_confidence`、`match_source`
- 到产品和存储文件的租户复合外键

手工上传记录为 `method=manual`、`confidence=1.000`。后续导入器只能使用已经确认的匹配优先级写入其他方法；低置信度图片必须进入 unmatched 流程。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET/POST` | `/api/v1/products` | 检索或创建产品 |
| `GET/PATCH` | `/api/v1/products/{id}` | 查看或更新产品及自定义字段 |
| `GET` | `/api/v1/products/stats` | 产品域统计 |
| `GET/POST` | `/api/v1/field-definitions` | 查看或创建字段定义 |
| `PATCH` | `/api/v1/field-definitions/{id}` | 更新字段显示属性与状态 |
| `GET/POST` | `/api/v1/products/{id}/images` | 产品图片列表或上传 |
| `GET` | `/api/v1/product-images` | 租户图片库 |
| `PATCH` | `/api/v1/product-images/{id}` | 调整类型、排序或主图 |
| `GET` | `/api/v1/product-images/{id}/content` | 鉴权读取图片内容 |

字段创建仅允许 Owner/Admin。产品与图片是业务协作数据，当前允许所有已登录租户成员维护；数据库 RLS 仍是最终安全边界。

## UI 设计基准

界面采用 3010 项目的企业 SaaS 视觉语言：海军蓝主色、白色侧栏、轻量渐变背景、紧凑卡片和表格、页面语义标题区，以及桌面侧栏/移动底栏双导航。只复用视觉系统，不复用其项目管理业务。

产品详情明确分为“客户报价字段”和“内部字段”两个区域，内部区域使用锁定标识和独立色彩提示，避免业务人员误把成本数据当作可输出字段。

## 验收

- Alembic 迁移：`20260925_0003`
- Alembic autogenerate check 无未同步操作
- 自动化覆盖产品 CRUD、字段权限和类型校验、SKU 去重、图片上传/指纹/尺寸/内容读取，以及跨租户产品 RLS 隔离
- 前端覆盖真实登录表单和租户产品列表渲染
