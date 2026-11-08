"""u5-website, batch-6 part P1: the GPU route (US4.5; contract C6 `GET /api/v1/gpu`, schema `Gpu`).

AC4.5.9: `GET /api/v1/gpu` answers `available: true` with the figures `nvidia-smi` prints (a value it
reports as unavailable is null); given no `nvidia-smi`, a failing or slow one, or output that does not
parse, it answers 200 with `available: false` and a reason, never a 500.

No test calls the real `nvidia-smi`: `read_gpu(run=...)` gets a fake `run` callable, and the route test
replaces `gsm8k.service.gpu.read_gpu`. FastAPI's `TestClient` binds no port; everything runs on the CPU
with temp folders (`tmp_project_dirs`); nothing touches the project's outputs/ or results/runs.csv. The
service modules are imported inside each test, so a missing piece fails each test on its own.
"""

import subprocess
from types import SimpleNamespace

import pytest

API = "/api/v1"
GPU_KEYS = {
    "available",
    "reason",
    "name",
    "utilization_pct",
    "memory_used_mb",
    "memory_total_mb",
    "temperature_c",
    "power_w",
    "power_limit_w",
    "sm_clock_mhz",
    "sm_clock_max_mhz",
}
FIGURE_KEYS = sorted(GPU_KEYS - {"available", "reason"})
QUERY = (
    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,"
    "power.draw,power.limit,clocks.sm,clocks.max.sm"
)
NAME = "NVIDIA GeForce RTX 3070"
NORMAL = f"{NAME}, 97, 6043, 8192, 59, 162.43, 200.00, 1920, 2100\n"
NOT_FOUND = "nvidia-smi was not found"
TIMED_OUT = "nvidia-smi did not answer within 3 seconds"
UNREADABLE = "nvidia-smi printed output that could not be read"


# --- helpers ---------------------------------------------------------------------------------------


class FakeRun:
    """A stand-in for subprocess.run that records its calls and returns, or raises, what it is given."""

    def __init__(self, *, returncode=0, stdout="", stderr="", raises: BaseException | None = None):
        self.result = SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
        self.raises = raises
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((list(cmd), kwargs))
        if self.raises is not None:
            raise self.raises
        return self.result


def _read(**fake):
    """read_gpu with a fake run; returns (result, the fake)."""
    from gsm8k.service import gpu

    run = FakeRun(**fake)
    return gpu.read_gpu(run=run), run


def _assert_unavailable(result: dict, reason: str | None = None) -> None:
    assert set(result) == GPU_KEYS, sorted(result)
    assert result["available"] is False, result
    assert isinstance(result["reason"], str) and result["reason"].strip(), result
    if reason is not None:
        assert result["reason"] == reason
    for key in FIGURE_KEYS:
        assert result[key] is None, (key, result)


def _client(dirs):
    from fastapi.testclient import TestClient

    from gsm8k.service.app import create_app

    app = create_app(
        results=dirs.results, finalists=dirs.results.parent / "finalists.json", outputs=dirs.outputs
    )
    return TestClient(app)


# --- AC4.5.9: what is asked of nvidia-smi ------------------------------------------------------------


def test_AC4_5_9_asks_nvidia_smi_for_the_nine_figures_with_a_3_second_timeout():
    result, run = _read(stdout=NORMAL)
    assert result["available"] is True
    assert len(run.calls) == 1
    cmd, kwargs = run.calls[0]
    assert cmd == ["nvidia-smi", QUERY, "--format=csv,noheader,nounits"]
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True
    assert kwargs.get("timeout") == 3.0


def test_AC4_5_9_passes_a_given_timeout_to_the_command():
    from gsm8k.service import gpu

    run = FakeRun(stdout=NORMAL)
    gpu.read_gpu(run=run, timeout=1.5)
    assert run.calls[0][1].get("timeout") == 1.5


# --- AC4.5.9: a normal answer ------------------------------------------------------------------------


def test_AC4_5_9_reads_nvidia_smi_values():
    result, _ = _read(stdout=NORMAL)
    assert set(result) == GPU_KEYS, sorted(result)
    assert result["available"] is True
    assert result["reason"] is None
    assert result["name"] == NAME
    assert result["utilization_pct"] == 97.0
    assert result["memory_used_mb"] == 6043.0
    assert result["memory_total_mb"] == 8192.0
    assert result["temperature_c"] == 59.0
    assert result["power_w"] == pytest.approx(162.43)
    assert result["power_limit_w"] == 200.0
    assert result["sm_clock_mhz"] == 1920.0
    assert result["sm_clock_max_mhz"] == 2100.0


