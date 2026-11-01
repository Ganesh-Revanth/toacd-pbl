#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <queue>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>
#include <functional>
#include <stdexcept>

class DAGNode;

struct Edge {
    std::shared_ptr<DAGNode> destination;
    int weight;

    Edge(std::shared_ptr<DAGNode> dest, int w) : destination(std::move(dest)), weight(w) {}
};

class DAGNode : public std::enable_shared_from_this<DAGNode> {
private:
    std::string nodeId;
    std::string label;
    std::vector<Edge> outgoingEdges;
    std::vector<std::weak_ptr<DAGNode>> incomingNodes;

public:
    DAGNode(std::string id, std::string lbl) : nodeId(std::move(id)), label(std::move(lbl)) {}

    const std::string& getId() const { return nodeId; }
    const std::string& getLabel() const { return label; }
    const std::vector<Edge>& getEdges() const { return outgoingEdges; }

    void addEdgeTo(const std::shared_ptr<DAGNode>& dest, int weight = 1) {
        outgoingEdges.emplace_back(dest, weight);
        dest->incomingNodes.push_back(weak_from_this());
    }

    size_t inDegree() const {
        size_t count = 0;
        for (const auto& w : incomingNodes) {
            if (!w.expired()) count++;
        }
        return count;
    }
};

class DirectedGraphEngine {
private:
    std::unordered_map<std::string, std::shared_ptr<DAGNode>> nodes;

public:
    std::shared_ptr<DAGNode> createNode(const std::string& id, const std::string& label) {
        if (nodes.find(id) != nodes.end()) return nodes[id];
        auto node = std::make_shared<DAGNode>(id, label);
        nodes[id] = node;
        return node;
    }

    bool addDependency(const std::string& fromId, const std::string& toId, int weight = 1) {
        auto fromIt = nodes.find(fromId);
        auto toIt = nodes.find(toId);
        if (fromIt == nodes.end() || toIt == nodes.end()) return false;
        fromIt->second->addEdgeTo(toIt->second, weight);
        return true;
    }

    std::vector<std::string> topologicalSort() const {
        std::unordered_map<std::string, int> inDegrees;
        for (const auto& pair : nodes) {
            inDegrees[pair.first] = 0;
        }
        for (const auto& pair : nodes) {
            for (const auto& edge : pair.second->getEdges()) {
                inDegrees[edge.destination->getId()]++;
            }
        }

        std::queue<std::string> zeroQueue;
        for (const auto& pair : inDegrees) {
            if (pair.second == 0) zeroQueue.push(pair.first);
        }

        std::vector<std::string> order;
        while (!zeroQueue.empty()) {
            std::string curr = zeroQueue.front();
            zeroQueue.pop();
            order.push_back(curr);

            auto nIt = nodes.find(curr);
            if (nIt != nodes.end()) {
                for (const auto& edge : nIt->second->getEdges()) {
                    std::string nextId = edge.destination->getId();
                    if (--inDegrees[nextId] == 0) {
                        zeroQueue.push(nextId);
                    }
                }
            }
        }

        if (order.size() != nodes.size()) {
            throw std::runtime_error("Graph contains cycles; topological sort invalid");
        }
        return order;
    }

    bool hasCycle() const {
        std::unordered_map<std::string, int> state; // 0=unvisited, 1=visiting, 2=visited
        for (const auto& pair : nodes) state[pair.first] = 0;

        std::function<bool(const std::string&)> dfs = [&](const std::string& currId) -> bool {
            state[currId] = 1;
            auto it = nodes.find(currId);
            if (it != nodes.end()) {
                for (const auto& e : it->second->getEdges()) {
                    std::string nextId = e.destination->getId();
                    if (state[nextId] == 1) return true; // back-edge = cycle
                    if (state[nextId] == 0 && dfs(nextId)) return true;
                }
            }
            state[currId] = 2;
            return false;
        };

        for (const auto& pair : nodes) {
            if (state[pair.first] == 0) {
                if (dfs(pair.first)) return true;
            }
        }
        return false;
    }

    std::vector<std::string> shortestPathBFS(const std::string& startId, const std::string& targetId) const {
        std::queue<std::string> q;
        std::unordered_map<std::string, std::string> parent;
        std::unordered_set<std::string> visited;

        q.push(startId);
        visited.insert(startId);

        while (!q.empty()) {
            std::string curr = q.front();
            q.pop();

            if (curr == targetId) break;

            auto it = nodes.find(curr);
            if (it != nodes.end()) {
                for (const auto& e : it->second->getEdges()) {
                    std::string nxt = e.destination->getId();
                    if (visited.find(nxt) == visited.end()) {
                        visited.insert(nxt);
                        parent[nxt] = curr;
                        q.push(nxt);
                    }
                }
            }
        }

        std::vector<std::string> path;
        if (visited.find(targetId) == visited.end()) return path;

        for (std::string at = targetId; at != startId; at = parent[at]) {
            path.push_back(at);
        }
        path.push_back(startId);
        std::reverse(path.begin(), path.end());
        return path;
    }

    void printGraph() const {
        std::cout << "\n================= DAG STRUCTURE ================\n";
        for (const auto& pair : nodes) {
            std::cout << "Node [" << pair.first << "] (" << pair.second->getLabel() << ") -> ";
            for (const auto& e : pair.second->getEdges()) {
                std::cout << "[" << e.destination->getId() << " (w:" << e.weight << ")] ";
            }
            std::cout << "\n";
        }
        std::cout << "================================================\n";
    }
};

int main() {
    DirectedGraphEngine dag;
    dag.createNode("TASK_SRC", "Compile Source AST");
    dag.createNode("TASK_LEX", "Run Lexical Scanner");
    dag.createNode("TASK_TYPE", "Type Check & Symbol Table");
    dag.createNode("TASK_OPT", "Intermediate Code Optimization");
    dag.createNode("TASK_BIN", "Generate Machine Executable");

    dag.addDependency("TASK_SRC", "TASK_LEX", 2);
    dag.addDependency("TASK_LEX", "TASK_TYPE", 3);
    dag.addDependency("TASK_TYPE", "TASK_OPT", 5);
    dag.addDependency("TASK_OPT", "TASK_BIN", 1);

    dag.printGraph();

    auto order = dag.topologicalSort();
    std::cout << "Topological Task Pipeline Execution Order:\n";
    for (size_t i = 0; i < order.size(); ++i) {
        std::cout << "  " << (i + 1) << ". " << order[i] << "\n";
    }

    std::cout << "Cycle detected in pipeline: " << (dag.hasCycle() ? "YES" : "NO") << "\n";
    auto path = dag.shortestPathBFS("TASK_SRC", "TASK_BIN");
    std::cout << "Shortest Pipeline Dependency Path: ";
    for (const auto& step : path) std::cout << step << " -> ";
    std::cout << "DONE\n";

    return 0;
}
