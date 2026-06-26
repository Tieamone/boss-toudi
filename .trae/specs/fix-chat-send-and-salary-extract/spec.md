# 修复聊天发送按钮与薪资抓取 Bug Spec

## Why
当前 `boss_auto_apply.py` 存在两个影响实际投递成功率的 bug：
1. 在聊天记录页向 HR 发送招呼语时，**概率性**出现"文字已写入输入框但未真正发送"——`chat_input.input()` 通过 JS 设置文本但未触发 Boss 框架（Vue）依赖的原生 input 事件，导致 send 按钮未被激活或点击无效果。
2. 列表页薪资抓取**丢失数字**，日志中出现 `-K`、`-K·薪` 等异常值，导致薪资上下限过滤失效，部分不该投递的岗位反而通过过滤。

## What Changes
- **修复薪资抓取**：在 `_job_card_snapshot` 的 JS 中加入 iconfont 数字解码逻辑（解析 `icon-num-0` ~ `icon-num-9`、`icon-num-point`、`icon-num-minus` 等类名），同时通过 `getComputedStyle(el, '::before').content` 兜底提取 PUA 字符；Python 侧 `_decode_boss_obfuscated_digits` 不变。
- **修复聊天发送（概率事件，仅做兜底）**：
  - 逐字输入完成后，对输入框 `dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text}))` 触发 Boss 框架依赖的 input 事件，提升 send 按钮激活概率；
  - 点击 send 按钮后追加一次 Enter 键兜底发送（Boss 输入框为空时 Enter 不会发送任何内容，安全无副作用），覆盖概率性失败场景；
  - 不再额外做 disabled 检测、输入框清空校验等复杂判断。
- **保留**：现有的逐字输入逻辑（受 `typing_char_delay` 配置控制），仅追加输入事件分发与 Enter 兜底。

## Impact
- Affected specs: 无（项目无现有 spec）
- Affected code:
  - [boss_auto_apply.py](file:///f:/code/test/boss-toudi/boss_auto_apply.py) `_job_card_snapshot`（JS 段）
  - [boss_auto_apply.py](file:///f:/code/test/boss-toudi/boss_auto_apply.py) `_send_message`
  - 可能小幅影响 `_find_salary`（在 Python 侧拼接 iconfont 解码后的字符串）

## ADDED Requirements
### Requirement: 薪资 iconfont 解码
系统 SHALL 在抓取岗位卡片薪资时，对 `.salary` 元素内的 iconfont 子节点进行解码，还原 `0-9`、`.`、`-`、`K` 等真实字符。

#### Scenario: 薪资元素只含 iconfont 数字
- **WHEN** `.salary` 元素的 `innerText` 仅返回 `-K` 或 `·薪`，但子节点存在 `<i class="icon-num-7">` 等
- **THEN** snapshot 的 `salary` 字段应返回 `7-10K` 这样的完整字符串

#### Scenario: 薪资元素含明文数字
- **WHEN** `.salary` 元素 `innerText` 已包含 `7-10K`
- **THEN** 解码逻辑不应破坏原有文本，返回 `7-10K`

#### Scenario: 完全无可解码内容
- **WHEN** `.salary` 元素既无明文也无 iconfont 子节点
- **THEN** `salary` 字段返回空字符串，后续由 `_find_salary` 兜底或详情页补抓

### Requirement: 聊天发送兜底机制
系统 SHALL 在 send 按钮点击后追加一次 Enter 键兜底发送，覆盖"send 按钮点击概率性失效"的场景。

#### Scenario: send 按钮点击成功
- **WHEN** send 按钮点击后输入框已被 Boss 清空
- **THEN** 后续 Enter 键因输入框为空不会发送任何内容，无副作用

#### Scenario: send 按钮点击失败
- **WHEN** send 按钮点击后输入框文字仍存在（概率性事件）
- **THEN** 追加的 Enter 键将兜底把文字真正发送出去

## MODIFIED Requirements
### Requirement: 输入事件触发
原 `_send_message` 通过 DrissionPage `chat_input.input(ch)` 逐字输入但未触发原生 input 事件。修改为：在逐字输入完成后，对输入框 `dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text}))` 一次，提升 Boss 框架对内容变化的感知概率，从而激活 send 按钮。

### Requirement: 不修改函数返回值语义
`_send_message` 维持现有返回值语义（执行流程正常即返回 True，异常返回 False），不引入新的 disabled/清空校验，避免过度设计。

## REMOVED Requirements
无。
