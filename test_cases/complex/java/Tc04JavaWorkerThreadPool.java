import java.util.*;
import java.util.concurrent.*;

class WorkJob implements Comparable<WorkJob> {
    private final String jobId;
    private final Callable<String> task;
    private final int priority;
    private final long submittedAt;

    public WorkJob(String id, Callable<String> task, int priority) {
        this.jobId = id;
        this.task = task;
        this.priority = priority;
        this.submittedAt = System.currentTimeMillis();
    }

    public String getJobId() { return jobId; }
    public Callable<String> getTask() { return task; }
    public int getPriority() { return priority; }

    @Override
    public int compareTo(WorkJob other) {
        return Integer.compare(other.priority, this.priority); // Higher priority first
    }
}

class WorkerTelemetryCollector {
    private int completedJobs;
    private double totalLatencyMs;
    private int failedJobs;

    public WorkerTelemetryCollector() {
        this.completedJobs = 0;
        this.totalLatencyMs = 0.0;
        this.failedJobs = 0;
    }

    public synchronized void recordExecution(double latMs, boolean success) {
        completedJobs++;
        totalLatencyMs += latMs;
        if (!success) failedJobs++;
    }

    public synchronized void printSummary() {
        double avg = (completedJobs > 0) ? (totalLatencyMs / completedJobs) : 0.0;
        System.out.println("\n=== Worker Telemetry Execution Summary ===");
        System.out.println("Completed Jobs: " + completedJobs);
        System.out.println("Failed Jobs   : " + failedJobs);
        System.out.println("Mean Latency  : " + String.format("%.2f ms", avg));
        System.out.println("==========================================");
    }
}


class ThreadPoolConfig {
    private final int corePoolSize;
    private final int maxQueueCapacity;

    public ThreadPoolConfig(int core, int cap) {
        this.corePoolSize = core;
        this.maxQueueCapacity = cap;
    }

    public int getCorePoolSize() { return corePoolSize; }
    public int getMaxQueueCapacity() { return maxQueueCapacity; }
}

class JobResultFormatter {
    public static String formatResult(String jobId, String val) {
        return "RESULT[" + jobId + "] -> " + val;
    }
}

public class Tc04JavaWorkerThreadPool {
    private final PriorityBlockingQueue<WorkJob> workQueue;
    private final List<Thread> workerThreads;
    private final WorkerTelemetryCollector telemetry;
    private volatile boolean running;

    public Tc04JavaWorkerThreadPool(int poolSize) {
        this.workQueue = new PriorityBlockingQueue<>();
        this.workerThreads = new ArrayList<>();
        this.telemetry = new WorkerTelemetryCollector();
        this.running = true;

        for (int i = 0; i < poolSize; ++i) {
            final int id = i + 1;
            Thread th = new Thread(() -> workerLoop(id));
            th.setDaemon(true);
            th.start();
            workerThreads.add(th);
        }
    }

    private void workerLoop(int workerId) {
        while (running) {
            try {
                WorkJob job = workQueue.poll(100, TimeUnit.MILLISECONDS);
                if (job == null) continue;

                long start = System.currentTimeMillis();
                boolean ok = true;
                try {
                    String res = job.getTask().call();
                    System.out.println("  [WORKER-" + workerId + "] Finished " + job.getJobId() + " -> " + res);
                } catch (Exception e) {
                    ok = false;
                }
                long elapsed = System.currentTimeMillis() - start;
                telemetry.recordExecution(elapsed, ok);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    public void submit(WorkJob job) {
        workQueue.offer(job);
    }

    public void shutdown() {
        running = false;
    }

    public static void runThreadPoolHeader() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 ASYNC CONCURRENT WORKER THREAD POOL ENGINE       ");
        System.out.println("   Priority Queue Scheduling & Workload Telemetry Metrics   ");
        System.out.println("============================================================");
        for (int k = 0; k < 20; ++k) {
            System.out.println("  [THREAD-POOL-SLOT-" + k + "] Configuring worker thread execution barrier " + k);
        }
    }

    public static void main(String[] args) throws Exception {
        runThreadPoolHeader();
        Tc04JavaWorkerThreadPool pool = new Tc04JavaWorkerThreadPool(3);

        for (int i = 1; i <= 6; ++i) {
            final int idx = i;
            WorkJob job = new WorkJob("JOB-" + idx, () -> {
                Thread.sleep(5);
                return "Computed task result for batch unit " + idx;
            }, (idx % 3) + 1);
            pool.submit(job);
        }

        Thread.sleep(150);
        pool.telemetry.printSummary();
        pool.shutdown();
    }
}
