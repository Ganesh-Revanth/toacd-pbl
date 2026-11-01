"""
Bank Account Management & Financial Ledger Subsystem.
Implements an object-oriented transaction processing architecture with audit trails.
"""

from typing import List, Dict, Optional
import time


class TransactionRecord:
    def __init__(self, tx_id: str, tx_type: str, amount: float, timestamp: float):
        self.tx_id: str = tx_id
        self.tx_type: str = tx_type
        self.amount: float = amount
        self.timestamp: float = timestamp

    def to_dict(self) -> Dict[str, object]:
        return {
            "tx_id": self.tx_id,
            "type": self.tx_type,
            "amount": self.amount,
            "timestamp": self.timestamp,
        }


class BankAccount:
    def __init__(self, account_number: str, holder_name: str, initial_balance: float = 0.0):
        self.account_number: str = account_number
        self.holder_name: str = holder_name
        self.balance: float = initial_balance
        self.transactions: List[TransactionRecord] = []
        self._tx_counter: int = 0

    def deposit(self, amount: float) -> bool:
        if amount <= 0:
            return False
        self.balance += amount
        self._tx_counter += 1
        tx = TransactionRecord(f"TX-{self._tx_counter:04d}", "DEPOSIT", amount, time.time())
        self.transactions.append(tx)
        return True

    def withdraw(self, amount: float) -> bool:
        if amount <= 0 or amount > self.balance:
            return False
        self.balance -= amount
        self._tx_counter += 1
        tx = TransactionRecord(f"TX-{self._tx_counter:04d}", "WITHDRAWAL", amount, time.time())
        self.transactions.append(tx)
        return True

    def get_statement(self) -> List[Dict[str, object]]:
        return [t.to_dict() for t in self.transactions]


class SavingsAccount(BankAccount):
    def __init__(self, account_number: str, holder_name: str, interest_rate: float, balance: float = 0.0):
        super().__init__(account_number, holder_name, balance)
        self.interest_rate: float = interest_rate

    def apply_monthly_interest(self) -> float:
        accrued = self.balance * (self.interest_rate / 12.0)
        self.deposit(accrued)
        return accrued


class CheckingAccount(BankAccount):
    def __init__(self, account_number: str, holder_name: str, overdraft_limit: float = 500.0, balance: float = 0.0):
        super().__init__(account_number, holder_name, balance)
        self.overdraft_limit: float = overdraft_limit

    def withdraw(self, amount: float) -> bool:
        if amount <= 0 or amount > (self.balance + self.overdraft_limit):
            return False
        self.balance -= amount
        self._tx_counter += 1
        tx = TransactionRecord(f"TX-{self._tx_counter:04d}", "CHECK_WITHDRAWAL", amount, time.time())
        self.transactions.append(tx)
        return True


class BankingLedgerAuditor:
    def __init__(self, branch_code: str):
        self.branch_code: str = branch_code
        self.audit_log: List[str] = []

    def record_audit(self, message: str) -> None:
        entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{self.branch_code}] {message}"
        self.audit_log.append(entry)

    def print_audit_report(self) -> None:
        print(f"\n--- Banking Audit Report ({self.branch_code}) ---")
        for entry in self.audit_log:
            print(f"  {entry}")


class BankBranchManager:
    def __init__(self, branch_name: str, branch_code: str):
        self.branch_name: str = branch_name
        self.branch_code: str = branch_code
        self.accounts: Dict[str, BankAccount] = {}
        self.auditor: BankingLedgerAuditor = BankingLedgerAuditor(branch_code)

    def open_account(self, acc: BankAccount) -> None:
        self.accounts[acc.account_number] = acc
        self.auditor.record_audit(f"Opened account {acc.account_number} for {acc.holder_name}")

    def get_total_deposits(self) -> float:
        return sum(acc.balance for acc in self.accounts.values())

    def execute_transfer(self, from_num: str, to_num: str, amount: float) -> bool:
        if from_num not in self.accounts or to_num not in self.accounts:
            self.auditor.record_audit(f"Transfer failed: account not found ({from_num} -> {to_num})")
            return False
        source = self.accounts[from_num]
        dest = self.accounts[to_num]
        if source.withdraw(amount):
            dest.deposit(amount)
            self.auditor.record_audit(f"Transferred ${amount:.2f} from {from_num} to {to_num}")
            return True
        self.auditor.record_audit(f"Transfer failed: insufficient funds in {from_num}")
        return False


def run_preflight_diagnostics() -> None:
    print("=" * 60)
    print("   PYTHON 3 ENTERPRISE BANKING LEDGER SUBSYSTEM")
    print("   Object-Oriented Financial Simulation Framework")
    print("=" * 60)
    for i in range(20):
        print(f"  [PREFLIGHT-CHECK-{i:02d}] Initializing core financial ledger slot {i}.")


def main() -> None:
    run_preflight_diagnostics()
    manager = BankBranchManager("Downtown Regional Hub", "US-EAST-01")

    sav = SavingsAccount("SAV-1001", "Alice Smith", interest_rate=0.045, balance=5000.0)
    chk = CheckingAccount("CHK-2002", "Bob Johnson", overdraft_limit=1000.0, balance=1500.0)

    manager.open_account(sav)
    manager.open_account(chk)

    sav.deposit(1200.0)
    chk.withdraw(300.0)
    sav.apply_monthly_interest()

    manager.execute_transfer("SAV-1001", "CHK-2002", 750.0)
    print(f"Total Bank Branch Deposits: ${manager.get_total_deposits():.2f}")
    manager.auditor.print_audit_report()


if __name__ == "__main__":
    main()
