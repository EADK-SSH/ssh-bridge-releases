# Skill: ok3562 ramdisk 内 NFS 烧写

根分区：`/dev/mmcblk0p8`，PARTUUID=`614e0000-0000`。

```bash
ip link set end0 up 2>/dev/null; ip link set eth0 up 2>/dev/null
ip addr add 192.168.137.100/24 dev end0 2>/dev/null || ip addr add 192.168.137.100/24 dev eth0
mkdir -p /mnt/share /mnt/root
mount -t nfs -o nolock,vers=3,tcp 192.168.137.1:/share /mnt/share
ls -lh /mnt/share/ok3562/
dd if=/mnt/share/ok3562/qsemos-image-noesis3562-20261031050807.rootfs.ext4 of=/dev/mmcblk0p8 bs=4M status=progress
sync
mount /dev/mmcblk0p8 /mnt/root
mkdir -p /mnt/root/boot
cp /mnt/share/ok3562/Image /mnt/root/boot/
cp /mnt/share/ok3562/noesis-rk3562-v8.dtb /mnt/root/boot/
sync; umount /mnt/root
```

U-Boot：
```
setenv bootargs console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000 root=PARTUUID=614e0000-0000 rw rootwait storagemedia=emmc
setenv bootcmd 'ext4load mmc 0:8 0x20000000 /boot/Image; ext4load mmc 0:8 0x1f000000 /boot/noesis-rk3562-v8.dtb; booti 0x20000000 - 0x1f000000'
saveenv; boot
```
登录：`root` / `Ncti2023`
