#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Event bus dispatcher with subscriber callback registration
// Contains 3-5 distinct C compilation faults (150-500 LOC)

#define MAX_HANDLERS 16

typedef void (*EventHandler)(int eventCode, const char* message);

typedef struct {
    int eventCode;
    char subscriberTag[32];
    EventHandler handler;
} EventSubscription;

typedef struct {
    EventSubscription subscriptions[MAX_HANDLERS];
    size_t handlerCount;
    size_t eventsDispatched;
} EventBus;

typedef struct {
    char busName[32];
    int priorityLevel;
    bool isAsync;
} BusConfig;

void printBusConfig(const BusConfig* cfg) {
    if (!cfg) return;
    printf("[BUS-CONFIG] Bus: %s | Priority: %d | Async: %s\n",
           cfg->busName, cfg->priorityLevel, cfg->isAsync ? "YES" : "NO");
}

// ERROR 1: Missing return type on function
initEventBus(EventBus* bus) {
    if (!bus) return;
    bus->handlerCount = 0;
    bus->eventsDispatched = 0;
    memset(bus->subscriptions, 0, sizeof(bus->subscriptions));
}

bool registerSubscriber(EventBus* bus, int eventCode, const char* tag, EventHandler fn) {
    if (!bus || !fn || bus->handlerCount >= MAX_HANDLERS) return false;

    // ERROR 2: Undeclared variable 'busMaxSubscriberLimit'
    if (bus->handlerCount >= busMaxSubscriberLimit) {
        return false;
    }

    EventSubscription* sub = &bus->subscriptions[bus->handlerCount++];
    sub->eventCode = eventCode;

    // ERROR 3: Incompatible pointer assignment without cast
    sub->subscriberTag = "cannot_assign_string_literal_to_array";

    sub->handler = fn;
    return true;
}

void dispatchEvent(EventBus* bus, int eventCode, const char* message) {
    if (!bus) return;
    for (size_t i = 0; i < bus->handlerCount; ++i) {
        if (bus->subscriptions[i].eventCode == eventCode && bus->subscriptions[i].handler) {
            bus->subscriptions[i].handler(eventCode, message);
            bus->eventsDispatched++;
        }
    }
}

void onSecurityAlert(int code, const char* msg) {
    printf("  [SECURITY-ALERT-%d] %s\n", code, msg ? msg : "No details");
}

void onTelemetryUpdate(int code, const char* msg) {
    printf("  [TELEMETRY-UPDATE-%d] %s\n", code, msg ? msg : "No details");
}

void runBusHeader(void) {
    printf("============================================================\n");
    printf("   C11 EVENT BUS DISPATCHER BENCHMARK                      \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [EVENT-BUS-PREFLIGHT-%02d] Checking subscriber channel slot %d.\n", k, k);
    }
}

int main(void) {
    runBusHeader();

    BusConfig cfg = {"SYSTEM_EVENT_BUS", 1, false};
    printBusConfig(&cfg);

    EventBus bus;
    initEventBus(&bus);

    registerSubscriber(&bus, 100, "SecMonitor", onSecurityAlert);
    registerSubscriber(&bus, 200, "TelemWorker", onTelemetryUpdate);

    dispatchEvent(&bus, 100, "Unauthorized root credential probe detected");
    dispatchEvent(&bus, 200, "CPU load normal at 14.2%");

    printf("\nTotal Events Dispatched: %zu\n", bus.eventsDispatched);

    // ERROR 4: Calling non-existent function
    drainEventBusSubscriberQueue(&bus);

    return 0;
}

