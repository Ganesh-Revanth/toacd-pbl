#include <iostream>
#include <vector>
#include <unordered_map>
#include <memory>
#include <string>
#include <cmath>
#include <iomanip>
#include <cstdint>

using EntityID = uint32_t;

struct TransformComponent {
    double x, y;
    double rotationDegrees;

    TransformComponent(double x_ = 0.0, double y_ = 0.0, double rot = 0.0)
        : x(x_), y(y_), rotationDegrees(rot) {}
};

struct VelocityComponent {
    double vx, vy;

    VelocityComponent(double vx_ = 0.0, double vy_ = 0.0) : vx(vx_), vy(vy_) {}
};

struct RenderComponent {
    std::string spriteTag;
    int layer;

    RenderComponent(std::string tag = "default_sprite", int l = 0)
        : spriteTag(std::move(tag)), layer(l) {}
};

struct BoundingBoxComponent {
    double width, height;

    BoundingBoxComponent(double w = 1.0, double h = 1.0) : width(w), height(h) {}
};

class EntityManager {
private:
    EntityID nextId;
    std::vector<EntityID> livingEntities;
    std::unordered_map<EntityID, TransformComponent> transforms;
    std::unordered_map<EntityID, VelocityComponent> velocities;
    std::unordered_map<EntityID, RenderComponent> renders;
    std::unordered_map<EntityID, BoundingBoxComponent> hitboxes;

public:
    EntityManager() : nextId(1) {}

    EntityID createEntity() {
        EntityID id = nextId++;
        livingEntities.push_back(id);
        return id;
    }

    void addTransform(EntityID id, double x, double y, double rot = 0.0) {
        transforms.emplace(id, TransformComponent(x, y, rot));
    }

    void addVelocity(EntityID id, double vx, double vy) {
        velocities.emplace(id, VelocityComponent(vx, vy));
    }

    void addRender(EntityID id, const std::string& tag, int layer = 0) {
        renders.emplace(id, RenderComponent(tag, layer));
    }

    void addHitbox(EntityID id, double w, double h) {
        hitboxes.emplace(id, BoundingBoxComponent(w, h));
    }

    TransformComponent* getTransform(EntityID id) {
        auto it = transforms.find(id);
        return (it != transforms.end()) ? &it->second : nullptr;
    }

    VelocityComponent* getVelocity(EntityID id) {
        auto it = velocities.find(id);
        return (it != velocities.end()) ? &it->second : nullptr;
    }

    RenderComponent* getRender(EntityID id) {
        auto it = renders.find(id);
        return (it != renders.end()) ? &it->second : nullptr;
    }

    BoundingBoxComponent* getHitbox(EntityID id) {
        auto it = hitboxes.find(id);
        return (it != hitboxes.end()) ? &it->second : nullptr;
    }

    const std::vector<EntityID>& getEntities() const { return livingEntities; }
};

class CollisionSystem {
public:
    static void checkCollisions(EntityManager& em) {
        const auto& entities = em.getEntities();
        for (size_t i = 0; i < entities.size(); ++i) {
            EntityID idA = entities[i];
            auto* tA = em.getTransform(idA);
            auto* bA = em.getHitbox(idA);
            if (!tA || !bA) continue;

            for (size_t j = i + 1; j < entities.size(); ++j) {
                EntityID idB = entities[j];
                auto* tB = em.getTransform(idB);
                auto* bB = em.getHitbox(idB);
                if (!tB || !bB) continue;

                bool overlapX = std::abs(tA->x - tB->x) * 2.0 < (bA->width + bB->width);
                bool overlapY = std::abs(tA->y - tB->y) * 2.0 < (bA->height + bB->height);

                if (overlapX && overlapY) {
                    std::cout << "[COLLISION] Entity #" << idA << " collided with Entity #" << idB << "\n";
                }
            }
        }
    }
};

class MovementSystem {
public:
    static void update(EntityManager& em, double dtSeconds) {
        for (EntityID id : em.getEntities()) {
            auto* t = em.getTransform(id);
            auto* v = em.getVelocity(id);
            if (t && v) {
                t->x += v->vx * dtSeconds;
                t->y += v->vy * dtSeconds;
            }
        }
    }
};

class RenderSystem {
public:
    static void render(EntityManager& em) {
        std::cout << "\n================ ECS FRAME RENDER ================\n";
        for (EntityID id : em.getEntities()) {
            auto* t = em.getTransform(id);
            auto* r = em.getRender(id);
            if (t && r) {
                std::cout << "Entity #" << id << " [" << std::setw(12) << std::left << r->spriteTag
                          << "] Pos: (" << std::fixed << std::setprecision(1) << t->x
                          << ", " << t->y << ") Layer: " << r->layer << "\n";
            }
        }
        std::cout << "==================================================\n";
    }
};

int main() {
    EntityManager em;

    EntityID player = em.createEntity();
    em.addTransform(player, 100.0, 200.0, 0.0);
    em.addVelocity(player, 15.0, -5.0);
    em.addRender(player, "hero_ship", 10);

    em.addHitbox(player, 32.0, 32.0);

    EntityID enemy1 = em.createEntity();
    em.addTransform(enemy1, 150.0, 200.0, 180.0);
    em.addVelocity(enemy1, -10.0, 0.0);
    em.addRender(enemy1, "alien_scout", 5);
    em.addHitbox(enemy1, 24.0, 24.0);

    EntityID asteroid = em.createEntity();
    em.addTransform(asteroid, 300.0, 150.0, 45.0);
    em.addRender(asteroid, "rock_large", 1);
    em.addHitbox(asteroid, 64.0, 64.0);

    RenderSystem::render(em);

    std::cout << "\nSimulating 3 physics ticks (dt = 0.5s):\n";
    for (int tick = 1; tick <= 3; ++tick) {
        MovementSystem::update(em, 0.5);
        std::cout << "--- Tick " << tick << " ---\n";
        CollisionSystem::checkCollisions(em);
        RenderSystem::render(em);
    }

    return 0;
}
