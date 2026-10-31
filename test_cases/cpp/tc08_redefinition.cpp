#include <iostream>
using namespace std;

int calculate(int x) {
    return x * 2;
}

int calculate(int x) {
    return x + 2;
}

int main() {
    cout << calculate(5) << endl;
    return 0;
}

