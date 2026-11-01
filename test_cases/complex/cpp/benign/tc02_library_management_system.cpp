#include <iostream>
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
