public class TC07_MissingImportMap {
    public static void main(String[] args) {
        Map<String, Integer> map = new HashMap<>();
        map.put("key", 99);
        System.out.println(map.get("key"));
    }
}

