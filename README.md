# Harbor Invest · FTEC5510

前端、中台和 AI 助手共用仓库。各模块原有的入口和文档都保留在各自目录。

| 模块 | 目录 | 导入版本 |
| --- | --- | --- |
| 前端 | [`frontend/`](frontend/) | [LeoLIU1233/5510-UI `6366904`](https://github.com/LeoLIU1233/5510-UI/tree/63669046ecabf3415b2e7e43efd964ffbddd2024) |
| 中台 | [`middle-office/`](middle-office/) | [ALLE77-maker/ftec5510-middle-office `0414afc`](https://github.com/ALLE77-maker/ftec5510-middle-office/tree/0414afc5e6aada231c4def932a2de394d7469b3c) |
| AI 助手 | [`ai/`](ai/) | [phillipyang62/crypto-ai-mvp `bcfd222`](https://github.com/phillipyang62/crypto-ai-mvp/tree/bcfd2220e3c3ab1f47deb983fb3869fa692542f3) |

## 一键启动

需要 Python 3.10 或更高版本，无需安装第三方 Python 依赖。

```shell
python run_demo.py
python -X utf8 check_integration.py
```

第一条命令启动三个 HTTP 服务，浏览器打开终端打印的本机地址，通常为 `http://127.0.0.1:5510/`。使用固定的模拟账户、两家模拟报价来源及预置问卷，退出后清理临时数据库。第二条命令独立检查接口，可在另一终端运行。

模型默认用模板。用 `python run_demo.py --ollama-model <本机已安装的模型>` 接 Ollama。需要 DeepSeek 时，在当前进程环境设置 `DEEPSEEK_API_KEY` 后加 `--enable-deepseek`。同时启用时，先尝试 Ollama；远程调用沿用 AI 模块对账户数据的限制。DeepSeek 请求使用该 Key 的 API 额度。

分别启动时，在 [`middle-office/`](middle-office/) 运行 `python -m middle_office`，在 [`ai/`](ai/) 运行 `python -m ai_mvp`，再运行 `python frontend/UI.py --integrated --no-browser`。从进程环境读取 [`.env.example`](.env.example) 中列出的变量。`MO_AI_READ_TOKEN` 与 `MO_API_TOKEN` 取不同值，`AI_MVP_MARKET_TOKEN` 和 `AI_MVP_TRADING_TOKEN` 使用 `MO_AI_READ_TOKEN`。先在中台创建 `HARBOR_DEMO_USER` 对应账户，并写入报价；启动器的模拟样本只在一键演示中自动写入。

## 已接通的 API

- 浏览器 → 中台：`GET /api/market/venues?symbol=BTC%2FUSDT&quantity=0.01&side=buy` 展示币种、计价币、价格、报价来源及时间。`GET /api/account/summary` 读取同一份中台账户快照，含余额、持仓和挂单。
- 问卷结果 → 中台 → AI：`PUT /api/profile` 接收现有问卷的 `assessment`，包含 `FC/RA/KE/BD/OC`、RAI、风险等级与产品上限。中台校验并保存，AI 持久化画像。`GET /api/profile` 返回 AI 画像。写入 AI 暂时失败时，下次读画像或聊天会重新同步中台已保存的结果。
- 浏览器 → AI → 中台：`POST /api/assistant/chat` 发送问题，AI 通过中台只读 API 查参考报价、持仓与挂单。`GET /api/risk` 输出 AI 风险统计。可在聊天里输入「查一下比特币报价、我的持仓和挂单」。
- 浏览器 → 中台预览与模拟下单：`POST /api/orders/preview` 返回估算与有效期 60 秒的 `preview_id`。`POST /api/orders` 用 `{"preview_id":"..."}` 确认，中台在写账时复核。有效期内重交同一 ID 返回同一订单。`GET /api/orders/{order_id}` 查询状态，`POST /api/orders/{order_id}/cancel` 撤销挂单。

## 联调边界

- 模拟账户只供本机访问。真实登录、多人账户权限、外部行情源和真实交易所成交需要另行接入。模拟报价按买卖价全量成交，订单簿和滑点暂无数据。
- 前端用中台的多源双边报价比价。AI 每个交易对读取一条参考价，暂时无法比较不同来源的费用。AI 风险统计与中台账本估值使用各自接口与口径，不能逐项对账。
- 原型的历史走势、报表导出、资金划转和自选管理没有接入服务。问卷页面或实际问卷系统通过 `PUT /api/profile` 接入，当前提供样例数据。
- 默认 HTTP 联调验证的是模板回答和三模块数据流，Ollama 与 DeepSeek 的实际生成需在对应模型可用时分别验证。

协作约定见 [CLAUDE.md](CLAUDE.md)。
