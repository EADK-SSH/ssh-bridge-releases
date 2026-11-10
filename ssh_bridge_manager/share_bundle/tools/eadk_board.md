# EADK SSH 桥 — 板卡 CLI 手册（人机共用）

> 下载：`GET <Base>/share/tools/eadk_board.md`  
> 脚本：`GET <Base>/share/tools/eadk_board.py`（Python3 标准库，**Win/Linux 同一脚本**）  
> 目录：`share/tools/`（兼容 `/tftp/download?path=tools/...`）

**关系**：`/help` 原始 HTTP → `/agent/*` 高阶接口 → `eadk_board.py` 本地命令。  
**铁律**：板名与能力以运行时为准；每次先 `discover` / `scan`，只调用该板 `+` 能力。

下文示例默认：

```text
桥地址  http://10.168.21.236:18081
板名    ok3568
```

可先设环境变量少打字：

```bash
# Linux / Git Bash / macOS
export EADK_BASE='http://10.168.21.236:18081'
export EADK_BOARD='ok3568'

# Windows PowerShell
$env:EADK_BASE='http://10.168.21.236:18081'
$env:EADK_BOARD='ok3568'
```

运行方式（二选一）：

```bash
python eadk_board.py ...
py -3 eadk_board.py ...          # Windows 常见
```

---

## 1. 落地（第一次）

从桥的 share/TFTP 拉 CLI（Win 用 `curl.exe`）：

```bash
curl.exe -sS -OJ "http://172.16.33.54:18071/share/tools/eadk_board.py"
curl.exe -sS -OJ "http://172.16.33.54:18071/share/tools/eadk_board.md"

# Linux / Git Bash
curl -sS -OJ 'http://172.16.33.54:18071/share/tools/eadk_board.py'
curl -sS -OJ 'http://172.16.33.54:18071/share/tools/eadk_board.md'
```

```bash
python eadk_board.py discover
python eadk_board.py -B http://172.16.33.54:18071 scan
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 list
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 run 'uname -a'
```

环境变量：`EADK_BASE` `EADK_BOARD` `EADK_USER` `EADK_PASS` `EADK_HOST` `EADK_PUT_CHUNK`  
反馈：`EADK_FEEDBACK_HOOK` / `FEISHU_HOOK`  
依赖：仅标准库（见 `requirements.txt`，无需 pip）。

---

## 2. 能力规则（必读）

| 条件 | 影响 |
|------|------|
| `type=ssh` | 无 serial / uboot；查询键用 `link=` |
| `type=serial` | 查询键用 `board=` |
| `/actions` 有某按钮 | 对应 id 为 `+`，可用 `action <id>` 或同名子命令 |
| 无 reboot 按钮 | 仍可用 `soft-reboot`、`bootlog`、`send` |
| `connected=false` | 先修连接，勿盲 `run` |

```text
+ run           ← 可以调
+ enter_uboot   ← 该板 /actions 有此按钮
- upgrade       ← 该板没有，勿调
```

---

## 3. 指令执行逻辑（流程）

| 子命令 | 流程 |
|--------|------|
| `send` | `POST /command` → `sleep N`（默认 1s，`-w`）→ `GET /log` 增量 |
| `cmd` / `exec` | `POST /command`（`cmd; echo end_…`）→ 轮询 `GET /log` 直到标记 |
| `run` | `ensure`（可 `power_on`/`login`）→ 同 `cmd` |
| `bootlog` | `[timestamp]` → `POST /log/clear` → `reboot`/`soft-reboot` → 等待/`-p` → `GET /log` |
| `uboot` | 有 `enter_uboot`：`POST /action`；否则 `log/clear` → 重启 → `send_keys` → 等 `=>` |
| `action <id>` | `POST /action` `{board\|link, id}`（仅 list 里 `+` 的按钮） |
| `reboot` 等 | 同 `action` |
| `soft-reboot` | `POST /command` `reboot` |
| `feedback` | 飞书 webhook：`[本机名][bug\|建议\|功能] 陈述` |

