# 机构接入指南（简要）

1. 在 `url.txt` 中添加机构入口 URL（每行一个）。优先填写机构“活动/課程/公告”页、Calendar、或 Events 列表页。
2. 如机构有公开 API 或 RSS，请在 URL 行后加注：`#api` 或 `#rss`。
3. 提交示例：

```
https://example.org/events
https://api.example.org/v1/events #api
```

4. 可选元数据：为提高匹配率，可在平行文件 `providers_meta.json` 中提供机构映射（网站域 -> provider_id / 名称 / 语言）。

5. 上线前建议：手动审阅少量抓取结果（raw HTML + screenshot），确认提取质量并在 `schemas/event_schema.json` 下调整字段。
