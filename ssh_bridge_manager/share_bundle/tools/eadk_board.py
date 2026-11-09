#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EADK 板卡统一 CLI（Win/Linux，仅标准库）。封装桥 Agent HTTP / 分片上传 / 局域网发现。
手册: GET $BASE/tftp/download?path=tools/eadk_board.md
用法: python eadk_board.py [-b 通道] [-B base] [-t 秒] [-T] [-p PAT] <子命令> ...
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_BASE = os.environ.get("EADK_BASE", "http://127.0.0.1:18071")
DEFAULT_BOARD = os.environ.get("EADK_BOARD", "zk-hi3095")
DEFAULT_PUT_CHUNK = int(os.environ.get("EADK_PUT_CHUNK", str(2 * 1024 * 1024)))
DEFAULT_FEEDBACK_HOOK = os.environ.get(
    "EADK_FEEDBACK_HOOK",
    os.environ.get(
        "FEISHU_HOOK",
        "https://open.feishu.cn/open-apis/bot/v2/hook/da16b473-98ca-44db-b108-77d818da76be",
    ),
)
POLL_INTERVAL = 0.5
STABLE_NEED = 6
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07")
LAN_PORTS = [(18071, "EADK1"), (38472, "SSHBM1")]
FEAT_ORDER = [
    "status", "log", "clear", "cmd", "keys", "ctrlc", "write", "timestamp", "reconnect",
    "serial", "reboot", "power_on", "power_off", "soft-reboot", "uboot", "bootlog",
    "probe", "health", "state", "login", "ensure", "run", "exec", "download", "help-url",
    "scan", "discover", "put", "feedback",
]


class Die(Exception):
    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


def warn(msg: str) -> None:
    print(f"warn: {msg}", file=sys.stderr)


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s.replace("\r", ""))


def local_host_name() -> str:
    return (
        os.environ.get("EADK_HOST")
        or os.environ.get("COMPUTERNAME")
        or os.environ.get("HOSTNAME")
        or socket.gethostname()
        or "unknown-host"
    )


def lan_local_ips() -> Tuple[str, set]:
    """Return (preferred_ipv4, set_of_local_ipv4). Win/Linux."""
    ips: set = set()
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


def lan_parse_reply(data: bytes) -> Optional[dict]:
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


def lan_reply_id(obj: dict) -> str:
    return "%s|%s|%s" % (
        obj.get("http_port"),
        obj.get("version"),
        json.dumps(obj.get("boards") or [], sort_keys=True, ensure_ascii=False),
    )


def lan_scan(wait_ms: int = 1500, targets: Optional[List[str]] = None) -> Tuple[List[dict], str, set]:
    preferred, lips = lan_local_ips()
    if not targets:
        targets = ["255.255.255.255"]
        for ip in lips:
            if ip.startswith("169.254."):
                continue
            parts = ip.split(".")
            if len(parts) == 4:
                targets.append(".".join(parts[:3] + ["255"]))
                targets.append(ip)
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
        for port, magic in LAN_PORTS:
            try:
                sock.sendto(("%s\nq" % magic).encode(), (ip, port))
            except OSError:
                pass

    best: Dict[str, dict] = {}
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
        obj = lan_parse_reply(data)
        if not obj:
            continue
        local = host in lips
        use = preferred if (local and preferred) else host
        obj = dict(obj)
        obj["host"] = use
        key = ("local|" + lan_reply_id(obj)) if local else (host + "|" + lan_reply_id(obj))
        if key not in best or (local and use == preferred):
            best[key] = obj
    sock.close()
    return list(best.values()), preferred, lips


def cmd_discover(argv: Sequence[str], as_json: bool = False) -> int:
    """UDP 发现局域网 ssh-bridge（原 lan_discover.py）。"""
    ap = argparse.ArgumentParser(prog="discover", add_help=False)
    ap.add_argument("-w", type=int, default=1500, help="wait ms")
    ap.add_argument("--host", action="append", default=[], help="unicast IP")
    ap.add_argument("--self", action="store_true", help="only this machine")
    ap.add_argument("--compact", action="store_true", help="one-line JSON")
    ap.add_argument("-h", "--help", dest="show_help", action="store_true")
    try:
        args = ap.parse_args(list(argv))
    except SystemExit:
        return 2
    if args.show_help:
        print(HELP_TOPICS["discover"])
        return 0
    preferred, lips = lan_local_ips()
    if args.self:
        targets = [ip for ip in lips if not ip.startswith("169.254.")] or (
            [preferred] if preferred else [])
    elif args.host:
        targets = list(args.host)
    else:
        targets = None
    hosts, _preferred, _lips = lan_scan(max(200, min(args.w, 10000)), targets)
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
    compact = args.compact or as_json
    print(json.dumps(out, ensure_ascii=False, indent=None if compact else 2))
    return 0


