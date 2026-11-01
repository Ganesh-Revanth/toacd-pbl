#include <iostream>
#include <string>
#include <vector>
#include <cctype>
#include <iomanip>
#include <sstream>
#include <stdexcept>

enum class JsonTokenType {
    BEGIN_OBJECT,    // {
    END_OBJECT,      // }
    BEGIN_ARRAY,     // [
    END_ARRAY,       // ]
    COLON,           // :
    COMMA,           // ,
    STRING_LITERAL,  // "..."
    NUMBER_LITERAL,  // 123.45
    BOOLEAN_TRUE,    // true
    BOOLEAN_FALSE,   // false
    NULL_LITERAL,    // null
    END_OF_STREAM
};

struct JsonToken {
    JsonTokenType type;
    std::string lexeme;
    int line;
    int column;

    JsonToken(JsonTokenType t, std::string lex, int l, int c)
        : type(t), lexeme(std::move(lex)), line(l), column(c) {}
};

class JsonLexicalScanner {
private:
    std::string source;
    size_t cursor;
    int currentLine;
    int currentColumn;

    char peek() const {
        return (cursor < source.size()) ? source[cursor] : '\0';
    }

    char advance() {
        char ch = (cursor < source.size()) ? source[cursor++] : '\0';
        if (ch == '\n') {
            currentLine++;
            currentColumn = 1;
        } else {
            currentColumn++;
        }
        return ch;
    }

    void skipWhitespaceAndComments() {
        while (cursor < source.size()) {
            char ch = source[cursor];
            if (std::isspace(static_cast<unsigned char>(ch))) {
                advance();
            } else if (ch == '/' && cursor + 1 < source.size() && source[cursor + 1] == '/') {
                while (cursor < source.size() && source[cursor] != '\n') advance();
            } else {
                break;
            }
        }
    }

    JsonToken scanString() {
        int startLine = currentLine;
        int startCol = currentColumn;
        advance(); // consume opening quote
        std::string str;
        while (cursor < source.size() && peek() != '"') {
            char ch = advance();
            if (ch == '\\') {
                char escaped = advance();
                switch (escaped) {
                    case 'n': str += '\n'; break;
                    case 't': str += '\t'; break;
                    case 'r': str += '\r'; break;
                    case '"': str += '"'; break;
                    case '\\': str += '\\'; break;
                    default: str += escaped; break;
                }
            } else {
                str += ch;
            }
        }
        if (cursor >= source.size()) throw std::runtime_error("Unterminated string literal at line " + std::to_string(startLine));
        advance(); // consume closing quote
        return JsonToken(JsonTokenType::STRING_LITERAL, str, startLine, startCol);
    }

    JsonToken scanNumber() {
        int startLine = currentLine;
        int startCol = currentColumn;
        std::string num;
        if (peek() == '-') num += advance();
        while (cursor < source.size() && std::isdigit(static_cast<unsigned char>(peek()))) {
            num += advance();
        }
        if (peek() == '.') {
            num += advance();
            while (cursor < source.size() && std::isdigit(static_cast<unsigned char>(peek()))) {
                num += advance();
            }
        }
        return JsonToken(JsonTokenType::NUMBER_LITERAL, num, startLine, startCol);
    }

public:
    explicit JsonLexicalScanner(std::string src)
        : source(std::move(src)), cursor(0), currentLine(1), currentColumn(1) {}

    std::vector<JsonToken> tokenizeAll() {
        std::vector<JsonToken> tokens;
        while (cursor < source.size()) {
            skipWhitespaceAndComments();
            if (cursor >= source.size()) break;

            int col = currentColumn;
            int line = currentLine;
            char ch = peek();

            switch (ch) {
                case '{': advance(); tokens.emplace_back(JsonTokenType::BEGIN_OBJECT, "{", line, col); break;
                case '}': advance(); tokens.emplace_back(JsonTokenType::END_OBJECT, "}", line, col); break;
                case '[': advance(); tokens.emplace_back(JsonTokenType::BEGIN_ARRAY, "[", line, col); break;
                case ']': advance(); tokens.emplace_back(JsonTokenType::END_ARRAY, "]", line, col); break;
                case ':': advance(); tokens.emplace_back(JsonTokenType::COLON, ":", line, col); break;
                case ',': advance(); tokens.emplace_back(JsonTokenType::COMMA, ",", line, col); break;
                case '"': tokens.push_back(scanString()); break;
                default:
                    if (std::isdigit(static_cast<unsigned char>(ch)) || ch == '-') {
                        tokens.push_back(scanNumber());
                    } else if (source.substr(cursor, 4) == "true") {
                        cursor += 4; currentColumn += 4;
                        tokens.emplace_back(JsonTokenType::BOOLEAN_TRUE, "true", line, col);
                    } else if (source.substr(cursor, 5) == "false") {
                        cursor += 5; currentColumn += 5;
                        tokens.emplace_back(JsonTokenType::BOOLEAN_FALSE, "false", line, col);
                    } else if (source.substr(cursor, 4) == "null") {
                        cursor += 4; currentColumn += 4;
                        tokens.emplace_back(JsonTokenType::NULL_LITERAL, "null", line, col);
                    } else {
                        advance();
                    }
                    break;
            }
        }
        tokens.emplace_back(JsonTokenType::END_OF_STREAM, "", currentLine, currentColumn);
        return tokens;
    }
};

int main() {
    std::string sampleJson = R"({
        "projectName": "Antigravity Compiler",
        "version": 2.4,
        "isProduction": true,
        "activeModules": ["lexer", "parser", "healer", "guardrail"],
        "maxThreads": 8,
        "fallbackHandler": null
    })";

    JsonLexicalScanner scanner(sampleJson);
    auto tokens = scanner.tokenizeAll();

    std::cout << "Tokenized " << tokens.size() << " JSON elements:\n";
    for (const auto& tok : tokens) {
        std::cout << "Line " << std::setw(2) << tok.line << ", Col " << std::setw(2) << tok.column
                  << " | Type: " << static_cast<int>(tok.type)
                  << " | Lexeme: [" << tok.lexeme << "]\n";
    }
    return 0;
}
