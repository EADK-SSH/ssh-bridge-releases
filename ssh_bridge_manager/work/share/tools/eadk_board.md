# EADK SSH 桥 — 板卡 CLI 手册（人机共用）

> 下载：`GET <Base>/share/tools/eadk_board.md`  
> 脚本：`GET <Base>/share/tools/eadk_board.py`（Python3 标准库，**Win/Linux 同一脚本**）  
> 目录：`share/tools/`（兼容 `/tftp/download?path=tools/...`）

**关系**：`GET /help` 原始 HTTP（权威）→ `/agent/*` 高阶 → `eadk_board.py` 本地封装。  
**铁律**：板名与能力以运行时为准；每次先 `discover` / `scan`，只调用该板 `+` 能力。

---

## 0. 网络拓扑（Agent 必读，勿混）

本工具常跨两张网：

| 名称 | 配置键 | 谁在用 | 典型用途 |
|------|--------|--------|----------|
| **内网 / 板侧** | `board_net.cidr` + `host_ip` | 板子 ↔ 桥的板网卡 | U-Boot `serverip`、TFTP、NFS、`tcp_forward`→板 `sshd` |
| **外网 / Agent 侧** | `agent_net.cidr` + `host_ip` | Agent ↔ 桥的 HTTP | `EADK_BASE`、网页、`/help` 里的「Agent 外网 Base」 |

回退规则（空串=`自动`；配置页用下拉，不要手填）：

- `tftp.bind_ip` **空** → `board_net.host_ip` → 本机落在 `board_net.cidr` 的地址 → 再 prefer
- `tcp_forward` 映射 **只用** `board_net.cidr`（与 Tunnel 公网 28xxx、入站 2222 无关）
- Agent 选 Base：同机 `http://127.0.0.1:<http_port>` → 否则 `agent_net.host_ip` → 再不通用 Tunnel
- 权威细节：设计文档 §2.15；运行时看 `GET /agent/scan` 的 `*_resolved`

**三套「SSH」不要混**：

| 能力 | 是什么 | 不是什么 |
|------|--------|----------|
| `inbound_ssh` / 串口 `/command` | 通道 ring（串口或 SSH-Link PTY） | 不是板子 `sshd:22` |
| `tcp_forward` | 本机 `port_base+末字节` → 板侧 sshd | 仅当**没有**系统 `~/.ssh/config` LocalForward 时再用 |
| Tunnel `map_inbound_ssh` | 把入站口映到公网 **28xxx** | 不是板网 22xxx 转发 |

`GET /agent/scan` 返回 `board_net` / `agent_net` / `nets_hint`；`GET /help` 文首有双网段表。

下文示例（请换成你环境的 **Agent 外网** Base）：

```text
桥 Base  http://10.168.21.236:18081   # Agent 侧，不是板网 192.168.137.x
板名     ok3568
```

```bash
# Linux / Git Bash / macOS
export EADK_BASE='http://10.168.21.236:18081'
export EADK_BOARD='ok3568'

# Windows PowerShell
$env:EADK_BASE='http://10.168.21.236:18081'
$env:EADK_BOARD='ok3568'
```

```bash
python eadk_board.py ...
py -3 eadk_board.py ...          # Windows 常见
```

---

## 1. 落地（第一次）

从桥的 share 拉 CLI（Base = **Agent 外网** 或环路；Win 用 `curl.exe`）：

```bash
curl.exe -sS -OJ "$EADK_BASE/share/tools/eadk_board.py"
curl.exe -sS -OJ "$EADK_BASE/share/tools/eadk_board.md"
# 或先 discover 再填 Base
python eadk_board.py discover
python eadk_board.py -B http://10.168.21.236:18081 scan
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 list
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'uname -a'
```

环境变量：`EADK_BASE` `EADK_BOARD` `EADK_USER` `EADK_PASS` `EADK_HOST`（仅反馈本机名）`EADK_PUT_CHUNK`  
反馈：`EADK_FEEDBACK_HOOK` / `FEISHU_HOOK`  
依赖：仅标准库（见 `requirements.txt`，无需 pip）。

---

## 2. 能力规则（必读）

| 条件 | 影响 |
|------|------|
| `type=ssh` / `ssh-link` | 无 serial/uboot；查询键用 **`link=`**（不是板侧 sshd，是 SSH-Link 中继） |
| `type=serial` | 查询键用 **`board=`** |
| `/actions` 有某按钮 | 对应 id 为 `+`，可用 `action <id>` 或同名子命令 |
| 无 reboot 按钮 | 仍可用 `soft-reboot`、`bootlog`、`send` / `command` |
| `connected=false` | 先修连接，勿盲 `run` |

```text
+ run           ← 可以调
+ enter_uboot   ← 该板 /actions 有此按钮
- upgrade       ← 该板没有，勿调
```

---

## 3. 指令执行逻辑（流程）

`/command` = **异步**写通道（串口/SSH-Link ring），**立刻**返回；不是传统 SSH，也不等输出。