class Client:
    def __init__(self, base: str, board: str, timeout: int = 60, reboot_wait: int = 60,
                 reboot_wait_set: bool = False, want_ts: bool = False, done_pat: str = "login:",
                 user: str = "", passwd: str = "", as_json: bool = False):
        self.base = base.rstrip("/")
        self.board = board
        self.timeout = timeout
        self.reboot_wait = reboot_wait
        self.reboot_wait_set = reboot_wait_set
        self.want_ts = want_ts
        self.done_pat = done_pat
        self.as_json = as_json
        self.login_user = user or os.environ.get("EADK_USER", "")
        self.login_pass = passwd if passwd is not None else os.environ.get("EADK_PASS", "")
        self.ch_name = ""
        self.ch_key = "board"
        self.ch_type = ""
        self.ch_connected = False
        self.ch_target_user = ""
        self.ch_target_pass = ""
        self.ch_error = ""
        self.ch_log_bytes = 0
        self.has_reboot = False
        self.has_power_on = False
        self.has_power_off = False
        self.has_soft_reboot = True
        self.action_ids: List[str] = []
        self.uboot_char = " "
        self.uboot_dur = 8.0
        self.uboot_int = 0.05
        self.uboot_mark = "=>"
        self._agent_api: Optional[bool] = None
        self._last_status: Dict[str, Any] = {}

    def api_get(self, path: str, timeout: float = 120) -> Any:
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                raw = r.read()
                ct = r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            raw = e.read()
            msg = raw.decode("utf-8", errors="replace")
            try:
                err = json.loads(msg)
                msg = err.get("error") or err.get("detail") or msg
            except Exception:
                pass
            raise Die(f"GET {path} HTTP {e.code}: {msg}") from e
        except Exception as e:
            raise Die(f"GET {path} 失败（网络/服务不可达）: {e}") from e
        text = raw.decode("utf-8", errors="replace")
        if "json" in ct or (text[:1] in "{["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text

    def api_post(self, path: str, body: dict, timeout: float = 120) -> Any:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                err = json.loads(raw.decode("utf-8", errors="replace"))
                msg = err.get("error") or err.get("detail") or raw.decode("utf-8", errors="replace")
            except Exception:
                msg = raw.decode("utf-8", errors="replace") or str(e)
            code = 3 if e.code == 423 else 1
            raise Die(f"POST {path} HTTP {e.code}: {msg}", code) from e
        except Exception as e:
            raise Die(f"POST {path} 失败（网络/服务不可达）: {e}") from e
        text = raw.decode("utf-8", errors="replace")
        if not text:
            return {}
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(out, dict) and (out.get("error") or out.get("detail")):
            raise Die(f"POST {path}: {out.get('error') or out.get('detail')}")
        return out

    def post_url(self, url: str, body: dict, timeout: float = 30) -> Any:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                code = getattr(r, "status", 200)
        except urllib.error.HTTPError as e:
            raw = e.read()
            raise Die(f"POST feedback HTTP {e.code}: {raw.decode('utf-8', errors='replace')}") from e
        except Exception as e:
            raise Die(f"POST feedback 失败: {e}") from e
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text) if text else {"ok": True, "http": code}
        except json.JSONDecodeError:
            return {"ok": True, "raw": text, "http": code}

    def has_agent_api(self) -> bool:
        if self._agent_api is None:
            try:
                helpj = self.api_get("/api/help", timeout=5)
                ops = helpj.get("operations") if isinstance(helpj, dict) else []
                ids = {(o.get("id") or o.get("name") or "") for o in (ops or [])}
                paths = {(o.get("path") or "") for o in (ops or [])}
                self._agent_api = ("agent_probe" in ids) or ("/agent/probe" in paths)
            except Exception:
                self._agent_api = False
        return bool(self._agent_api)

    def apply_uboot_profile(self) -> None:
        if self.ch_name in ("zk-hi3095", "kede-hi3095"):
            self.uboot_char, self.uboot_dur, self.uboot_int, self.uboot_mark = "U", 18.0, 0.05, "=>"
        else:
            self.uboot_char, self.uboot_dur, self.uboot_int, self.uboot_mark = " ", 8.0, 0.05, "=>"

    def default_login(self) -> None:
        if self.login_user:
            return
        if self.ch_target_user:
            self.login_user = self.ch_target_user
            self.login_pass = self.ch_target_pass
            return
        if self.ch_name in ("zk-hi3095", "kede-hi3095"):
            self.login_user = "root"
            if not self.login_pass:
                self.login_pass = "Ncti2023"
        else:
            self.login_user = "root"

    def load_channel(self) -> None:
        name = self.board
        st = None
        try:
            st = self.api_get(f"/status?board={urllib.parse.quote(name)}&view=agent")
        except Die:
            st = None
        if not isinstance(st, dict) or not st.get("board_name"):
            try:
                st = self.api_get(f"/status?link={urllib.parse.quote(name)}&view=agent")
            except Die as e:
                raise Die(f"通道不存在或桥不可达: {name} ({e})") from e
        if not isinstance(st, dict) or not st.get("board_name"):
            raise Die(f"通道不存在: {name}（先 scan/list 看真实名；键 serial=board ssh=link）")
        self._last_status = st
        self.ch_name = st["board_name"]
        self.ch_type = st.get("channel_type") or ""
        if self.ch_type in ("ssh", "ssh-link"):
            self.ch_key = "link"
        else:
            self.ch_key = "board"
        if st.get("shell_connected") is not None:
            self.ch_connected = bool(st.get("shell_connected"))
        else:
            self.ch_connected = bool(st.get("serial_connected"))
        self.ch_target_user = st.get("target_username") or ""
        self.ch_target_pass = st.get("target_password") or ""
        self.ch_error = st.get("last_serial_error") or st.get("last_shell_error") or ""
        self.ch_log_bytes = int(st.get("log_bytes") or 0)
        self.action_ids = []
        self.has_reboot = self.has_power_on = self.has_power_off = False
        try:
            q = self.api_get(f"/actions?{self.ch_key}={urllib.parse.quote(self.ch_name)}&view=agent")
            if isinstance(q, dict) and q.get("buttons"):
                self.action_ids = [b["id"] for b in q["buttons"] if b.get("id")]
                self.has_reboot = "reboot" in self.action_ids
                self.has_power_on = "power_on" in self.action_ids
                self.has_power_off = "power_off" in self.action_ids
        except Die as e:
            warn(f"读 actions 失败（按无按钮处理）: {e}")
        self.has_soft_reboot = True
        self.apply_uboot_profile()
        self.default_login()

    def require_connected(self) -> None:
        self.load_channel()
        if not self.ch_connected:
            hint = self.ch_error or "检查串口/SSH 目标；可用 reconnect 或 serial open"
            raise Die(f"通道 {self.ch_name} 未连接（connected=false）；{hint}", 2)

    def ch_body(self, **extra: Any) -> dict:
        d = {self.ch_key: self.ch_name}
        d.update(extra)
        return d

    def feature_enabled(self, f: str) -> bool:
        always = {
            "list", "status", "log", "clear", "cmd", "keys", "ctrlc", "write", "timestamp",
            "reconnect", "help-url", "probe", "health", "state", "login", "ensure", "run",
            "download", "exec", "scan", "feedback", "suggest", "bug",
        }
        if f in always:
            return True
        if f == "serial":
            return self.ch_type == "serial"
        if f == "reboot":
            return self.has_reboot
        if f == "power_on":
            return self.has_power_on
        if f == "power_off":
            return self.has_power_off
        if f == "soft-reboot":
            return self.has_soft_reboot
        if f == "uboot":
            return (self.has_reboot or self.has_soft_reboot) and self.ch_type == "serial"
        if f == "bootlog":
            return self.has_reboot or self.has_soft_reboot
        return False

    def feature_reason(self, f: str) -> str:
        if self.feature_enabled(f):
            return "ok"
        if f == "serial":
            return "仅 serial 通道；当前是 ssh，键用 link"
        if f in ("reboot", "power_on", "power_off"):
            return f"GET /actions 无按钮 id={f}；可用 soft-reboot 或先配继电器按钮"
        if f == "uboot":
            if self.ch_type != "serial":
                return "uboot 仅 serial；ssh 通道不支持抢 U-Boot"
            return "需要 reboot 按钮或 soft-reboot"
        if f == "bootlog":
            return "需要 reboot 按钮或 soft-reboot"
        return "本通道不支持"

    def require_feat(self, f: str) -> None:
        if not self.feature_enabled(f):
            raise Die(
                f"通道 {self.ch_name}(type={self.ch_type}) 不支持: {f}；"
                f"原因: {self.feature_reason(f)}；请先 `-b {self.ch_name} list` 看 +/-"
            )

    def feats_map(self) -> Dict[str, bool]:
        return {f: self.feature_enabled(f) for f in FEAT_ORDER if f not in ("scan", "feedback", "suggest", "bug")}

    def powered_label(self, st: str) -> str:
        if self.ch_type in ("ssh", "ssh-link"):
            return "n/a"
        if self.board_alive(st):
            return "yes"
        if self.ch_connected and self.has_power_on:
            return "no"
        return "unknown"

    def channel_snapshot(self, do_wake: bool = False) -> Dict[str, Any]:
        self.load_channel()
        st = self.detect_state()
        if do_wake and self.ch_connected and not self.board_alive(st):
            st = self.wake_probe_state()
        feats = self.feats_map()
        plus = [k for k, v in feats.items() if v]
        minus = [k for k, v in feats.items() if not v]
        return {
            "name": self.ch_name,
            "type": self.ch_type,
            "key": self.ch_key,
            "connected": self.ch_connected,
            "terminal": st,
            "powered": self.powered_label(st),
            "log_bytes": self.ch_log_bytes,
            "buttons": list(self.action_ids),
            "error": self.ch_error or None,
            "features_plus": plus,
            "features_minus": minus,
            "features": feats,
            "uboot_profile": {
                "char": "<space>" if self.uboot_char == " " else self.uboot_char,
                "duration": self.uboot_dur,
                "interval": self.uboot_int,
                "mark": self.uboot_mark,
            },
            "login_user": self.login_user,
        }

    def fetch_log(self, extra: str = "") -> str:
        out = self.api_get(f"/log?{self.ch_key}={urllib.parse.quote(self.ch_name)}{extra}")
        return out if isinstance(out, str) else str(out)

    def raw_write(self, data: str) -> None:
        self.api_post("/write", self.ch_body(data=data))

    def raw_command(self, cmd: str) -> None:
        self.api_post("/command", self.ch_body(command=cmd))

    def do_reboot_any(self) -> None:
        if self.has_reboot:
            self.api_post("/action", self.ch_body(id="reboot"))
        else:
            self.api_post("/command", self.ch_body(command="reboot"))

    def reboot_wait_sec(self) -> int:
        return self.timeout if self.reboot_wait_set else self.reboot_wait

    def gen_cmdid(self) -> str:
        return f"{int(time.time())}{random.randint(0, 999999):06d}"[-12:]

    def log_has_marker(self, log: str, marker: str) -> bool:
        for line in strip_ansi(log).splitlines():
            if line.strip() == marker:
                return True
        return False

    def detect_state(self) -> str:
        if not self.ch_connected:
            return "disconnected"
        # Prefer server probe when available
        if self.has_agent_api():
            try:
                r = self.api_get(
                    f"/agent/probe?{self.ch_key}={urllib.parse.quote(self.ch_name)}", timeout=10)
                if isinstance(r, dict) and r.get("state"):
                    return str(r["state"])
            except Die:
                pass
        log = self.fetch_log()
        return detect_state_from_log(log, self.ch_key == "link", self.ch_connected)

    def wake_probe_state(self) -> str:
        try:
            self.raw_write("\n")
        except Die:
            pass
        time.sleep(0.6)
        return self.detect_state()

    def board_alive(self, st: str) -> bool:
        return st in ("shell", "login", "password", "uboot")

    def wait_state_or_mark(self, timeout: float, *wants: str) -> Optional[str]:
        start = time.time()
        while True:
            st = self.detect_state()
            if st in wants:
                return st
            log = None
            for want in wants:
                if want.startswith("end_") or want.startswith("ready_"):
                    if log is None:
                        log = self.fetch_log()
                    if self.log_has_marker(log, want):
                        return f"mark:{want}"
            if time.time() - start >= timeout:
                return None
            time.sleep(POLL_INTERVAL)

    def ensure_powered(self, mode: str = "shell") -> None:
        if self.ch_type != "serial" or not self.has_power_on:
            return
        st = self.detect_state()
        if self.board_alive(st):
            return
        st = self.wake_probe_state()
        if self.board_alive(st):
            return
        warn(f"板无终端回显（state={st}），执行 power_on")
        self.api_post("/action", self.ch_body(id="power_on"))
        wait_s = self.reboot_wait_sec()
        wants = ("login", "password", "shell", "uboot") if mode == "any" else ("login", "password", "shell")
        got = self.wait_state_or_mark(wait_s, *wants)
        if got:
            warn(f"上电后状态: {got}")
            return
        raise Die(f"power_on 后 {wait_s}s 仍无终端态（state={self.detect_state()}；可加大 -t）")

    # ---- commands ----
    def cmd_list_all(self) -> None:
        st = self.api_get("/status?view=agent")
        print("NAME\tTYPE\tCONNECTED\tLOG_BYTES\tBUTTONS")
        for b in (st.get("bridges") or []) if isinstance(st, dict) else []:
            name = b.get("board_name", "")
            typ = b.get("channel_type", "")
            key = "board" if typ == "serial" else "link"
            conn = b.get("shell_connected")
            if conn is None:
                conn = b.get("serial_connected")
            buttons = ""
            try:
                q = self.api_get(f"/actions?{key}={urllib.parse.quote(name)}&view=agent")
                if isinstance(q, dict):
                    buttons = ",".join(x["id"] for x in q.get("buttons") or [])
            except Die:
                pass
            print(f"{name}\t{typ}\t{conn}\t{b.get('log_bytes', 0)}\t{buttons}")

    def cmd_list_feats(self) -> None:
        snap = self.channel_snapshot(False)
        if self.as_json:
            print(json.dumps(snap, ensure_ascii=False, indent=2))
            return
        uch = snap["uboot_profile"]["char"]
        print(f"通道: {snap['name']}  类型: {snap['type']}  键: {snap['key']}  connected: {snap['connected']}")
        print(f"按钮: {','.join(snap['buttons']) or '（无）'}")
        print(f"U-Boot抢键: char={uch} dur={snap['uboot_profile']['duration']}s "
              f"int={snap['uboot_profile']['interval']} mark={snap['uboot_profile']['mark']}")
        print(f"登录默认: {snap['login_user']}/****")
        print("支持功能（+ 可调 / - 勿调；不同板能力不同，以本表为准）:")
        for f in FEAT_ORDER:
            if f in ("scan", "feedback", "suggest", "bug"):
                continue
            ok = self.feature_enabled(f)
            mark = "+" if ok else "-"
            extra = "" if ok else f"  # {self.feature_reason(f)}"
            print(f"  {mark} {f}{extra}")

    def cmd_status(self) -> None:
        self.load_channel()
        st = self.api_get(f"/status?{self.ch_key}={urllib.parse.quote(self.ch_name)}&view=agent")
        print(json.dumps(st, ensure_ascii=False, indent=2))

    def cmd_log(self, args: Sequence[str]) -> None:
        self.load_channel()
        extra = ""
        if len(args) >= 2 and args[0] == "lines":
            extra = f"&lines={args[1]}"
        elif len(args) >= 2 and args[0] == "chars":
            extra = f"&chars={args[1]}"
        text = self.fetch_log(extra).replace("\r", "")
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")

    def cmd_clear(self) -> None:
        self.load_channel()
        self.api_post("/log/clear", self.ch_body())

    def cmd_keys(self, char: str, dur: float = 7.0, interval: float = 0.1) -> None:
        self.load_channel()
        # send_keys may take duration seconds
        self.api_post("/send_keys", self.ch_body(char=char, duration=dur, interval=interval),
                      timeout=max(120.0, dur + 30))

    def cmd_ctrlc(self) -> None:
        self.cmd_keys("<ctrl+c>", 2.0, 0.1)

    def cmd_write(self, data: str) -> None:
        self.load_channel()
        self.raw_write(data)

    def cmd_timestamp(self, on: str) -> None:
        self.load_channel()
        if on in ("on", "1", "true"):
            ts = True
        elif on in ("off", "0", "false"):
            ts = False
        else:
            raise Die("timestamp on|off")
        self.api_post("/channel/configure", self.ch_body(timestamp=ts, persist=False))

    def cmd_reconnect(self) -> None:
        self.load_channel()
        self.api_post("/reconnect", self.ch_body())

    def cmd_serial(self, op: str) -> None:
        self.load_channel()
        self.require_feat("serial")
        if op == "open":
            self.api_post("/serial/open", self.ch_body())
        elif op == "close":
            self.api_post("/serial/close", self.ch_body())
        else:
            raise Die("serial open|close")

    def cmd_action(self, aid: str) -> None:
        self.load_channel()
        self.require_feat(aid)
        self.api_post("/action", self.ch_body(id=aid))

    def cmd_soft_reboot(self) -> None:
        self.load_channel()
        self.require_feat("soft-reboot")
        self.raw_command("reboot")

    def extract_after_echo_marker(self, log: str, marker: str) -> str:
        clean = strip_ansi(log)
        needle = f"echo {marker}"
        i = clean.rfind(needle)
        if i < 0:
            i = clean.find(needle)
        if i >= 0:
            clean = clean[i + len(needle):]
        j = clean.find(marker)
        if j >= 0:
            clean = clean[:j]
        return clean.strip("\n")

    def cmd_cmd(self, cmdline: str) -> None:
        self.require_connected()
        self.require_feat("cmd")
        st = self.detect_state()
        if st in ("login", "password"):
            raise Die(f"当前在 {st}，请先: login  或用 run")
        if st == "uboot":
            raise Die("当前在 U-Boot，不能执行 Linux cmd")
        if st == "disconnected":
            raise Die("未连接")
        if st == "unknown":
            warn("状态 unknown，仍尝试下发；失败请先 ensure/login")
        # Prefer server /agent/exec
        if self.has_agent_api():
            try:
                r = self.api_post(
                    "/agent/exec",
                    self.ch_body(command=cmdline, timeout=self.timeout),
                    timeout=float(self.timeout) + 30,
                )
                if isinstance(r, dict):
                    if r.get("timed_out"):
                        raise Die(f"timeout {self.timeout}s（state={r.get('state')}）")
                    out = r.get("output")
                    if out is None:
                        out = ""
                    print(out if str(out).endswith("\n") else str(out))
                    return
            except Die as e:
                if "not found" in str(e).lower() or "404" in str(e):
                    self._agent_api = False
                else:
                    raise
        cmdid = self.gen_cmdid()
        marker = f"end_cmd_{cmdid}"
        self.raw_command(f"{cmdline}; echo {marker}")
        start = time.time()
        while True:
            log = self.fetch_log()
            if self.log_has_marker(log, marker):
                print(self.extract_after_echo_marker(log, marker))
                return
            st = self.detect_state()
            if st in ("login", "password"):
                raise Die(f"命令似乎打到了 {st} 提示符（未登录）。请: login 或 run")
            if time.time() - start >= self.timeout:
                raise Die(f"timeout {self.timeout}s 等待 {marker}（state={self.detect_state()}）")
            time.sleep(POLL_INTERVAL)

    def cmd_probe(self) -> None:
        self.load_channel()
        print(self.detect_state())

    def cmd_health(self) -> int:
        self.load_channel()
        stj = self.api_get(f"/status?{self.ch_key}={urllib.parse.quote(self.ch_name)}&view=agent")
        err = ""
        if isinstance(stj, dict):
            err = stj.get("last_serial_error") or stj.get("last_shell_error") or ""
        st = self.detect_state()
        line = (f"name={self.ch_name} type={self.ch_type} key={self.ch_key} "
                f"connected={str(self.ch_connected).lower()} state={st}")
        if err:
            line += f" error={err}"
        print(line)
        if not self.ch_connected or st == "disconnected":
            return 2
        return 0

    def emit_board_state_line(self, do_wake: bool = False) -> Dict[str, Any]:
        snap = self.channel_snapshot(do_wake)
        if self.as_json:
            return snap
        line = (
            f"name={snap['name']} type={snap['type']} connected={str(snap['connected']).lower()} "
            f"terminal={snap['terminal']} powered={snap['powered']} log_bytes={snap['log_bytes']} "
            f"buttons={','.join(snap['buttons'])}"
        )
        if snap.get("error"):
            line += f" error={snap['error']}"
        print(line)
        return snap

    def cmd_state_one(self) -> None:
        snap = self.emit_board_state_line(True)
        if self.as_json:
            print(json.dumps(snap, ensure_ascii=False, indent=2))

    def cmd_state_all(self) -> None:
        st = self.api_get("/status?view=agent")
        rows = []
        for b in (st.get("bridges") or []) if isinstance(st, dict) else []:
            self.board = b["board_name"]
            rows.append(self.emit_board_state_line(False))
        if self.as_json:
            print(json.dumps({"channels": rows}, ensure_ascii=False, indent=2))

    def cmd_scan(self, names: Optional[Sequence[str]] = None) -> int:
        """扫描全部（或指定）板卡：连接/终端态/能力 +/- /错误。"""
        # Prefer server /agent/scan when available
        if not names and self.has_agent_api():
            try:
                data = self.api_get("/agent/scan", timeout=30)
                if isinstance(data, dict) and data.get("channels") is not None:
                    return self._print_scan(data["channels"], from_server=True)
            except Die:
                pass
        st = self.api_get("/status?view=agent")
        bridges = (st.get("bridges") or []) if isinstance(st, dict) else []
        if names:
            want = set(names)
            bridges = [b for b in bridges if b.get("board_name") in want]
            missing = want - {b.get("board_name") for b in bridges}
            if missing:
                raise Die(f"通道不存在: {', '.join(sorted(missing))}")
        rows = []
        for b in bridges:
            self.board = b["board_name"]
            try:
                snap = self.channel_snapshot(do_wake=True)
            except Die as e:
                snap = {
                    "name": b.get("board_name"),
                    "type": b.get("channel_type"),
                    "connected": False,
                    "terminal": "error",
                    "powered": "unknown",
                    "log_bytes": b.get("log_bytes", 0),
                    "buttons": [],
                    "error": str(e),
                    "features_plus": [],
                    "features_minus": [],
                    "features": {},
                }
            rows.append(snap)
        return self._print_scan(rows, from_server=False)

    def _print_scan(self, rows: List[Dict[str, Any]], from_server: bool) -> int:
        worst = 0
        for snap in rows:
            conn = snap.get("connected")
            term = snap.get("terminal") or snap.get("state")
            err = snap.get("error")
            if not conn or term in ("disconnected", "error"):
                worst = max(worst, 2)
            elif err:
                worst = max(worst, 1)
        if self.as_json:
            print(json.dumps({"channels": rows, "source": "server" if from_server else "cli"},
                             ensure_ascii=False, indent=2))
            return worst
        print(f"# scan {len(rows)} channels  (规则: 只调用该板 + 功能；- 勿调)")
        for snap in rows:
            name = snap.get("name") or snap.get("board")
            typ = snap.get("type") or snap.get("channel_type")
            conn = snap.get("connected")
            term = snap.get("terminal") or snap.get("state")
            powered = snap.get("powered", "?")
            buttons = snap.get("buttons") or []
            if isinstance(buttons, list) and buttons and isinstance(buttons[0], dict):
                buttons = [x.get("id") for x in buttons if x.get("id")]
            err = snap.get("error")
            plus = snap.get("features_plus")
            minus = snap.get("features_minus")
            if plus is None and isinstance(snap.get("features"), dict):
                feats = snap["features"]
                plus = [k for k, v in feats.items() if v]
                minus = [k for k, v in feats.items() if not v]
            plus = plus or []
            minus = minus or []
            line = (f"name={name} type={typ} connected={str(conn).lower()} "
                    f"terminal={term} powered={powered} "
                    f"buttons={','.join(buttons) if isinstance(buttons, list) else buttons}")
            if err:
                line += f" error={err}"
            print(line)
            print(f"  + {','.join(plus) if plus else '(none)'}")
            if minus:
                print(f"  - {','.join(minus)}")
        return worst

    def cmd_feedback(self, kind: str, text: str, host: str = "") -> None:
        kind = (kind or "").strip()
        text = (text or "").strip()
        if not kind:
            raise Die("feedback <kind> <陈述...>  例: feedback bug 串口无回显")
        if not text:
            raise Die("反馈陈述不能为空")
        # normalize kind aliases
        kind_map = {
            "bug": "bug", "缺陷": "bug", "issue": "bug",
            "建议": "建议", "suggest": "建议", "suggestion": "建议", "enhancement": "建议",
            "功能": "功能", "feature": "功能", "feat": "功能",
        }
        kind_norm = kind_map.get(kind.lower(), kind)
        host_name = host or self.board or local_host_name()
        # if -b pointed at a real channel, prefer it
        try:
            if self.board:
                self.load_channel()
                host_name = host or self.ch_name or host_name
        except Die:
            pass
        payload_text = f"[{host_name}][问题属性：{kind_norm}] {text}"
        hook = DEFAULT_FEEDBACK_HOOK
        if not hook:
            raise Die("未配置反馈 Webhook（EADK_FEEDBACK_HOOK / FEISHU_HOOK）")
        body = {"msg_type": "text", "content": {"text": payload_text}}
        resp = self.post_url(hook, body, timeout=20)
        ok = True
        if isinstance(resp, dict):
            code = resp.get("StatusCode", resp.get("code", 0))
            if code not in (0, "0", None) and resp.get("StatusMessage") not in (None, "success"):
                # Feishu success is StatusCode=0
                if code not in (0, 0.0):
                    ok = False
        if not ok:
            raise Die(f"飞书返回异常: {resp}")
        if self.as_json:
            print(json.dumps({"ok": True, "text": payload_text, "response": resp},
                             ensure_ascii=False, indent=2))
        else:
            print(f"feedback_ok text={payload_text}")
            if isinstance(resp, dict) and resp:
                print(json.dumps(resp, ensure_ascii=False))

    def wait_shell_marker(self, timeout: float = 15) -> bool:
        mid = self.gen_cmdid()
        marker = f"ready_{mid}"
        self.raw_command(f"echo {marker}")
        start = time.time()
        while True:
            if self.log_has_marker(self.fetch_log(), marker):
                return True
            if time.time() - start >= timeout:
                return False
            time.sleep(POLL_INTERVAL)

    def login_once(self, user: str, passwd: str) -> bool:
        st = self.detect_state()
        if st in ("password", "unknown"):
            self.raw_write("\n")
            time.sleep(0.5)
            st = self.detect_state()
        if st not in ("login", "shell"):
            try:
                self.api_post("/send_keys", self.ch_body(char="<ctrl+c>", duration=0.5, interval=0.1),
                              timeout=30)
            except Die:
                pass
            time.sleep(0.3)
            self.raw_write("\n")
            time.sleep(0.8)
            st = self.detect_state()
        if st == "shell":
            return True
        if st not in ("login", "password"):
            return False
        if st == "login":
            self.raw_write(user + "\n")
            got = self.wait_state_or_mark(10, "password", "shell")
            if not got:
                return False
            st = got
        if st == "password":
            self.raw_write(passwd + "\n")
        for _ in range(30):
            time.sleep(POLL_INTERVAL)
            st = self.detect_state()
            log = strip_ansi(self.fetch_log())
            if re.search(r"Login incorrect", "\n".join(log.splitlines()[-8:]), re.I):
                return False
            if st == "shell":
                return self.wait_shell_marker(10)
            if st == "login":
                return False
        return False

    def cmd_login(self, user: str = "", passwd: Optional[str] = None) -> None:
        self.require_connected()
        self.ensure_powered()
        u = user or self.login_user
        p = self.login_pass if passwd is None else passwd
        if not u:
            raise Die("login 需要用户名（参数或 EADK_USER）")
        st = self.detect_state()
        if st == "shell":
            if self.wait_shell_marker(8):
                print("already_shell")
                return
            warn("看似 shell 但校验失败，重新登录")
        elif st == "uboot":
            raise Die("当前在 U-Boot，无法 login；请先启动系统或用 uboot 操作")
        elif st == "disconnected":
            raise Die("未连接")
        if self.login_once(u, p):
            print(f"login_ok user={u}")
            return
        if p:
            warn("密码登录失败，尝试空密码")
            if self.login_once(u, ""):
                print(f"login_ok user={u} pass=empty")
                return
        raise Die(f"登录失败 user={u}（state={self.detect_state()}；可: login <user> <pass>）")

    def cmd_ensure(self) -> None:
        self.require_connected()
        self.ensure_powered()
        st = self.detect_state()
        if st == "shell":
            if self.wait_shell_marker(8):
                print("shell_ok")
                return
            warn("shell 校验失败，尝试重新登录")
            self.cmd_login(self.login_user, self.login_pass)
        elif st in ("login", "password", "unknown"):
            self.cmd_login(self.login_user, self.login_pass)
        elif st == "uboot":
            raise Die("当前在 U-Boot；ensure 只用于 Linux shell")
        elif st == "disconnected":
            raise Die("未连接")
        else:
            raise Die(f"无法 ensure: state={st}")

    def cmd_run(self, cmdline: str) -> None:
        # silence ensure chatter
        import io
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            self.cmd_ensure()
        finally:
            sys.stdout = old
        self.cmd_cmd(cmdline)

    def wait_mark(self, mark: str, timeout: float) -> str:
        start = time.time()
        log = ""
        while True:
            log = self.fetch_log()
            if mark in log:
                return log
            if time.time() - start >= timeout:
                print(f"timeout {timeout}s waiting '{mark}'", file=sys.stderr)
                print(log, file=sys.stderr)
                raise SystemExit(124)
            time.sleep(POLL_INTERVAL)

    def wait_boot(self, timeout: float, pat: str) -> str:
        start = time.time()
        last = ""
        stable = 0
        log = ""
        while True:
            log = self.fetch_log()
            if pat and pat in log:
                return log
            if log and log == last:
                stable += 1
                if stable >= STABLE_NEED:
                    return log
            else:
                stable = 0
                last = log
            if time.time() - start >= timeout:
                print(f"timeout {timeout}s boot (pat={pat})", file=sys.stderr)
                return log
            time.sleep(POLL_INTERVAL)

    def cmd_uboot(self) -> None:
        self.load_channel()
        self.require_feat("uboot")
        self.require_connected()
        self.ensure_powered("any")
        wait_s = self.reboot_wait_sec()
        self.cmd_timestamp("on" if self.want_ts else "off")
        self.cmd_clear()
        self.do_reboot_any()
        self.cmd_keys(self.uboot_char, self.uboot_dur, self.uboot_int)
        print(self.wait_mark(self.uboot_mark, wait_s).replace("\r", ""))

    def cmd_bootlog(self) -> None:
        self.load_channel()
        self.require_feat("bootlog")
        self.require_connected()
        self.ensure_powered("any")
        wait_s = self.reboot_wait_sec()
        self.cmd_timestamp("on" if self.want_ts else "off")
        self.cmd_clear()
        self.do_reboot_any()
        print(self.wait_boot(wait_s, self.done_pat).replace("\r", ""))

    def cmd_download(self, out_path: str = "") -> None:
        self.load_channel()
        url = f"{self.base}/log/download?{self.ch_key}={urllib.parse.quote(self.ch_name)}"
        path = out_path or f"{self.ch_name}.log"
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        print(path)

    def cmd_help_url(self) -> None:
        self.load_channel()
        print(f"{self.base}/help/{self.ch_name}")

    def api_post_bytes(self, path: str, data: bytes, timeout: float = 300) -> Any:
        req = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/octet-stream"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raw = e.read()
            raise Die(f"POST {path} HTTP {e.code}: {raw.decode('utf-8', errors='replace')}") from e
        except Exception as e:
            raise Die(f"POST {path} 失败（网络/服务不可达）: {e}") from e
        text = raw.decode("utf-8", errors="replace")
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def cmd_put(self, local: str, rel: str, chunk: int = 0) -> None:
        """分片上传本地文件到 share（原 share_put.sh/.ps1，Win/Linux 同脚本）。"""
        if not local or not rel:
            raise Die("put <本地文件> <share相对路径> [chunk字节]")
        path = os.path.abspath(local)
        if not os.path.isfile(path):
            raise Die(f"本地文件不存在: {local}")
        chunk = int(chunk) if chunk else DEFAULT_PUT_CHUNK
        if chunk < 64 * 1024:
            raise Die("chunk 过小（最小 65536）")
        total = os.path.getsize(path)
        rel_q = urllib.parse.quote(rel, safe="/")
        print(f"upload {path} ({total}) -> {self.base}  path={rel}")
        off = 0
        with open(path, "rb") as f:
            while off < total:
                buf = f.read(chunk)
                if not buf:
                    break
                n = len(buf)
                url_path = f"/tftp/upload?path={rel_q}&offset={off}"
                resp = self.api_post_bytes(url_path, buf, timeout=max(120, self.timeout))
                print(f"[{off}+{n}/{total}] {resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)}")
                ok = False
                if isinstance(resp, dict):
                    ok = (resp.get("ok") is True or resp.get("status") == "ok"
                          or resp.get("ok") == 1)
                    if resp.get("error") or resp.get("detail"):
                        ok = False
                elif isinstance(resp, str):
                    ok = '"ok"' in resp or resp.strip() == "ok"
                if not ok:
                    raise Die(f"upload failed at offset={off}: {resp}")
                off += n
        md5 = self.api_get(f"/tftp/md5?path={rel_q}", timeout=120)
        if self.as_json:
            print(json.dumps({"ok": True, "path": rel, "size": total, "md5": md5},
                             ensure_ascii=False, indent=2))
        else:
            print(md5 if isinstance(md5, str) else json.dumps(md5, ensure_ascii=False))


