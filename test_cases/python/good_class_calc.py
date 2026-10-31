class Calculator:
    def __init__(self, base=0):
        self.base = base

    def add(self, x):
        return self.base + x

    def multiply(self, x, y):
        return x * y


if __name__ == "__main__":
    calc = Calculator(10)
    print(calc.add(5))
    print(calc.multiply(3, 4))