def test_AC4_5_9_numbers_are_floats():
    result, _ = _read(stdout=NORMAL)
    for key in FIGURE_KEYS:
        if key == "name":
            continue
        assert isinstance(result[key], float), (key, result[key])


def test_AC4_5_9_uses_the_first_non_empty_line_and_strips_the_cells():
    second = "NVIDIA GeForce GTX 1080, 5, 100, 8192, 40, 30.0, 180.0, 300, 1900\n"
    stdout = f"\n   \r\n\t{NAME} ,  97 ,6043,   8192,59 ,162.43,200.00 ,1920,2100  \r\n{second}"
    result, _ = _read(stdout=stdout)
    assert result["available"] is True
    assert result["name"] == NAME
    assert result["utilization_pct"] == 97.0
    assert result["memory_used_mb"] == 6043.0
    assert result["sm_clock_max_mhz"] == 2100.0


# --- AC4.5.9: a value nvidia-smi reports as unavailable is null --------------------------------------


@pytest.mark.parametrize("cell", ["[N/A]", "N/A", "[Not Supported]"])
def test_AC4_5_9_unavailable_cells_are_null(cell):
    stdout = f"{NAME}, 12, {cell}, 8192, {cell}, {cell}, {cell}, 1920, {cell}\n"
    result, _ = _read(stdout=stdout)
    assert set(result) == GPU_KEYS, sorted(result)
    assert result["available"] is True
    assert result["reason"] is None
    assert result["name"] == NAME
    assert result["utilization_pct"] == 12.0
    assert result["memory_total_mb"] == 8192.0
    assert result["sm_clock_mhz"] == 1920.0
    for key in ("memory_used_mb", "temperature_c", "power_w", "power_limit_w", "sm_clock_max_mhz"):
        assert result[key] is None, (key, result)


def test_AC4_5_9_a_not_available_power_draw_does_not_make_the_gpu_unavailable():
    stdout = f"{NAME}, 3, 512, 8192, 41, [N/A], [N/A], 210, 2100\n"
    result, _ = _read(stdout=stdout)
    assert result["available"] is True
    assert result["power_w"] is None and result["power_limit_w"] is None
    assert result["temperature_c"] == 41.0


# --- AC4.5.9: no nvidia-smi, a slow one, a failing one -----------------------------------------------


def test_AC4_5_9_missing_binary_is_unavailable_with_a_reason():
    result, _ = _read(raises=FileNotFoundError(2, "No such file or directory: 'nvidia-smi'"))
    _assert_unavailable(result, NOT_FOUND)


def test_AC4_5_9_timeout_is_unavailable_with_a_reason():
    result, _ = _read(raises=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=3.0))
    _assert_unavailable(result, TIMED_OUT)


def test_AC4_5_9_failing_exit_gives_the_first_line_of_stderr():
    stderr = (
        "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver.\n"
        "Make sure that the latest NVIDIA driver is installed and running.\n"
    )
    result, _ = _read(returncode=9, stderr=stderr)
    _assert_unavailable(
        result, "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
    )


def test_AC4_5_9_failing_exit_with_empty_stderr_gives_the_first_line_of_stdout():
    result, _ = _read(returncode=2, stdout="Unable to determine the device handle\nsecond line\n", stderr="")
    _assert_unavailable(result, "Unable to determine the device handle")


def test_AC4_5_9_failing_exit_without_any_text_names_the_exit_code():
    result, _ = _read(returncode=6, stdout="", stderr="")
    _assert_unavailable(result, "nvidia-smi failed (exit 6)")


def test_AC4_5_9_a_failing_exit_wins_over_output_that_would_parse():
    result, _ = _read(returncode=1, stdout=NORMAL, stderr="driver mismatch\n")
    _assert_unavailable(result, "driver mismatch")


# --- AC4.5.9: output that does not parse -------------------------------------------------------------


