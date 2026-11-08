# Skill: ok3562 ramdisk 拿交互 shell

buildroot 默认 getty 在 `ttyAMA1`，板子控制台是 `ttyFIQ0`，会刷 `can't open /dev/ttyAMA1`。

用 `rdinit=/bin/sh`：
```
setenv bootargs console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000 rdinit=/bin/sh
booti 0x20000000 0x0a200000:SIZE 0x1f000000
```
见到 `~ #` 后先挂虚拟文件系统（否则无 `/dev/mmcblk*`）：
```
mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs devtmpfs /dev || { mount -t tmpfs tmpfs /dev; mdev -s; }
```
再配网：
```
ip link set eth0 up
ip addr add 192.168.137.100/24 dev eth0
# ping 可能被主机防火墙挡 ICMP；NFS/TCP 仍可用
mount -t nfs -o nolock,vers=3,tcp 192.168.137.1:/share /mnt/share
```
