#!/usr/bin/env python3
"""模拟首屏/切项目并行 GET，检测是否超过前端 22s/28s 逾时（可在容器内跑）。"""
import concurrent.futures
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

THRESH_WARN = 22.0
THRESH_STUCK = 28.0


def req(base, method, path, body=None, headers=None):
    url = base + path
    data = None
    h = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    ctx = ssl.create_default_context() if base.startswith("https") else None
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(r, timeout=90, context=ctx) as resp:
            raw = resp.read()
            dt = time.perf_counter() - t0
            cookie = resp.headers.get("Set-Cookie") or ""
            return dt, resp.status, raw, cookie
    except urllib.error.HTTPError as e:
        dt = time.perf_counter() - t0
        return dt, e.code, e.read(), ""
    except Exception as e:
        dt = time.perf_counter() - t0
        return dt, -1, str(e).encode(), ""


def login(base):
    user = os.environ.get("APP_ADMIN_USER") or "admin"
    pw = os.environ.get("APP_ADMIN_PASSWORD") or os.environ.get("APP_LOGIN_PASSWORD") or ""
    if not pw:
        return None, "no password in env"
    dt, code, raw, cookie = req(
        base, "POST", "/api/auth/login", {"username": user, "password": pw}
    )
    if code != 200:
        return None, f"login {code} {raw[:200]!r}"
    sess = ""
    for chunk in cookie.replace(",", ";").split(";"):
        chunk = chunk.strip()
        if chunk.startswith("session="):
            sess = chunk
            break
    if not sess:
        return None, "no session cookie"
    return {"Cookie": sess}, f"login {dt:.2f}s"


def hit(base, hdr, label, path):
    dt, code, raw, _ = req(base, "GET", path, headers=hdr)
    ok = code == 200
    if ok:
        try:
            ok = json.loads(raw).get("success", True)
        except json.JSONDecodeError:
            ok = False
    flag = ""
    if dt >= THRESH_STUCK:
        flag = " STUCK?"
    elif dt >= THRESH_WARN:
        flag = " slow"
    return {"label": label, "sec": round(dt, 3), "code": code, "ok": ok, "flag": flag}


def heaviest_project_id():
    import sqlite3

    db = os.environ.get("DB_PATH") or "/data/qs_system.db"
    if not os.path.isfile(db):
        return None, 0
    conn = sqlite3.connect(db)
    row = conn.execute(
        """
        SELECT p.id, COUNT(pay.id) AS c
        FROM projects p
        LEFT JOIN payment_records pay ON pay.project_id = p.id
        GROUP BY p.id
        ORDER BY c DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    if not row:
        return None, 0
    return int(row[0]), int(row[1])


def run_suite(base, name):
    hdr, msg = login(base)
    print(f"\n=== {name} ({base}) {msg} ===")
    if not hdr:
        print("SKIP:", msg)
        return False
    _, code, raw, _ = req(base, "GET", "/api/projects", headers=hdr)
    if code != 200:
        print("projects failed", code)
        return False
    projects = json.loads(raw).get("data") or []
    ids = [p["id"] for p in projects]
    if not ids:
        print("no projects")
        return False
    heavy = max(ids)

    seq = [
        ("status", "/api/system/status"),
        ("auth/me", "/api/auth/me"),
        ("projects", "/api/projects"),
        ("portfolio/fac", "/api/portfolio/fac"),
        ("portfolio/progress", "/api/portfolio/progress"),
    ]
    print("-- sequential --")
    any_bad = False
    for lab, path in seq:
        r = hit(base, hdr, lab, path)
        any_bad = any_bad or (not r["ok"]) or r["sec"] >= THRESH_WARN
        print(f"  {r['sec']:6.3f}s {r['code']} {lab}{r['flag']}")

    pid = heavy
    for lab, path in [
        ("project", f"/api/projects/{pid}"),
        ("ip", f"/api/projects/{pid}/interim-payments"),
        ("summary", f"/api/reports/summary/{pid}"),
    ]:
        r = hit(base, hdr, lab, path)
        any_bad = any_bad or (not r["ok"]) or r["sec"] >= THRESH_WARN
        print(f"  {r['sec']:6.3f}s {r['code']} {lab} (pid={pid}){r['flag']}")

    print("-- portfolio/fac cache --")
    for i in (1, 2):
        r = hit(base, hdr, f"fac#{i}", "/api/portfolio/fac")
        print(f"  {r['sec']:6.3f}s fac#{i}{r['flag']}")

    tasks = []
    for p in ids[:5]:
        tasks.extend([
            (f"p{p}/proj", f"/api/projects/{p}"),
            (f"p{p}/ip", f"/api/projects/{p}/interim-payments"),
            (f"p{p}/sum", f"/api/reports/summary/{p}"),
        ])
    tasks += [("fac", "/api/portfolio/fac"), ("prog", "/api/portfolio/progress")]
    print(f"-- parallel x{len(tasks)} --")
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(lambda t: hit(base, hdr, t[0], t[1]), tasks))
    wall = time.perf_counter() - t0
    max_r = max(results, key=lambda x: x["sec"])
    slow = [r for r in results if r["sec"] >= THRESH_WARN or not r["ok"]]
    print(f"  wall {wall:.2f}s; max {max_r['sec']}s ({max_r['label']})")
    if slow:
        any_bad = True
        for r in sorted(slow, key=lambda x: -x["sec"])[:10]:
            print(f"    {r['sec']}s {r['label']} code={r['code']}{r['flag']}")
    else:
        print("  all OK under 22s")

    hid, hpays = heaviest_project_id()
    if hid:
        print(f"-- heaviest project id={hid} payments={hpays} --")
        for lab, path in [
            ("h/proj", f"/api/projects/{hid}"),
            ("h/ip", f"/api/projects/{hid}/interim-payments"),
            ("h/summary", f"/api/reports/summary/{hid}"),
            ("h/payments", f"/api/projects/{hid}/payments"),
            ("h/dash", f"/api/projects/{hid}/dashboard-overview?lite=1"),
        ]:
            r = hit(base, hdr, lab, path)
            any_bad = any_bad or (not r["ok"]) or r["sec"] >= THRESH_WARN
            print(f"  {r['sec']:6.3f}s {r['code']} {lab}{r['flag']}")

    print("-- stress: all projects summary sequential --")
    t0 = time.perf_counter()
    worst = 0.0
    worst_id = None
    for pid in ids:
        r = hit(base, hdr, f"sum/{pid}", f"/api/reports/summary/{pid}")
        if r["sec"] > worst:
            worst = r["sec"]
            worst_id = pid
        if not r["ok"] or r["sec"] >= THRESH_WARN:
            any_bad = True
            print(f"  {r['sec']:6.3f}s pid={pid}{r['flag']}")
    total = time.perf_counter() - t0
    print(f"  {len(ids)} projects in {total:.2f}s; worst {worst:.3f}s (pid={worst_id})")

    print("-- stress: 30x parallel /api/projects --")
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        burst = list(
            ex.map(
                lambda i: hit(base, hdr, f"proj{i}", "/api/projects"),
                range(30),
            )
        )
    wall = time.perf_counter() - t0
    max_r = max(burst, key=lambda x: x["sec"])
    fails = [r for r in burst if not r["ok"] or r["sec"] >= THRESH_WARN]
    print(f"  wall {wall:.2f}s max {max_r['sec']}s fails={len(fails)}")
    if fails:
        any_bad = True

    return not any_bad


def main():
    bases = sys.argv[1:] or ["http://127.0.0.1:8080", "https://mossys.xyz"]
    ok = True
    for b in bases:
        if not run_suite(b, b):
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
