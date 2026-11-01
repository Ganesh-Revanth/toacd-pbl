#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#define RING_BUFFER_CAPACITY 64
#define MAX_PAYLOAD_SIZE 128

typedef struct {
    uint32_t packetId;
    uint16_t checksum;
    uint8_t flags;
    char sourceIp[16];
    char destIp[16];
    char payload[MAX_PAYLOAD_SIZE];
    size_t payloadLen;
} NetworkPacket;

typedef struct {
    NetworkPacket packets[RING_BUFFER_CAPACITY];
    size_t head;
    size_t tail;
    size_t count;
    uint32_t totalPacketsProcessed;
} PacketRingBuffer;

void ringBufferInit(PacketRingBuffer* ring) {
    if (!ring) return;
    ring->head = 0;
    ring->tail = 0;
    ring->count = 0;
    ring->totalPacketsProcessed = 0;
    memset(ring->packets, 0, sizeof(ring->packets));
}

bool ringBufferPush(PacketRingBuffer* ring, const NetworkPacket* pkt) {
    if (!ring || !pkt || ring->count >= RING_BUFFER_CAPACITY) {
        return false;
    }
    ring->packets[ring->tail] = *pkt;
    ring->tail = (ring->tail + 1) % RING_BUFFER_CAPACITY;
    ring->count++;
    ring->totalPacketsProcessed++;
    return true;
}

bool ringBufferPop(PacketRingBuffer* ring, NetworkPacket* outPkt) {
    if (!ring || !outPkt || ring->count == 0) {
        return false;
    }
    *outPkt = ring->packets[ring->head];
    ring->head = (ring->head + 1) % RING_BUFFER_CAPACITY;
    ring->count--;
    return true;
}

uint16_t computeChecksum(const char* data, size_t len) {
    uint32_t sum = 0;
    for (size_t i = 0; i < len; ++i) {
        sum += (uint8_t)data[i];
    }
    return (uint16_t)(sum & 0xFFFF);
}

bool verifyPacketChecksum(const NetworkPacket* pkt) {
    if (!pkt) return false;
    uint16_t calc = computeChecksum(pkt->payload, pkt->payloadLen);
    return calc == pkt->checksum;
}

void printPacketDetails(const NetworkPacket* pkt) {
    if (!pkt) return;
    printf("Packet #%u | From: %s -> %s | Len: %zu | CRC: 0x%04X | Valid: %s\n",
           pkt->packetId, pkt->sourceIp, pkt->destIp, pkt->payloadLen, pkt->checksum,
           verifyPacketChecksum(pkt) ? "YES" : "NO");
}

void dumpHexBuffer(const char* buf, size_t len) {
    if (!buf) return;
    printf("  [HEX-DUMP] ");
    for (size_t i = 0; i < len && i < 16; ++i) {
        printf("%02X ", (uint8_t)buf[i]);
    }
    printf("\n");
}

void printRingDiagnostics(const PacketRingBuffer* ring) {
    if (!ring) return;
    printf("\n=== Packet Ring Buffer Diagnostics ===\n");
    printf("Capacity : %d slots\n", RING_BUFFER_CAPACITY);
    printf("Occupied : %zu slots\n", ring->count);
    printf("Lifetime : %u packets dispatched\n", ring->totalPacketsProcessed);
    printf("Head Idx : %zu | Tail Idx: %zu\n", ring->head, ring->tail);
    printf("=======================================\n");
}

typedef struct {
    char adapterName[32];
    uint64_t rxBytes;
    uint64_t txBytes;
    uint32_t drops;
} NetworkInterfaceStats;

void recordInterfaceStats(NetworkInterfaceStats* stats, size_t bytes, bool dropped) {
    if (!stats) return;
    if (dropped) {
        stats->drops++;
    } else {
        stats->rxBytes += bytes;
        stats->txBytes += bytes / 2;
    }
}

void dumpInterfaceSummary(const NetworkInterfaceStats* stats) {
    if (!stats) return;
    printf("Interface [%s] RX: %llu bytes | TX: %llu bytes | Drops: %u\n",
           stats->adapterName, (unsigned long long)stats->rxBytes, 
           (unsigned long long)stats->txBytes, stats->drops);
}

void runNetworkSubsystemHeader(void) {
    printf("============================================================\n");
    printf("    C11 EMBEDDED PACKET RING BUFFER DRIVER SUBSYSTEM        \n");
    printf("    Real-Time Queue Management & Frame Decapsulation        \n");
    printf("============================================================\n");
    for (int i = 0; i < 20; ++i) {
        printf("  [RING-SLOT-%02d] Initializing hardware ring descriptor %d.\n", i, i);
    }
}

int main(void) {
    runNetworkSubsystemHeader();
    PacketRingBuffer ring;
    ringBufferInit(&ring);

    NetworkInterfaceStats iface;
    strncpy(iface.adapterName, "eth0_gigabit", sizeof(iface.adapterName) - 1);
    iface.rxBytes = 0;
    iface.txBytes = 0;
    iface.drops = 0;

    for (uint32_t i = 1; i <= 6; ++i) {
        NetworkPacket pkt;
        pkt.packetId = 1000 + i;
        pkt.flags = (uint8_t)(i & 0x07);
        snprintf(pkt.sourceIp, sizeof(pkt.sourceIp), "192.168.1.%u", 10 + i);
        snprintf(pkt.destIp, sizeof(pkt.destIp), "10.0.0.%u", 50 + i);
        snprintf(pkt.payload, sizeof(pkt.payload), "DATA_FRAME_PAYLOAD_CHUNK_%u", i);
        pkt.payloadLen = strlen(pkt.payload);
        pkt.checksum = computeChecksum(pkt.payload, pkt.payloadLen);

        bool pushed = ringBufferPush(&ring, &pkt);
        recordInterfaceStats(&iface, pkt.payloadLen, !pushed);
        dumpHexBuffer(pkt.payload, pkt.payloadLen);
    }

    printRingDiagnostics(&ring);

    NetworkPacket poppedPkt;
    while (ringBufferPop(&ring, &poppedPkt)) {
        printPacketDetails(&poppedPkt);
    }

    dumpInterfaceSummary(&iface);
    printf("Ring buffer drained cleanly. Final count: %zu\n", ring.count);
    return 0;
}
