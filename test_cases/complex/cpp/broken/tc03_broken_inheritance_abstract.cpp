#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <iomanip>
#include <stdexcept>
#include <algorithm>

// Complex inheritance hierarchy fixture with pure virtual and access control errors.
class BankAccount {
protected:
    std::string accountNumber;
    std::string accountHolder;
    double currentBalance;
    std::vector<std::string> transactionHistory;

public:
    BankAccount(std::string accNum, std::string holder, double initialBalance)
        : accountNumber(std::move(accNum)), accountHolder(std::move(holder)), currentBalance(initialBalance) {
        transactionHistory.push_back("Account opened with balance: " + std::to_string(initialBalance));
    }

    virtual ~BankAccount() = default;

    virtual void deposit(double amount) {
        if (amount <= 0.0) {
            throw std::invalid_argument("Deposit amount must be strictly positive");
        }
        currentBalance += amount;
        transactionHistory.push_back("Deposit: +" + std::to_string(amount));
    }

    virtual bool withdraw(double amount) {
        if (amount <= 0.0 || currentBalance < amount) {
            return false;
        }
        currentBalance -= amount;
        transactionHistory.push_back("Withdrawal: -" + std::to_string(amount));
        return true;
    }

    // Pure virtual methods requiring concrete subclass implementation
    virtual double calculateMonthlyInterest() const = 0;
    virtual std::string getAccountType() const = 0;
    virtual void printAccountSummary() const = 0;

    double getBalance() const { return currentBalance; }
    const std::string& getAccountNumber() const { return accountNumber; }
    const std::string& getAccountHolder() const { return accountHolder; }

    void dumpHistory() const {
        std::cout << "Transaction Statement for " << accountNumber << " (" << accountHolder << "):
";
        for (const auto& record : transactionHistory) {
            std::cout << "  > " << record << "
";
        }
    }
};

// ERROR 1: Fails to implement pure virtual calculateMonthlyInterest(), leaving class abstract
class IncompleteSavingsAccount : public BankAccount {
private:
    double annualInterestRate;
    double minimumBalanceThreshold;

public:
    IncompleteSavingsAccount(std::string accNum, std::string holder, double balance, double rate)
        : BankAccount(std::move(accNum), std::move(holder), balance),
          annualInterestRate(rate), minimumBalanceThreshold(500.0) {}

    // ERROR 2: Incompatible return type: returns double where std::string is expected
    std::string getAccountType() const override {
        return 4.25;
    }

    void printAccountSummary() const override {
        std::cout << "[SAVINGS] " << accountNumber << " | Balance: $" << currentBalance 
                  << " | Rate: " << annualInterestRate << "%
";
    }
};

// Private inheritance hides public interface of BankAccount
class PrivateCheckingAccount : private BankAccount {
private:
    double overdraftLimit;

public:
    PrivateCheckingAccount(std::string accNum, std::string holder, double balance, double overdraft)
        : BankAccount(std::move(accNum), std::move(holder), balance), overdraftLimit(overdraft) {}

    void executeCheckPayment(double amount) {
        if (amount <= currentBalance + overdraftLimit) {
            currentBalance -= amount;
            transactionHistory.push_back("Check payment: -" + std::to_string(amount));
        }
    }

    double getUsableFunds() const {
        return currentBalance + overdraftLimit;
    }
};

class BankBranchManager {
private:
    std::string branchName;
    std::vector<std::string> operationLogs;

public:
    explicit BankBranchManager(std::string name) : branchName(std::move(name)) {}

    void logOperation(const std::string& op) {
        operationLogs.push_back(op);
    }

    void displayBranchAudit() const {
        std::cout << "
Branch: " << branchName << " Audit Log:
";
        for (const auto& entry : operationLogs) {
            std::cout << "  [AUDIT] " << entry << "
";
        }
    }
};

class AccountPortfolioAuditor {
private:
    std::vector<std::string> auditQueue;
    int reviewedCount;

public:
    AccountPortfolioAuditor() : reviewedCount(0) {}

    void queueAudit(const std::string& accId) {
        auditQueue.push_back(accId);
        reviewedCount++;
    }

    void outputAuditSummary() const {
        std::cout << "Audited total accounts: " << reviewedCount << "
";
    }
};

int main() {
    std::cout << "Starting Bank Account Hierarchy Diagnostic...
";
    BankBranchManager manager("Downtown Flagship");
    manager.logOperation("Opening daily batch processing.");

    AccountPortfolioAuditor auditor;
    auditor.queueAudit("SAV-10029");

    // ERROR 3: Cannot allocate an object of abstract type 'IncompleteSavingsAccount'
    IncompleteSavingsAccount savAcc("SAV-10029", "Alice Johnson", 4500.0, 3.5);
    savAcc.printAccountSummary();

    PrivateCheckingAccount chkAcc("CHK-90812", "Robert Smith", 1200.0, 500.0);
    chkAcc.executeCheckPayment(350.0);

    // ERROR 4: Access violation: cannot cast to inaccessible base class 'BankAccount' due to private inheritance
    BankAccount* basePtr = &chkAcc;
    std::cout << "Base Pointer Balance: " << basePtr->getBalance() << "
";

    // ERROR 5: Calling non-existent member method
    savAcc.applyCompoundBonusQuarterly();

    manager.displayBranchAudit();
    auditor.outputAuditSummary();
    return 0;
}
