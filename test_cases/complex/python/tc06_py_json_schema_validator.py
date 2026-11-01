"""
Recursive JSON Schema Type Checking & Constraint Validation Engine.
Performs structural typing assertions, required key lookups, and constraint reporting.
"""

from typing import Dict, List, Any, Optional, Tuple


class SchemaValidationError:
    def __init__(self, path: str, message: str):
        self.path: str = path
        self.message: str = message

    def __repr__(self) -> str:
        return f"ValidationError(path='{self.path}', error='{self.message}')"


class SchemaDefinition:
    def __init__(self, schema_dict: Dict[str, Any]):
        self.raw_schema: Dict[str, Any] = schema_dict

    def validate(self, instance: Any, current_path: str = "$") -> List[SchemaValidationError]:
        errors: List[SchemaValidationError] = []
        expected_type = self.raw_schema.get("type")

        if expected_type == "object":
            if not isinstance(instance, dict):
                return [SchemaValidationError(current_path, f"Expected object, got {type(instance).__name__}")]

            required = self.raw_schema.get("required", [])
            for req_key in required:
                if req_key not in instance:
                    errors.append(SchemaValidationError(f"{current_path}.{req_key}", "Required property is missing"))

            properties = self.raw_schema.get("properties", {})
            for key, val in instance.items():
                if key in properties:
                    sub_schema = SchemaDefinition(properties[key])
                    sub_errors = sub_schema.validate(val, f"{current_path}.{key}")
                    errors.extend(sub_errors)

        elif expected_type == "array":
            if not isinstance(instance, list):
                return [SchemaValidationError(current_path, f"Expected array, got {type(instance).__name__}")]

            item_schema_dict = self.raw_schema.get("items")
            if item_schema_dict:
                sub_schema = SchemaDefinition(item_schema_dict)
                for idx, item in enumerate(instance):
                    errors.extend(sub_schema.validate(item, f"{current_path}[{idx}]"))

        elif expected_type == "string":
            if not isinstance(instance, str):
                errors.append(SchemaValidationError(current_path, f"Expected string, got {type(instance).__name__}"))

        elif expected_type == "number":
            if not isinstance(instance, (int, float)) or isinstance(instance, bool):
                errors.append(SchemaValidationError(current_path, f"Expected number, got {type(instance).__name__}"))

        elif expected_type == "boolean":
            if not isinstance(instance, bool):
                errors.append(SchemaValidationError(current_path, f"Expected boolean, got {type(instance).__name__}"))

        return errors




class ValidationMetricsCollector:
    def __init__(self):
        self.checked_fields: int = 0

    def record_field(self) -> None:
        self.checked_fields += 1


class CustomFormatRegistry:
    def __init__(self):
        self.registered_formats: Dict[str, str] = {
            "email": r"^[^@]+@[^@]+\.[^@]+$",
            "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        }

    def register_format(self, name: str, pattern: str) -> None:
        self.registered_formats[name] = pattern

    def has_format(self, name: str) -> bool:
        return name in self.registered_formats


class SchemaValidationPipeline:
    def __init__(self):
        self.validation_records: List[Tuple[str, int, bool]] = []

    def run_check(self, name: str, schema: SchemaDefinition, payload: Any) -> bool:
        errors = schema.validate(payload)
        is_valid = len(errors) == 0
        self.validation_records.append((name, len(errors), is_valid))

        print(f"\nValidation Result for [{name}]: {'PASSED' if is_valid else 'FAILED'}")
        for err in errors:
            print(f"  ! {err}")
        return is_valid

    def dump_summary(self) -> None:
        print("\n=== Validation Pipeline Summary ===")
        for name, err_count, ok in self.validation_records:
            print(f"  * Schema: {name:20s} | Errors: {err_count:2d} | Valid: {ok}")


def run_schema_header() -> None:
    print("=" * 60)
    print("   PYTHON 3 RECURSIVE JSON SCHEMA TYPE VALIDATOR")
    print("   Structural Schema Assertions & Path Traversal Pipeline")
    print("=" * 60)
    for i in range(20):
        print(f"  [SCHEMA-SLOT-{i:02d}] Pre-compiling schema validation AST node {i}.")


def main() -> None:
    run_schema_header()
    pipeline = SchemaValidationPipeline()

    user_schema = SchemaDefinition({
        "type": "object",
        "required": ["id", "username", "is_active", "roles"],
        "properties": {
            "id": {"type": "number"},
            "username": {"type": "string"},
            "is_active": {"type": "boolean"},
            "roles": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    })

    valid_payload = {
        "id": 1042,
        "username": "developer_alice",
        "is_active": True,
        "roles": ["viewer", "editor"]
    }

    invalid_payload = {
        "id": "not_a_number",
        "is_active": "true_string",
        "roles": [100, 200]
    }

    pipeline.run_check("ValidUserPayload", user_schema, valid_payload)
    pipeline.run_check("InvalidUserPayload", user_schema, invalid_payload)
    pipeline.dump_summary()


if __name__ == "__main__":
    main()