@pytest.mark.parametrize(
    "stdout",
    [
        "this is not csv at all\n",
        "NVIDIA GeForce RTX 3070, 97, 6043\n",  # three fields, not nine
        f"{NAME}, 97, 6043, 8192, 59, 162.43, 200.00, 1920\n",  # eight fields
        f"{NAME}, 97, 6043, 8192, 59, 162.43, 200.00, 1920, 2100, 7\n",  # ten fields
        f"{NAME}, busy, 6043, 8192, 59, 162.43, 200.00, 1920, 2100\n",  # utilisation is not a number
        "<?xml version='1.0'?><nvidia_smi_log></nvidia_smi_log>\n",
        "\x00\x01\x02 garbage, , , \n",
    ],
)
def test_AC4_5_9_garbage_output_is_unavailable_with_a_reason(stdout):
    result, _ = _read(returncode=0, stdout=stdout)
    _assert_unavailable(result, UNREADABLE)


@pytest.mark.parametrize("stdout", ["", "\n", "   \n\t\n\r\n"])
def test_AC4_5_9_empty_output_is_unavailable_with_a_reason(stdout):
    result, _ = _read(returncode=0, stdout=stdout)
    _assert_unavailable(result, UNREADABLE)


def test_AC4_5_9_read_gpu_never_raises():
    from gsm8k.service import gpu

    for raises in (
        FileNotFoundError("nvidia-smi"),
        subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=3.0),
        PermissionError(13, "Permission denied"),
        OSError("Exec format error"),
    ):
        result = gpu.read_gpu(run=FakeRun(raises=raises))
        _assert_unavailable(result)
    for returncode, stdout, stderr in ((0, "", ""), (1, "", ""), (0, "junk", ""), (127, "x", "y")):
        result = gpu.read_gpu(run=FakeRun(returncode=returncode, stdout=stdout, stderr=stderr))
        _assert_unavailable(result)


def test_AC4_5_9_an_available_answer_has_exactly_the_gpu_keys_and_no_figure_is_missing():
    result, _ = _read(stdout=NORMAL)
    assert set(result) == GPU_KEYS
    assert all(result[key] is not None for key in GPU_KEYS - {"reason"})


# --- AC4.5.9: GET /api/v1/gpu -------------------------------------------------------------------------


def test_AC4_5_9_route_returns_200_and_the_dict_when_available(tmp_project_dirs, monkeypatch):
    available = {
        "available": True,
        "reason": None,
        "name": NAME,
        "utilization_pct": 97.0,
        "memory_used_mb": 6043.0,
        "memory_total_mb": 8192.0,
        "temperature_c": 59.0,
        "power_w": 162.43,
        "power_limit_w": 200.0,
        "sm_clock_mhz": 1920.0,
        "sm_clock_max_mhz": 2100.0,
    }
    calls = []

    def fake_read_gpu(*args, **kwargs):
        calls.append((args, kwargs))
        return dict(available)

    monkeypatch.setattr("gsm8k.service.gpu.read_gpu", fake_read_gpu)
    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/gpu")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == available
    assert len(calls) == 1
    # Reading the GPU writes nothing.
    assert list(tmp_project_dirs.outputs.iterdir()) == []
    assert not tmp_project_dirs.results.exists()


def test_AC4_5_9_route_returns_200_and_the_dict_when_unavailable(tmp_project_dirs, monkeypatch):
    unavailable = {
        "available": False,
        "reason": NOT_FOUND,
        "name": None,
        "utilization_pct": None,
        "memory_used_mb": None,
        "memory_total_mb": None,
        "temperature_c": None,
        "power_w": None,
        "power_limit_w": None,
        "sm_clock_mhz": None,
        "sm_clock_max_mhz": None,
    }
    monkeypatch.setattr("gsm8k.service.gpu.read_gpu", lambda *args, **kwargs: dict(unavailable))
    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/gpu")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == unavailable
    assert set(body) == GPU_KEYS
    assert body["available"] is False and body["reason"] == NOT_FOUND


def test_AC4_5_9_route_gives_null_for_a_figure_nvidia_smi_does_not_report(tmp_project_dirs, monkeypatch):
    from gsm8k.service import gpu

    real_read_gpu = gpu.read_gpu
    run = FakeRun(stdout=f"{NAME}, 3, 512, 8192, 41, [N/A], [N/A], 210, 2100\n")
    monkeypatch.setattr("gsm8k.service.gpu.read_gpu", lambda *args, **kwargs: real_read_gpu(run=run))
    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/gpu")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True and body["name"] == NAME
    assert body["power_w"] is None and body["power_limit_w"] is None
    assert body["temperature_c"] == 41.0
    assert len(run.calls) == 1
