# share/tools

本目录随 ssh-bridge 打包，启动时同步到 `{work}/share/tools/`，供 Agent / 板端经 TFTP·NFS 拉取。

| 文件 | 用途 |
|------|------|
| `eadk_board.py` | **推荐**：跨 Win/Linux 统一 CLI（控板 / `put` 上传 / `discover` 发现） |
| `eadk_board.md` | CLI 手册 |
| `requirements.txt` | 依赖说明（标准库，无需 pip） |
| `share_put.sh` / `share_put.ps1` | 旧分片上传脚本（已合入 `eadk_board.py put`） |
| `lan_discover.py` | 旧局域网发现（已合入 `eadk_board.py discover`） |

```bash
# 下载（Win/Linux 同一脚本）
curl -sS -OJ "http://HOST:18071/tftp/download?path=tools/eadk_board.py"

# 发现局域网主机/板卡
python eadk_board.py discover
python eadk_board.py discover --self

# 控板
python eadk_board.py -B http://HOST:18071 scan
python eadk_board.py -B http://HOST:18071 -b zk-hi3095 run 'uname -a'

# 大文件分片上传
python eadk_board.py -B http://HOST:18071 put ./rootfs.ext4 zk-hi3095/rootfs.ext4
```
