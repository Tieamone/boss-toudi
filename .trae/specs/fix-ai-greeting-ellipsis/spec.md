# AI 招呼语省略号 Bug 修复 Spec

## Why
AI 生成的招呼语中出现省略号（`...`），让 HR 容易识别为 AI 自动投递。根因是 `max_completion_tokens=256` 对 MiMo reasoning 模型过小（255 token 被思考消耗，正文只剩 1 token），导致 AI 返回空内容，触发本地兜底招呼语；而兜底函数 `_shorten_text()` 会把作品证据截断到 42 字符并加 `...`，产生不自然的省略号。

## What Changes
- **增大 `max_completion_tokens`**：从 `256` 提升到 `1024`，给 reasoning 模型留足思考+输出空间
- **优化兜底招呼语截断逻辑**：`_build_local_fallback_greeting()` 中不再用 `...` 截断作品证据，改为完整保留或用句号自然结尾
- **优化 `_shorten_text()` 函数**：将省略号 `...` 替换为更自然的结尾（句号 `。` 或完整保留），避免暴露 AI 痕迹
- **增加日志诊断**：当 AI 因 `finish_reason=length` 返回空内容时，日志中给出明确的修复建议提示

## Impact
- Affected specs: 无
- Affected code:
  - `boss_auto_apply.py` 中 `call_mimo_api()` 的 payload `max_completion_tokens`（约第 893 行）
  - `boss_auto_apply.py` 中 `_shorten_text()` 函数（约第 795-799 行）
  - `boss_auto_apply.py` 中 `_build_local_fallback_greeting()` 函数（约第 801-816 行）
  - `boss_auto_apply.py` 中 AI 返回空内容的日志提示（约第 912-917 行）

## ADDED Requirements

### Requirement: 兜底招呼语不得包含省略号
系统在生成本地兜底招呼语时，SHALL NOT 使用省略号（`...`、`…`、`。。。`）截断作品证据或技能描述，避免暴露 AI 自动投递痕迹。

#### Scenario: 作品证据超过长度限制
- **WHEN** 作品证据文本超过 `_shorten_text` 的 max_len 限制
- **THEN** 系统在完整句子边界处截断并以句号 `。` 结尾，或完整保留不截断

#### Scenario: AI 因 token 限制返回空内容
- **WHEN** MiMo API 返回 `finish_reason=length` 且 content 为空
- **THEN** 日志中提示"max_completion_tokens 可能过小，reasoning 模型思考 token 占用过多"，并使用本地兜底招呼语（不含省略号）

## MODIFIED Requirements

### Requirement: AI 招呼语生成 token 限制
`call_mimo_api()` 中 `max_completion_tokens` SHALL 设置为 `1024`，确保 MiMo reasoning 模型有足够 token 完成思考并输出完整正文（80~120 字）。

### Requirement: 文本截断函数
`_shorten_text()` 函数 SHALL 在截断时使用句号 `。` 作为结尾，而非省略号 `...`，使截断后的文本看起来像完整的句子。

### Requirement: 兜底招呼语作品证据呈现
`_build_local_fallback_greeting()` 中作品证据 `proof` SHALL 完整保留或自然截断，不得出现 `...` 省略号。
