# Skill: zk-hi3095 TFTP + ramdisk

```
setenv serverip 192.168.137.1; setenv ipaddr 192.168.137.30
tftpboot 0x98400000 zk-hi3095/zk-hi3095.dtb
tftpboot 0x9d280000 zk-hi3095/rootfs.cpio.gz
tftpboot 0x98480000 zk-hi3095/uImage
bootm 0x98480000 0x9d280000:SIZE 0x98400000
```
SIZE 为 `rootfs.cpio.gz` 字节数。U-Boot ARP 失败时查网线与 `ethaddr`。
