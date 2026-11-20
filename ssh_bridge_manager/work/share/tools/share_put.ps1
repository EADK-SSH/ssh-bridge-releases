# 类似 wget，反向上传到 ssh-bridge share（自动分片）
# 用法: .\tools\share_put.ps1 http://127.0.0.1:18071 .\rootfs.ext4 ok3562/rootfs.ext4
param(
  [Parameter(Mandatory=$true)][string]$Base,
  [Parameter(Mandatory=$true)][string]$Local,
  [Parameter(Mandatory=$true)][string]$Path,
  [int]$Chunk = 2MB
)
$Base = $Base.TrimEnd('/')
$fs = [IO.File]::OpenRead((Resolve-Path $Local))
try {
  $buf = New-Object byte[] $Chunk
  $off = [long]0
  $total = $fs.Length
  Write-Host "upload $Local ($total) -> $Base path=$Path"
  while (($n = $fs.Read($buf, 0, $buf.Length)) -gt 0) {
    $tmp = Join-Path $env:TEMP ("share_put_{0}.bin" -f $off)
    [IO.File]::WriteAllBytes($tmp, $buf[0..($n-1)])
    $url = "{0}/tftp/upload?path={1}&offset={2}" -f $Base, [uri]::EscapeDataString($Path), $off
    $resp = & curl.exe -sS -f -X POST -H "Content-Type: application/octet-stream" --data-binary "@$tmp" $url
    Write-Host "[$off+$n/$total] $resp"
    if ($resp -notmatch '"ok"') { throw "upload failed" }
    Remove-Item -Force $tmp -ErrorAction SilentlyContinue
    $off += $n
  }
} finally { $fs.Close() }
curl.exe -sS "$Base/tftp/md5?path=$([uri]::EscapeDataString($Path))"
Write-Host ""
