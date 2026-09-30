<div align="center">

# ProductFlow · 产品资料与报价工作台

**多租户产品资料管理、客户组合与可编辑报价文件生成平台**

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

</div>

ProductFlow 面向外贸业务团队：将供应商 Excel 与嵌入图片导入标准产品资料库，按客户维护产品组合和模板，并输出原生可编辑的 PPTX/XLSX 文件或可离线交付的精品 HTML 报价单。

> 当前为 MVP：核心流程已经实现，审计整改与真实业务模板验收仍在进行中。

## 真实界面截图

以下均为 ProductFlow 实际运行界面截图，展示的游戏机产品资料为项目演示数据；不包含登录界面或账号信息。

<p align="center"><img src="docs/screenshots/business-overview.png" alt="ProductFlow 业务概览与系统健康状态" width="100%" /></p>

<p align="center"><img src="docs/screenshots/product-library.png" alt="ProductFlow 产品资料库中的游戏机产品数据" width="100%" /></p>

## 功能一览

| 模块 | 可完成的工作 |
| --- | --- |
| 账号与租户 | 注册、登录、角色控制；租户数据由 PostgreSQL RLS 隔离。管理员重置密码后会立即撤销该用户已有登录会话。 |
| 产品资料 | 维护 SKU、产品图片、字段、分类与品牌；分类/品牌是租户级字典，既可筛选复用，也会在保存新值时自动补充。 |
| 图片库 | 批量上传和关联产品。系统保留原图，并可识别边缘白底、生成裁切后的透明 PNG，报价输出优先使用透明衍生图。 |
| 数据导入 | 导入供应商 Excel，设置字段映射、数据起始行、重复 SKU 策略与图片匹配规则；审核预览和置信度后才写入资料库。 |
| 客户与组合 | 管理客户、客户可见字段和产品组合，确保内部字段不会输出给客户。 |
| 模板与生成 | 校验 PPTX/XLSX 模板、保存字段/图片 Mapping，并生成原生可编辑的 PPTX/XLSX 报价文件。每次生成均固化产品、图片、客户、模板和参数快照。 |
| 精品 HTML 报价 | 内置 Editorial Luxury、Curated Journey、Bold Energy 三种版式，支持批量选品、三图展示、图片内嵌和浏览器打印/PDF。生成的单个 HTML 文件可离线交付。 |
| 多币种 | 同一次报价可选择多个币种，默认 USD。系统只显示该产品实际存在的所选币种金额，不做汇率换算，也不会使用其他市场价格回填。 |
| 系统后台 | 平台管理员可跨租户查看汇总信息；业务数据保持只读。 |

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vite、Nginx |
| 后端 | Python 3.12、FastAPI、Uvicorn、Alembic |
| 数据 | PostgreSQL 16、Redis 7.4 |
| 部署 | Docker Compose |
| 输出 | 自包含 HTML、PPTX/XLSX 原生文件 |

## 快速开始

### 前置条件

- Docker Engine 与 Docker Compose
- 私有环境变量文件 `.env`（不要提交）

```bash
cp .env.example .env
# 在 .env 中设置强密码和 JWT_SECRET 后再启动
docker compose up -d --build
```

默认 Web 端口为 `7030`，API 端口为 `8030`。服务状态与健康检查：

```bash
docker compose ps
curl http://localhost:8030/health
```

停止服务并保留数据：

```bash
docker compose down
```

不要在没有完整备份和明确授权的情况下执行 `docker compose down -v`。

## 配置与安全

从 `.env.example` 创建仅保存在本机的 `.env`。部署前必须替换 PostgreSQL 管理账号密码、应用账号密码、JWT 签名密钥和初始管理员密码；任何 `.env`、Token、Cookie、数据库连接串、上传文件或生成的报价文件都不应提交到仓库。

正常业务 API 应使用受 RLS 约束的数据库应用账号。生产环境还应配置真实域名、HTTPS、备份策略和不可变镜像标签。

## 操作步骤

### 1. 建立产品资料

1. 进入“数据导入”，上传供应商 Excel；设置表头、数据起始行和字段映射。
2. 按预览检查数据和图片匹配结果，选择遇到同 SKU 时的处理方式，再确认导入。
3. 在“产品资料”中补充或修改 SKU、分类、品牌和业务字段。新增分类或品牌会自动进入当前租户的字典，之后可作为筛选条件使用。
4. 在“图片库”批量上传或补传产品图片，并关联到对应产品。白底图片会保留原图，并生成供报价使用的透明裁切图。

### 2. 配置客户、字段与产品组合

1. 在“字段管理”维护产品字段，明确每个字段是内部字段还是客户可见字段。
2. 在“客户管理”创建客户资料；只将允许交付的信息标记为客户可见。
3. 创建“产品组合”，从产品库选入本次客户需要的 SKU，供后续报价复用。

### 3. 生成 PPTX/XLSX 报价文件

1. 在“模板中心”上传 PPTX 或 XLSX 模板，完成字段和图片 Mapping，并通过模板校验。
2. 打开“生成中心”，选择客户、产品组合、输出模板和一个或多个报价币种。
3. 创建任务并下载生成结果。文件仍可用 PowerPoint 或 Excel 编辑；生成记录会保留当时使用的数据快照，便于追溯。

### 4. 生成可离线交付的 HTML 报价单

1. 在“生成中心”选择“精品 HTML 报价单”，从 Editorial Luxury、Curated Journey、Bold Energy 中选择版式。
2. 勾选产品、选择至少一个报价币种，并填写报价标题和备注。
3. 下载 `.html` 文件。产品图片和本次允许输出的资料已嵌入文件，浏览器直接打开即可预览、打印或另存为 PDF，不依赖 ProductFlow 登录态。

### 5. 使用多币种

- 默认币种为 USD，可同时勾选 JPY 等其他已配置币种。
- 某产品没有某一所选币种的价格时，只隐藏该币种；所有所选币种均无价格时，才隐藏该产品的价格区块。
- 系统不做汇率换算：`price_usd` 与 `price_jpy` 应分别维护对应市场的实际价格。需要 EUR、GBP 等币种时，在字段管理创建客户可见金额字段，字段代码使用 `price_eur`、`price_gbp` 这类三位 ISO 货币代码格式；生成中心会自动识别。

当前任天堂演示产品的 `price_usd` 是美国市场首发 MSRP，并非日元换算。Game Boy Light（日本限定）和没有美国独立标准版首发价的新任天堂 3DS 标准版保留空 USD 值；同时选择 USD 与 JPY 时，它们仅显示 JPY。

## Renderer 边界

当前稳定支持：PPT 文本/文本 Run/图片 Shape，以及 XLSX 单元格、合并单元格和图片。DOCX/PDF Renderer、在线 PPT 编辑器、SmartArt、复杂图表、动画、VBA、复杂母版以及动态复制幻灯片/表格行不在当前范围内。

模板文件变更后必须重新验证 Mapping；内部字段不会进入客户输出。被历史生成任务引用的产品或输出模板应归档而不是永久删除。

## 测试

```bash
docker compose --profile test run --rm backend-test pytest -q
docker compose --profile test run --rm frontend-test npm test -- --run
docker compose exec -T backend python -m ruff check app tests
```

## 许可证

本仓库暂未声明开源许可证；未经授权不得复制、分发或用于生产部署。
