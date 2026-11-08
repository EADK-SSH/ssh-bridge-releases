# Skill: 拉取本目录 skills

主机 share 已导出：
- NFS：`192.168.137.1:/share/skills/`
- HTTP：`http://HOST:18071/tftp/download?path=skills/<name>.md`
- TFTP：把文件放到 `share/` 根后按短文件名拉

板端：
```bash
mkdir -p /mnt/share /tmp/skills
mount -t nfs -o nolock,vers=3,tcp 192.168.137.1:/share /mnt/share
cp -a /mnt/share/skills /tmp/
```
Agent：优先读 `/mnt/share/skills/*.md` 再操作板卡。
