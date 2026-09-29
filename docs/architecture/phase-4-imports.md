# Phase 4 — Excel 导入引擎

## 范围

Phase 4 实现服务端 Excel 导入能力，不包含 Phase 5 的导入向导 UI，也不包含 PPT/XLSX 输出模板和 Renderer。

本阶段提供：

- 普通 `.xlsx` 上传、内容寻址存储和 SHA256 去重。
- openpyxl 工作簿结构解析。
- Sheet、行列、合并单元格、单元格值和基础格式分析。
- OOXML Drawing Relationship 级别的图片提取，保留原始媒体文件名和 Anchor。
- Microsoft MarkItDown 辅助内容理解；openpyxl 仍是结构数据的唯一权威来源。
- 带 transform、default、required、validation 和 formatter 的导入映射。
- 导入模板、导入任务、逐行预览和图片候选持久化。
- SKU 新增、更新、跳过和冲突判断。
- 用户明确选择 `overwrite`、`update_non_empty` 或 `skip` 后才执行写入。
- 图片自动匹配阈值和人工匹配 API。
- 全表 RLS、多租户复合外键和租户生命周期约束。

## 数据表

### `import_templates`

保存租户可复用的 XLSX 字段映射。模板名称在租户内不区分大小写唯一。

### `import_jobs`

保存源文件、分析结果、映射快照、重复处理策略、统计和最终状态。`mapping_snapshot` 在确认导入时固定，不依赖后续模板修改。

### `import_rows`

保存每个源 Sheet/行的原始数据、映射数据、校验错误、预览动作和最终产品关联。

### `import_image_candidates`

保存每个图片出现位置的原始文件名、安全文件名、来源坐标、匹配方法、置信度、来源说明和产品关联。底层字节及 SHA256、MIME、尺寸由 `stored_files` 保存。

## Import Mapping

```json
{
  "version": "1.0",
  "sheet_names": ["Products"],
  "header_row": 1,
  "data_start_row": 3,
  "fields": [
    {
      "source": "B",
      "target": "sku",
      "transform": "trim",
      "default_value": null,
      "required": true,
      "validation": {"pattern": "^[A-Za-z0-9/_-]+$"},
      "formatter": null
    },
    {
      "source": "E",
      "target": "product_name",
      "transform": "trim",
      "required": true,
      "validation": {"max_length": 300}
    },
    {
      "source": "T",
      "target": "supplier_cost",
      "transform": "decimal",
      "required": false,
      "validation": {"min": 0},
      "formatter": "currency"
    }
  ]
}
```

`source` 可以是 Excel 列字母或表头文字。映射目标必须是当前租户中存在且启用的 Field Definition。系统不会因为相似名称自行创建字段。

当前 transform：

- `text`
- `trim`
- `uppercase`
- `lowercase`
- `decimal`
- `integer`
- `boolean`
- `date`
- `normalize_dimension`

## 图片匹配

匹配顺序固定为：

1. 文件名 SKU，置信度 `1.000`。
2. Anchor 所在行的映射 SKU，置信度 `0.990`。
3. 相邻两行内唯一 SKU，置信度 `0.900`。
4. 上下文候选，置信度 `0.700`，只记录候选依据，不自动归属。
5. AI/Vision 预留，本阶段不默认调用。
6. 无可靠结果时保持 `unmatched`。

自动归属阈值为 `0.850`。低于阈值时 `matched_product_id` 保持为空，必须人工确认。

## API

- `GET /api/v1/import-templates`
- `POST /api/v1/import-templates`
- `PATCH /api/v1/import-templates/{template_id}`
- `GET /api/v1/import-jobs`
- `POST /api/v1/import-jobs/analyze`
- `GET /api/v1/import-jobs/{job_id}`
- `POST /api/v1/import-jobs/{job_id}/preview`
- `POST /api/v1/import-jobs/{job_id}/confirm`
- `PATCH /api/v1/import-image-candidates/{candidate_id}`

## 安全边界

- 仅支持普通 `.xlsx`；不处理 `.xls`、VBA 或企业文档保护解密。
- 无法读取时提示用户先解除企业文档保护并另存为普通 XLSX。
- 上传体积受 `MAX_UPLOAD_SIZE_MB` 限制。
- XLSX 解压后最大 512 MiB、单个内部对象最大 128 MiB、内部对象数量最大 20,000。
- XML 使用 defusedxml 解析；openpyxl 禁用外部链接保留。
- MarkItDown 仅以 `convert_local` 读取租户存储中的确定路径，不接受远程 URI。
- Excel 公式不会在服务器执行；预览使用缓存结果，缺少缓存的必填字段会进入校验错误。
- 不能静默覆盖已有 SKU。

## DEMO 验证

`D:\ProductFlow\DEMO` 的 7 个真实工作簿均已通过分析：

| 工作簿 | Sheet | 分析行数 | 提取图片 |
| --- | ---: | ---: | ---: |
| Birdbath_Birdhouse.xlsx | 1 | 120 | 32 |
| Garden Decors.xlsx | 5 | 570 | 121 |
| Garden stake.xlsx | 4 | 387 | 19 |
| Plastic planter.xlsx | 2 | 169 | 21 |
| Step stone.xlsx | 2 | 195 | 18 |
| Wall décor.xlsx | 1 | 111 | 19 |
| Windchime.xlsx | 1 | 123 | 19 |

所有工作簿的 MarkItDown 转换状态均为 `ok`，每个 Sheet 均识别出 SKU 字段建议，图片数量与 openpyxl 读取结果一致。
