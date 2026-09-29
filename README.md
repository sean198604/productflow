# ProductFlow

**多租户产品资料管理与报价文件生成平台**

ProductFlow 面向外贸业务团队：将供应商 Excel 与嵌入图片导入标准产品资料库，按客户维护产品组合和模板，并从经验证的 PPTX/XLSX 模板生成原生可编辑的报价文件。

> 当前为 MVP：核心流程已经实现，审计整改与真实业务模板验收仍在进行中。

## 真实界面截图

以下均为 ProductFlow 实际运行界面截图，展示的游戏机产品资料为项目演示数据；不包含登录界面或账号信息。

<p align="center"><img src="docs/screenshots/business-overview.png" alt="ProductFlow 业务概览与系统健康状态" width="100%" /></p>

<p align="center"><img src="docs/screenshots/product-library.png" alt="ProductFlow 产品资料库中的游戏机产品数据" width="100%" /></p>

## 核心能力

- 多租户注册、登录、角色控制与 PostgreSQL RLS 数据隔离。
- 产品、图片、自定义字段及内部字段/客户字段隔离。
- Excel 导入：字段映射、说明行忽略、重复 SKU 策略、图片匹配与置信度审计。
- 客户、产品组合、导入模板和输出模板管理。
- PPTX/XLSX 模板解析、字段/图片映射与 SHA-256 指纹验证。
- 原生可编辑的 PPTX/XLSX 报价文件生成，以及可追溯的不可变 Generation Snapshot。
- 平台管理员跨租户只读汇总后台。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vite、Nginx |
| 后端 | Python 3.12、FastAPI、Uvicorn、Alembic |
| 数据 | PostgreSQL 16、Redis 7.4 |
| 部署 | Docker Compose |
| 输出 | PPTX/XLSX 原生文件 |

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

## 使用流程

1. 上传并分析供应商 Excel，配置字段映射、数据起始行和图片匹配规则。
2. 审核导入预览并选择重复 SKU 策略，将资料写入产品库。
3. 维护客户、产品组合和客户可见字段。
4. 上传 PPTX/XLSX 输出模板，验证参数化对象并保存字段/图片 Mapping。
5. 创建生成任务；系统冻结产品、图片、客户、组合、模板和参数快照后生成可编辑报价文件。

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
