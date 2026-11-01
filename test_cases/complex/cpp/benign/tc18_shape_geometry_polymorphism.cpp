#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <cmath>
#include <iomanip>

class Shape;
class Circle;
class Rectangle;
class Triangle;
class Polygon2D;

class IShapeVisitor {
public:
    virtual ~IShapeVisitor() = default;
    virtual void visit(const Circle& c) = 0;
    virtual void visit(const Rectangle& r) = 0;
    virtual void visit(const Triangle& t) = 0;
    virtual void visit(const Polygon2D& p) = 0;
};

class Shape {
protected:
    std::string shapeName;

public:
    explicit Shape(std::string name) : shapeName(std::move(name)) {}
    virtual ~Shape() = default;

    virtual double calculateArea() const = 0;
    virtual double calculatePerimeter() const = 0;
    virtual void accept(IShapeVisitor& visitor) const = 0;

    const std::string& getName() const { return shapeName; }
};

class Circle : public Shape {
private:
    double radius;

public:
    Circle(std::string name, double r) : Shape(std::move(name)), radius(r) {}
    double getRadius() const { return radius; }

    double calculateArea() const override {
        return 3.141592653589793 * radius * radius;
    }

    double calculatePerimeter() const override {
        return 2.0 * 3.141592653589793 * radius;
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

class Rectangle : public Shape {
private:
    double width;
    double height;

public:
    Rectangle(std::string name, double w, double h) : Shape(std::move(name)), width(w), height(h) {}
    double getWidth() const { return width; }
    double getHeight() const { return height; }

    double calculateArea() const override {
        return width * height;
    }

    double calculatePerimeter() const override {
        return 2.0 * (width + height);
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

class Triangle : public Shape {
private:
    double sideA, sideB, sideC;

public:
    Triangle(std::string name, double a, double b, double c)
        : Shape(std::move(name)), sideA(a), sideB(b), sideC(c) {}

    double calculateArea() const override {
        double s = calculatePerimeter() / 2.0;
        return std::sqrt(s * (s - sideA) * (s - sideB) * (s - sideC));
    }

    double calculatePerimeter() const override {
        return sideA + sideB + sideC;
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

struct Point2D {
    double x, y;
    Point2D(double x_, double y_) : x(x_), y(y_) {}
};

class Polygon2D : public Shape {
private:
    std::vector<Point2D> vertices;

public:
    Polygon2D(std::string name, std::vector<Point2D> pts)
        : Shape(std::move(name)), vertices(std::move(pts)) {}

    const std::vector<Point2D>& getVertices() const { return vertices; }

    double calculatePerimeter() const override {
        if (vertices.size() < 2) return 0.0;
        double p = 0.0;
        for (size_t i = 0; i < vertices.size(); ++i) {
            const auto& p1 = vertices[i];
            const auto& p2 = vertices[(i + 1) % vertices.size()];
            double dx = p1.x - p2.x;
            double dy = p1.y - p2.y;
            p += std::sqrt(dx * dx + dy * dy);
        }
        return p;
    }

    double calculateArea() const override {
        if (vertices.size() < 3) return 0.0;
        double area = 0.0;
        for (size_t i = 0; i < vertices.size(); ++i) {
            const auto& p1 = vertices[i];
            const auto& p2 = vertices[(i + 1) % vertices.size()];
            area += (p1.x * p2.y) - (p2.x * p1.y);
        }
        return std::abs(area) / 2.0;
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

class ShapeMetricsVisitor : public IShapeVisitor {
public:
    void visit(const Circle& c) override {
        std::cout << "[Circle] " << c.getName() << " (R=" << c.getRadius() << ") "
                  << "Area=" << std::fixed << std::setprecision(2) << c.calculateArea()
                  << " | Perim=" << c.calculatePerimeter() << "\n";
    }

    void visit(const Rectangle& r) override {
        std::cout << "[Rectangle] " << r.getName() << " (W=" << r.getWidth() << ", H=" << r.getHeight() << ") "
                  << "Area=" << r.calculateArea() << " | Perim=" << r.calculatePerimeter() << "\n";
    }

    void visit(const Triangle& t) override {
        std::cout << "[Triangle] " << t.getName() << " "
                  << "Area=" << t.calculateArea() << " | Perim=" << t.calculatePerimeter() << "\n";
    }

    void visit(const Polygon2D& p) override {
        std::cout << "[Polygon2D] " << p.getName() << " (" << p.getVertices().size() << " vertices) "
                  << "Area=" << p.calculateArea() << " | Perim=" << p.calculatePerimeter() << "\n";
    }
};

int main() {
    std::vector<std::unique_ptr<Shape>> shapes;
    shapes.push_back(std::make_unique<Circle>("Wheel", 5.0));
    shapes.push_back(std::make_unique<Rectangle>("DisplayPanel", 1920.0, 1080.0));
    shapes.push_back(std::make_unique<Triangle>("TrussSupport", 3.0, 4.0, 5.0));
    shapes.push_back(std::make_unique<Circle>("Lens", 12.5));
    shapes.push_back(std::make_unique<Polygon2D>("Pentagon", std::vector<Point2D>{
        {0.0, 0.0}, {4.0, 0.0}, {5.0, 3.0}, {2.0, 5.0}, {-1.0, 3.0}
    }));

    ShapeMetricsVisitor visitor;
    std::cout << "================ POLYMORPHIC SHAPE GEOMETRY ================\n";
    for (const auto& s : shapes) {
        s->accept(visitor);
    }
    return 0;
}
