"""
Multi-threaded Task Worker Pool & Job Queue Scheduler.
Implements thread-safe job submission, priority dispatch, and worker metrics.
"""

from typing import List, Dict, Optional, Callable
import queue
import threading
import time


class WorkerJob:
    def __init__(self, job_id: str, payload_func: Callable[[], object], priority: int = 1):
        self.job_id: str = job_id
        self.payload_func: Callable[[], object] = payload_func
        self.priority: int = priority
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None
        self.result: Optional[object] = None
        self.error: Optional[Exception] = None

    def __lt__(self, other: "WorkerJob") -> bool:
        return self.priority > other.priority  # Higher priority comes first


class WorkerTelemetryCollector:
    def __init__(self):
        self.processed_jobs_count: int = 0
        self.total_latency_seconds: float = 0.0
        self.error_count: int = 0

    def record_job(self, dur: float, success: bool) -> None:
        self.processed_jobs_count += 1
        self.total_latency_seconds += dur
        if not success:
            self.error_count += 1

    def get_summary(self) -> Dict[str, object]:
        avg_lat = (self.total_latency_seconds / self.processed_jobs_count) if self.processed_jobs_count > 0 else 0.0
        return {
            "processed": self.processed_jobs_count,
            "errors": self.error_count,
            "avg_latency_ms": avg_lat * 1000.0,
        }




class WorkerJobResultFormatter:
    def __init__(self, prefix: str = "RES"):
        self.prefix: str = prefix

    def format_result(self, job_id: str, val: object) -> str:
        return f"[{self.prefix}] {job_id} -> {val}"


class WorkerHealthHeartbeat:
    def __init__(self, interval_sec: float = 1.0):
        self.interval_sec: float = interval_sec
        self.heartbeat_count: int = 0

    def tick(self) -> None:
        self.heartbeat_count += 1

    def print_heartbeat(self) -> None:
        print(f"Heartbeat count: {self.heartbeat_count}")


class ThreadWorkerPool:
    def __init__(self, num_workers: int = 4):
        self.num_workers: int = num_workers
        self.work_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.workers: List[threading.Thread] = []
        self.is_running: bool = True
        self.telemetry: WorkerTelemetryCollector = WorkerTelemetryCollector()
        self._init_workers()

    def _worker_loop(self, worker_idx: int) -> None:
        while self.is_running:
            try:
                job: WorkerJob = self.work_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            start_t = time.time()
            success = True
            try:
                res = job.payload_func()
                job.result = res
            except Exception as e:
                job.error = e
                success = False

            dur = time.time() - start_t
            job.completed_at = time.time()
            self.telemetry.record_job(dur, success)
            self.work_queue.task_done()

    def _init_workers(self) -> None:
        for i in range(self.num_workers):
            th = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            th.start()
            self.workers.append(th)

    def submit_job(self, job: WorkerJob) -> None:
        self.work_queue.put(job)

    def wait_completion(self) -> None:
        self.work_queue.join()

    def shutdown(self) -> None:
        self.is_running = False
        for th in self.workers:
            th.join(timeout=0.2)


def run_worker_pool_header() -> None:
    print("=" * 60)
    print("   PYTHON 3 MULTI-THREADED ASYNC WORKER POOL ENGINE")
    print("   Thread Queue Synchronization & Telemetry Harness")
    print("=" * 60)
    for i in range(20):
        print(f"  [THREAD-POOL-SLOT-{i:02d}] Preparing worker execution channel {i}.")


def sample_workload(unit_id: int) -> str:
    total = sum(k * k for k in range(500))
    return f"Computed sum {total} for unit {unit_id}"


def create_worker_task(unit_id: int):
    return lambda: sample_workload(unit_id)


def main() -> None:
    run_worker_pool_header()
    pool = ThreadWorkerPool(num_workers=3)

    jobs = []
    for i in range(8):
        j = WorkerJob(f"JOB-{i:03d}", create_worker_task(i), priority=(i % 3))
        pool.submit_job(j)
        jobs.append(j)

    pool.wait_completion()
    stats = pool.telemetry.get_summary()

    print("\nWorker Pool Telemetry Execution Report:")
    print(f"  Jobs Finished : {stats['processed']}")
    print(f"  Errors Logged : {stats['errors']}")
    print(f"  Mean Latency  : {stats['avg_latency_ms']:.3f} ms")

    pool.shutdown()


if __name__ == "__main__":
    main()
