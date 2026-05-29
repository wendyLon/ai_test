## 一、数据库字段分析（sys_training 每个字段应存什么）

### sys_training_provider（机构表）

| 字段 | 类型 | 应存内容 | 来源 |
|------|------|---------|------|
| id | INT PK | 与 id_hint 对应，1-23 id_hint |
| status | INT | 1=正常 | 固定=1 |
| name_zh_tw | VARCHAR(150) | 繁体名称 |
| name_zh_cn | VARCHAR(150) | 简体名称 |
| name_en_us | VARCHAR(150) | 英文名称 |
| intro_zh_cn | VARCHAR(500) | 简体简介 |
| intro_en_us | VARCHAR(500) | 英文简介 |
| intro_zh_tw | VARCHAR(500) | 繁体简介 |
| website_url | VARCHAR(255) | 官方网站首页 |
| contact_phone | VARCHAR(50) | 联系电话 |
| contact_email | VARCHAR(100) | 联系email |
| provider_type_code | VARCHAR(64)  | 机构性质 | NGO/Private/Social enterprise/Charitable trust |
| main_sen_type_code | VARCHAR(54) | 主要SEN类型 | all_sen/autism/adhd/dyslexia等 |
| logo | varchar(255) |
| recommend_count(10) | INT | 
| sort | smallint(5) | 
| addtime/updatetime | INT | Unix timestamp | 自动 |

### sys_training（培训活动表）

| 字段 | 类型 | 应存内容 | 来源 | 优先级 |
|------|------|---------|------|--------|
| provider_id | INT FK | 关联机构id | 自动 | 必填 |
| status | INT | 1=正常, 0=停用 | enrollment_status推断 | 必填 |
| title_zh_tw | VARCHAR(255) | 课程繁体标题（非机构名！） | scraped | 必填 |
| title_zh_cn | VARCHAR(255) | 课程简体标题（可为空） | scraped | 选填 |
| title_en_us | VARCHAR(255) | 课程英文标题（可为空） | scraped | 选填 |
| description_zh_cn | text | 课程完整描述（简体） | scraped | 重要 |
| description_zh_tw | text | 课程完整描述（繁体） | scraped | 重要 |
| description_en_us | text | 课程完整描述（英文） | scraped | 重要 |
| summary_zh_cn | VARCHAR(500) | 课程摘要（简体）（service_content截500字） | scraped | 重要 |
| summary_zh_tw | VARCHAR(500) | 课程摘要（繁体）（service_content截500字） | scraped | 重要 |
| summary_en_us | VARCHAR(500) | 课程摘要（英文）（service_content截500字） | scraped | 重要 |
| target_group | VARCHAR(255) | 服务对象、目标群体（年龄/学级/SEN类型） | scraped | 重要 |
| teaching_mode | VARCHAR(32) | 授課模式 | 重要 |
| fee_type | VARCHAR(32) | free/paid/subsidised | 从fee推断 | 重要 |
| fee | VARCHAR(255) | 费用原文（如"$240/1堂"） | scraped | 重要 |
| fee_amount | VARCHAR(255) | 从fee获取（如"$240"） | scraped | 重要 |
| currency | VARCHAR(10) | HKD | 固定 | 必填 |
| venue_name | VARCHAR(1000) | 地点/地址 | scraped location | 重要 |
| web_url | VARCHAR(255) | 课程来源URL（去重键！唯一约束） | source_url | 必填 |
| signup_url | VARCHAR(255) | 报名链接 | scraped | 重要 |
| schedule_time | VARCHAR(255) | 上课时间文本 | scraped schedule | 重要 |
| end_time | VARCHAR(255) | 活动结束时间 | scraped schedule | 重要 |
| sen_codes_json | TEXT | JSON数组，SEN类型代码 | scraped/推断 | 重要 |
| sen_types | VARCHAR(500) | SEN类型文本 | scraped/推断 | 重要 |
| district_codes_json | TEXT | 地区(多选JSON)（如：["kwun_tong", "kowloon", "sai_kung"]） | 选填 |
| age_ranges_json | TEXT | JSON数组，年龄范围 | scraped age_range | 选填 |
| audience_type | VARCHAR(32) | child/parent | 从标题/描述推断 | 重要 |
| format_type | VARCHAR(32) | offline/online/hybrid | 固定=offline | 必填 |
| language_codes_json | TEXT | JSON数组，语言代码 | ["zh-tw","zh-cn","en-us"] | 重要 |
| language_text | VARCHAR(255) | 语言文本 | 繁體中文、简体中文、英文、粤语等等 | 选填 |
| frequency | VARCHAR(255) | 频率（如"每週一次"） | scraped | 选填 |
| duration | VARCHAR(100) | 每节时长（如"60分钟"） | scraped | 选填 |
| quota | VARCHAR(255) | 名额（如"6人小组"） | scraped | 选填 |
| deadline | VARCHAR(255) | 报名截止日期 | scraped | 选填 |
| is_recommended | INT | 0 | 固定 | - |
| is_interest_open | INT | 1 | 固定 | - |
| addtime/updatetime | INT | Unix timestamp | 自动 | 必填 |

**字段填充完善** — 确保每条活动尽量填满：
   - target_group（从描述提取年龄、学级、SEN类型）
   - sen_codes_json（从title/description推断SEN类型）
   - venue_name（提取实际地址）
   - schedule_time（提取上课时间）
   - fee（提取费用）
