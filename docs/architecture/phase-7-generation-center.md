# Phase 7：客户、产品组合与生成中心

## 完成范围

- Customer 与 Tenant 分离，客户拥有独立代码、状态、Logo、区域设置和默认 PPTX/XLSX 模板。
- Customer Settings 和 Customer Template Bindings 使用独立表保存。
- Product Set 支持产品多对多、稳定排序、客户专属组合和批量选择。
- Output Mapping 增加 `product_slot` 与 XLSX `allow_formula`，并支持客户名称、客户代码和客户 Logo。
- Generation Task 固化产品字段、图片、客户、产品组合、模板版本和输出参数快照。
- PPTX Renderer 修改原生 Text Shape、Picture Shape 和表格文本，不把整页转成图片。
- XLSX Renderer 修改原生 Cell 和图片对象，保留工作表结构、样式、合并单元格、行高和列宽。
- 普通 XLSX 文本禁止公式注入，只有 Mapping 明确设置 `allow_formula=true` 才允许公式。
- 渲染前重新计算模板 SHA256；指纹变化立即失败，不做 Shape 模糊匹配。
- 输出先写入租户临时目录，通过结构验证后原子移动到租户 exports。

## 生成链路

```text
Customer
  + Product Set / Selection
  + Ready Output Template Version
  -> Generation Task Snapshot
  -> Permission-filtered Render Context
  -> PPTX / XLSX Renderer
  -> Atomic Export
  -> Authenticated Download
```

## 安全边界

- Render Context 仅包含 Mapping 实际引用且属于 `scope=customer` 的有效字段。
- 内部字段不进入产品快照；`visible=false` 的绑定不进入渲染上下文。
- 图片只从当前 Product 的明确类型及 fallback 顺序中选择；全部缺失时使用占位图。
- 失败任务没有 `output_file_id`，下载接口拒绝非 completed 状态。
- 新增业务表全部启用并强制执行 PostgreSQL RLS；平台管理员只读策略与既有域一致。

## 当前执行模型

MVP 在创建任务请求内同步执行 Renderer，同时完整记录 `queued -> processing -> completed/failed` 状态。后续可以把同一服务边界接入 Redis Worker，不改变 Generation Task、Snapshot 或 Renderer 接口。
