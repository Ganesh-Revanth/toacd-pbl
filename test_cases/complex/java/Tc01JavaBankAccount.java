import java.util.*;

class TransactionRecord {
    private final String txId;
    private final String type;
    private final double amount;
    private final long timestamp;

    public TransactionRecord(String txId, String type, double amount, long timestamp) {
        this.txId = txId;
        this.type = type;
        this.amount = amount;
        this.timestamp = timestamp;
    }

    public String getTxId() { return txId; }
    public String getType() { return type; }
    public double getAmount() { return amount; }
    public long getTimestamp() { return timestamp; }
}

abstract class BankAccount {
    protected String accountNumber;
    protected String holderName;
    protected double balance;
    protected List<TransactionRecord> history;
    protected int txCounter;

    public BankAccount(String accNum, String holder, double initialBalance) {
        this.accountNumber = accNum;
        this.holderName = holder;
        this.balance = initialBalance;
        this.history = new ArrayList<>();
        this.txCounter = 0;
    }

    public boolean deposit(double amount) {
        if (amount <= 0.0) return false;
        balance += amount;
        txCounter++;
        history.add(new TransactionRecord("TX-" + txCounter, "DEPOSIT", amount, System.currentTimeMillis()));
        return true;
    }

    public abstract boolean withdraw(double amount);
    public abstract String getAccountType();

    public double getBalance() { return balance; }
    public String getAccountNumber() { return accountNumber; }
    public String getHolderName() { return holderName; }
    public List<TransactionRecord> getHistory() { return Collections.unmodifiableList(history); }
}

class SavingsAccount extends BankAccount {
    private final double interestRate;

    public SavingsAccount(String accNum, String holder, double initialBalance, double rate) {
        super(accNum, holder, initialBalance);
        this.interestRate = rate;
    }

    @Override
    public boolean withdraw(double amount) {
        if (amount <= 0.0 || amount > balance) return false;
        balance -= amount;
        txCounter++;
        history.add(new TransactionRecord("TX-" + txCounter, "SAVINGS_WITHDRAW", amount, System.currentTimeMillis()));
        return true;
    }

    @Override
    public String getAccountType() { return "SAVINGS"; }

    public double applyMonthlyInterest() {
        double interest = balance * (interestRate / 12.0);
        deposit(interest);
        return interest;
    }
}

class CheckingAccount extends BankAccount {
    private final double overdraftLimit;

    public CheckingAccount(String accNum, String holder, double initialBalance, double overdraft) {
        super(accNum, holder, initialBalance);
        this.overdraftLimit = overdraft;
    }

    @Override
    public boolean withdraw(double amount) {
        if (amount <= 0.0 || amount > (balance + overdraftLimit)) return false;
        balance -= amount;
        txCounter++;
        history.add(new TransactionRecord("TX-" + txCounter, "CHECKING_WITHDRAW", amount, System.currentTimeMillis()));
        return true;
    }

    @Override
    public String getAccountType() { return "CHECKING"; }
}

class BankBranchAuditor {
    private final String branchTag;
    private final List<String> auditRecords;

    public BankBranchAuditor(String branchTag) {
        this.branchTag = branchTag;
        this.auditRecords = new ArrayList<>();
    }

    public void logAudit(String event) {
        auditRecords.add("[" + branchTag + "] " + event);
    }

    public void printAuditReport() {
        System.out.println("\n=== Branch Audit Report [" + branchTag + "] ===");
        for (String record : auditRecords) {
            System.out.println("  * " + record);
        }
    }
}

public class Tc01JavaBankAccount {
    private final Map<String, BankAccount> accounts;
    private final BankBranchAuditor auditor;

    public Tc01JavaBankAccount(String branchTag) {
        this.accounts = new HashMap<>();
        this.auditor = new BankBranchAuditor(branchTag);
    }

    public void addAccount(BankAccount acc) {
        accounts.put(acc.getAccountNumber(), acc);
        auditor.logAudit("Opened account " + acc.getAccountNumber() + " for " + acc.getHolderName());
    }

    public boolean transferFunds(String fromNum, String toNum, double amount) {
        BankAccount src = accounts.get(fromNum);
        BankAccount dst = accounts.get(toNum);
        if (src == null || dst == null) {
            auditor.logAudit("Transfer failed: Account not found (" + fromNum + " -> " + toNum + ")");
            return false;
        }
        if (src.withdraw(amount)) {
            dst.deposit(amount);
            auditor.logAudit("Transferred $" + amount + " from " + fromNum + " to " + toNum);
            return true;
        }
        auditor.logAudit("Transfer failed: Insufficient balance in " + fromNum);
        return false;
    }

    public static void runDiagnosticsHeader() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 ENTERPRISE BANKING LEDGER SUBSYSTEM              ");
        System.out.println("   Object-Oriented Polymorphic Financial Simulation Core    ");
        System.out.println("============================================================");
        for (int k = 0; k < 20; ++k) {
            System.out.println("  [LEDGER-SLOT-" + k + "] Initializing ledger descriptor " + k);
        }
    }

    public static void main(String[] args) {
        runDiagnosticsHeader();
        Tc01JavaBankAccount branch = new Tc01JavaBankAccount("US-EAST-FLAGSHIP");

        SavingsAccount sav = new SavingsAccount("SAV-1001", "Alice Johnson", 4500.0, 0.04);
        CheckingAccount chk = new CheckingAccount("CHK-2002", "Bob Martin", 1200.0, 500.0);

        branch.addAccount(sav);
        branch.addAccount(chk);

        sav.deposit(1000.0);
        chk.withdraw(200.0);
        sav.applyMonthlyInterest();

        branch.transferFunds("SAV-1001", "CHK-2002", 650.0);
        branch.auditor.printAuditReport();
    }
}