**何时用 `send`**：U-Boot、login 前、或不保证在 shell 时。  
**何时用 `run`/`cmd`**：已在 Linux shell，需要干净截取命令输出时。

---

## 4. 子命令示例（逐条）

全局选项（多数命令可用）：

| 选项 | 含义 | 例 |
|------|------|----|
| `-B URL` | 桥 Base | `-B http://172.16.33.54:18071` |
| `-b 名` | 通道名 | `-b zk-hi3095` |
| `-t 秒` | 超时 / 启动等待 | `-t 120` |
| `-w 秒` | `send` 等待（默认 1） | `-w 2` |
| `-T` | bootlog 打开时间戳 | 见 `bootlog` |
| `-p PAT` | bootlog 完成特征 | `-p login:` |
| `-j` | JSON 输出 | `scan -j` |

已设 `EADK_BASE`/`EADK_BOARD` 时可省略 `-B`/`-b`。下列示例写全参数，便于复制。

### 3.1 discover — 局域网找桥

不用先知道 IP；广播找 ssh-bridge。

```bash
python eadk_board.py discover
python eadk_board.py discover --self
python eadk_board.py discover --host 10.168.21.236 -w 2000
python eadk_board.py discover --compact
```

输出含 `base_url`、`boards`，把 `base_url` 填进后面的 `-B`。

### 3.2 scan — 扫本桥全部（或指定）板

看连接、终端态、能力 `+/-`。**开场首选。**

```bash
python eadk_board.py -B http://10.168.21.236:18081 scan
python eadk_board.py -B http://10.168.21.236:18081 scan ok3568
python eadk_board.py -B http://10.168.21.236:18081 -j scan
```

退出码：`0` 正常；`1` 有 error；`2` 有断线。

### 3.3 list — 列通道 / 单板能力

```bash
python eadk_board.py -B http://10.168.21.236:18081 list
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 list
python eadk_board.py -B http://10.168.21.236:18081 list ok3568
```

### 3.4 state / health / probe / status — 看状态

```bash
# 全部通道一行摘要
python eadk_board.py -B http://10.168.21.236:18081 state

# 单板
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 state
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 health
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 probe
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 status
```

`probe` 常见结果：`shell` / `login` / `uboot` / `disconnected` / `unknown`。  
`health` 断线时 exit `2`。

### 4.5 run / cmd / exec / send — 在板子上执行命令

`run` = 先 `ensure`（可自动上电/登录）再执行，**日常 shell 首选**。  
`send` = 原始下发+等 N 秒+读 log，**U-Boot / 非 shell 首选**。

```bash
# shell
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 run 'uname -a'
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 -t 120 run 'make -j4'
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 cmd 'ls /'
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 exec 'hostname'

# 原始（U-Boot / 任意终端态）
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 send 'printenv'
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 -w 2 send 'help'
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 -w 0.5 send 'version'
```

勿对 Linux shell 下发 `exit`（会退回 `login:`）。

### 3.6 login / ensure — 进 shell

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 ensure
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 login
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 login root mypass
```

也可用环境变量：`EADK_USER` / `EADK_PASS`。

### 3.7 log / clear / download — 日志

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 log
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 log lines 50
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 log chars 4000
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 clear
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 download
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 download ok3568-boot.log
```

### 3.8 keys / ctrlc / write — 底层按键与写字节

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 ctrlc
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 write 'help\n'
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 keys ' ' 8 0.05
```

`keys`：字符、持续秒、间隔秒（抢 U-Boot 时常用空格）。

### 3.9 timestamp / reconnect / serial — 串口侧杂项

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 timestamp on
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 timestamp off
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 reconnect
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 serial open
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 serial close
```

`serial` 仅 serial 通道；先 `list` 确认是 `+serial`。

### 4.10 reboot / power_* / action / soft-reboot — 电源与板控按钮

先 `list` 看按钮。`/actions` 里有的 id（含 `enter_uboot` / `upgrade` / `enter_upgrade_mode`）都能调。

