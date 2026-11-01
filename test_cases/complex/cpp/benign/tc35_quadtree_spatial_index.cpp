#include <iostream>
#include <vector>
#include <memory>
#include <cmath>
#include <iomanip>

struct SpatialPoint {
    double x, y;
    int id;

    SpatialPoint(double x_, double y_, int id_ = 0) : x(x_), y(y_), id(id_) {}
};

struct SpatialBoundingBox {
    double xMin, yMin, xMax, yMax;

    SpatialBoundingBox(double x0, double y0, double x1, double y1)
        : xMin(x0), yMin(y0), xMax(x1), yMax(y1) {}

    bool contains(const SpatialPoint& pt) const {
        return (pt.x >= xMin && pt.x <= xMax && pt.y >= yMin && pt.y <= yMax);
    }

    bool intersects(const SpatialBoundingBox& other) const {
        return !(other.xMin > xMax || other.xMax < xMin ||
                 other.yMin > yMax || other.yMax < yMin);
    }
};

class QuadtreeNode {
private:
    SpatialBoundingBox boundary;
    size_t capacity;
    std::vector<SpatialPoint> points;
    bool isDivided;

    std::unique_ptr<QuadtreeNode> northWest;
    std::unique_ptr<QuadtreeNode> northEast;
    std::unique_ptr<QuadtreeNode> southWest;
    std::unique_ptr<QuadtreeNode> southEast;

public:
    QuadtreeNode(SpatialBoundingBox b, size_t cap = 4)
        : boundary(b), capacity(cap), isDivided(false) {}

    bool insert(const SpatialPoint& pt) {
        if (!boundary.contains(pt)) return false;

        if (points.size() < capacity && !isDivided) {
            points.push_back(pt);
            return true;
        }

        if (!isDivided) {
            subdivide();
        }

        return (northWest->insert(pt) || northEast->insert(pt) ||
                southWest->insert(pt) || southEast->insert(pt));
    }

    void queryRange(const SpatialBoundingBox& range, std::vector<SpatialPoint>& found) const {
        if (!boundary.intersects(range)) return;

        for (const auto& p : points) {
            if (range.contains(p)) {
                found.push_back(p);
            }
        }

        if (isDivided) {
            northWest->queryRange(range, found);
            northEast->queryRange(range, found);
            southWest->queryRange(range, found);
            southEast->queryRange(range, found);
        }
    }

    size_t countPoints() const {
        size_t c = points.size();
        if (isDivided) {
            c += northWest->countPoints();
            c += northEast->countPoints();
            c += southWest->countPoints();
            c += southEast->countPoints();
        }
        return c;
    }

    void queryRadius(double cx, double cy, double radius, std::vector<SpatialPoint>& found) const {
        SpatialBoundingBox box(cx - radius, cy - radius, cx + radius, cy + radius);
        std::vector<SpatialPoint> candidates;
        queryRange(box, candidates);

        double rSquared = radius * radius;
        for (const auto& p : candidates) {
            double dx = p.x - cx;
            double dy = p.y - cy;
            if (dx * dx + dy * dy <= rSquared) {
                found.push_back(p);
            }
        }
    }

private:
    void subdivide() {
        double xMid = (boundary.xMin + boundary.xMax) / 2.0;
        double yMid = (boundary.yMin + boundary.yMax) / 2.0;

        northWest = std::make_unique<QuadtreeNode>(SpatialBoundingBox(boundary.xMin, yMid, xMid, boundary.yMax), capacity);
        northEast = std::make_unique<QuadtreeNode>(SpatialBoundingBox(xMid, yMid, boundary.xMax, boundary.yMax), capacity);
        southWest = std::make_unique<QuadtreeNode>(SpatialBoundingBox(boundary.xMin, boundary.yMin, xMid, yMid), capacity);
        southEast = std::make_unique<QuadtreeNode>(SpatialBoundingBox(xMid, boundary.yMin, boundary.xMax, yMid), capacity);

        isDivided = true;

        for (const auto& p : points) {
            northWest->insert(p) || northEast->insert(p) ||
            southWest->insert(p) || southEast->insert(p);
        }
        points.clear();
    }
};

int main() {
    QuadtreeNode root(SpatialBoundingBox(0.0, 0.0, 100.0, 100.0), 4);

    for (int i = 0; i < 25; ++i) {
        root.insert(SpatialPoint(i * 3.5, i * 3.8, i));
    }

    SpatialBoundingBox searchBox(20.0, 20.0, 60.0, 60.0);
    std::vector<SpatialPoint> results;
    root.queryRange(searchBox, results);

    std::cout << "Quadtree Spatial Range Search ([20, 20] -> [60, 60]):\n";
    std::cout << "Found " << results.size() << " points within range:\n";
    for (const auto& pt : results) {
        std::cout << "  Point #" << pt.id << " at (" << pt.x << ", " << pt.y << ")\n";
    }

    std::vector<SpatialPoint> circleResults;
    root.queryRadius(50.0, 50.0, 25.0, circleResults);
    std::cout << "\nRadius Search (Center: (50, 50), Radius: 25.0):\n";
    std::cout << "Found " << circleResults.size() << " points within circular radius.\n";
    for (const auto& cp : circleResults) {
        std::cout << "  * Circular Neighbor Point #" << cp.id << " at (" << cp.x << ", " << cp.y << ")\n";
    }
    std::cout << "Total Spatial Elements Indexed: " << root.countPoints() << "\n";

    return 0;
}
