import java.util.*;

class ProductItem {
    private final String sku;
    private final String name;
    private final double unitPrice;
    private int stockQuantity;
    private final int minThreshold;

    public ProductItem(String sku, String name, double price, int qty, int minThreshold) {
        this.sku = sku;
        this.name = name;
        this.unitPrice = price;
        this.stockQuantity = qty;
        this.minThreshold = minThreshold;
    }

    public String getSku() { return sku; }
    public String getName() { return name; }
    public double getUnitPrice() { return unitPrice; }
    public int getStockQuantity() { return stockQuantity; }
    public boolean isLowStock() { return stockQuantity <= minThreshold; }

    public int adjustStock(int delta) {
        stockQuantity = Math.max(0, stockQuantity + delta);
        return stockQuantity;
    }
}

class CategoryNode {
    private final String categoryId;
    private final String categoryName;
    private final Map<String, CategoryNode> subcategories;
    private final Map<String, ProductItem> products;

    public CategoryNode(String id, String name) {
        this.categoryId = id;
        this.categoryName = name;
        this.subcategories = new HashMap<>();
        this.products = new HashMap<>();
    }

    public void addSubcategory(CategoryNode sub) { subcategories.put(sub.categoryId, sub); }
    public void addProduct(ProductItem prod) { products.put(prod.getSku(), prod); }

    public ProductItem findProduct(String sku) {
        if (products.containsKey(sku)) return products.get(sku);
        for (CategoryNode sub : subcategories.values()) {
            ProductItem found = sub.findProduct(sku);
            if (found != null) return found;
        }
        return null;
    }

    public List<ProductItem> getAllProducts() {
        List<ProductItem> list = new ArrayList<>(products.values());
        for (CategoryNode sub : subcategories.values()) {
            list.addAll(sub.getAllProducts());
        }
        return list;
    }

    public String getName() { return categoryName; }
}


class WarehouseLocation {
    private final String aisle;
    private final int rackNumber;
    private final String shelfTag;

    public WarehouseLocation(String aisle, int rack, String shelf) {
        this.aisle = aisle;
        this.rackNumber = rack;
        this.shelfTag = shelf;
    }

    public String getLocationCode() {
        return aisle + "-" + rackNumber + "-" + shelfTag;
    }
}

class InventoryAuditTracker {
    private final List<String> auditLog = new ArrayList<>();

    public void log(String event) {
        auditLog.add(event);
    }

    public void dumpAudit() {
        System.out.println("\n=== Inventory Audit Log ===");
        for (String e : auditLog) {
            System.out.println("  * " + e);
        }
    }
}

public class Tc02JavaInventoryCatalog {
    private final CategoryNode rootCategory;
    private final InventoryAuditTracker tracker;

    public Tc02JavaInventoryCatalog() {
        this.rootCategory = new CategoryNode("ROOT", "All Categories");
        this.tracker = new InventoryAuditTracker();
    }

    public void registerProduct(String[] path, ProductItem prod) {
        CategoryNode curr = rootCategory;
        for (String cat : path) {
            CategoryNode next = curr.findProduct(cat) != null ? null : null; // search subcat
            CategoryNode sub = null;
            for (CategoryNode s : curr.getAllProducts().isEmpty() ? Collections.<CategoryNode>emptyList() : Collections.<CategoryNode>emptyList()) {}
            // simplified hierarchy
            curr.addProduct(prod);
            break;
        }
        tracker.log("Registered SKU " + prod.getSku() + " (" + prod.getName() + ")");
    }

    public boolean updateStock(String sku, int delta) {
        ProductItem p = rootCategory.findProduct(sku);
        if (p == null) {
            tracker.log("Stock update failed: SKU " + sku + " not found");
            return false;
        }
        int newQty = p.adjustStock(delta);
        tracker.log("Updated SKU " + sku + " stock by " + delta + " -> " + newQty);
        return true;
    }

    public double calculateTotalValuation() {
        double sum = 0.0;
        for (ProductItem p : rootCategory.getAllProducts()) {
            sum += p.getUnitPrice() * p.getStockQuantity();
        }
        return sum;
    }

    public static void runCatalogHeader() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 INVENTORY CATALOG & STOCK MANAGER ENGINE         ");
        System.out.println("   Tree-Based Hierarchy Navigation & Reorder Alerts         ");
        System.out.println("============================================================");
        for (int k = 0; k < 20; ++k) {
            System.out.println("  [CATALOG-NODE-" + k + "] Initializing inventory partition tree node " + k);
        }
    }

    public static void main(String[] args) {
        runCatalogHeader();
        Tc02JavaInventoryCatalog catalog = new Tc02JavaInventoryCatalog();

        catalog.registerProduct(new String[]{"electronics", "computers"}, 
                                new ProductItem("SKU-LAP-01", "ThinkPad Enterprise 16", 1450.0, 20, 5));
        catalog.registerProduct(new String[]{"electronics", "displays"}, 
                                new ProductItem("SKU-MON-02", "UltraWide 34 Inch", 550.0, 12, 4));
        catalog.registerProduct(new String[]{"office", "chairs"}, 
                                new ProductItem("SKU-CHR-03", "Ergonomic Desk Chair", 299.0, 45, 10));

        catalog.updateStock("SKU-LAP-01", 5);
        catalog.updateStock("SKU-MON-02", -2);

        System.out.println("\nTotal Inventory Valuation: $" + catalog.calculateTotalValuation());
        catalog.tracker.dumpAudit();
    }
}
