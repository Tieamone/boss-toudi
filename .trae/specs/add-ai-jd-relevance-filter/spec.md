# AI JD 相关性筛选 Spec

## Why
当前岗位筛选仅基于职位名（`skip_keywords` 检查 `position+company`、`require_keywords` 检查 `position`），存在"漏网之鱼"：部分岗位的职位名不含跳过词、含必要词（如"设计"），但 JD 实际要求的是候选人不掌握的工具/方向（如室内设计要求 CAD/3D Max/酷家乐，机械设计要求 SolidWorks/UG），导致误投。

用户的核心原则：**JD 中只要有候选人没有掌握的工具，最好不要投**。现已接入 mimo AI 模型，应利用 AI 对 JD 做语义级相关性判断，弥补关键词匹配的不足。

## What Changes
- 新增 AI JD 相关性判断函数 `judge_job_relevance_by_ai(position, company, job_desc, core_stack)`，调用 mimo 模型判断岗位是否与候选人掌握的工具/能力相关
- 在 `_process_job_card` 中，于本地适配分检查（`min_fit_score`）通过后、查找沟通按钮前，插入 AI 相关性筛选环节
- AI 判定"无关"→ 跳过该岗位（记录 `skipped` + 原因），不再生成招呼语、不投递
- AI 判定"相关"→ 继续后续投递流程
- 在 `AI_CONFIG` 中新增开关 `jd_relevance_filter_enabled`（默认 `True`），仅在 `AI_CONFIG["enabled"]` 为 `True` 时生效
- test_mode 下 AI 筛选照常执行；判定结果（通过/跳过 + 原因 + 命中的未掌握工具）输出到日志和终端，便于用户验证与微调 prompt

## Impact
- Affected specs: 无（与已完成的 `fix-chat-send-and-salary-extract` 无重叠）
- Affected code:
  - [boss_auto_apply.py](file:///f:/code/test/boss-toudi/boss_auto_apply.py) `AI_CONFIG`（新增开关字段）
  - [boss_auto_apply.py](file:///f:/code/test/boss-toudi/boss_auto_apply.py) 新增 `judge_job_relevance_by_ai` 函数
  - [boss_auto_apply.py](file:///f:/code/test/boss-toudi/boss_auto_apply.py) `_process_job_card`（插入筛选调用）
  - 复用现有 `_call_mimo_api`、`AI_CONFIG` 基础设施

## ADDED Requirements

### Requirement: AI JD 相关性判断
系统 SHALL 提供一个 AI 相关性判断函数，输入为职位名、公司、JD 文本、候选人掌握的工具栈，输出为（是否相关, 原因, 命中的未掌握工具列表）。

#### Scenario: JD 核心要求含候选人不掌握的工具
- **WHEN** JD 明确要求 CAD / 3D Max / 酷家乐 / SolidWorks / UG / ProE 等候选人不掌握的工具，或岗位方向（如室内设计、机械设计、建筑设计）与候选人视觉传达设计方向不符
- **THEN** AI 返回"无关"，系统跳过该岗位并记录原因（如"JD要求未掌握工具：CAD、3D Max"）

#### Scenario: JD 要求均在候选人掌握范围内
- **WHEN** JD 要求 Photoshop / Illustrator / C4D / AE / XD / 剪映 等 candidate 已掌握的工具，或 AI 设计工具
- **THEN** AI 返回"相关"，系统继续后续投递流程

#### Scenario: JD 含少量不掌握工具但非核心要求
- **WHEN** JD 主要求是候选人掌握的工具，但"加分项/了解即可"中提到候选人不掌握的工具
- **THEN** AI 应综合判断，若核心要求匹配则返回"相关"，并在原因中说明

#### Scenario: AI 接口调用失败
- **WHEN** mimo API 调用超时或报错
- **THEN** 默认放行（返回"相关"），记录警告日志，不因 API 故障阻断全部投递

### Requirement: AI 相关性筛选插入投递流程
系统 SHALL 在 `_process_job_card` 中、本地适配分检查通过后、查找沟通按钮前，调用 AI 相关性判断；判定"无关"时短路退出并记录 `skipped`。

#### Scenario: 岗位通过本地筛选但 AI 判定无关
- **WHEN** 职位名含"设计"通过 `require_keywords`，适配分达标，但 AI 判定 JD 要求未掌握工具
- **THEN** 该岗位标记为 `skipped`，原因为 AI 判定结果，不生成招呼语、不点击沟通按钮、不投递

#### Scenario: test_mode 下 AI 判定无关
- **WHEN** test_mode 为 True 且 AI 判定无关
- **THEN** 不生成/不打印招呼语，终端输出 AI 判定结果（跳过 + 原因），记录 `skipped`

### Requirement: AI 筛选开关
`AI_CONFIG` SHALL 新增 `jd_relevance_filter_enabled` 字段控制此功能，默认开启；`AI_CONFIG["enabled"]` 为 False 时此功能自动失效。

#### Scenario: 开关关闭
- **WHEN** `jd_relevance_filter_enabled` 为 False
- **THEN** 跳过 AI 相关性判断环节，恢复原有行为

#### Scenario: AI 整体关闭
- **WHEN** `AI_CONFIG["enabled"]` 为 False
- **THEN** AI 相关性判断不执行（无 API Key 无法调用）

## MODIFIED Requirements

### Requirement: _process_job_card 投递流程
原流程：JD 抓取 → 校招检测 → 画像选择 → 适配分检查 → 查找沟通按钮 → AI 招呼语生成 → test_mode/投递。

修改为：JD 抓取 → 校招检测 → 画像选择 → 适配分检查 → **AI JD 相关性筛选（新增）** → 查找沟通按钮 → AI 招呼语生成 → test_mode/投递。

AI 相关性筛选在本地适配分（廉价关键词匹配）之后执行，避免对明显不匹配的岗位浪费 API 调用；在招呼语生成之前执行，避免对不相关岗位生成招呼语。

## REMOVED Requirements
无。
