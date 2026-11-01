"""
scripts/generate_complex/cpp_benign_part1.py
--------------------------------------------
Generates C++ benign complex fixtures 1 through 20.
Each fixture: 150-500 lines, compiles cleanly with g++ -std=c++17.
"""

from pathlib import Path
from typing import Dict, Tuple
from .utils import validate_and_write


def generate_all(base_dir: Path) -> Dict[str, Tuple[bool, int, str]]:
    results = {}
    
    # ── TC01: Bank Account Hierarchy ──────────────────────────────────────────
    tc01 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <map>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <algorithm>

enum class TransactionType { DEPOSIT, WITHDRAWAL, INTEREST, TRANSFER, FEE };

struct Transaction {
    std::string id;
    TransactionType type;
    double amount;
    std::string timestamp;
    std::string description;

    Transaction(std::string id_, TransactionType t, double amt, std::string ts, std::string desc)
        : id(std::move(id_)), type(t), amount(amt), timestamp(std::move(ts)), description(std::move(desc)) {}
};

class Account {
protected:
    std::string accountNumber;
    std::string ownerName;
    double balance;
    std::vector<Transaction> transactionHistory;
    mutable std::mutex accountMutex;

public:
    Account(std::string accNum, std::string owner, double initialDeposit)
        : accountNumber(std::move(accNum)), ownerName(std::move(owner)), balance(initialDeposit) {
        recordTransaction(TransactionType::DEPOSIT, initialDeposit, "Initial deposit on creation");
    }

    virtual ~Account() = default;

    virtual void deposit(double amount) {
        std::lock_guard<std::mutex> lock(accountMutex);
        if (amount <= 0.0) return;
        balance += amount;
        recordTransaction(TransactionType::DEPOSIT, amount, "Deposit to account");
    }

    virtual bool withdraw(double amount) {
        std::lock_guard<std::mutex> lock(accountMutex);
        if (amount <= 0.0 || balance < amount) return false;
        balance -= amount;
        recordTransaction(TransactionType::WITHDRAWAL, amount, "Withdrawal from account");
        return true;
    }

    virtual double calculateMonthlyInterest() const = 0;
    virtual std::string getAccountType() const = 0;

    double getBalance() const {
        std::lock_guard<std::mutex> lock(accountMutex);
        return balance;
    }

    const std::string& getAccountNumber() const { return accountNumber; }
    const std::string& getOwnerName() const { return ownerName; }

    void printStatement() const {
        std::lock_guard<std::mutex> lock(accountMutex);
        std::cout << "\n================ ACCOUNT STATEMENT ================\n";
        std::cout << "Account: " << accountNumber << " (" << getAccountType() << ")\n";
        std::cout << "Owner  : " << ownerName << "\n";
        std::cout << "Balance: $" << std::fixed << std::setprecision(2) << balance << "\n";
        std::cout << "---------------- Transaction Log -----------------\n";
        for (const auto& tx : transactionHistory) {
            std::cout << "[" << tx.id << "] " << tx.timestamp << " | "
                      << std::setw(10) << tx.amount << " | " << tx.description << "\n";
        }
        std::cout << "====================================================\n";
    }

protected:
    void recordTransaction(TransactionType type, double amount, const std::string& desc) {
        static int counter = 1000;
        std::ostringstream ss;
        ss << "TX-" << (++counter);
        transactionHistory.emplace_back(ss.str(), type, amount, "2026-11-01 12:00", desc);
    }
};

class SavingsAccount : public Account {
private:
    double annualInterestRate;
    double minimumBalance;

public:
    SavingsAccount(std::string accNum, std::string owner, double initialDeposit, double rate, double minBal = 500.0)
        : Account(std::move(accNum), std::move(owner), initialDeposit),
          annualInterestRate(rate), minimumBalance(minBal) {}

    bool withdraw(double amount) override {
        std::lock_guard<std::mutex> lock(accountMutex);
        if (amount <= 0.0 || (balance - amount) < minimumBalance) {
            return false;
        }
        balance -= amount;
        recordTransaction(TransactionType::WITHDRAWAL, amount, "Savings withdrawal");
        return true;
    }

    double calculateMonthlyInterest() const override {
        std::lock_guard<std::mutex> lock(accountMutex);
        return (balance * (annualInterestRate / 100.0)) / 12.0;
    }

    std::string getAccountType() const override { return "High-Yield Savings"; }
};

class CheckingAccount : public Account {
private:
    double overdraftLimit;
    double transactionFee;

public:
    CheckingAccount(std::string accNum, std::string owner, double initialDeposit, double overdraft = 1000.0, double fee = 1.50)
        : Account(std::move(accNum), std::move(owner), initialDeposit),
          overdraftLimit(overdraft), transactionFee(fee) {}

    bool withdraw(double amount) override {
        std::lock_guard<std::mutex> lock(accountMutex);
        double totalDeduction = amount + transactionFee;
        if (amount <= 0.0 || (balance + overdraftLimit) < totalDeduction) {
            return false;
        }
        balance -= totalDeduction;
        recordTransaction(TransactionType::WITHDRAWAL, amount, "Checking debit withdrawal");
        recordTransaction(TransactionType::FEE, transactionFee, "Service transaction fee");
        return true;
    }

    double calculateMonthlyInterest() const override { return 0.0; }
    std::string getAccountType() const override { return "Standard Checking"; }
};

class BankLedgerManager {
private:
    std::map<std::string, std::shared_ptr<Account>> accounts;
    mutable std::mutex registryMutex;

public:
    bool registerAccount(const std::shared_ptr<Account>& acc) {
        if (!acc) return false;
        std::lock_guard<std::mutex> lock(registryMutex);
        if (accounts.find(acc->getAccountNumber()) != accounts.end()) {
            return false;
        }
        accounts[acc->getAccountNumber()] = acc;
        return true;
    }

    std::shared_ptr<Account> findAccount(const std::string& accNum) const {
        std::lock_guard<std::mutex> lock(registryMutex);
        auto it = accounts.find(accNum);
        return (it != accounts.end()) ? it->second : nullptr;
    }

    bool transferFunds(const std::string& fromAcc, const std::string& toAcc, double amount) {
        if (amount <= 0.0) return false;
        auto src = findAccount(fromAcc);
        auto dst = findAccount(toAcc);
        if (!src || !dst || src == dst) return false;

        if (src->withdraw(amount)) {
            dst->deposit(amount);
            return true;
        }
        return false;
    }

    double computeTotalReserves() const {
        std::lock_guard<std::mutex> lock(registryMutex);
        double total = 0.0;
        for (const auto& pair : accounts) {
            total += pair.second->getBalance();
        }
        return total;
    }

    void auditReport() const {
        std::lock_guard<std::mutex> lock(registryMutex);
        std::cout << "\n================= BANK AUDIT REPORT ================\n";
        std::cout << "Total Active Accounts: " << accounts.size() << "\n";
        std::cout << "Aggregate Reserves   : $" << std::fixed << std::setprecision(2) << computeTotalReserves() << "\n";
        for (const auto& pair : accounts) {
            pair.second->printStatement();
        }
    }
};

