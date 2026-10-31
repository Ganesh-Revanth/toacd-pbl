#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int id;
    double value;
} Item;

int main(void) {
    Item *item = (Item *)malloc(sizeof(Item));
    if (item == NULL) {
        return 1;
    }
    item->id = 101;
    item->value = 99.5;
    printf("Item: id=%d, value=%.1f\n", item->id, item->value);
    free(item);
    return 0;
}

