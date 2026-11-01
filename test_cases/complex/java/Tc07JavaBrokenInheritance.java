import java.util.*;

abstract class BaseRepositoryEntity {
    protected String entityId;
    protected long createdTimestamp;

    public BaseRepositoryEntity(String id) {
        this.entityId = id;
        this.createdTimestamp = System.currentTimeMillis();
    }

    public abstract void validateEntityConstraints();
    public abstract String getEntityKind();

    public String getId() { return entityId; }
}

// ERROR 1: Class does not implement abstract method 'validateEntityConstraints()' and is not declared abstract
class IncompleteCustomerEntity extends BaseRepositoryEntity {
    private String emailAddress;

    public IncompleteCustomerEntity(String id, String email) {
        super(id);
        this.emailAddress = email;
    }

    // ERROR 2: Incompatible return type in override: returns int where String is expected
    @Override
    public int getEntityKind() {
        return 42;
    }
}




class CustomerCreditHistoryAuditor {
    private final List<Double> creditHistory = new ArrayList<>();

    public void addCreditEvent(double amount) {
        creditHistory.add(amount);
    }

    public double getAverageCredit() {
        if (creditHistory.isEmpty()) return 0.0;
        double sum = 0.0;
        for (double d : creditHistory) sum += d;
        return sum / creditHistory.size();
    }
}

class CustomerNotificationService {
    private final List<String> notifications = new ArrayList<>();

    public void sendWelcomeEmail(String customerId, String email) {
        notifications.add("Sent welcome email to " + customerId + " (" + email + ")");
    }

    public void printNotifications() {
        for (String n : notifications) {
            System.out.println("  [NOTIF] " + n);
        }
    }
}

class CustomerLoyaltyProgram {
    private final String tier;
    private int pointsBalance;

    public CustomerLoyaltyProgram(String tier) {
        this.tier = tier;
        this.pointsBalance = 100;
    }

    public void addPoints(int pts) { pointsBalance += pts; }
    public int getPoints() { return pointsBalance; }
}

class CustomerAccountProfile {
    private final String customerId;
    private final String creditTier;
    private double creditLimit;

    public CustomerAccountProfile(String id, String tier, double limit) {
        this.customerId = id;
        this.creditTier = tier;
        this.creditLimit = limit;
    }

    public String getCustomerId() { return customerId; }
    public String getCreditTier() { return creditTier; }
    public double getCreditLimit() { return creditLimit; }
}

class CustomerRiskScorer {
    public static double computeScore(CustomerAccountProfile profile) {
        if ("PLATINUM".equals(profile.getCreditTier())) return 95.0;
        if ("GOLD".equals(profile.getCreditTier())) return 80.0;
        return 60.0;
    }
}

class EntitySerializationHarness {
    public static String serializeEntity(BaseRepositoryEntity e) {
        return "ENTITY[" + e.getId() + "] KIND=" + e.getEntityKind();
    }
}

class CustomerAuditReportPrinter {
    private final String departmentCode;

    public CustomerAuditReportPrinter(String dept) {
        this.departmentCode = dept;
    }

    public void printAuditHeader() {
        System.out.println("Customer Audit Department: " + departmentCode);
        System.out.println("Verification Status: ENFORCING_STRICT_SCHEMA");
    }

    public void printSummaryStats(int processed, int flagged) {
        System.out.println("Processed records: " + processed + ", Flagged: " + flagged);
    }
}

class DatabaseEntityRegistry {
    private final List<BaseRepositoryEntity> registry = new ArrayList<>();

    public void register(BaseRepositoryEntity e) {
        registry.add(e);
    }

    public void dumpRegistry() {
        System.out.println("Entity Registry contains " + registry.size() + " records.");
    }
}

public class Tc07JavaBrokenInheritance {
    public static void runDiagnosticsHeader() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 BROKEN INHERITANCE EVALUATION FIXTURE            ");
        System.out.println("   Target for Self-Healing Compiler Benchmark               ");
        System.out.println("============================================================");
        for (int k = 0; k < 25; ++k) {
            System.out.println("  [ENTITY-SLOT-" + k + "] Verifying repository entity descriptor " + k);
        }
    }

    public static void main(String[] args) {
        runDiagnosticsHeader();
        DatabaseEntityRegistry db = new DatabaseEntityRegistry();

        // ERROR 3: Cannot instantiate abstract class (or broken concrete class with unimplement abstract methods)
        IncompleteCustomerEntity customer = new IncompleteCustomerEntity("CUST-901", "alice@corp.internal");
        db.register(customer);

        // ERROR 4: Calling undefined method
        customer.invokeNonExistentPersistenceSync();

        db.dumpRegistry();
    }
}
