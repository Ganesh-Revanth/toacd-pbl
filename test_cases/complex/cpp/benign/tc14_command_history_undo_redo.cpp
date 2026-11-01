#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <algorithm>

class TextDocument {
private:
    std::string content;

public:
    TextDocument() = default;

    void insert(size_t pos, const std::string& text) {
        if (pos > content.size()) pos = content.size();
        content.insert(pos, text);
    }

    void erase(size_t pos, size_t length) {
        if (pos >= content.size()) return;
        content.erase(pos, length);
    }

    const std::string& getContent() const { return content; }
};

class IDocumentCommand {
public:
    virtual ~IDocumentCommand() = default;
    virtual void execute(TextDocument& doc) = 0;
    virtual void undo(TextDocument& doc) = 0;
    virtual std::string describe() const = 0;
};

class InsertTextCommand : public IDocumentCommand {
private:
    size_t insertPosition;
    std::string textToInsert;

public:
    InsertTextCommand(size_t pos, std::string text)
        : insertPosition(pos), textToInsert(std::move(text)) {}

    void execute(TextDocument& doc) override {
        doc.insert(insertPosition, textToInsert);
    }

    void undo(TextDocument& doc) override {
        doc.erase(insertPosition, textToInsert.size());
    }

    std::string describe() const override {
        return "Insert '" + textToInsert + "' at " + std::to_string(insertPosition);
    }
};

class DeleteTextCommand : public IDocumentCommand {
private:
    size_t deletePosition;
    size_t deleteLength;
    std::string deletedSnapshot;

public:
    DeleteTextCommand(size_t pos, size_t len)
        : deletePosition(pos), deleteLength(len) {}

    void execute(TextDocument& doc) override {
        const std::string& c = doc.getContent();
        if (deletePosition < c.size()) {
            deletedSnapshot = c.substr(deletePosition, deleteLength);
            doc.erase(deletePosition, deleteLength);
        }
    }

    void undo(TextDocument& doc) override {
        doc.insert(deletePosition, deletedSnapshot);
    }

    std::string describe() const override {
        return "Delete len " + std::to_string(deleteLength) + " at " + std::to_string(deletePosition);
    }
};

class CommandHistoryManager {
private:
    TextDocument document;
    std::vector<std::unique_ptr<IDocumentCommand>> undoStack;
    std::vector<std::unique_ptr<IDocumentCommand>> redoStack;
    size_t maxHistorySize;

public:
    explicit CommandHistoryManager(size_t maxSize = 50) : maxHistorySize(maxSize) {}

    void executeCommand(std::unique_ptr<IDocumentCommand> cmd) {
        if (!cmd) return;
        cmd->execute(document);
        undoStack.push_back(std::move(cmd));
        redoStack.clear();

        if (undoStack.size() > maxHistorySize) {
            undoStack.erase(undoStack.begin());
        }
    }

    bool undo() {
        if (undoStack.empty()) return false;
        auto cmd = std::move(undoStack.back());
        undoStack.pop_back();
        cmd->undo(document);
        redoStack.push_back(std::move(cmd));
        return true;
    }

    bool redo() {
        if (redoStack.empty()) return false;
        auto cmd = std::move(redoStack.back());
        redoStack.pop_back();
        cmd->execute(document);
        undoStack.push_back(std::move(cmd));
        return true;
    }

    const std::string& getCurrentText() const {
        return document.getContent();
    }

    void printHistory() const {
        std::cout << "\nDocument Content: \"" << document.getContent() << "\"\n";
        std::cout << "Undo Stack (" << undoStack.size() << "):\n";
        for (const auto& cmd : undoStack) {
            std::cout << "  <- [UNDO] " << cmd->describe() << "\n";
        }
        std::cout << "Redo Stack (" << redoStack.size() << "):\n";
        for (const auto& cmd : redoStack) {
            std::cout << "  -> [REDO] " << cmd->describe() << "\n";
        }
    }
};

int main() {
    CommandHistoryManager editor;

    editor.executeCommand(std::make_unique<InsertTextCommand>(0, "Hello World"));
    editor.executeCommand(std::make_unique<InsertTextCommand>(11, " in C++17"));
    editor.executeCommand(std::make_unique<DeleteTextCommand>(0, 6)); // deletes "Hello "

    editor.printHistory();

    std::cout << "\nPerforming Undo Operation...\n";
    editor.undo();
    editor.printHistory();

    std::cout << "\nPerforming Another Undo Operation...\n";
    editor.undo();
    editor.printHistory();

    std::cout << "\nPerforming Redo Operation...\n";
    editor.redo();
    editor.printHistory();

    return 0;
}
