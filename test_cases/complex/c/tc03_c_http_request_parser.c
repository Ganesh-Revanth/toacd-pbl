#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <strings.h>

#define MAX_HEADERS 16
#define MAX_HEADER_KEY 32
#define MAX_HEADER_VAL 64
#define MAX_URI_LEN 128

typedef struct {
    char key[MAX_HEADER_KEY];
    char value[MAX_HEADER_VAL];
} HttpHeader;

typedef struct {
    char method[8];
    char uri[MAX_URI_LEN];
    char version[16];
    HttpHeader headers[MAX_HEADERS];
    size_t headerCount;
    int contentLength;
} HttpRequest;

void httpRequestInit(HttpRequest* req) {
    if (!req) return;
    memset(req, 0, sizeof(HttpRequest));
}

bool parseRequestLine(HttpRequest* req, const char* line) {
    if (!req || !line) return false;
    char m[8], u[MAX_URI_LEN], v[16];
    if (sscanf(line, "%7s %127s %15s", m, u, v) == 3) {
        strncpy(req->method, m, sizeof(req->method) - 1);
        strncpy(req->uri, u, sizeof(req->uri) - 1);
        strncpy(req->version, v, sizeof(req->version) - 1);
        return true;
    }
    return false;
}

bool addHeader(HttpRequest* req, const char* k, const char* v) {
    if (!req || !k || !v || req->headerCount >= MAX_HEADERS) return false;
    strncpy(req->headers[req->headerCount].key, k, MAX_HEADER_KEY - 1);
    strncpy(req->headers[req->headerCount].value, v, MAX_HEADER_VAL - 1);
    if (strcasecmp(k, "Content-Length") == 0) {
        req->contentLength = atoi(v);
    }
    req->headerCount++;
    return true;
}

const char* getHeader(const HttpRequest* req, const char* k) {
    if (!req || !k) return NULL;
    for (size_t i = 0; i < req->headerCount; ++i) {
        if (strcasecmp(req->headers[i].key, k) == 0) {
            return req->headers[i].value;
        }
    }
    return NULL;
}


typedef struct {
    char rawQuery[128];
    int paramCount;
} UrlQueryParamParser;

void initQueryParser(UrlQueryParamParser* q, const char* str) {
    if (!q) return;
    strncpy(q->rawQuery, str ? str : "", 127);
    q->paramCount = 0;
}

bool hasQueryKey(const UrlQueryParamParser* q, const char* key) {
    if (!q || !key) return false;
    return strstr(q->rawQuery, key) != NULL;
}

bool hasHeader(const HttpRequest* req, const char* k) {
    return getHeader(req, k) != NULL;
}

void printParsedRequest(const HttpRequest* req) {
    if (!req) return;
    printf("\n=== HTTP Request Dissection ===\n");
    printf("Method  : %s\n", req->method);
    printf("URI     : %s\n", req->uri);
    printf("Version : %s\n", req->version);
    printf("Headers (%zu parsed):\n", req->headerCount);
    for (size_t i = 0; i < req->headerCount; ++i) {
        printf("  * %s: %s\n", req->headers[i].key, req->headers[i].value);
    }
    printf("Body Len: %d bytes\n", req->contentLength);
    printf("================================\n");
}

typedef struct {
    size_t requestsParsed;
    size_t invalidRequests;
    size_t totalBytesReceived;
} HttpMetrics;

void recordHttpMetric(HttpMetrics* m, bool success, size_t bytes) {
    if (!m) return;
    if (success) {
        m->requestsParsed++;
        m->totalBytesReceived += bytes;
    } else {
        m->invalidRequests++;
    }
}

void dumpHttpMetrics(const HttpMetrics* m) {
    if (!m) return;
    printf("HTTP Server Metrics: Valid=%zu | Malformed=%zu | Bytes=%zu\n", 
           m->requestsParsed, m->invalidRequests, m->totalBytesReceived);
}

void runHttpParserHeader(void) {
    printf("============================================================\n");
    printf("    C11 EMBEDDED HTTP/1.1 PROTOCOL PARSER ENGINE            \n");
    printf("    Zero-Copy Header Deserialization & Route Matching       \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [HTTP-PARSER-SLOT-%02d] Initializing parser rule table %d.\n", k, k);
    }
}

int main(void) {
    runHttpParserHeader();
    HttpRequest req;
    httpRequestInit(&req);

    HttpMetrics metrics = {0, 0, 0};

    const char* reqLine = "GET /api/v2/telemetry/stats HTTP/1.1";
    bool ok = parseRequestLine(&req, reqLine);
    recordHttpMetric(&metrics, ok, strlen(reqLine));

    addHeader(&req, "Host", "gateway.internal.corp");
    addHeader(&req, "User-Agent", "AntigravityCodeStudio/2.0");
    addHeader(&req, "Accept", "application/json");
    addHeader(&req, "Content-Length", "48");

    printParsedRequest(&req);

    const char* hostHeader = getHeader(&req, "Host");
    printf("Verification - Host Header Value: %s\n", hostHeader ? hostHeader : "NONE");
    printf("Verification - Has Accept Header: %s\n", hasHeader(&req, "Accept") ? "YES" : "NO");

    dumpHttpMetrics(&metrics);
    return 0;
}
