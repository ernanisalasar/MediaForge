import threading
import time

from mediaforge.errors import DownloadError, OperationCancelled
from mediaforge.models.task import ProgressInfo, Task, TaskKind, TaskStatus
from mediaforge.services.task_manager import TaskManager


def wait_until(cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_success_with_progress(tmp_path):
    out = tmp_path / "r.mp4"
    out.write_bytes(b"12345")
    updates, finished = [], []
    tm = TaskManager(on_update=lambda t: updates.append((t.status, t.progress)), on_finished=finished.append)

    def job(task, report):
        time.sleep(0.15)  # passa o intervalo de limitação de notificações (100 ms)
        report(ProgressInfo(fraction=0.5, speed_bps=100.0))
        return out

    t = tm.submit(Task(TaskKind.CONVERT, "x"), job)
    assert wait_until(lambda: t.status is TaskStatus.COMPLETED)
    assert t.output_path == out and t.size_bytes == 5 and t.progress == 1.0
    assert (TaskStatus.RUNNING, 0.5) in updates
    assert finished == [t]
    tm.shutdown()


def test_failure_message_and_unexpected_error():
    tm = TaskManager()

    def bad(task, report):
        raise DownloadError("falha de rede")

    def boom(task, report):
        raise RuntimeError("bug")

    a = tm.submit(Task(TaskKind.DOWNLOAD, "a"), bad)
    b = tm.submit(Task(TaskKind.DOWNLOAD, "b"), boom)
    assert wait_until(lambda: a.status.is_final and b.status.is_final)
    assert a.status is TaskStatus.FAILED and a.message == "falha de rede"
    assert b.status is TaskStatus.FAILED and "RuntimeError" in b.message
    tm.shutdown()


def test_cancel_running_task():
    tm = TaskManager()
    started = threading.Event()

    def job(task, report):
        started.set()
        while not task.cancel_event.wait(0.02):
            pass
        raise OperationCancelled("x")

    t = tm.submit(Task(TaskKind.CONVERT, "x"), job)
    assert started.wait(3)
    tm.cancel(t.id)
    assert wait_until(lambda: t.status is TaskStatus.CANCELLED)
    tm.shutdown()


def test_cancel_waiting_task_never_runs():
    tm = TaskManager(max_workers=1)
    release = threading.Event()
    ran = []

    def blocker(task, report):
        release.wait(5)

    tm.submit(Task(TaskKind.CONVERT, "bloqueio"), blocker)
    waiting = tm.submit(Task(TaskKind.CONVERT, "espera"), lambda t, r: ran.append(1))
    assert waiting.status is TaskStatus.WAITING
    tm.cancel(waiting.id)
    assert waiting.status is TaskStatus.CANCELLED
    release.set()
    time.sleep(0.3)
    assert ran == [] and waiting.status is TaskStatus.CANCELLED
    tm.shutdown()


def test_queue_runs_in_order_with_single_worker():
    tm = TaskManager(max_workers=1)
    order = []
    tasks = [tm.submit(Task(TaskKind.CONVERT, str(i)), lambda t, r, i=i: order.append(i)) for i in range(4)]
    assert wait_until(lambda: all(t.status.is_final for t in tasks))
    assert order == [0, 1, 2, 3]
    tm.shutdown()


def test_callback_exceptions_do_not_break_queue():
    def explode(task):
        raise ValueError("ui quebrou")

    tm = TaskManager(on_update=explode, on_finished=explode)
    t = tm.submit(Task(TaskKind.CONVERT, "x"), lambda task, r: None)
    assert wait_until(lambda: t.status is TaskStatus.COMPLETED)
    tm.shutdown()
