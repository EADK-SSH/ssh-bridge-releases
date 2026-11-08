# Skill: zk-hi3095 NFS 烧写

1. 进系统（或 ramdisk）后挂载：
```
mkdir -p /mnt/share
mount -t nfs -o nolock,vers=3,tcp 192.168.137.1:/share /mnt/share
ls /mnt/share/zk-hi3095/
```
2. `dd` 对应分区（按板卡分区表）。
3. U-Boot TFTP 受限时优先 NFS 拉镜像；ARP 不通先清主机邻居表。