def detect_state_from_log(log: str, is_ssh: bool, connected: bool) -> str:
    if not connected:
        return "disconnected"
    text = strip_ansi(log)
    if is_ssh and not text.strip():
        return "shell"
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    tail = lines[-30:] if lines else []
    last = tail[-1] if tail else ""
    if re.search(r"Login incorrect", last, re.I):
        return "login"
    if re.search(r"password:\s*$", last, re.I):
        return "password"
    if re.search(r"login:\s*$", last, re.I):
        return "login"
    if re.search(r"^\s*=>\s*$", last) or re.search(r"(^|\s)=>\s*$", last):
        return "uboot"
    if re.search(r"(#|\$)\s*$", last):
        return "shell"
    for ln in reversed(tail):
        if re.search(r"(#|\$)\s*$", ln):
            return "shell"
    return "unknown"


HELP_TOPICS = {
    "list": "list — 全部通道概览；-b NAME / list NAME 列该板 +/- 能力\n"
            "  例: eadk_board.py -B http://10.168.21.236:18081 list\n"
            "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 list\n"
            "      eadk_board.py -B http://10.168.21.236:18081 list ok3568",
    "scan": "scan [名...] — 扫描全部/指定板：连接、终端态、buttons、+/-；-j JSON\n"
            "  退出码: 0 全好；1 有 error；2 有断线。开场首选。\n"
            "  例: eadk_board.py -B http://10.168.21.236:18081 scan\n"
            "      eadk_board.py -B http://10.168.21.236:18081 scan ok3568\n"
            "      eadk_board.py -B http://10.168.21.236:18081 -j scan",
    "discover": "discover [-w ms] [--host IP] [--self] [--compact] — UDP 扫局域网桥\n"
                "  输出 JSON：host/http_port/base_url/boards\n"
                "  例: eadk_board.py discover\n"
                "      eadk_board.py discover --self\n"
                "      eadk_board.py discover --host 10.168.21.236 -w 2000",
    "put": "put <本地文件> <share相对路径> [chunk] — 分片上传到 share（Win/Linux 同命令）\n"
           "  默认 chunk=2MiB（$EADK_PUT_CHUNK）\n"
           "  例: eadk_board.py -B http://10.168.21.236:18081 put ./uImage ok3568/uImage\n"
           "      eadk_board.py -B http://10.168.21.236:18081 put ./rootfs.ext4 ok3568/rootfs.ext4 16777216",
    "status": "status — 通道 agent 状态 JSON\n"
              "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 status",
    "log": "log [lines N|chars N] — 读日志\n"
           "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 log\n"
           "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 log lines 50\n"
           "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 log chars 4000",
    "clear": "clear — 清空日志\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 clear",
    "cmd": "cmd <命令> — 已在 shell 时阻塞执行\n"
           "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 cmd 'ls /'",
    "run": "run <命令> — ensure + cmd（日常首选）\n"
           "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 run 'uname -a'\n"
           "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 120 run 'make -j4'",
    "exec": "exec <命令> — 同 cmd；优先 POST /agent/exec\n"
            "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 exec 'hostname'",
    "probe": "probe — 终端态：disconnected|login|password|uboot|shell|unknown\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 probe",
    "health": "health — 连通检查；断线 exit 2\n"
              "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 health",
    "state": "state [名] — 状态摘要；无参=全部\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 state\n"
             "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 state",
    "login": "login [user [pass]] — 串口/SSH 登录\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 login\n"
             "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 login root mypass",
    "ensure": "ensure — 确保在 shell（可自动上电/登录）\n"
              "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 ensure",
    "keys": "keys <char> [dur秒] [interval秒] — 连续发键（抢 U-Boot 常用空格）\n"
            "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 keys ' ' 8 0.05",
    "ctrlc": "ctrlc — 发送 Ctrl+C\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 ctrlc",
    "write": "write <data> — 写原始字节/字符串\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 write 'help\\n'",
    "timestamp": "timestamp on|off — 日志时间戳\n"
                 "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 timestamp on",
    "reconnect": "reconnect — 重连通道\n"
                 "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 reconnect",
    "serial": "serial open|close — 仅 serial 通道\n"
              "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 serial open\n"
              "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 serial close",
    "reboot": "reboot / power_on / power_off — 需对应按钮为 +；无按钮用 soft-reboot\n"
              "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 reboot\n"
              "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 power_on\n"
              "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 soft-reboot",
    "uboot": "uboot — 仅 serial；重启并抢进 U-Boot\n"
             "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 90 uboot",
    "bootlog": "bootlog — 抓启动日志；-t 等待、-T 时间戳、-p 完成特征\n"
               "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 120 bootlog\n"
               "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 -t 180 -T -p login: bootlog",
    "download": "download [path] — 下载内存日志到本地文件\n"
                "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 download\n"
                "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 download ok3568.log",
    "help-url": "help-url — 打印 /help/<通道> 链接\n"
                "  例: eadk_board.py -B http://10.168.21.236:18081 -b ok3568 help-url",
    "feedback": "feedback <kind> <陈述...> — 推送建议/Bug 到飞书\n"
                "  kind: bug|建议|功能|suggest|feature；别名 suggest / bug\n"
                "  例: eadk_board.py feedback bug '串口 reconnect 后 log 为空'\n"
                "      eadk_board.py suggest '希望 bootlog 可自定义等待'\n"
                "      eadk_board.py -b ok3568 feedback 功能 '该板缺 xxx'",
    "suggest": "suggest <陈述...> — 同 feedback 建议\n"
               "  例: eadk_board.py suggest '希望…'",
    "bug": "bug <陈述...> — 同 feedback bug\n"
           "  例: eadk_board.py bug '现象与期望…'",
    "caps": "能力判定（必读）:\n"
            "  1) 先 scan 或 -b NAME list，只调用 + 项\n"
            "  2) ssh → -serial -uboot；键用 link=\n"
            "  3) /actions 无某按钮 → -reboot/-power_*；仍可用 soft-reboot/bootlog\n"
            "  4) serial + power_on + 无终端回显 → powered=no；run/ensure 可自动上电\n"
            "  5) connected=false → 先修串口/SSH，勿盲 run\n"
            "  例: eadk_board.py -B http://10.168.21.236:18081 scan\n"
            "      eadk_board.py -B http://10.168.21.236:18081 -b ok3568 list",
}


