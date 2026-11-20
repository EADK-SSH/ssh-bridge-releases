#!/usr/bin/env python3
"""Scan LAN for ssh-bridge / EADK (UDP EADK1@18071 + SSHBM1@38472). stdout=JSON."""
import argparse, json, re, socket, subprocess, sys, time

PORTS = [(18071, "EADK1"), (38472, "SSHBM1")]


def local_ips():
    """Return (preferred, set_of_local_ipv4)."""
    ips = set()
    preferred = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        preferred = s.getsockname()[0]
        s.close()
        if preferred and not preferred.startswith("127."):
            ips.add(preferred)
    except Exception:
        preferred = ""
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue "
                 "| Select-Object -ExpandProperty IPAddress"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode("utf-8", "replace")
        else:
            out = subprocess.check_output(
                ["ip", "-4", "-o", "addr", "show"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", "replace")
        for m in re.finditer(r"\b(\d+\.\d+\.\d+\.\d+)\b", out):
            ip = m.group(1)
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    if not preferred and ips:
        for ip in sorted(ips):
            if not ip.startswith("169.254."):
                preferred = ip
                break
        if not preferred:
            preferred = next(iter(ips))
    return preferred, ips


def parse_reply(data: bytes):
    t = data.decode("utf-8", "replace")
    for magic in ("EADK1", "SSHBM1"):
        if not t.startswith(magic):
            continue
        i = len(magic)
        while i < len(t) and t[i] in "\r\n \t":
            i += 1
        if i < len(t) and t[i] == "{":
            try:
                return json.loads(t[i:])
            except Exception:
                return None
    return None


def reply_id(obj):
    return "%s|%s|%s" % (
        obj.get("http_port"),
        obj.get("version"),
        json.dumps(obj.get("boards") or [], sort_keys=True, ensure_ascii=False),
    )


def scan(wait_ms=1500, targets=None):
    preferred, lips = local_ips()
    if not targets:
        targets = ["255.255.255.255"]
        for ip in lips:
            if ip.startswith("169.254."):
                continue
            parts = ip.split(".")
            if len(parts) == 4:
                targets.append(".".join(parts[:3] + ["255"]))
                targets.append(ip)
        # unique keep order
        seen_t, uniq = set(), []
        for t in targets:
            if t not in seen_t:
                seen_t.add(t)
                uniq.append(t)
        targets = uniq

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", 0))
    sock.settimeout(0.2)
    for ip in targets:
        if ip.startswith("127."):
            continue
        for port, magic in PORTS:
            try:
                sock.sendto(("%s\nq" % magic).encode(), (ip, port))
            except OSError:
                pass

    best = {}  # key -> obj
    end = time.time() + wait_ms / 1000.0
    while time.time() < end:
        try:
            data, (host, _) = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        if host.startswith("127."):
            continue
        obj = parse_reply(data)
        if not obj:
            continue
        local = host in lips
        use = preferred if (local and preferred) else host
        obj = dict(obj)
        obj["host"] = use
        key = ("local|" + reply_id(obj)) if local else (host + "|" + reply_id(obj))
        if key not in best or (local and use == preferred):
            best[key] = obj
    sock.close()
    return list(best.values()), preferred, lips


def main():
    ap = argparse.ArgumentParser(description="LAN discover ssh-bridge hosts/boards")
    ap.add_argument("-w", type=int, default=1500, help="wait ms")
    ap.add_argument("--host", action="append", default=[], help="unicast IP")
    ap.add_argument("--self", action="store_true", help="only this machine")
    ap.add_argument("--compact", action="store_true", help="one-line JSON")
    args = ap.parse_args()

    preferred, lips = local_ips()
    if args.self:
        targets = [ip for ip in lips if not ip.startswith("169.254.")] or ([preferred] if preferred else [])
    elif args.host:
        targets = list(args.host)
    else:
        targets = None

    hosts, preferred, _lips = scan(max(200, min(args.w, 10000)), targets)
    out = []
    for h in hosts:
        port = h.get("http_port") or 18071
        boards = []
        for b in h.get("boards") or []:
            if not isinstance(b, dict):
                continue
            one = {"name": b.get("name"), "type": b.get("type")}
            if b.get("ssh_port") is not None:
                one["ssh_port"] = b.get("ssh_port")
            if b.get("ssh_user"):
                one["ssh_user"] = b.get("ssh_user")
            boards.append(one)
        out.append({
            "host": h.get("host"),
            "http_port": port,
            "alias": h.get("alias") or "",
            "base_url": "http://%s:%s" % (h.get("host"), port),
            "boards": boards,
        })
    print(json.dumps(out, ensure_ascii=False, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
