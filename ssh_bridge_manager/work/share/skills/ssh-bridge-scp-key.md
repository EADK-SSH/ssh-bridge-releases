# Skill: 板 ↔ Agent 主机免密 SCP（含可选跳板）

目标：不用交互密码，在 **板** 与 **跑 Agent/工程的主机** 之间 `scp`/`ssh`。  
本工具通道 `/command` **不是**板 `sshd`；直连板 `sshd` 用系统网或 `tcp_forward`。

## 0. 先分清方向

| 方向 | 谁主动 | 私钥放哪 | 公钥放哪 |
|------|--------|----------|----------|
| **板拉主机**（scp-pull / `to-board` 第 1 步） | 板 | **板** `~/.ssh/id_ed25519` | **主机**该用户 `~/.ssh/authorized_keys` |
| **主机推板**（scp-push / `to-board` 第 2 步） | 主机 | **主机** | **板** `~/.ssh/authorized_keys` |

两边都配好即可互通；至少配你常用的那一方向。

## 1. 主机推板（最常见）

在 **Agent 主机**：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_eadk_board -N ""
# 把公钥拷到板（首次可用串口/SSH-Link 通道写入，或临时密码一次）
PUB=$(cat ~/.ssh/id_eadk_board.pub)
```

经本工具通道写入板（已在 shell）：

```bash
python eadk_board.py -B http://桥:18071 -b 板名 run \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$PUB' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

若板在板网、主机不在同一网：开 `tcp_forward`（或系统 LocalForward），再：

```bash
# 查端口：GET /tcp_forward/map?ip=<板IP>  → 例 192.168.0.100 → port_base+100
scp -i ~/.ssh/id_eadk_board -P <port> -o BatchMode=yes ./Image root@127.0.0.1:/tmp/Image
```

CLI：`eadk_board.py -b 板名 to-board ./Image /tmp/Image --method=scp-push`

## 2. 板拉主机

在 **主机** 把板的公钥写入 `authorized_keys`（或主机生成密钥对，**私钥 scp 到板**，公钥留主机——少见）。

板上：

```bash
scp -o BatchMode=yes -o StrictHostKeyChecking=no \
  user@板网主机IP:/path/on/host/Image /tmp/Image
```

主机 IP = `GET /agent/scan` → `board_net.host_ip_resolved`（板网侧，不是 Agent 外网）。

## 3. 可选：SSH 跳板（ProxyJump / ProxyCommand）

Agent 主机到板要先经跳板时，在 **Agent 主机** `~/.ssh/config`：

```sshconfig
Host jump
    HostName 172.16.36.143
    User Huawei
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

Host board-i5
    HostName 192.168.0.100
    User root
    ProxyJump jump
    IdentityFile ~/.ssh/id_eadk_board
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
```

免密：跳板与目标都用密钥；**不要**把密码写进 config。  
（旧写法 `ProxyCommand sshpass -p '...' ssh -W %h:%p ...` 仅临时调试，勿给 Agent 当常态。）

然后：`scp board-i5:/tmp/x .` / `ssh board-i5`。

有跳板时 **优先系统 ProxyJump**，不必再开本工具 `tcp_forward`。无跳板、主机又不在板网 → 再用 `/tcp_forward/*`（公式：`本机端口 = port_base + 板IP末字节` → `板IP:22`）。

## 4. 自检

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 board-i5 'echo ok'
# 或经 tcp_forward:
ssh -o BatchMode=yes -p <port> root@127.0.0.1 'echo ok'
```

失败：查 `authorized_keys` 权限（家目录不组写、`.ssh` 700、文件 600）、用户是否对、`tcp_forward/map` 端口是否对。

## 5. 与 `to-board` 关系

`eadk_board.py to-board` 自动：ping 通则板拉 → 否则 tcp_forward 推 → 再不行走 share。  
本 skill 把前两步的密钥一次配好，之后 `to-board` / 手工 `scp` 都免密。
