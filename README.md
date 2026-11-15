# Market Holidays

独立 Google Calendar 订阅：Cboe 美国期权常规交易时段（RTH）休市及提前收盘；针对 SPXW 0DTE。全部为全天标记，提前收盘时间写在标题，方便置顶显示且不占据盘中时间格。

- `market-holidays.ics`：已附经官方日历核对的 2026、2027 年初始数据，可上传后立即订阅。
- `holidays.json`：最近一次通过校验的官方数据快照。
- `market_holidays.py`：从 Cboe 官方页面更新，失败时不发布，保留旧数据。
- `.github/workflows/update-calendar.yml`：每日 UTC 06:23 检查，支持手动运行，无需 API key。

## GitHub 安装

1. 创建公开仓库 `market-holidays`（公开仓库可被查看及 Fork）。
2. 上传所有项目文件到 main，包含隐藏目录 `.github`。若网页未上传隐藏目录，手动创建 `.github/workflows/update-calendar.yml` 并粘贴内容。
3. Actions → Update Market Holidays → Run workflow（main），核对 Generate Market Holidays 和 Publish calendar。
4. 将 `https://raw.githubusercontent.com/你的用户名/market-holidays/main/market-holidays.ics` 通过网址添加到 Google Calendar（不是导入）。Google 刷新可能延迟。

本地测试：`pip install -r requirements.txt`，`python market_holidays.py --offline`；真实抓取：`python market_holidays.py`。

## 范围与限制

初始 23 个事件（2026、2027），未来年份在 Cboe 发布后自动加入。休市仅指 RTH，不代表 SPX 全球交易时段或 ES 全天停市；ES 和 ES 期权另查 CME，不能直接使用本日历控制自动下单或撤单。临时停市等以交易所及券商实时公告为准。脚本不会修改其他日历的重复交易时间。

官方来源：
- https://www.cboe.com/about/hours/us-options/
- https://www.cboe.com/tradable-products/sp-500/spx-options/spx-specifications
- https://www.nyse.com/trade/hours-calendars
- https://www.cmegroup.com/trading-hours.html
