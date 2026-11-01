#include <iostream>
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
