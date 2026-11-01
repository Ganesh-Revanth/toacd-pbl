import java.util.*;

class SchemaValidationError {
    private final String path;
    private final String message;

    public SchemaValidationError(String path, String message) {
        this.path = path;
        this.message = message;
    }

    public String getPath() { return path; }
    public String getMessage() { return message; }

    @Override
    public String toString() {
        return "ValidationError(path='" + path + "', message='" + message + "')";
    }
}

class JsonSchemaDefinition {
    private final String expectedType;
    private final List<String> requiredFields;
    private final Map<String, JsonSchemaDefinition> propertySchemas;

    public JsonSchemaDefinition(String expectedType, List<String> required) {
        this.expectedType = expectedType;
        this.requiredFields = new ArrayList<>(required);
        this.propertySchemas = new HashMap<>();
    }

    public void addPropertySchema(String prop, JsonSchemaDefinition schema) {
        propertySchemas.put(prop, schema);
    }

    public List<SchemaValidationError> validate(Object instance, String currentPath) {
        List<SchemaValidationError> errors = new ArrayList<>();
        if ("object".equals(expectedType)) {
            if (!(instance instanceof Map)) {
                errors.add(new SchemaValidationError(currentPath, "Expected Object, got " + (instance == null ? "null" : instance.getClass().getSimpleName())));
                return errors;
            }
            Map<?, ?> map = (Map<?, ?>) instance;
            for (String req : requiredFields) {
                if (!map.containsKey(req)) {
                    errors.add(new SchemaValidationError(currentPath + "." + req, "Required field missing"));
                }
            }
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (propertySchemas.containsKey(key)) {
                    errors.addAll(propertySchemas.get(key).validate(entry.getValue(), currentPath + "." + key));
                }
            }
        } else if ("string".equals(expectedType)) {
            if (!(instance instanceof String)) {
                errors.add(new SchemaValidationError(currentPath, "Expected String"));
            }
        } else if ("number".equals(expectedType)) {
            if (!(instance instanceof Number)) {
                errors.add(new SchemaValidationError(currentPath, "Expected Number"));
            }
        }
        return errors;
    }
}


class CustomFormatValidator {
    private final Map<String, String> formatPatterns = new HashMap<>();

    public void register(String name, String regex) {
        formatPatterns.put(name, regex);
    }

    public boolean validateFormat(String name, String val) {
        String pat = formatPatterns.get(name);
        return pat == null || (val != null && val.matches(pat));
    }
}

class SchemaValidationContext {
    private final String rootDocId;
    private int assertionCount = 0;

    public SchemaValidationContext(String docId) { this.rootDocId = docId; }
    public void incrementAssertions() { assertionCount++; }
    public int getAssertions() { return assertionCount; }
}

class ValidationPipelineAuditor {
    private final List<String> validationSummary = new ArrayList<>();

    public void record(String name, boolean pass) {
        validationSummary.add("Schema [" + name + "] -> " + (pass ? "VALID" : "INVALID"));
    }

    public void dumpSummary() {
        System.out.println("\n=== Validation Pipeline Report ===");
        for (String s : validationSummary) {
            System.out.println("  * " + s);
        }
    }
}

public class Tc06JavaJsonValidator {
    public static void runValidatorHeader() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 RECURSIVE JSON SCHEMA TYPE VALIDATOR ENGINE      ");
        System.out.println("   Structural Hierarchy Checking & Path Error Assertion     ");
        System.out.println("============================================================");
        for (int k = 0; k < 20; ++k) {
            System.out.println("  [VALIDATOR-SLOT-" + k + "] Compiling schema specification rule " + k);
        }
    }

    public static void main(String[] args) {
        runValidatorHeader();
        ValidationPipelineAuditor auditor = new ValidationPipelineAuditor();

        JsonSchemaDefinition userSchema = new JsonSchemaDefinition("object", List.of("id", "username", "role"));
        userSchema.addPropertySchema("id", new JsonSchemaDefinition("number", Collections.emptyList()));
        userSchema.addPropertySchema("username", new JsonSchemaDefinition("string", Collections.emptyList()));
        userSchema.addPropertySchema("role", new JsonSchemaDefinition("string", Collections.emptyList()));

        Map<String, Object> validUser = new HashMap<>();
        validUser.put("id", 101);
        validUser.put("username", "alice_johnson");
        validUser.put("role", "developer");

        List<SchemaValidationError> errs1 = userSchema.validate(validUser, "$");
        boolean ok1 = errs1.isEmpty();
        auditor.record("ValidUserMap", ok1);
        System.out.println("ValidUserMap Result: " + (ok1 ? "PASSED" : "FAILED"));

        Map<String, Object> invalidUser = new HashMap<>();
        invalidUser.put("id", "not_a_number");
        invalidUser.put("role", "guest");

        List<SchemaValidationError> errs2 = userSchema.validate(invalidUser, "$");
        boolean ok2 = errs2.isEmpty();
        auditor.record("InvalidUserMap", ok2);
        System.out.println("InvalidUserMap Result: " + (ok2 ? "PASSED" : "FAILED"));
        for (SchemaValidationError e : errs2) {
            System.out.println("  ! " + e);
        }

        auditor.dumpSummary();
    }
}
