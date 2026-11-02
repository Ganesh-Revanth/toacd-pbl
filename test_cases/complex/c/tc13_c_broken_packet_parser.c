#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

// Complex broken C program for self-healing compiler benchmark
// Binary network packet decoder and frame validation
// Contains 3-5 distinct C compilation faults (150-500 LOC)

#define MAX_PAYLOAD_SIZE 128
#define PROTOCOL_MAGIC 0xA55A

typedef struct {
    uint16_t magic;
    uint8_t packetType;
    uint8_t flags;
    uint16_t payloadLength;
    uint16_t checksum;
} PacketHeader;

typedef struct {
    PacketHeader header;
    uint8_t payload[MAX_PAYLOAD_SIZE];
    bool isValid;
} ParsedPacket;

typedef struct {
    char interfaceName[16];
    uint64_t packetsReceived;
    uint64_t packetsDropped;
} NetworkInterfaceStats;

void printInterfaceStats(const NetworkInterfaceStats* stats) {
    if (!stats) return;
    printf("[IFACE-STATS] %s | Rx: %llu | Dropped: %llu\n",
           stats->interfaceName, (unsigned long long)stats->packetsReceived,
           (unsigned long long)stats->packetsDropped);
}

// ERROR 1: Missing return type on function
calculateChecksum(const uint8_t* data, size_t length) {
    if (!data || length == 0) return 0;
    uint16_t sum = 0;
    for (size_t i = 0; i < length; ++i) {
        sum = (sum << 1) ^ data[i];
    }
    return sum;
}

void initParsedPacket(ParsedPacket* pkt) {
    if (!pkt) return;
    memset(pkt, 0, sizeof(ParsedPacket));
    pkt->isValid = false;
}

bool decodePacket(const uint8_t* buffer, size_t bufferLength, ParsedPacket* outPacket) {
    if (!buffer || !outPacket || bufferLength < sizeof(PacketHeader)) {
        return false;
    }

    // ERROR 2: Undeclared variable 'networkMaxFrameSize'
    if (bufferLength > networkMaxFrameSize) {
        return false;
    }

    const PacketHeader* hdr = (const PacketHeader*)buffer;
    if (hdr->magic != PROTOCOL_MAGIC) {
        return false;
    }

    if (hdr->payloadLength > MAX_PAYLOAD_SIZE) {
        return false;
    }

    outPacket->header = *hdr;
    memcpy(outPacket->payload, buffer + sizeof(PacketHeader), hdr->payloadLength);

    // ERROR 3: Incompatible pointer assignment without cast
    outPacket->payload = "literal_string_cannot_assign_to_array";

    uint16_t calcCrc = calculateChecksum(outPacket->payload, hdr->payloadLength);
    outPacket->isValid = (calcCrc == hdr->checksum);
    return true;
}

void printPacketDetails(const ParsedPacket* pkt) {
    if (!pkt) return;
    printf("\n=== Packet Information ===\n");
    printf("Type:     0x%02X\n", pkt->header.packetType);
    printf("Length:   %u bytes\n", pkt->header.payloadLength);
    printf("Checksum: 0x%04X (Valid: %s)\n",
           pkt->header.checksum, pkt->isValid ? "YES" : "NO");
}

void runPacketParserHeader(void) {
    printf("============================================================\n");
    printf("   C11 NETWORK PACKET FRAME PARSER BENCHMARK               \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [PACKET-FRAME-VERIFY-%02d] Validating protocol header descriptor %d.\n", k, k);
    }
}

int main(void) {
    runPacketParserHeader();

    NetworkInterfaceStats ifStats = {"eth0", 1024, 4};
    printInterfaceStats(&ifStats);

    uint8_t dummyFrame[sizeof(PacketHeader) + 16];
    PacketHeader* hdr = (PacketHeader*)dummyFrame;
    hdr->magic = PROTOCOL_MAGIC;
    hdr->packetType = 0x01;
    hdr->flags = 0x00;
    hdr->payloadLength = 16;
    hdr->checksum = 0x1234;

    memset(dummyFrame + sizeof(PacketHeader), 0x55, 16);

    ParsedPacket parsed;
    initParsedPacket(&parsed);

    if (decodePacket(dummyFrame, sizeof(dummyFrame), &parsed)) {
        printPacketDetails(&parsed);
    }

    // ERROR 4: Calling undeclared function
    flushPacketDecoderBufferPool(&parsed);

    return 0;
}

