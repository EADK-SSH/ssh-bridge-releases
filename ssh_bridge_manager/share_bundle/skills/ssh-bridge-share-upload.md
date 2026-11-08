# Skill: HTTP 上传到 share

## 传文件优先级（约定）

| 角色 | 优先 | 说明 |
|------|------|------|
| **Agent / 主机** | HTTP → share | `share_put` / `POST /tftp/upload` / `POST /share/upload` |
| **开发板读共享** | NFS 挂载 | `mount -t nfs HOST:/share /mnt/share` |
| **开发板拉单文件** | TFTP → 再 `wget` | U-Boot/`tftp`；Linux 下可 `wget http://HOST:18071/tftp/download?...` |
| 缺工具且有网 | `dnf`/`apt` 安装 | 如 `tftp-hpa`、`nfs-utils`、`wget` |

大文件（推荐）：
```bash
bash /mnt/share/tools/share_put.sh http://HOST:18071 ./file.bin ok3562/file.bin
```
小文件：
```bash
curl -X POST --data-binary @./uImage "http://HOST:18071/tftp/upload?path=ok3562/uImage"
# 分片：&offset=字节
```
校验：`curl -s "http://HOST:18071/tftp/md5?path=ok3562/uImage"`  
网页：`GET /share`；终端右键菜单可上传到板目录 / common（带进度条）。
反馈/建议通道设计见仓库 `docs/用户反馈与建议通道.md`。
