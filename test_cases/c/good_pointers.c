#include <stdio.h>

void swap(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

int main(void) {
    int x = 10;
    int y = 20;
    int *px = &x;
    int *py = &y;
    swap(px, py);
    printf("x=%d, y=%d\n", *px, *py);
    return 0;
}

