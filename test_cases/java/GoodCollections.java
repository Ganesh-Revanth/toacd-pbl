import java.util.ArrayList;
import java.util.List;

public class GoodCollections {
    public static void main(String[] args) {
        List<String> items = new ArrayList<>();
        items.add("Alpha");
        items.add("Beta");
        for (String item : items) {
            System.out.println(item);
        }
    }
}