| 子命令 | 流程 | 何时用 |
|--------|------|--------|
| `command` | 仅 `POST /command` → queued | 只要下发、自己再 sleep/log |
| `send` | `POST /command` → sleep N（默认 1，`-w`）→ `GET /log` 增量 | U-Boot / 非 shell |
| `cmd` | 标记阻塞（可 `/agent/exec`） | 已在 Linux shell |
| `run` | `ensure`（可上电/login）→ 同 `cmd` | 日常 shell **首选** |
| `login` | 板 `target_*` → `login_credentials` → 写回 persist | 进 shell 前 |
| `bootlog` | clear → reboot → 等待 → log | 抓启动 |
| `uboot` / `action` | 见下 | 按钮或抢键 |
| `feedback` | 飞书 `[本机名][bug\|建议\|功能]` | 反馈 |
| `to-board` | 见 §3.12b：scp-pull → scp-push → share | 主机工程文件→板 **首选** |

**已移除对外 `exec` 别名**；阻塞执行用 `cmd`/`run` 或 `POST /agent/exec`。  
送文件到板：**优先本 CLI `to-board`**；无 Python 时按 `GET /help` §3.4 原始 HTTP。

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

### 4.5 run / cmd / send / command — 在通道上执行（非板侧 sshd）

`run` = 先 `ensure`（可自动上电/登录）再执行，**日常 shell 首选**。  
`cmd` = 已在 shell 时阻塞执行（内部可走 `/agent/exec`）。  
`send` = `command` + 短等 + 读 log，**U-Boot / 非 shell 首选**。  
`command` = 纯异步 `POST /command`（不读 log）。

```bash
# 自动 ensure 后跑 shell 命令
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'uname -a'
# 长任务加大超时
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 120 run 'make -j4'
# 已在 shell 时直接 cmd
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 cmd 'ls /'
# 纯异步
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 command 'uname -a'

# U-Boot / 非 shell：原始下发
python eadk_board.py -B http://172.16.33.54:18071 -b zk-hi3095 send 'printenv'
# 等 2 秒再读 log
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

### 3.12 put / ls / mkdir / md5 / rm — share 文件

`put`：分片上传 + **本地/远端 MD5 校验**；失败自动重传；`-t` 总超时默认 **3600s**（也可用 `EADK_PUT_TIMEOUT`）。

```bash
# 列目录 / 建目录
python eadk_board.py -B http://10.168.21.236:18081 ls
python eadk_board.py -B http://10.168.21.236:18081 ls tools
python eadk_board.py -B http://10.168.21.236:18081 mkdir ok3568/out
# 上传（校验 MD5；默认超时 1 小时）
python eadk_board.py -B http://10.168.21.236:18081 put ./uImage ok3568/uImage
python eadk_board.py -B http://10.168.21.236:18081 -t 7200 put ./rootfs.ext4 ok3568/rootfs.ext4
# 自定义分片字节（第 3 参数，默认 2MiB / $EADK_PUT_CHUNK）
python eadk_board.py -B http://10.168.21.236:18081 put ./rootfs.ext4 ok3568/rootfs.ext4 16777216
# 校验 / 删除
python eadk_board.py -B http://10.168.21.236:18081 md5 ok3568/uImage
python eadk_board.py -B http://10.168.21.236:18081 rm ok3568/old.bin
```

### 3.12b to-board — 主机工程文件送到板（首选）

阶梯（`--method=auto`）：① 板 ping 通板网主机 → 板 `scp` 拉；② 开 `tcp_forward` → 主机 `scp` 推；③ `put` share → 板 tftp/http/nfs 拉。

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 to-board ./Image /tmp/Image
python eadk_board.py -b ok3568 to-board ./a.bin /tmp/a.bin --method=share
python eadk_board.py -b ok3568 to-board ./a.bin --board-ip=192.168.137.100 --method=scp-push
```

密钥：拉=私钥在板、公钥在主机；推=私钥在主机、公钥在板 `authorized_keys`。无 CLI 时见 `GET /help` §3.4。

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
# 找桥 → 扫板 → 看能力 → 健康 → 跑命令 → 上传
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
| `uboot` | 有按钮则 `action enter_uboot`；否则 clear→重启→抢键 |
| `put` | 分片上传 + MD5 校验/重传（默认超时 1h） |
| `to-board` | 主机文件→板：scp-pull / tcp_forward 推 / share |
| `ls/mkdir/md5/rm` | share 列目录/建目录/校验/删除 |

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
| `put` | `POST /tftp/upload` + `GET /tftp/md5`（校验/重传） |
| `to-board` | `/agent/exec` ping+scp；`/tcp_forward/*`+本机 scp；或 put+板拉 |
| `ls/mkdir/md5/rm` | `/tftp/files` `/tftp/mkdir` `/tftp/md5` `/tftp/delete` |
| `run` / `cmd` | `/agent/exec` 或 `/command`+标记 |
| `reboot` | `POST /action` `id=reboot` |
| `feedback` | 飞书 webhook |