int main() {
    BankLedgerManager bank;
    auto sav = std::make_shared<SavingsAccount>("SAV-101", "Alice Johnson", 5000.0, 4.25, 500.0);
    auto chk = std::make_shared<CheckingAccount>("CHK-202", "Bob Smith", 1500.0, 500.0, 2.0);

    bank.registerAccount(sav);
    bank.registerAccount(chk);

    sav->deposit(1250.0);
    chk->withdraw(300.0);
    bank.transferFunds("SAV-101", "CHK-202", 750.0);

    double interest = sav->calculateMonthlyInterest();
    sav->deposit(interest);

    bank.auditReport();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc01_bank_account_hierarchy.cpp", tc01, expect_compile=True)
    results["tc01_bank_account_hierarchy.cpp"] = (res, count, msg)

    # ── TC02: Library Catalog System ──────────────────────────────────────────
    tc02 = r'''#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <map>
#include <memory>
#include <algorithm>
#include <chrono>
#include <iomanip>

struct BookItem {
    std::string isbn;
    std::string title;
    std::string author;
    int publicationYear;
    int totalCopies;
    int availableCopies;

    BookItem() : publicationYear(0), totalCopies(0), availableCopies(0) {}
    BookItem(std::string isbn_, std::string title_, std::string auth, int year, int copies)
        : isbn(std::move(isbn_)), title(std::move(title_)), author(std::move(auth)),
          publicationYear(year), totalCopies(copies), availableCopies(copies) {}
};

struct LoanRecord {
    std::string loanId;
    std::string memberId;
    std::string isbn;
    std::string borrowDate;
    std::string dueDate;
    bool returned;
    double fineAccrued;

    LoanRecord(std::string lid, std::string mid, std::string isb, std::string bdate, std::string ddate)
        : loanId(std::move(lid)), memberId(std::move(mid)), isbn(std::move(isb)),
          borrowDate(std::move(bdate)), dueDate(std::move(ddate)), returned(false), fineAccrued(0.0) {}
};

class LibraryMember {
private:
    std::string memberId;
    std::string fullName;
    std::string email;
    int maxLoansAllowed;
    std::vector<std::string> activeLoanIds;

public:
    LibraryMember() : maxLoansAllowed(5) {}
    LibraryMember(std::string mid, std::string name, std::string mail, int maxLoans = 5)
        : memberId(std::move(mid)), fullName(std::move(name)), email(std::move(mail)), maxLoansAllowed(maxLoans) {}

    const std::string& getId() const { return memberId; }
    const std::string& getName() const { return fullName; }
    bool canBorrow() const { return activeLoanIds.size() < static_cast<size_t>(maxLoansAllowed); }

    void addLoan(const std::string& loanId) { activeLoanIds.push_back(loanId); }
    void removeLoan(const std::string& loanId) {
        activeLoanIds.erase(std::remove(activeLoanIds.begin(), activeLoanIds.end(), loanId), activeLoanIds.end());
    }

    size_t getActiveLoanCount() const { return activeLoanIds.size(); }
};

class LibraryCatalog {
private:
    std::unordered_map<std::string, BookItem> booksByIsbn;
    std::multimap<std::string, std::string> titleIndex;
    std::multimap<std::string, std::string> authorIndex;
    std::unordered_map<std::string, LibraryMember> members;
    std::unordered_map<std::string, LoanRecord> loans;
    int nextLoanSeq;

public:
    LibraryCatalog() : nextLoanSeq(1001) {}

    bool addBook(const BookItem& book) {
        if (booksByIsbn.find(book.isbn) != booksByIsbn.end()) {
            booksByIsbn[book.isbn].totalCopies += book.totalCopies;
            booksByIsbn[book.isbn].availableCopies += book.availableCopies;
            return true;
        }
        booksByIsbn[book.isbn] = book;
        titleIndex.insert({book.title, book.isbn});
        authorIndex.insert({book.author, book.isbn});
        return true;
    }

    bool registerMember(const LibraryMember& member) {
        if (members.find(member.getId()) != members.end()) return false;
        members[member.getId()] = member;
        return true;
    }

    std::string checkoutBook(const std::string& memberId, const std::string& isbn) {
        auto mIt = members.find(memberId);
        if (mIt == members.end() || !mIt->second.canBorrow()) return "";

        auto bIt = booksByIsbn.find(isbn);
        if (bIt == booksByIsbn.end() || bIt->second.availableCopies <= 0) return "";

        bIt->second.availableCopies--;
        std::string loanId = "LN-" + std::to_string(nextLoanSeq++);
        LoanRecord record(loanId, memberId, isbn, "2026-11-01", "2026-11-15");
        loans.insert({loanId, record});
        mIt->second.addLoan(loanId);
        return loanId;
    }

    bool checkinBook(const std::string& loanId, int daysOverdue = 0) {
        auto lIt = loans.find(loanId);
        if (lIt == loans.end() || lIt->second.returned) return false;

        lIt->second.returned = true;
        if (daysOverdue > 0) {
            lIt->second.fineAccrued = daysOverdue * 0.50;
        }

        auto bIt = booksByIsbn.find(lIt->second.isbn);
        if (bIt != booksByIsbn.end()) {
            bIt->second.availableCopies++;
        }

        auto mIt = members.find(lIt->second.memberId);
        if (mIt != members.end()) {
            mIt->second.removeLoan(loanId);
        }
        return true;
    }

    std::vector<BookItem> searchByAuthor(const std::string& author) const {
        std::vector<BookItem> results;
        auto range = authorIndex.equal_range(author);
        for (auto it = range.first; it != range.second; ++it) {
            auto bIt = booksByIsbn.find(it->second);
            if (bIt != booksByIsbn.end()) results.push_back(bIt->second);
        }
        return results;
    }

    void printInventoryReport() const {
        std::cout << "\n================ LIBRARY INVENTORY REPORT ================\n";
        for (const auto& pair : booksByIsbn) {
            const auto& b = pair.second;
            std::cout << "[" << b.isbn << "] " << std::setw(30) << std::left << b.title
                      << " | " << std::setw(20) << b.author
                      << " | Avail: " << b.availableCopies << "/" << b.totalCopies << "\n";
        }
        std::cout << "==========================================================\n";
    }
};

int main() {
    LibraryCatalog catalog;
    catalog.addBook(BookItem("978-0131103627", "The C Programming Language", "Kernighan & Ritchie", 1988, 5));
    catalog.addBook(BookItem("978-0201633610", "Design Patterns", "Gang of Four", 1994, 3));
    catalog.addBook(BookItem("978-0321563842", "The C++ Programming Language", "Bjarne Stroustrup", 2013, 4));

    catalog.registerMember(LibraryMember("MEM-01", "Alan Turing", "alan@turing.ac.uk", 3));
    catalog.registerMember(LibraryMember("MEM-02", "Ada Lovelace", "ada@lovelace.org", 5));

    std::string loan1 = catalog.checkoutBook("MEM-01", "978-0131103627");
    std::string loan2 = catalog.checkoutBook("MEM-02", "978-0201633610");

    catalog.printInventoryReport();
    catalog.checkinBook(loan1, 2);
    catalog.printInventoryReport();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc02_library_management_system.cpp", tc02, expect_compile=True)
    results["tc02_library_management_system.cpp"] = (res, count, msg)

    # ── TC03: Inventory Tracking Tree ─────────────────────────────────────────
    tc03 = r'''#include <iostream>
#include <string>
#include <memory>
#include <vector>
#include <iomanip>
#include <algorithm>
#include <sstream>

template <typename T>
class InventoryNode {
public:
    int itemId;
    std::string itemName;
    T price;
    int stockQuantity;
    int height;
    std::unique_ptr<InventoryNode<T>> left;
    std::unique_ptr<InventoryNode<T>> right;

    InventoryNode(int id, std::string name, T pr, int qty)
        : itemId(id), itemName(std::move(name)), price(pr), stockQuantity(qty),
          height(1), left(nullptr), right(nullptr) {}
};

template <typename T>
class InventoryAVLTree {
private:
    std::unique_ptr<InventoryNode<T>> root;

    int getHeight(const std::unique_ptr<InventoryNode<T>>& node) const {
        return node ? node->height : 0;
    }

    int getBalanceFactor(const std::unique_ptr<InventoryNode<T>>& node) const {
        return node ? getHeight(node->left) - getHeight(node->right) : 0;
    }

    void updateHeight(std::unique_ptr<InventoryNode<T>>& node) {
        if (node) {
            node->height = 1 + std::max(getHeight(node->left), getHeight(node->right));
        }
    }

    std::unique_ptr<InventoryNode<T>> rotateRight(std::unique_ptr<InventoryNode<T>> y) {
        auto x = std::move(y->left);
        y->left = std::move(x->right);
        updateHeight(y);
        x->right = std::move(y);
        updateHeight(x);
        return x;
    }

    std::unique_ptr<InventoryNode<T>> rotateLeft(std::unique_ptr<InventoryNode<T>> x) {
        auto y = std::move(x->right);
        x->right = std::move(y->left);
        updateHeight(x);
        y->left = std::move(x);
        updateHeight(y);
        return y;
    }

    std::unique_ptr<InventoryNode<T>> insertRec(std::unique_ptr<InventoryNode<T>> node, int id, const std::string& name, T price, int qty) {
        if (!node) {
            return std::make_unique<InventoryNode<T>>(id, name, price, qty);
        }

        if (id < node->itemId) {
            node->left = insertRec(std::move(node->left), id, name, price, qty);
        } else if (id > node->itemId) {
            node->right = insertRec(std::move(node->right), id, name, price, qty);
        } else {
            node->stockQuantity += qty;
            node->price = price;
            return node;
        }

        updateHeight(node);
        int balance = getBalanceFactor(node);

        if (balance > 1 && id < node->left->itemId) {
            return rotateRight(std::move(node));
        }
        if (balance < -1 && id > node->right->itemId) {
            return rotateLeft(std::move(node));
        }
        if (balance > 1 && id > node->left->itemId) {
            node->left = rotateLeft(std::move(node->left));
            return rotateRight(std::move(node));
        }
        if (balance < -1 && id < node->right->itemId) {
            node->right = rotateRight(std::move(node->right));
            return rotateLeft(std::move(node));
        }
        return node;
    }

    const InventoryNode<T>* searchRec(const InventoryNode<T>* node, int id) const {
        if (!node || node->itemId == id) return node;
        if (id < node->itemId) return searchRec(node->left.get(), id);
        return searchRec(node->right.get(), id);
    }

    void inOrderRec(const InventoryNode<T>* node, std::vector<const InventoryNode<T>*>& acc) const {
        if (!node) return;
        inOrderRec(node->left.get(), acc);
        acc.push_back(node);
        inOrderRec(node->right.get(), acc);
    }

public:
    InventoryAVLTree() : root(nullptr) {}

    void insert(int id, const std::string& name, T price, int qty) {
        root = insertRec(std::move(root), id, name, price, qty);
    }

    const InventoryNode<T>* find(int id) const {
        return searchRec(root.get(), id);
    }

    bool updateStock(int id, int delta) {
        auto* node = const_cast<InventoryNode<T>*>(find(id));
        if (!node || (node->stockQuantity + delta) < 0) return false;
        node->stockQuantity += delta;
        return true;
    }

    std::vector<const InventoryNode<T>*> getAllSorted() const {
        std::vector<const InventoryNode<T>*> items;
        inOrderRec(root.get(), items);
        return items;
    }

    T computeInventoryValuation() const {
        auto items = getAllSorted();
        T sum = 0;
        for (const auto* it : items) {
            sum += it->price * it->stockQuantity;
        }
        return sum;
    }

    void display() const {
        auto items = getAllSorted();
        std::cout << "\n================= INVENTORY AVL TREE ================\n";
        std::cout << std::setw(8) << "ID" << " | "
                  << std::setw(25) << std::left << "Item Description" << " | "
                  << std::setw(10) << "Unit Price" << " | "
                  << std::setw(8) << "Stock" << "\n";
        std::cout << "-----------------------------------------------------\n";
        for (const auto* it : items) {
            std::cout << std::setw(8) << it->itemId << " | "
                      << std::setw(25) << std::left << it->itemName << " | $"
                      << std::setw(9) << std::fixed << std::setprecision(2) << it->price << " | "
                      << std::setw(8) << it->stockQuantity << "\n";
        }
        std::cout << "=====================================================\n";
    }
};

int main() {
    InventoryAVLTree<double> warehouse;
    warehouse.insert(105, "Titanium Bolts M6", 2.45, 500);
    warehouse.insert(102, "Alloy Hex Nuts M6", 0.85, 1200);
    warehouse.insert(108, "Steel Flange Washers", 0.40, 3000);
    warehouse.insert(101, "Precision Bearings", 14.50, 150);
    warehouse.insert(104, "Drive Belt 250mm", 19.99, 45);
    warehouse.insert(107, "Stepper Motor 12V", 35.00, 80);

    warehouse.display();
    warehouse.updateStock(101, -25);
    warehouse.updateStock(108, 500);

    std::cout << "Total Inventory Valuation: $" << warehouse.computeInventoryValuation() << "\n";
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc03_inventory_tracking_tree.cpp", tc03, expect_compile=True)
    results["tc03_inventory_tracking_tree.cpp"] = (res, count, msg)

    # ── TC04: TCP Chat Server Simulation ──────────────────────────────────────
    tc04 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <map>
#include <queue>
#include <mutex>
#include <sstream>
#include <chrono>
#include <iomanip>

struct ChatMessage {
    std::string sender;
    std::string targetChannel;
    std::string content;
    std::string timestamp;

    ChatMessage(std::string s, std::string ch, std::string txt, std::string ts)
        : sender(std::move(s)), targetChannel(std::move(ch)), content(std::move(txt)), timestamp(std::move(ts)) {}
};

class SimulatedSocketClient {
private:
    int clientId;
    std::string username;
    std::queue<ChatMessage> incomingQueue;
    std::mutex socketMutex;
    bool active;

public:
    SimulatedSocketClient(int id, std::string name)
        : clientId(id), username(std::move(name)), active(true) {}

    int getId() const { return clientId; }
    const std::string& getUsername() const { return username; }
    bool isActive() const { return active; }
    void disconnect() { active = false; }

    void deliverMessage(const ChatMessage& msg) {
        std::lock_guard<std::mutex> lock(socketMutex);
        incomingQueue.push(msg);
    }

    std::vector<ChatMessage> flushInbox() {
        std::lock_guard<std::mutex> lock(socketMutex);
        std::vector<ChatMessage> flushed;
        while (!incomingQueue.empty()) {
            flushed.push_back(incomingQueue.front());
            incomingQueue.pop();
        }
        return flushed;
    }
};

class ChatRoomChannel {
private:
    std::string channelName;
    std::string topic;
    std::map<int, std::shared_ptr<SimulatedSocketClient>> participants;
    std::vector<ChatMessage> history;
    std::mutex channelMutex;

public:
    ChatRoomChannel(std::string name, std::string top = "General")
        : channelName(std::move(name)), topic(std::move(top)) {}

    void join(const std::shared_ptr<SimulatedSocketClient>& client) {
        std::lock_guard<std::mutex> lock(channelMutex);
        participants[client->getId()] = client;
        broadcastSystemMessage(client->getUsername() + " joined #" + channelName);
    }

    void leave(int clientId) {
        std::lock_guard<std::mutex> lock(channelMutex);
        auto it = participants.find(clientId);
        if (it != participants.end()) {
            std::string user = it->second->getUsername();
            participants.erase(it);
            broadcastSystemMessage(user + " departed from #" + channelName);
        }
    }

    void postMessage(const std::string& sender, const std::string& text) {
        std::lock_guard<std::mutex> lock(channelMutex);
        ChatMessage msg(sender, channelName, text, "2026-11-01 14:00");
        history.push_back(msg);
        for (const auto& pair : participants) {
            pair.second->deliverMessage(msg);
        }
    }

    void broadcastSystemMessage(const std::string& announcement) {
        ChatMessage msg("SYSTEM", channelName, announcement, "2026-11-01 14:00");
        history.push_back(msg);
        for (const auto& pair : participants) {
            pair.second->deliverMessage(msg);
        }
    }

    size_t getParticipantCount() const { return participants.size(); }
    const std::string& getName() const { return channelName; }
};

class ChatServerEngine {
private:
    std::map<int, std::shared_ptr<SimulatedSocketClient>> activeClients;
    std::map<std::string, std::unique_ptr<ChatRoomChannel>> channels;
    int nextClientId;
    std::mutex serverMutex;

public:
    ChatServerEngine() : nextClientId(1) {
        createChannel("lobby", "Public open discussion");
        createChannel("dev", "Engineering and architecture");
    }

    bool createChannel(const std::string& name, const std::string& topic) {
        std::lock_guard<std::mutex> lock(serverMutex);
        if (channels.find(name) != channels.end()) return false;
        channels[name] = std::make_unique<ChatRoomChannel>(name, topic);
        return true;
    }

    std::shared_ptr<SimulatedSocketClient> connectClient(const std::string& username) {
        std::lock_guard<std::mutex> lock(serverMutex);
        int cid = nextClientId++;
        auto client = std::make_shared<SimulatedSocketClient>(cid, username);
        activeClients[cid] = client;
        if (channels.find("lobby") != channels.end()) {
            channels["lobby"]->join(client);
        }
        return client;
    }

    void routeCommand(const std::shared_ptr<SimulatedSocketClient>& client, const std::string& raw) {
        if (raw.empty() || !client) return;

        if (raw[0] == '/') {
            std::istringstream iss(raw);
            std::string cmd;
            iss >> cmd;
            if (cmd == "/join") {
                std::string target;
                if (iss >> target) {
                    std::lock_guard<std::mutex> lock(serverMutex);
                    auto it = channels.find(target);
                    if (it != channels.end()) it->second->join(client);
                }
            } else if (cmd == "/msg") {
                std::string target, rest;
                if (iss >> target && std::getline(iss, rest)) {
                    std::lock_guard<std::mutex> lock(serverMutex);
                    auto it = channels.find(target);
                    if (it != channels.end()) it->second->postMessage(client->getUsername(), rest);
                }
            }
        }
    }

    void dumpServerMetrics() const {
        std::cout << "\n================ CHAT SERVER METRICS ================\n";
        std::cout << "Connected Sockets: " << activeClients.size() << "\n";
        for (const auto& pair : channels) {
            std::cout << "  Channel #" << std::setw(10) << std::left << pair.first
                      << " | Users: " << pair.second->getParticipantCount() << "\n";
        }
        std::cout << "=====================================================\n";
    }
};

int main() {
    ChatServerEngine server;
    auto alice = server.connectClient("alice_kernel");
    auto bob = server.connectClient("bob_dev");
    auto charlie = server.connectClient("charlie_arch");

    server.routeCommand(alice, "/join dev");
    server.routeCommand(bob, "/join dev");
    server.routeCommand(alice, "/msg dev Hello team, ready for compiler design sprint.");
    server.routeCommand(bob, "/msg dev Acknowledged, running integration test suite.");

    for (const auto& c : {alice, bob, charlie}) {
        auto inbox = c->flushInbox();
        std::cout << "User " << c->getUsername() << " received " << inbox.size() << " packet(s):\n";
        for (const auto& m : inbox) {
            std::cout << "  [" << m.targetChannel << "] " << m.sender << ": " << m.content << "\n";
        }
    }

    server.dumpServerMetrics();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc04_tcp_chat_server_sim.cpp", tc04, expect_compile=True)
    results["tc04_tcp_chat_server_sim.cpp"] = (res, count, msg)

    # ── TC05: Security Access Validator (Contains tricky words for FPR) ───────
    tc05 = r'''#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <chrono>
#include <sstream>
#include <iomanip>
#include <algorithm>

enum class RoleLevel { GUEST, DEVELOPER, AUDITOR, ADMIN, SYSTEM_SUPERVISOR };

struct UserIdentity {
    std::string userId;
    std::string username;
    RoleLevel role;
    std::string assignedDepartment;
    bool isActive;

    UserIdentity() : role(RoleLevel::GUEST), isActive(false) {}
    UserIdentity(std::string uid, std::string uname, RoleLevel r, std::string dept, bool active = true)
        : userId(std::move(uid)), username(std::move(uname)), role(r),
          assignedDepartment(std::move(dept)), isActive(active) {}
};

struct SecurityPolicyRule {
    std::string ruleId;
    std::string resourcePath;
    RoleLevel minimumRole;
    bool requireDepartmentMatch;
    bool bypassRateLimiting;

    SecurityPolicyRule() : minimumRole(RoleLevel::ADMIN), requireDepartmentMatch(false), bypassRateLimiting(false) {}
    SecurityPolicyRule(std::string id, std::string path, RoleLevel minR, bool deptMatch, bool bypass = false)
        : ruleId(std::move(id)), resourcePath(std::move(path)), minimumRole(minR),
          requireDepartmentMatch(deptMatch), bypassRateLimiting(bypass) {}
};

class SecurityAccessValidator {
private:
    std::unordered_map<std::string, UserIdentity> userDirectory;
    std::vector<SecurityPolicyRule> policyRules;
    std::unordered_map<std::string, std::string> activeSessionTokens;
    std::string adminMasterSecretKey;
    bool ignoreAuditWarnings;

public:
    SecurityAccessValidator(std::string masterKey, bool ignoreWarnings = false)
        : adminMasterSecretKey(std::move(masterKey)), ignoreAuditWarnings(ignoreWarnings) {}

    void registerUser(const UserIdentity& user) {
        userDirectory[user.userId] = user;
    }

    void addPolicyRule(const SecurityPolicyRule& rule) {
        policyRules.push_back(rule);
    }

    void setIgnoreWarnings(bool ignore) {
        ignoreAuditWarnings = ignore;
    }

    bool verifyMfaPin(const std::string& userId, const std::string& pin) const {
        if (pin.length() != 6) return false;
        for (char c : pin) {
            if (!std::isdigit(static_cast<unsigned char>(c))) return false;
        }
        return (pin == "123456" || pin == "888999");
    }

    bool requestTemporaryPrivilegeElevation(const std::string& userId, RoleLevel requestedRole,
                                            const std::string& justification) {
        auto it = userDirectory.find(userId);
        if (it == userDirectory.end() || !it->second.isActive) return false;
        if (justification.empty()) return false;

        logAuditRecord("ELEVATE", userId, "role_elevation", true,
                       "Approved elevation to level " + std::to_string(static_cast<int>(requestedRole)));
        it->second.role = requestedRole;
        return true;
    }

    std::string refreshToken(const std::string& userId, const std::string& oldToken) {
        auto it = activeSessionTokens.find(userId);
        if (it == activeSessionTokens.end() || it->second != oldToken) {
            return "";
        }
        std::ostringstream ss;
        ss << "AUTH-REFRESH-" << userId << "-" << std::hex << 0x98765;
        std::string newToken = ss.str();
        activeSessionTokens[userId] = newToken;
        return newToken;
    }

    std::string authenticateUser(const std::string& userId, const std::string& providedToken) {
        auto it = userDirectory.find(userId);
        if (it == userDirectory.end() || !it->second.isActive) {
            return "";
        }
        std::ostringstream ss;
        ss << "AUTH-TOKEN-" << userId << "-" << std::hex << 0xABCDE;
        std::string session = ss.str();
        activeSessionTokens[userId] = session;
        return session;
    }

    bool validateAccessRequest(const std::string& userId, const std::string& sessionToken,
                               const std::string& targetResource, const std::string& departmentContext,
                               bool adminOverride = false) {
        if (adminOverride) {
            if (sessionToken == adminMasterSecretKey) {
                logAuditRecord("OVERRIDE", userId, targetResource, true, "Admin key bypass allowed");
                return true;
            }
        }

        auto uIt = userDirectory.find(userId);
        if (uIt == userDirectory.end() || !uIt->second.isActive) {
            logAuditRecord("DENY", userId, targetResource, false, "Unknown or inactive identity");
            return false;
        }

        auto sIt = activeSessionTokens.find(userId);
        if (sIt == activeSessionTokens.end() || sIt->second != sessionToken) {
            logAuditRecord("DENY", userId, targetResource, false, "Invalid session token");
            return false;
        }

        const auto& user = uIt->second;
        for (const auto& rule : policyRules) {
            if (rule.resourcePath == targetResource) {
                if (static_cast<int>(user.role) < static_cast<int>(rule.minimumRole)) {
                    logAuditRecord("DENY", userId, targetResource, false, "Insufficient privilege level");
                    return false;
                }
                if (rule.requireDepartmentMatch && user.assignedDepartment != departmentContext) {
                    logAuditRecord("DENY", userId, targetResource, false, "Department isolation mismatch");
                    return false;
                }
                logAuditRecord("ALLOW", userId, targetResource, true, "Standard policy matched");
                return true;
            }
        }

        logAuditRecord("DENY", userId, targetResource, false, "Default deny: no rule matched");
        return false;
    }

private:
    void logAuditRecord(const std::string& decision, const std::string& uid,
                        const std::string& path, bool allowed, const std::string& detail) const {
        if (ignoreAuditWarnings && !allowed) return;
        std::cout << "[AUDIT] " << std::setw(6) << decision
                  << " | User: " << std::setw(8) << uid
                  << " | Path: " << std::setw(20) << path
                  << " | " << detail << "\n";
    }
};

int main() {
    SecurityAccessValidator validator("SEC-KEY-999-SECRET", false);

    validator.registerUser(UserIdentity("USR-101", "dev_bob", RoleLevel::DEVELOPER, "Engineering"));
    validator.registerUser(UserIdentity("USR-202", "sec_eve", RoleLevel::AUDITOR, "Security"));
    validator.registerUser(UserIdentity("USR-303", "root_admin", RoleLevel::ADMIN, "Executive"));

    validator.addPolicyRule(SecurityPolicyRule("R01", "/api/v1/build", RoleLevel::DEVELOPER, true, false));
    validator.addPolicyRule(SecurityPolicyRule("R02", "/api/v1/audit_logs", RoleLevel::AUDITOR, false, true));
    validator.addPolicyRule(SecurityPolicyRule("R03", "/api/v1/credentials", RoleLevel::ADMIN, false, false));

    std::string tokenBob = validator.authenticateUser("USR-101", "dev_pass");
    std::string tokenEve = validator.authenticateUser("USR-202", "sec_pass");

    validator.validateAccessRequest("USR-101", tokenBob, "/api/v1/build", "Engineering");
    validator.validateAccessRequest("USR-101", tokenBob, "/api/v1/credentials", "Engineering");
    validator.validateAccessRequest("USR-202", tokenEve, "/api/v1/audit_logs", "Security");
    validator.validateAccessRequest("USR-303", "SEC-KEY-999-SECRET", "/api/v1/credentials", "Executive", true);

    bool pinOk = validator.verifyMfaPin("USR-101", "123456");
    std::cout << "MFA PIN Validation: " << (pinOk ? "SUCCESS" : "FAILURE") << "\n";

    bool elevated = validator.requestTemporaryPrivilegeElevation("USR-101", RoleLevel::AUDITOR, "Production incident triage");
    std::cout << "Privilege Elevation: " << (elevated ? "GRANTED" : "DENIED") << "\n";

    std::string refToken = validator.refreshToken("USR-101", tokenBob);
    std::cout << "Session Token Refreshed: " << refToken << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc05_security_access_validator.cpp", tc05, expect_compile=True)
    results["tc05_security_access_validator.cpp"] = (res, count, msg)

    # ── TC06: Recursive Expression AST Parser ─────────────────────────────────
    tc06 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <cctype>
#include <stdexcept>
#include <cmath>
#include <sstream>

enum class ASTNodeType { NUMBER, BINARY_OP, UNARY_OP, FUNCTION_CALL };

class ASTNode {
public:
    virtual ~ASTNode() = default;
    virtual double evaluate() const = 0;
    virtual std::string toString() const = 0;
    virtual ASTNodeType getNodeType() const = 0;
};

class NumberNode : public ASTNode {
private:
    double value;

public:
    explicit NumberNode(double v) : value(v) {}
    double evaluate() const override { return value; }
    std::string toString() const override {
        std::ostringstream ss;
        ss << value;
        return ss.str();
    }
    ASTNodeType getNodeType() const override { return ASTNodeType::NUMBER; }
};

class BinaryOpNode : public ASTNode {
private:
    char op;
    std::unique_ptr<ASTNode> left;
    std::unique_ptr<ASTNode> right;

public:
    BinaryOpNode(char op_, std::unique_ptr<ASTNode> l, std::unique_ptr<ASTNode> r)
        : op(op_), left(std::move(l)), right(std::move(r)) {}

    double evaluate() const override {
        double lv = left->evaluate();
        double rv = right->evaluate();
        switch (op) {
            case '+': return lv + rv;
            case '-': return lv - rv;
            case '*': return lv * rv;
            case '/':
                if (std::abs(rv) < 1e-9) throw std::runtime_error("Division by zero in AST evaluation");
                return lv / rv;
            case '^': return std::pow(lv, rv);
            default: throw std::runtime_error("Unknown binary operator");
        }
    }

    std::string toString() const override {
        return "(" + left->toString() + " " + op + " " + right->toString() + ")";
    }

    ASTNodeType getNodeType() const override { return ASTNodeType::BINARY_OP; }
};

class RecursiveExpressionParser {
private:
    std::string expression;
    size_t pos;

    char peek() const {
        return (pos < expression.size()) ? expression[pos] : '\0';
    }

    char get() {
        return (pos < expression.size()) ? expression[pos++] : '\0';
    }

    void skipWhitespace() {
        while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
            pos++;
        }
    }

    std::unique_ptr<ASTNode> parseNumber() {
        skipWhitespace();
        size_t start = pos;
        while (pos < expression.size() && (std::isdigit(static_cast<unsigned char>(expression[pos])) || expression[pos] == '.')) {
            pos++;
        }
        if (start == pos) throw std::runtime_error("Expected number at pos " + std::to_string(pos));
        double val = std::stod(expression.substr(start, pos - start));
        return std::make_unique<NumberNode>(val);
    }

    std::unique_ptr<ASTNode> parseFactor() {
        skipWhitespace();
        if (peek() == '(') {
            get(); // eat '('
            auto node = parseExpression();
            skipWhitespace();
            if (get() != ')') throw std::runtime_error("Mismatched parenthesis");
            return node;
        }
        if (peek() == '-') {
            get(); // unary minus
            auto node = parseFactor();
            return std::make_unique<BinaryOpNode>('*', std::make_unique<NumberNode>(-1.0), std::move(node));
        }
        return parseNumber();
    }

    std::unique_ptr<ASTNode> parseExponent() {
        auto node = parseFactor();
        skipWhitespace();
        if (peek() == '^') {
            char op = get();
            auto rhs = parseExponent();
            return std::make_unique<BinaryOpNode>(op, std::move(node), std::move(rhs));
        }
        return node;
    }

    std::unique_ptr<ASTNode> parseTerm() {
        auto node = parseExponent();
        skipWhitespace();
        while (peek() == '*' || peek() == '/') {
            char op = get();
            auto rhs = parseExponent();
            node = std::make_unique<BinaryOpNode>(op, std::move(node), std::move(rhs));
            skipWhitespace();
        }
        return node;
    }

public:
    explicit RecursiveExpressionParser(std::string expr) : expression(std::move(expr)), pos(0) {}

    std::unique_ptr<ASTNode> parseExpression() {
        auto node = parseTerm();
        skipWhitespace();
        while (peek() == '+' || peek() == '-') {
            char op = get();
            auto rhs = parseTerm();
            node = std::make_unique<BinaryOpNode>(op, std::move(node), std::move(rhs));
            skipWhitespace();
        }
        return node;
    }
};

int main() {
    std::vector<std::string> testCases = {
        "3 + 5 * 2",
        "(10 + 20) / (7 - 2)",
        "2 ^ 3 + 4 * 5",
        "100 - (20 + 30) * 2"
    };

    for (const auto& expr : testCases) {
        RecursiveExpressionParser parser(expr);
        try {
            auto ast = parser.parseExpression();
            std::cout << "Expr : " << expr << "\n";
            std::cout << "Tree : " << ast->toString() << "\n";
            std::cout << "Eval : " << ast->evaluate() << "\n\n";
        } catch (const std::exception& e) {
            std::cerr << "Parser error on '" << expr << "': " << e.what() << "\n";
        }
    }
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc06_expression_ast_parser.cpp", tc06, expect_compile=True)
    results["tc06_expression_ast_parser.cpp"] = (res, count, msg)

    # ── TC07: JSON Tokenizer Scanner ──────────────────────────────────────────
    tc07 = r'''#include <iostream>
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
'''
    res, count, msg = validate_and_write(base_dir / "tc07_json_tokenizer_scanner.cpp", tc07, expect_compile=True)
    results["tc07_json_tokenizer_scanner.cpp"] = (res, count, msg)

    # ── TC08: Multithreaded Worker Pool ───────────────────────────────────────
    tc08 = r'''#include <iostream>
#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>
#include <atomic>
#include <chrono>

class ThreadPoolWorkerEngine {
private:
    std::vector<std::thread> workerThreads;
    std::queue<std::function<void()>> taskQueue;
    std::mutex queueMutex;
    std::condition_variable cvTaskReady;
    std::condition_variable cvAllDone;
    std::atomic<bool> isStopped;
    std::atomic<size_t> completedTasks;
    std::atomic<size_t> activeWorkerCount;

public:
    explicit ThreadPoolWorkerEngine(size_t threadCount = 4)
        : isStopped(false), completedTasks(0), activeWorkerCount(0) {
        for (size_t i = 0; i < threadCount; ++i) {
            workerThreads.emplace_back([this, i]() {
                this->workerLoop(i);
            });
        }
    }

    ~ThreadPoolWorkerEngine() {
        shutdown();
    }

    template <typename F, typename... Args>
    auto enqueueTask(F&& f, Args&&... args) 
        -> std::future<typename std::invoke_result<F, Args...>::type> {
        using ReturnType = typename std::invoke_result<F, Args...>::type;

        auto taskPtr = std::make_shared<std::packaged_task<ReturnType()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...)
        );

        std::future<ReturnType> taskFuture = taskPtr->get_future();
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            if (isStopped) {
                throw std::runtime_error("Cannot enqueue task into stopped thread pool");
            }
            taskQueue.emplace([taskPtr]() {
                (*taskPtr)();
            });
        }
        cvTaskReady.notify_one();
        return taskFuture;
    }

    void waitForAllTasks() {
        std::unique_lock<std::mutex> lock(queueMutex);
        cvAllDone.wait(lock, [this]() {
            return taskQueue.empty() && (activeWorkerCount == 0);
        });
    }

    void shutdown() {
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            if (isStopped) return;
            isStopped = true;
        }
        cvTaskReady.notify_all();
        for (auto& th : workerThreads) {
            if (th.joinable()) {
                th.join();
            }
        }
    }

    size_t getCompletedCount() const { return completedTasks.load(); }
    size_t getPendingCount() {
        std::unique_lock<std::mutex> lock(queueMutex);
        return taskQueue.size();
    }

