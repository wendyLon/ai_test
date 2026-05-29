# 平台架构概览

目标：构建模块化、可扩展、AI 驱动的 SEN 活动聚合平台。

模块划分：
- `crawler/`：负责抓取网页（Playwright、Crawlee），保存原始 HTML、截图与元数据。
- `analyzer/`：对 DOM 进行分块、语义识别、候选事件段落检测。
- `extractor/`：结合启发式规则与 LLM，将候选段落抽取成结构化字段（JSON）。
- `normalizer/`：统一币种、费用、日期、语言、年龄区间等格式。
- `deduper/`：基于 `web_url`、指纹和 title+date 进行去重判定。
- `exporter/`：把 JSON 转为 INSERT/UPDATE/UPSERT SQL，并保存 SQL 文件。
- `scheduler/`：任务调度（周期性抓取、重试、失败报警）。
- `agents/`：OpenClaw 集成接口与任务队列适配器。

数据流：
1. 从 `url.txt` 读取入口 URL 列表（每行一个组织首页或目录页）。
2. `crawler` 抓取页面，保存 HTML、截图、HTTP 元数据，产出候选 URL。
3. `analyzer` 对页面做 DOM 分块、事件容器识别，标注候选块。
4. `extractor` 使用本地规则 + LLM（可插拔后端）对候选块抽取字段，输出符合 `schemas/event_schema.json` 的 JSON。
5. `normalizer` 清洗字段，标准化时间/货币/语言等。
6. `deduper` 判断是否重复并决定 INSERT/UPDATE。
7. `exporter` 生成 SQL 文件并可选择直接写入 MySQL。

扩展性要点：
- 每个模块提供清晰接口（Python package），可被替换/扩展。
- AI/LLM 调用通过抽象层（`agents/llm_client.py`），支持多家 LLM 提供商。
- 抓取与提取分离：避免为单站点写死选择器。

日志与审计：保存原始 HTML、截图、提取的原始 JSON、最终 SQL 与抓取日志。

隐私与合规：尊重 robots.txt，可配置最大抓取速率与并发，支持代理/验证码策略。