def usage() -> str:
    return """用法: eadk_board.py [全局选项] <子命令> [参数]
      eadk_board.py help [子命令|caps]

全局选项:
  -b NAME   通道名（默认 $EADK_BOARD）
  -B URL    桥 Base（默认 $EADK_BASE）
  -t SEC    超时秒；对 uboot/bootlog 即重启等待
  -T        bootlog/uboot 打开日志时间戳
  -p PAT    bootlog 完成特征（默认 login:）
  -j        scan/state/list/discover 输出 JSON
  -h        本摘要

推荐开场:
  eadk_board.py discover              # 局域网找桥
  eadk_board.py -B http://桥:端口 scan
  eadk_board.py -b <名> list          # 只看该板 +/-
  eadk_board.py -b <名> run 'uname -a'
  eadk_board.py -B http://桥:端口 put ./file.bin 板名/file.bin
  eadk_board.py feedback bug '现象...'

原始 HTTP: GET $BASE/help  /  GET $BASE/api/help
高阶 HTTP: GET /agent/probe|/agent/state|/agent/scan  POST /agent/exec
详细文档: $BASE/tftp/download?path=tools/eadk_board.md
"""


def cmd_help(topic: str = "") -> None:
    if not topic:
        print(usage())
        print("环境变量: EADK_BASE  EADK_BOARD  EADK_USER  EADK_PASS  EADK_PUT_CHUNK")
        print("          EADK_FEEDBACK_HOOK|FEISHU_HOOK  EADK_HOST")
        print("依赖: Python3 标准库；跨 Win/Linux")
        print("能力规则: eadk_board.py help caps")
        print("查看子命令: eadk_board.py help <子命令>")
        return
    if topic in HELP_TOPICS:
        print(HELP_TOPICS[topic])
        return
    if topic in ("reboot", "power_on", "power_off", "soft-reboot"):
        print(HELP_TOPICS["reboot"])
        return
    if topic in ("lan", "lan_discover"):
        print(HELP_TOPICS["discover"])
        return
    if topic in ("share_put", "upload"):
        print(HELP_TOPICS["put"])
        return
    raise Die(f"无此帮助主题: {topic}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-b", dest="board", default=DEFAULT_BOARD)
    p.add_argument("-B", dest="base", default=DEFAULT_BASE)
    p.add_argument("-t", dest="timeout", type=int, default=None)
    p.add_argument("-T", dest="want_ts", action="store_true")
    p.add_argument("-p", dest="done_pat", default="login:")
    p.add_argument("-j", "--json", dest="as_json", action="store_true")
    p.add_argument("-h", dest="show_help", action="store_true")
    args, rest = p.parse_known_args(argv)
    if args.show_help or not rest:
        cmd_help()
        return 0
    sub = rest[0]
    rest = rest[1:]
    timeout = 60
    reboot_wait_set = False
    if args.timeout is not None:
        timeout = args.timeout
        reboot_wait_set = True
    c = Client(
        base=args.base, board=args.board, timeout=timeout, reboot_wait=60,
        reboot_wait_set=reboot_wait_set, want_ts=args.want_ts, done_pat=args.done_pat,
        user=os.environ.get("EADK_USER", ""),
        passwd=os.environ.get("EADK_PASS", "") if "EADK_PASS" in os.environ else "",
        as_json=args.as_json,
    )

    try:
        if sub in ("help", "--help"):
            cmd_help(rest[0] if rest else "")
            return 0
        if sub == "list":
            if rest:
                c.board = rest[0]
                c.cmd_list_feats()
            elif "-b" in argv:
                c.cmd_list_feats()
            else:
                c.cmd_list_all()
            return 0
        if sub in ("feats", "features"):
            c.cmd_list_feats()
            return 0
        if sub == "scan":
            return c.cmd_scan(rest if rest else None)
        if sub in ("discover", "lan", "lan_discover"):
            return cmd_discover(rest, as_json=args.as_json)
        if sub == "put":
            if len(rest) < 2:
                raise Die("put <本地文件> <share相对路径> [chunk字节]")
            chunk = int(rest[2]) if len(rest) > 2 else 0
            c.cmd_put(rest[0], rest[1], chunk)
            return 0
        if sub == "status":
            c.cmd_status()
            return 0
        if sub == "log":
            c.cmd_log(rest)
            return 0
        if sub == "clear":
            c.cmd_clear()
            return 0
        if sub == "cmd":
            if not rest:
                raise Die("cmd <命令...>")
            c.cmd_cmd(" ".join(rest))
            return 0
        if sub == "exec":
            if not rest:
                raise Die("exec <命令...>")
            c.cmd_cmd(" ".join(rest))
            return 0
        if sub == "keys":
            if not rest:
                raise Die("keys <char> [dur] [interval]")
            dur = float(rest[1]) if len(rest) > 1 else 7.0
            interval = float(rest[2]) if len(rest) > 2 else 0.1
            c.cmd_keys(rest[0], dur, interval)
            return 0
        if sub == "ctrlc":
            c.cmd_ctrlc()
            return 0
        if sub == "write":
            if not rest:
                raise Die("write <data>")
            c.cmd_write(rest[0])
            return 0
        if sub == "timestamp":
            if not rest:
                raise Die("timestamp on|off")
            c.cmd_timestamp(rest[0])
            return 0
        if sub == "reconnect":
            c.cmd_reconnect()
            return 0
        if sub == "serial":
            if not rest:
                raise Die("serial open|close")
            c.cmd_serial(rest[0])
            return 0
        if sub == "reboot":
            c.cmd_action("reboot")
            return 0
        if sub == "power_on":
            c.cmd_action("power_on")
            return 0
        if sub == "power_off":
            c.cmd_action("power_off")
            return 0
        if sub == "soft-reboot":
            c.cmd_soft_reboot()
            return 0
        if sub == "uboot":
            c.cmd_uboot()
            return 0
        if sub == "bootlog":
            c.cmd_bootlog()
            return 0
        if sub == "probe":
            c.cmd_probe()
            return 0
        if sub == "health":
            return c.cmd_health()
        if sub == "state":
            if rest:
                c.board = rest[0]
                c.cmd_state_one()
            elif "-b" in argv:
                c.cmd_state_one()
            else:
                c.cmd_state_all()
            return 0
        if sub == "login":
            u = rest[0] if rest else ""
            pw = rest[1] if len(rest) > 1 else None
            c.cmd_login(u, pw)
            return 0
        if sub == "ensure":
            c.cmd_ensure()
            return 0
        if sub == "run":
            if not rest:
                raise Die("run <命令...>")
            c.cmd_run(" ".join(rest))
            return 0
        if sub == "download":
            c.cmd_download(rest[0] if rest else "")
            return 0
        if sub == "help-url":
            c.cmd_help_url()
            return 0
        if sub == "feedback":
            if len(rest) < 2:
                raise Die("feedback <kind> <陈述...>")
            c.cmd_feedback(rest[0], " ".join(rest[1:]))
            return 0
        if sub == "suggest":
            if not rest:
                raise Die("suggest <陈述...>")
            c.cmd_feedback("建议", " ".join(rest))
            return 0
        if sub == "bug":
            if not rest:
                raise Die("bug <陈述...>")
            c.cmd_feedback("bug", " ".join(rest))
            return 0
        raise Die(f"未知子命令: {sub} （见 eadk_board.py help）")
    except Die as e:
        print(f"error: {e}", file=sys.stderr)
        return int(getattr(e, "code", 1) or 1)
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1


if __name__ == "__main__":
    sys.exit(main())