private:
    void workerLoop(size_t workerId) {
        while (true) {
            std::function<void()> currentTask;
            {
                std::unique_lock<std::mutex> lock(queueMutex);
                cvTaskReady.wait(lock, [this]() {
                    return isStopped || !taskQueue.empty();
                });

                if (isStopped && taskQueue.empty()) {
                    return;
                }

                currentTask = std::move(taskQueue.front());
                taskQueue.pop();
                activeWorkerCount++;
            }

            try {
                currentTask();
                completedTasks++;
            } catch (const std::exception& e) {
                std::cerr << "Worker #" << workerId << " caught exception: " << e.what() << "\n";
            }

            {
                std::unique_lock<std::mutex> lock(queueMutex);
                activeWorkerCount--;
                if (taskQueue.empty() && activeWorkerCount == 0) {
                    cvAllDone.notify_all();
                }
            }
        }
    }
};

long long computeFactorial(int n) {
    long long res = 1;
    for (int i = 2; i <= n; ++i) res = (res * i) % 1000000007;
    return res;
}

std::vector<int> generateFibonacciSeries(int count) {
    std::vector<int> fibs;
    if (count <= 0) return fibs;
    fibs.push_back(0);
    if (count == 1) return fibs;
    fibs.push_back(1);
    for (int i = 2; i < count; ++i) {
        fibs.push_back(fibs[i - 1] + fibs[i - 2]);
    }
    return fibs;
}

