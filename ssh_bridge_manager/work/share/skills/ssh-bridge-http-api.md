# Skill: ssh-bridge HTTP API 全表

BASE=`http://HOST:18071`  
人类/Agent 完整说明：`GET /help`；机器可读：`GET /api/help`。

## 通道
- `GET /status` / `GET /status?board=`（SSH 用 `link=`）
- `GET /boards` · `POST /boards`（`op=add|delete|enable|set_*`，成功后自动热同步）· `POST /reload`（仅手工改 config 文件后）
- `POST /command` 异步 · `POST /command_block` 阻塞（`timeout`）
- `POST /write` 原始字节 · `POST /send_keys` · `POST /reconnect`
- `POST /log/clear` · `GET /log?board=&lines=` · `GET /log/download`
- `POST /lock` / `POST /unlock`（头 `X-Agent-Session`）
- `GET /actions?board=` · `POST /action`（`id` 以 actions 列表为准）
- `POST /serial/open|close|break` · `POST /channel/configure`

## share / TFTP / NFS
- 同根目录（默认 `{work}/share`）；U-Boot `serverip` = TFTP `bind_ip`
- `GET|POST /tftp/config`（POST 可写 enable/port/bind_ip/…；**惯例 Agent 只开不关**）
- `GET /tftp/status` · `GET /tftp/ips` · `GET /tftp/files` · `POST /tftp/mkdir` · `POST /tftp/delete`
- `POST /tftp/upload?path=&offset=`（body 原始字节；整文件 md5 用 `?md5=1` 或 `GET /tftp/md5`）
- `GET /tftp/download` · `GET /share` · `POST /share/upload?dir=`（multipart）
- `GET|POST /nfs/config`（POST 可写 enable/export_alias/uid/gid；**惯例 Agent 只开不关**）· `GET /nfs/status`
- 大文件：`tools/share_put.sh` 或 `share/tools/share_put.sh $BASE 本地文件 板名/远程名`
- Tunnel：仅网页，无 Agent 接口

## 其它
- `GET /help` Agent 手册 · `GET /relay` · `GET /config`（Tunnel 配置页非 Agent）
