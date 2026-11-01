#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <sstream>
#include <iomanip>

enum class PluginLifecycleState { UNLOADED, INITIALIZED, ACTIVE, SUSPENDED, TERMINATED };

class IPluginComponent {
public:
    virtual ~IPluginComponent() = default;
    virtual std::string getPluginId() const = 0;
    virtual std::string getVersion() const = 0;
    virtual bool onInitialize() = 0;
    virtual void onExecute() = 0;
    virtual void onShutdown() = 0;
};

class LexerOptimizerPlugin : public IPluginComponent {
public:
    std::string getPluginId() const override { return "plugin.lexer.optimizer"; }
    std::string getVersion() const override { return "2.4.1"; }

    bool onInitialize() override {
        std::cout << "  [" << getPluginId() << "] Fast regex lookup tables compiled.\n";
        return true;
    }

    void onExecute() override {
        std::cout << "  [" << getPluginId() << "] Token streaming buffer optimized.\n";
    }

    void onShutdown() override {
        std::cout << "  [" << getPluginId() << "] Flushed scratch state.\n";
    }
};

class AstHealerPlugin : public IPluginComponent {
public:
    std::string getPluginId() const override { return "plugin.ast.healer"; }
    std::string getVersion() const override { return "1.0.8"; }

    bool onInitialize() override {
        std::cout << "  [" << getPluginId() << "] Heuristic rules loaded.\n";
        return true;
    }

    void onExecute() override {
        std::cout << "  [" << getPluginId() << "] Synthesizing repair candidate patch.\n";
    }

    void onShutdown() override {
        std::cout << "  [" << getPluginId() << "] Healer plugin resources released.\n";
    }
};

class PluginRegistryEngine {
private:
    struct PluginDescriptor {
        std::shared_ptr<IPluginComponent> instance;
        PluginLifecycleState state;
    };

    std::map<std::string, PluginDescriptor> registry;

public:
    bool registerPlugin(std::shared_ptr<IPluginComponent> plugin) {
        if (!plugin) return false;
        std::string id = plugin->getPluginId();
        if (registry.find(id) != registry.end()) return false;

        registry[id] = {std::move(plugin), PluginLifecycleState::UNLOADED};
        return true;
    }

    bool initializePlugin(const std::string& id) {
        auto it = registry.find(id);
        if (it == registry.end() || it->second.state != PluginLifecycleState::UNLOADED) return false;

        if (it->second.instance->onInitialize()) {
            it->second.state = PluginLifecycleState::INITIALIZED;
            return true;
        }
        return false;
    }

    void executeAllActive() {
        for (auto& pair : registry) {
            if (pair.second.state == PluginLifecycleState::INITIALIZED ||
                pair.second.state == PluginLifecycleState::ACTIVE) {
                pair.second.instance->onExecute();
                pair.second.state = PluginLifecycleState::ACTIVE;
            }
        }
    }

    void shutdownAll() {
        for (auto& pair : registry) {
            pair.second.instance->onShutdown();
            pair.second.state = PluginLifecycleState::TERMINATED;
        }
    }

    void printRegistryStatus() const {
        std::cout << "\n================ PLUGIN REGISTRY STATUS ================\n";
        for (const auto& pair : registry) {
            std::cout << "Plugin: " << std::setw(25) << std::left << pair.first
                      << " | Ver: " << std::setw(8) << pair.second.instance->getVersion()
                      << " | State: " << stateToString(pair.second.state) << "\n";
        }
        std::cout << "========================================================\n";
    }

private:
    static const char* stateToString(PluginLifecycleState s) {
        switch (s) {
            case PluginLifecycleState::UNLOADED:    return "UNLOADED";
            case PluginLifecycleState::INITIALIZED: return "INITIALIZED";
            case PluginLifecycleState::ACTIVE:      return "ACTIVE";
            case PluginLifecycleState::SUSPENDED:   return "SUSPENDED";
            case PluginLifecycleState::TERMINATED:  return "TERMINATED";
            default: return "UNKNOWN";
        }
    }
};

int main() {
    PluginRegistryEngine registry;
    registry.registerPlugin(std::make_shared<LexerOptimizerPlugin>());
    registry.registerPlugin(std::make_shared<AstHealerPlugin>());

    registry.printRegistryStatus();

    std::cout << "\nInitializing Registered Extensions:\n";
    registry.initializePlugin("plugin.lexer.optimizer");
    registry.initializePlugin("plugin.ast.healer");
    registry.printRegistryStatus();

    std::cout << "\nExecuting Active Extensions:\n";
    registry.executeAllActive();
    registry.printRegistryStatus();

    std::cout << "\nShutting Down Extension Framework:\n";
    registry.shutdownAll();
    registry.printRegistryStatus();

    return 0;
}
