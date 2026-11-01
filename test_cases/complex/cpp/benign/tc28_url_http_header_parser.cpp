#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <sstream>
#include <iomanip>

struct ParsedUrl {
    std::string scheme;
    std::string host;
    int port;
    std::string path;
    std::unordered_map<std::string, std::string> queryParams;
};

struct HttpRequestMessage {
    std::string method;
    std::string uri;
    std::string httpVersion;
    std::unordered_map<std::string, std::string> headers;
    std::string body;

    std::string getHeader(const std::string& name, const std::string& fallback = "") const {
        auto it = headers.find(name);
        return (it != headers.end()) ? it->second : fallback;
    }

    bool hasHeader(const std::string& name) const {
        return headers.find(name) != headers.end();
    }
};

class HttpRequestParser {
public:
    static HttpRequestMessage parseRawRequest(const std::string& raw) {
        HttpRequestMessage req;
        std::istringstream stream(raw);
        std::string line;

        if (std::getline(stream, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            std::istringstream lineStream(line);
            lineStream >> req.method >> req.uri >> req.httpVersion;
        }

        while (std::getline(stream, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty()) break; // End of headers

            size_t colon = line.find(':');
            if (colon != std::string::npos) {
                std::string headerName = line.substr(0, colon);
                std::string headerValue = line.substr(colon + 1);
                // Trim leading whitespace
                size_t start = headerValue.find_first_not_of(" \t");
                if (start != std::string::npos) headerValue = headerValue.substr(start);
                req.headers[headerName] = headerValue;
            }
        }

        // Remaining text is body
        std::string bodyLine;
        while (std::getline(stream, bodyLine)) {
            req.body += bodyLine + "\n";
        }
        return req;
    }
};

class HttpUrlParser {
public:
    static std::string urlDecode(const std::string& in) {
        std::string out;
        for (size_t i = 0; i < in.size(); ++i) {
            if (in[i] == '%' && i + 2 < in.size()) {
                int hexVal = 0;
                std::istringstream hexStream(in.substr(i + 1, 2));
                if (hexStream >> std::hex >> hexVal) {
                    out += static_cast<char>(hexVal);
                    i += 2;
                } else {
                    out += in[i];
                }
            } else if (in[i] == '+') {
                out += ' ';
            } else {
                out += in[i];
            }
        }
        return out;
    }

    static ParsedUrl parseUrl(const std::string& raw) {
        ParsedUrl url;
        url.port = 80;

        size_t schemeEnd = raw.find("://");
        if (schemeEnd != std::string::npos) {
            url.scheme = raw.substr(0, schemeEnd);
            std::string rest = raw.substr(schemeEnd + 3);

            size_t slash = rest.find('/');
            std::string hostPort = (slash != std::string::npos) ? rest.substr(0, slash) : rest;
            url.path = (slash != std::string::npos) ? rest.substr(slash) : "/";

            size_t colon = hostPort.find(':');
            if (colon != std::string::npos) {
                url.host = hostPort.substr(0, colon);
                url.port = std::stoi(hostPort.substr(colon + 1));
            } else {
                url.host = hostPort;
                url.port = (url.scheme == "https") ? 443 : 80;
            }

            size_t question = url.path.find('?');
            if (question != std::string::npos) {
                std::string queryStr = url.path.substr(question + 1);
                url.path = url.path.substr(0, question);

                std::istringstream qs(queryStr);
                std::string pair;
                while (std::getline(qs, pair, '&')) {
                    size_t eq = pair.find('=');
                    if (eq != std::string::npos) {
                        url.queryParams[pair.substr(0, eq)] = pair.substr(eq + 1);
                    }
                }
            }
        }
        return url;
    }
};

int main() {
    std::string targetUrl = "https://compiler.internal.net:8443/api/v2/heal?lang=cpp&model=gemini-2.5-pro";
    ParsedUrl parsed = HttpUrlParser::parseUrl(targetUrl);

    std::cout << "Scheme : " << parsed.scheme << "\n";
    std::cout << "Host   : " << parsed.host << "\n";
    std::cout << "Port   : " << parsed.port << "\n";
    std::cout << "Path   : " << parsed.path << "\n";
    std::cout << "Query Parameters:\n";
    for (const auto& q : parsed.queryParams) {
        std::cout << "  " << q.first << " = " << q.second << "\n";
    }

    std::string rawHttp = 
        "POST /api/v2/heal HTTP/1.1\r\n"
        "Host: compiler.internal.net:8443\r\n"
        "User-Agent: AntigravityClient/2.4\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: 48\r\n"
        "Authorization: Bearer SECRET_ACCESS_TOKEN_123\r\n"
        "\r\n"
        "{\"source\":\"int main(){ return 0; }\",\"lang\":\"cpp\"}";

    std::cout << "\nParsing Raw HTTP/1.1 Wire Stream:\n";
    HttpRequestMessage req = HttpRequestParser::parseRawRequest(rawHttp);
    std::cout << "Method       : " << req.method << "\n";
    std::cout << "URI          : " << req.uri << "\n";
    std::cout << "HTTP Version : " << req.httpVersion << "\n";
    std::cout << "Content-Type : " << req.getHeader("Content-Type") << "\n";
    std::cout << "Auth Header  : " << req.getHeader("Authorization") << "\n";
    std::cout << "Body Payload : " << req.body << "\n";

    return 0;
}
