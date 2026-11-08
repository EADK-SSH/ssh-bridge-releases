# share/tools

本目录随 ssh-bridge 打包，启动时同步到 `{work}/share/tools/`，供 Agent / 板端经 TFTP·NFS 拉取。

| 文件 | 用途 |
|------|------|
| `share_put.sh` | Linux/bash：大文件 HTTP 分片上传到 share |
| `share_put.ps1` | Windows：同上 |
| `lan_discover.py` | 扫局域网 ssh-bridge 主机与可发现板卡（stdout JSON） |

```bash
# 上传机（HTTP 能通工具机即可）
bash share_put.sh http://172.16.33.54:18071 ./rootfs.ext4 zk-hi3095/rootfs.ext4

# 发现局域网主机/板卡
python lan_discover.py
python lan_discover.py --self
python lan_discover.py --host 172.16.33.54
```
