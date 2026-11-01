#include <iostream>
#include <string>
#include <vector>
#include <functional>
#include <chrono>
#include <iomanip>

enum class JobRunStatus { SCHEDULED, ACTIVE, PAUSED, COMPLETED, FAILED };

struct ScheduledJob {
    std::string jobName;
    int intervalSeconds;
    int executionCount;
    int maxRuns; // 0 for infinite
    JobRunStatus status;
    std::function<void()> taskCallback;

    ScheduledJob(std::string name, int interval, std::function<void()> cb, int maxR = 0)
        : jobName(std::move(name)), intervalSeconds(interval),
          executionCount(0), maxRuns(maxR), status(JobRunStatus::SCHEDULED),
          taskCallback(std::move(cb)) {}
};

class SimulatedCronScheduler {
private:
    std::vector<ScheduledJob> jobs;
    int simulatedClockSeconds;
    int totalDispatches;

public:
    SimulatedCronScheduler() : simulatedClockSeconds(0), totalDispatches(0) {}

    void registerJob(std::string name, int interval, std::function<void()> cb, int maxRuns = 0) {
        jobs.emplace_back(std::move(name), interval, std::move(cb), maxRuns);
    }

    bool pauseJob(const std::string& name) {
        for (auto& job : jobs) {
            if (job.jobName == name) {
                job.status = JobRunStatus::PAUSED;
                return true;
            }
        }
        return false;
    }

    bool resumeJob(const std::string& name) {
        for (auto& job : jobs) {
            if (job.jobName == name && job.status == JobRunStatus::PAUSED) {
                job.status = JobRunStatus::SCHEDULED;
                return true;
            }
        }
        return false;
    }

    bool cancelJob(const std::string& name) {
        for (auto it = jobs.begin(); it != jobs.end(); ++it) {
            if (it->jobName == name) {
                jobs.erase(it);
                return true;
            }
        }
        return false;
    }

    size_t getJobCount() const { return jobs.size(); }
    int getClock() const { return simulatedClockSeconds; }

    void advanceTime(int seconds) {
        for (int t = 1; t <= seconds; ++t) {
            simulatedClockSeconds++;
            for (auto& job : jobs) {
                if (job.status == JobRunStatus::PAUSED || job.status == JobRunStatus::COMPLETED) {
                    continue;
                }

                if (simulatedClockSeconds % job.intervalSeconds == 0) {
                    job.executionCount++;
                    totalDispatches++;
                    std::cout << "[CRON t=" << simulatedClockSeconds << "s] Triggered: " << job.jobName << "\n";
                    if (job.taskCallback) {
                        try {
                            job.taskCallback();
                        } catch (const std::exception& e) {
                            std::cerr << "  ERROR in job '" << job.jobName << "': " << e.what() << "\n";
                            job.status = JobRunStatus::FAILED;
                        }
                    }
                    if (job.maxRuns > 0 && job.executionCount >= job.maxRuns) {
                        job.status = JobRunStatus::COMPLETED;
                        std::cout << "  -> Job '" << job.jobName << "' completed all " << job.maxRuns << " runs.\n";
                    }
                }
            }
        }
    }

    void printSummary() const {
        std::cout << "\n================ CRON SCHEDULER SUMMARY ================\n";
        std::cout << "Simulated Clock   : " << simulatedClockSeconds << " seconds\n";
        std::cout << "Total Dispatches  : " << totalDispatches << "\n";
        for (const auto& job : jobs) {
            std::cout << "  Job: " << std::setw(20) << std::left << job.jobName
                      << " | Interval: " << std::setw(3) << job.intervalSeconds << "s"
                      << " | Runs: " << std::setw(3) << job.executionCount
                      << " | Status: " << statusToString(job.status) << "\n";
        }
        std::cout << "========================================================\n";
    }

private:
    static const char* statusToString(JobRunStatus s) {
        switch (s) {
            case JobRunStatus::SCHEDULED: return "SCHEDULED";
            case JobRunStatus::ACTIVE:    return "ACTIVE";
            case JobRunStatus::PAUSED:    return "PAUSED";
            case JobRunStatus::COMPLETED: return "COMPLETED";
            case JobRunStatus::FAILED:    return "FAILED";
            default: return "UNKNOWN";
        }
    }
};

int main() {
    SimulatedCronScheduler cron;
    cron.registerJob("CacheFlush", 5, []() { std::cout << "    -> Purged expired AST cache.\n"; });
    cron.registerJob("HeartbeatCheck", 10, []() { std::cout << "    -> Health check status: OK.\n"; });
    cron.registerJob("DailyBackup", 30, []() { std::cout << "    -> Incremental snapshot saved.\n"; });
    cron.registerJob("OneShotBootstrap", 2, []() { std::cout << "    -> System boot initialization executed.\n"; }, 1);

    std::cout << "Advancing Cron Scheduler by 15 seconds:\n";
    cron.advanceTime(15);
    cron.printSummary();

    std::cout << "\nPausing 'CacheFlush' and advancing 15 more seconds:\n";
    cron.pauseJob("CacheFlush");
    cron.advanceTime(15);
    cron.printSummary();

    std::cout << "\nCancelling 'HeartbeatCheck' and Resuming 'CacheFlush':\n";
    cron.cancelJob("HeartbeatCheck");
    cron.resumeJob("CacheFlush");
    cron.advanceTime(10);
    cron.printSummary();

    std::cout << "Scheduler Simulation Concluded. Final Clock: " << cron.getClock() << "s\n";
    std::cout << "Total Scheduled Jobs Active: " << cron.getJobCount() << "\n";

    return 0;
}
