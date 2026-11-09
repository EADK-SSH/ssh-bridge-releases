# EADK SSH 桥 — 板卡 CLI 手册（人机共用）

> 下载：`GET <Base>/tftp/download?path=tools/eadk_board.md`  
> 脚本：`GET <Base>/tftp/download?path=tools/eadk_board.py`（Python3 标准库，**Win/Linux 同一脚本**）  
> 目录：`share/tools/`

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

```bash
curl -sS -OJ 'http://10.168.21.236:18081/tftp/download?path=tools/eadk_board.py'
curl -sS -OJ 'http://10.168.21.236:18081/tftp/download?path=tools/eadk_board.md'

python eadk_board.py discover
python eadk_board.py -B http://10.168.21.236:18081 scan
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 list
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'uname -a'
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
| 无某按钮 | 对应 `reboot` / `power_on` / `power_off` 为 `-` |
| 无 reboot 按钮 | 仍可用 `soft-reboot`、`bootlog` |
| `connected=false` | 先修连接，勿盲 `run` |

```text
+ run      ← 可以调
- uboot    ← 不要调
```

---

## 3. 子命令示例（逐条）

全局选项（多数命令可用）：

| 选项 | 含义 | 例 |
|------|------|----|
| `-B URL` | 桥 Base | `-B http://10.168.21.236:18081` |
| `-b 名` | 通道名 | `-b ok3568` |
| `-t 秒` | 超时 / 启动等待 | `-t 120` |
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

### 3.5 run / cmd / exec — 在板子上执行命令

`run` = 先 `ensure`（可自动上电/登录）再执行，**日常首选**。

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'uname -a'
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'cat /proc/version'
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 120 run 'make -j4'

# 已确认在 shell 时，可直接 cmd / exec
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 cmd 'ls /'
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 exec 'hostname'
```

勿对板下发 `exit`（会退回 `login:`）。

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

### 3.10 reboot / power_on / power_off / soft-reboot — 电源与重启

先 `list` 看该板是否 `+reboot` / `+power_on` / `+power_off`。

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 reboot
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 power_on
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 power_off

# 无硬件 reboot 按钮时：软重启
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 soft-reboot
```

### 3.11 uboot / bootlog — 进 U-Boot / 抓启动日志

仅 serial 且可重启时；先确认 `+uboot` / `+bootlog`。

```bash
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 90 uboot

python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 120 bootlog
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 120 -T bootlog
python eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 180 -p 'login:' bootlog
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

### 3.14 feedback / suggest / bug — 建议与缺陷

```bash
python eadk_board.py feedback bug '串口 reconnect 后 log 为空'
python eadk_board.py feedback 建议 '希望 bootlog 支持自定义等待'
python eadk_board.py feedback 功能 '希望一键导出全部板状态'
python eadk_board.py suggest '希望…'
python eadk_board.py bug '现象与期望…'
python eadk_board.py -b ok3568 feedback bug '该板 probe 误判'
```

正文格式：`[主机或板名][问题属性：bug|建议|功能] 陈述`。

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