```bash
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 list
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 reboot
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 power_on
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 action enter_uboot
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 enter_uboot
# 无硬件 reboot 按钮时：
python eadk_board.py -B http://172.16.33.54:18071 -b ssh-link-96 soft-reboot
```

### 4.11 uboot / bootlog — 进 U-Boot / 抓启动日志

```bash
# 有 enter_uboot 按钮时 uboot ≡ action enter_uboot
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 uboot

# bootlog: log/clear → 重启 → 等待 → GET /log
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 -t 120 bootlog
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 -t 180 -T -p 'login:' bootlog
```

### 3.12 put — 大文件分片上传到 share

Win/Linux 同命令（替代旧 `share_put.sh` / `.ps1`）。

```bash
python eadk_board.py -B http://10.168.21.236:18081 put ./uImage ok3568/uImage
python eadk_board.py -B http://10.168.21.236:18081 put ./rootfs.ext4 ok3568/rootfs.ext4
python eadk_board.py -B http://10.168.21.236:18081 put ./rootfs.ext4 ok3568/rootfs.ext4 16777216
```

第三个参数为分片字节（默认 2MiB，可用 `EADK_PUT_CHUNK`）。上传后会打印远端 MD5。

### 3.13 help-url — 打印该板 /help 链接

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 help-url
```

### 4.14 feedback / suggest / bug — 建议与缺陷

```bash
python eadk_board.py feedback bug '串口 reconnect 后 log 为空'
python eadk_board.py feedback 建议 '希望 bootlog 支持自定义等待'
python eadk_board.py suggest '希望…'
python eadk_board.py bug '现象与期望…'
```

正文格式：`[本机名][bug|建议|功能] 陈述`（本机名，不是板名；不要写「问题属性」）。

### 3.15 help — 本机帮助

```bash
python eadk_board.py help
python eadk_board.py help caps
python eadk_board.py help run
python eadk_board.py help put
python eadk_board.py help discover
```

---

## 4. 推荐工作流（复制即用）

```bash
python eadk_board.py discover
python eadk_board.py -B http://10.168.21.236:18081 scan
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 list
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 health
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'uname -a'
python eadk_board.py -B http://10.168.21.236:18081 put ./Image ok3568/Image
```

| 组合 | 行为 |
|------|------|
| `run` | `ensure`（可自动上电）+ 阻塞执行 |
| `bootlog` | clear → 重启 → 等到 `-p` → 打日志 |
| `uboot` | clear → 重启 → 抢键 → 等 `=>` |
| `put` | 分片 `POST /tftp/upload` + 查 MD5 |

---

## 5. 错误对照

| 现象 | 处理 |
|------|------|
| `通道不存在` | 先 `scan`/`list` 核对板名 |
| `未连接` exit 2 | `reconnect` / `serial open`；查线/SSH |
| `不支持: xxx` | 该板 `-` 能力，换命令 |
| `当前在 login/password` | 用 `run` 或 `login` |
| `当前在 U-Boot` | 不能 `cmd`；先启动或继续 uboot |
| `timeout` | 加大 `-t`；或 `ctrlc` / `reboot` |
| HTTP `423` | 其它 Agent 持有 `/lock` |
| `网络/服务不可达` | 检查 `-B` / 桥是否在跑；可先 `discover` |

成功信息走 stdout，`error: …` 走 stderr。

---

## 6. 无 Python 时（原始 HTTP）

```bash
curl -s 'http://10.168.21.236:18081/agent/scan'
curl -s 'http://10.168.21.236:18081/agent/probe?board=ok3568'
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"board":"ok3568","command":"uname -a","timeout":60}' \
  'http://10.168.21.236:18081/agent/exec'
```

| CLI | 对应 |
|-----|------|
| `discover` | UDP `EADK1@18071` / `SSHBM1@38472` |
| `scan` / `state` | `/agent/scan` `/agent/state` |
| `put` | `POST /tftp/upload` + `GET /tftp/md5` |
| `run` / `exec` | `/agent/exec` |
| `reboot` | `POST /action` `id=reboot` |
| `feedback` | 飞书 webhook |
