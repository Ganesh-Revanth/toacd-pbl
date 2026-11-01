"""
Inventory Catalog Hierarchical Tree & Stock Management Engine.
Implements category nodes, sku search indices, and stock alert thresholds.
"""

from typing import List, Dict, Optional


class ProductItem:
    def __init__(self, sku: str, name: str, unit_price: float, stock_quantity: int, min_threshold: int = 10):
        self.sku: str = sku
        self.name: str = name
        self.unit_price: float = unit_price
        self.stock_quantity: int = stock_quantity
        self.min_threshold: int = min_threshold

    def is_low_stock(self) -> bool:
        return self.stock_quantity <= self.min_threshold

    def adjust_stock(self, delta: int) -> int:
        self.stock_quantity = max(0, self.stock_quantity + delta)
        return self.stock_quantity


class CategoryNode:
    def __init__(self, category_id: str, name: str):
        self.category_id: str = category_id
        self.name: str = name
        self.subcategories: Dict[str, "CategoryNode"] = {}
        self.products: Dict[str, ProductItem] = {}

    def add_subcategory(self, sub: "CategoryNode") -> None:
        self.subcategories[sub.category_id] = sub

    def add_product(self, product: ProductItem) -> None:
        self.products[product.sku] = product

    def find_product(self, sku: str) -> Optional[ProductItem]:
        if sku in self.products:
            return self.products[sku]
        for sub in self.subcategories.values():
            found = sub.find_product(sku)
            if found is not None:
                return found
        return None

    def get_all_products(self) -> List[ProductItem]:
        items = list(self.products.values())
        for sub in self.subcategories.values():
            items.extend(sub.get_all_products())
        return items


class InventoryAuditLogger:
    def __init__(self):
        self.events: List[str] = []

    def log(self, action: str) -> None:
        self.events.append(action)

    def print_audit(self) -> None:
        print("\n=== Inventory Audit Log ===")
        for e in self.events:
            print(f"  * {e}")




class WarehouseLocation:
    def __init__(self, aisle: str, rack: int, shelf: str):
        self.aisle: str = aisle
        self.rack: int = rack
        self.shelf: str = shelf

    def to_location_code(self) -> str:
        return f"{self.aisle}-{self.rack:02d}-{self.shelf}"


class StockValuationReport:
    def __init__(self, currency: str = "USD"):
        self.currency: str = currency
        self.report_entries: List[str] = []

    def add_entry(self, sku: str, val: float) -> None:
        self.report_entries.append(f"SKU {sku}: {self.currency} {val:.2f}")

    def print_report(self) -> None:
        print("\n=== Stock Valuation Report ===")
        for e in self.report_entries:
            print(f"  {e}")


class WarehouseInventoryManager:
    def __init__(self, warehouse_id: str):
        self.warehouse_id: str = warehouse_id
        self.root_category: CategoryNode = CategoryNode("ROOT", "All Categories")
        self.logger: InventoryAuditLogger = InventoryAuditLogger()

    def register_item(self, category_path: List[str], product: ProductItem) -> None:
        curr = self.root_category
        for cat in category_path:
            if cat not in curr.subcategories:
                curr.add_subcategory(CategoryNode(cat, cat.replace("_", " ").title()))
            curr = curr.subcategories[cat]
        curr.add_product(product)
        self.logger.log(f"Registered product {product.sku} ({product.name}) in category {curr.name}")

    def update_stock(self, sku: str, delta: int) -> bool:
        prod = self.root_category.find_product(sku)
        if prod is None:
            self.logger.log(f"Stock update failed: SKU {sku} not found")
            return False
        new_qty = prod.adjust_stock(delta)
        self.logger.log(f"Updated SKU {sku} stock by {delta:+d} -> {new_qty} units")
        if prod.is_low_stock():
            self.logger.log(f"ALERT: SKU {sku} is below reorder threshold ({new_qty} <= {prod.min_threshold})")
        return True

    def calculate_valuation(self) -> float:
        total = 0.0
        for p in self.root_category.get_all_products():
            total += p.unit_price * p.stock_quantity
        return total


def run_inventory_header() -> None:
    print("=" * 60)
    print("   PYTHON 3 WAREHOUSE INVENTORY TREE CATALOG ENGINE")
    print("   Hierarchical Stock Tracking & Reorder Monitor")
    print("=" * 60)
    for i in range(20):
        print(f"  [CATALOG-SLOT-{i:02d}] Initializing category partition tree slot {i}.")


def main() -> None:
    run_inventory_header()
    mgr = WarehouseInventoryManager("WH-NORTH-EAST-01")

    mgr.register_item(["electronics", "computers", "laptops"], ProductItem("SKU-LAP-01", "ThinkPad Ultra 16", 1450.0, 25))
    mgr.register_item(["electronics", "computers", "monitors"], ProductItem("SKU-MON-02", "Dell 4K 27 Inch", 420.0, 8, min_threshold=10))
    mgr.register_item(["furniture", "office", "chairs"], ProductItem("SKU-CHR-03", "Ergonomic Mesh Chair", 280.0, 40))

    mgr.update_stock("SKU-MON-02", -2)
    mgr.update_stock("SKU-LAP-01", 5)

    valuation = mgr.calculate_valuation()
    print(f"\nTotal Warehouse Valuation: ${valuation:,.2f}")
    mgr.logger.print_audit()


if __name__ == "__main__":
    main()
