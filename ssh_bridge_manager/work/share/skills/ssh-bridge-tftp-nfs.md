# TFTP / NFS

与 share 同根。网页 `/tftp` `/nfs` `/config` 可开关。  
Agent：**开启**用 `enable:true`（TFTP 常加 `bind_ip`）；**不要随意 `enable:false`**。Tunnel 无 Agent 接口。

```bash
curl -s http://HOST:18071/tftp/status
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"enable":true,"bind_ip":"192.168.137.1"}' http://HOST:18071/tftp/config
curl -s http://HOST:18071/nfs/status
curl -s -X POST -H 'Content-Type: application/json' -d '{"enable":true,"export_alias":"/share"}' http://HOST:18071/nfs/config
```

板端（以 `/nfs/status` 的 `mount_hint` 为准）：  
`mount -t nfs -o nolock,vers=3,tcp 192.168.137.1:/share /mnt/share`

- Windows：内嵌 WinNFSd  
- Linux：内核 `nfs-server` + `/share` bind；若 `tftpd-hpa` 占 UDP 69，开 TFTP 时会停掉它  