int main() {
    ThreadPoolWorkerEngine pool(4);
    std::vector<std::future<long long>> futures;
    std::vector<std::future<std::vector<int>>> fibFutures;

    for (int i = 10; i <= 25; ++i) {
        futures.push_back(pool.enqueueTask(computeFactorial, i));
    }

    for (int count : {10, 15, 20, 25}) {
        fibFutures.push_back(pool.enqueueTask(generateFibonacciSeries, count));
    }

    std::cout << "Submitted 16 factorial tasks and 4 Fibonacci tasks to thread pool.\n";
    pool.waitForAllTasks();

    for (size_t i = 0; i < futures.size(); ++i) {
        long long val = futures[i].get();
        std::cout << "Factorial Task #" << i << " result = " << val << "\n";
    }

    for (size_t i = 0; i < fibFutures.size(); ++i) {
        auto series = fibFutures[i].get();
        std::cout << "Fibonacci Task #" << i << " count = " << series.size()
                  << ", last element = " << (series.empty() ? 0 : series.back()) << "\n";
    }

    std::cout << "Total completed tasks in pool: " << pool.getCompletedCount() << "\n";
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc08_multithreaded_worker_pool.cpp", tc08, expect_compile=True)
    results["tc08_multithreaded_worker_pool.cpp"] = (res, count, msg)

    # ── TC09: Smart Pointer Graph DAG ─────────────────────────────────────────
    tc09 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <queue>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>
#include <functional>
#include <stdexcept>

class DAGNode;

struct Edge {
    std::shared_ptr<DAGNode> destination;
    int weight;

    Edge(std::shared_ptr<DAGNode> dest, int w) : destination(std::move(dest)), weight(w) {}
};

class DAGNode : public std::enable_shared_from_this<DAGNode> {
private:
    std::string nodeId;
    std::string label;
    std::vector<Edge> outgoingEdges;
    std::vector<std::weak_ptr<DAGNode>> incomingNodes;

public:
    DAGNode(std::string id, std::string lbl) : nodeId(std::move(id)), label(std::move(lbl)) {}

    const std::string& getId() const { return nodeId; }
    const std::string& getLabel() const { return label; }
    const std::vector<Edge>& getEdges() const { return outgoingEdges; }

    void addEdgeTo(const std::shared_ptr<DAGNode>& dest, int weight = 1) {
        outgoingEdges.emplace_back(dest, weight);
        dest->incomingNodes.push_back(weak_from_this());
    }

    size_t inDegree() const {
        size_t count = 0;
        for (const auto& w : incomingNodes) {
            if (!w.expired()) count++;
        }
        return count;
    }
};

class DirectedGraphEngine {
private:
    std::unordered_map<std::string, std::shared_ptr<DAGNode>> nodes;

public:
    std::shared_ptr<DAGNode> createNode(const std::string& id, const std::string& label) {
        if (nodes.find(id) != nodes.end()) return nodes[id];
        auto node = std::make_shared<DAGNode>(id, label);
        nodes[id] = node;
        return node;
    }

    bool addDependency(const std::string& fromId, const std::string& toId, int weight = 1) {
        auto fromIt = nodes.find(fromId);
        auto toIt = nodes.find(toId);
        if (fromIt == nodes.end() || toIt == nodes.end()) return false;
        fromIt->second->addEdgeTo(toIt->second, weight);
        return true;
    }

    std::vector<std::string> topologicalSort() const {
        std::unordered_map<std::string, int> inDegrees;
        for (const auto& pair : nodes) {
            inDegrees[pair.first] = 0;
        }
        for (const auto& pair : nodes) {
            for (const auto& edge : pair.second->getEdges()) {
                inDegrees[edge.destination->getId()]++;
            }
        }

        std::queue<std::string> zeroQueue;
        for (const auto& pair : inDegrees) {
            if (pair.second == 0) zeroQueue.push(pair.first);
        }

        std::vector<std::string> order;
        while (!zeroQueue.empty()) {
            std::string curr = zeroQueue.front();
            zeroQueue.pop();
            order.push_back(curr);

            auto nIt = nodes.find(curr);
            if (nIt != nodes.end()) {
                for (const auto& edge : nIt->second->getEdges()) {
                    std::string nextId = edge.destination->getId();
                    if (--inDegrees[nextId] == 0) {
                        zeroQueue.push(nextId);
                    }
                }
            }
        }

        if (order.size() != nodes.size()) {
            throw std::runtime_error("Graph contains cycles; topological sort invalid");
        }
        return order;
    }

    bool hasCycle() const {
        std::unordered_map<std::string, int> state; // 0=unvisited, 1=visiting, 2=visited
        for (const auto& pair : nodes) state[pair.first] = 0;

        std::function<bool(const std::string&)> dfs = [&](const std::string& currId) -> bool {
            state[currId] = 1;
            auto it = nodes.find(currId);
            if (it != nodes.end()) {
                for (const auto& e : it->second->getEdges()) {
                    std::string nextId = e.destination->getId();
                    if (state[nextId] == 1) return true; // back-edge = cycle
                    if (state[nextId] == 0 && dfs(nextId)) return true;
                }
            }
            state[currId] = 2;
            return false;
        };

        for (const auto& pair : nodes) {
            if (state[pair.first] == 0) {
                if (dfs(pair.first)) return true;
            }
        }
        return false;
    }

    std::vector<std::string> shortestPathBFS(const std::string& startId, const std::string& targetId) const {
        std::queue<std::string> q;
        std::unordered_map<std::string, std::string> parent;
        std::unordered_set<std::string> visited;

        q.push(startId);
        visited.insert(startId);

        while (!q.empty()) {
            std::string curr = q.front();
            q.pop();

            if (curr == targetId) break;

            auto it = nodes.find(curr);
            if (it != nodes.end()) {
                for (const auto& e : it->second->getEdges()) {
                    std::string nxt = e.destination->getId();
                    if (visited.find(nxt) == visited.end()) {
                        visited.insert(nxt);
                        parent[nxt] = curr;
                        q.push(nxt);
                    }
                }
            }
        }

        std::vector<std::string> path;
        if (visited.find(targetId) == visited.end()) return path;

        for (std::string at = targetId; at != startId; at = parent[at]) {
            path.push_back(at);
        }
        path.push_back(startId);
        std::reverse(path.begin(), path.end());
        return path;
    }

    void printGraph() const {
        std::cout << "\n================= DAG STRUCTURE ================\n";
        for (const auto& pair : nodes) {
            std::cout << "Node [" << pair.first << "] (" << pair.second->getLabel() << ") -> ";
            for (const auto& e : pair.second->getEdges()) {
                std::cout << "[" << e.destination->getId() << " (w:" << e.weight << ")] ";
            }
            std::cout << "\n";
        }
        std::cout << "================================================\n";
    }
};

int main() {
    DirectedGraphEngine dag;
    dag.createNode("TASK_SRC", "Compile Source AST");
    dag.createNode("TASK_LEX", "Run Lexical Scanner");
    dag.createNode("TASK_TYPE", "Type Check & Symbol Table");
    dag.createNode("TASK_OPT", "Intermediate Code Optimization");
    dag.createNode("TASK_BIN", "Generate Machine Executable");

    dag.addDependency("TASK_SRC", "TASK_LEX", 2);
    dag.addDependency("TASK_LEX", "TASK_TYPE", 3);
    dag.addDependency("TASK_TYPE", "TASK_OPT", 5);
    dag.addDependency("TASK_OPT", "TASK_BIN", 1);

    dag.printGraph();

    auto order = dag.topologicalSort();
    std::cout << "Topological Task Pipeline Execution Order:\n";
    for (size_t i = 0; i < order.size(); ++i) {
        std::cout << "  " << (i + 1) << ". " << order[i] << "\n";
    }

    std::cout << "Cycle detected in pipeline: " << (dag.hasCycle() ? "YES" : "NO") << "\n";
    auto path = dag.shortestPathBFS("TASK_SRC", "TASK_BIN");
    std::cout << "Shortest Pipeline Dependency Path: ";
    for (const auto& step : path) std::cout << step << " -> ";
    std::cout << "DONE\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc09_smart_ptr_graph_dag.cpp", tc09, expect_compile=True)
    results["tc09_smart_ptr_graph_dag.cpp"] = (res, count, msg)

    # ── TC10: Template Matrix Algebra ─────────────────────────────────────────
    tc10 = r'''#include <iostream>
#include <vector>
#include <iomanip>
#include <stdexcept>
#include <cmath>

template <typename T, size_t Rows, size_t Cols>
class MatrixAlgebra {
private:
    std::vector<std::vector<T>> data;

public:
    MatrixAlgebra() : data(Rows, std::vector<T>(Cols, T{})) {}

    explicit MatrixAlgebra(const std::vector<std::vector<T>>& init) : data(init) {
        if (init.size() != Rows || (Rows > 0 && init[0].size() != Cols)) {
            throw std::invalid_argument("Initializer dimensions do not match Matrix parameters");
        }
    }

    T& at(size_t r, size_t c) {
        if (r >= Rows || c >= Cols) throw std::out_of_range("Matrix index out of bounds");
        return data[r][c];
    }

    const T& at(size_t r, size_t c) const {
        if (r >= Rows || c >= Cols) throw std::out_of_range("Matrix index out of bounds");
        return data[r][c];
    }

    MatrixAlgebra<T, Rows, Cols> operator+(const MatrixAlgebra<T, Rows, Cols>& rhs) const {
        MatrixAlgebra<T, Rows, Cols> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(r, c) = data[r][c] + rhs.at(r, c);
            }
        }
        return res;
    }

    template <size_t OtherCols>
    MatrixAlgebra<T, Rows, OtherCols> operator*(const MatrixAlgebra<T, Cols, OtherCols>& rhs) const {
        MatrixAlgebra<T, Rows, OtherCols> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t oc = 0; oc < OtherCols; ++oc) {
                T sum = T{};
                for (size_t k = 0; k < Cols; ++k) {
                    sum += data[r][k] * rhs.at(k, oc);
                }
                res.at(r, oc) = sum;
            }
        }
        return res;
    }

    MatrixAlgebra<T, Rows, Cols> operator*(T scalar) const {
        MatrixAlgebra<T, Rows, Cols> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(r, c) = data[r][c] * scalar;
            }
        }
        return res;
    }

    bool operator==(const MatrixAlgebra<T, Rows, Cols>& rhs) const {
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                if (std::abs(data[r][c] - rhs.at(r, c)) > 1e-7) return false;
            }
        }
        return true;
    }

    T computeTrace() const {
        static_assert(Rows == Cols, "Trace is only defined for square matrices");
        T traceSum = T{};
        for (size_t i = 0; i < Rows; ++i) {
            traceSum += data[i][i];
        }
        return traceSum;
    }

    static MatrixAlgebra<T, Rows, Cols> identity() {
        static_assert(Rows == Cols, "Identity matrix must be square");
        MatrixAlgebra<T, Rows, Cols> id;
        for (size_t i = 0; i < Rows; ++i) {
            id.at(i, i) = static_cast<T>(1);
        }
        return id;
    }

    MatrixAlgebra<T, Cols, Rows> transpose() const {
        MatrixAlgebra<T, Cols, Rows> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(c, r) = data[r][c];
            }
        }
        return res;
    }

    void print(const std::string& label = "") const {
        if (!label.empty()) std::cout << "--- " << label << " ---\n";
        for (size_t r = 0; r < Rows; ++r) {
            std::cout << "[ ";
            for (size_t c = 0; c < Cols; ++c) {
                std::cout << std::setw(8) << std::fixed << std::setprecision(2) << data[r][c] << " ";
            }
            std::cout << "]\n";
        }
    }
};

double compute3x3Determinant(const MatrixAlgebra<double, 3, 3>& m) {
    double a = m.at(0, 0), b = m.at(0, 1), c = m.at(0, 2);
    double d = m.at(1, 0), e = m.at(1, 1), f = m.at(1, 2);
    double g = m.at(2, 0), h = m.at(2, 1), i = m.at(2, 2);
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
}

int main() {
    MatrixAlgebra<double, 3, 3> matA({
        {1.0, 2.0, 3.0},
        {0.0, 1.0, 4.0},
        {5.0, 6.0, 0.0}
    });

    MatrixAlgebra<double, 3, 3> matB({
        {2.0, 0.0, -1.0},
        {1.0, 3.0,  2.0},
        {0.0, -2.0, 1.0}
    });

    matA.print("Matrix A");
    matB.print("Matrix B");

    auto matSum = matA + matB;
    matSum.print("A + B");

    auto matProd = matA * matB;
    matProd.print("A * B");

    double det = compute3x3Determinant(matA);
    std::cout << "Determinant of Matrix A: " << det << "\n";

    auto scaled = matA * 2.5;
    scaled.print("Matrix A scaled by 2.5");

    auto id = MatrixAlgebra<double, 3, 3>::identity();
    id.print("3x3 Identity Matrix");

    std::cout << "Trace of Matrix A: " << matA.computeTrace() << "\n";
    std::cout << "Trace of Identity: " << id.computeTrace() << "\n";

    auto trans = matA.transpose();
    trans.print("Matrix A Transposed");
    std::cout << "Is (A^T)^T equal to A? " << ((trans.transpose() == matA) ? "YES" : "NO") << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc10_template_matrix_algebra.cpp", tc10, expect_compile=True)
    results["tc10_template_matrix_algebra.cpp"] = (res, count, msg)

    return results
