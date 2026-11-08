#!/usr/bin/env bash
# 类似 wget，方向相反：本地文件 HTTP 分片上传到 ssh-bridge share
# 用法:
#   ./tools/share_put.sh http://172.16.33.54:18071 ./rootfs.ext4 ok3562/rootfs.ext4
#   ./tools/share_put.sh http://172.16.33.54:18071 ./uImage zk-hi3095/uImage 2097152
set -euo pipefail
BASE="${1%/}"
LOCAL="${2:-}"
REL="${3:-}"
CHUNK="${4:-2097152}"
if [[ -z "$BASE" || -z "$LOCAL" || -z "$REL" || ! -f "$LOCAL" ]]; then
  echo "usage: $0 <BASE> <local-file> <share-rel-path> [chunk]" >&2
  exit 2
fi
CURL=curl
command -v curl.exe >/dev/null 2>&1 && CURL=curl.exe
SIZE=$(wc -c <"$LOCAL" | tr -d ' ')
OFF=0
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
echo "upload $LOCAL ($SIZE) -> $BASE  path=$REL"
while [[ "$OFF" -lt "$SIZE" ]]; do
  dd if="$LOCAL" of="$TMP" bs="$CHUNK" skip=$((OFF / CHUNK)) count=1 status=none 2>/dev/null
  ACT=$(wc -c <"$TMP" | tr -d ' ')
  [[ "$ACT" -gt 0 ]] || break
  RESP=$($CURL -sS -f -X POST -H "Content-Type: application/octet-stream" \
    --data-binary @"$TMP" "$BASE/tftp/upload?path=${REL}&offset=${OFF}")
  echo "[$OFF+$ACT/$SIZE] $RESP"
  echo "$RESP" | grep -q '"ok"' || exit 1
  OFF=$((OFF + ACT))
done
$CURL -sS "$BASE/tftp/md5?path=${REL}"
echo
