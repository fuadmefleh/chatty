import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.web import state
from src.web.auth import require_api_key

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {"service": "chatty-web-api", "status": "ok", "version": "1.0.0"}


@router.get("/api/chatty/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Server Health (CPU, RAM, Disk, GPU) ──────────────────────────────────────
def _get_gpu_info() -> list[dict]:
    """Query NVIDIA GPUs via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.used,memory.total,utilization.gpu,"
             "utilization.memory,temperature.gpu,power.draw,power.limit,"
             "clocks.gr,clocks.mem,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 10:
                gpus.append({
                    "name": parts[0],
                    "memory_used_miB": _parse_int(parts[1]),
                    "memory_total_miB": _parse_int(parts[2]),
                    "gpu_util_percent": _parse_float(parts[3]),
                    "mem_util_percent": _parse_float(parts[4]),
                    "temperature_c": _parse_float(parts[5]),
                    "power_draw_w": _parse_float(parts[6]),
                    "power_limit_w": _parse_float(parts[7]),
                    "clock_gr_mhz": _parse_int(parts[8]),
                    "clock_mem_mhz": _parse_int(parts[9]),
                    "driver_version": parts[10] if len(parts) > 10 else "unknown",
                })
        return gpus
    except Exception:
        return []


def _parse_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _parse_float(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


@router.get("/api/chatty/health/server", dependencies=[Depends(require_api_key)])
async def server_health():
    """Return server resource metrics: CPU, RAM, disk, GPU, load, uptime."""
    import psutil

    # CPU
    cpu_logical = psutil.cpu_count(logical=True)
    cpu_physical = psutil.cpu_count(logical=False)
    cpu_percent = psutil.cpu_percent(interval=0.1)
    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
    load_avg = {}  # type: dict[str, float]
    try:
        la = psutil.getloadavg()
        load_avg = {"1m": la[0], "5m": la[1], "15m": la[2]}
    except (OSError, AttributeError):
        pass

    # RAM
    vm = psutil.virtual_memory()
    ram = {
        "total_bytes": vm.total,
        "used_bytes": vm.used,
        "available_bytes": vm.available,
        "percent": vm.percent,
    }

    # Swap
    swap = psutil.swap_memory()
    swap_info = {
        "total_bytes": swap.total,
        "used_bytes": swap.used,
        "percent": swap.percent,
    }

    # Disk partitions (skip squashfs snap mounts - noise, not real filesystems)
    disks = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype == "squashfs" or part.mountpoint.startswith("/snap/"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent": usage.percent,
            })
        except PermissionError:
            pass

    # Network I/O counters (snapshot)
    net = psutil.net_io_counters()
    network = {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
    }

    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = (datetime.now() - boot_time).total_seconds()

    # GPU
    gpus = _get_gpu_info()

    return {
        "cpu": {
            "logical_cores": cpu_logical,
            "physical_cores": cpu_physical,
            "overall_percent": cpu_percent,
            "per_core_percent": per_cpu,
            "load_average": load_avg,
        },
        "memory": ram,
        "swap": swap_info,
        "disks": disks,
        "network": network,
        "gpus": gpus,
        "boot_time": boot_time.isoformat(),
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _get_storage_breakdown(mountpoint: str, depth: int = 1) -> list[dict]:
    """Walk a mountpoint's directories up to `depth` levels and return sizes.

    Uses `du` for speed rather than Python's os.walk (which is much slower for
    large filesystems). Returns a list of {"path", "size_bytes", "depth"} dicts
    sorted by size descending.
    """
    results: list[dict] = []
    mpath = Path(mountpoint)
    if not mpath.exists():
        return results

    try:
        # du -B1 gives byte-precision; --max-depth controls recursion
        # Using absolute glob paths avoids issues with du and relative paths
        if depth == 0:
            # Just the mountpoint total
            result = subprocess.run(
                ["du", "-B1", str(mpath)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                line = result.stdout.strip().splitlines()[-1]
                parts = line.split("\t")
                if len(parts) == 2:
                    results.append({
                        "path": parts[1],
                        "size_bytes": int(parts[0]),
                        "depth": 0,
                    })
        else:
            result = subprocess.run(
                ["du", "-B1", f"--max-depth={depth}", str(mpath)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) == 2:
                        p = parts[1]
                        # Calculate depth relative to mountpoint
                        rel = Path(p).relative_to(mpath) if Path(p).is_relative_to(mpath) else Path(p)
                        d = len(rel.parts)
                        results.append({
                            "path": p,
                            "size_bytes": int(parts[0]),
                            "depth": d,
                        })
        # Sort by size descending, but put the root mountpoint first
        results.sort(key=lambda r: (0 if r["path"] == mountpoint else 1, -r["size_bytes"]))
    except (subprocess.TimeoutExpired, Exception) as e:
        state.logger.warning(f"Storage breakdown failed for {mountpoint}: {e}")

    return results


@router.get("/api/chatty/health/storage-breakdown", dependencies=[Depends(require_api_key)])
async def storage_breakdown(
    mountpoint: Optional[str] = Query(default=None),
    depth: int = Query(default=1, ge=0, le=3),
):
    """Return a breakdown of disk usage by directory.

    Without `mountpoint`, returns the top-level directories for all non-snap
    partitions. With `mountpoint`, returns directories under that specific
    mount. `depth` controls recursion (0 = mount total only, 1 = immediate
    children, 2 = grand-children, etc.).
    """
    import psutil

    partitions_to_scan: list[str] = []
    if mountpoint:
        partitions_to_scan = [mountpoint]
    else:
        for part in psutil.disk_partitions(all=False):
            if part.fstype == "squashfs" or part.mountpoint.startswith("/snap/"):
                continue
            partitions_to_scan.append(part.mountpoint)

    breakdown: list[dict] = []
    for mp in partitions_to_scan:
        entries = _get_storage_breakdown(mp, depth=depth)
        for entry in entries:
            entry["mountpoint"] = mp
            entry["path_display"] = entry["path"]
            breakdown.append(entry)

    return {
        "mountpoints": partitions_to_scan,
        "depth": depth,
        "entries": breakdown,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/api/chatty/token-usage/summary", dependencies=[Depends(require_api_key)])
async def token_usage_summary(days: int = 30):
    """Return aggregate LLM token usage: totals, per-model/provider breakdown, daily series."""
    return state.token_usage_manager.get_summary(days=days)


@router.get("/api/chatty/token-usage/recent", dependencies=[Depends(require_api_key)])
async def token_usage_recent(limit: int = 50):
    """Return the most recent individual LLM requests logged."""
    return state.token_usage_manager.get_recent(limit=limit)
