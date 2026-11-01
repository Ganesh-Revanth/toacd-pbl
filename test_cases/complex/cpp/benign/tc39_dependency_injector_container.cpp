#include <iostream>
#include <string>
#include <memory>
#include <unordered_map>
#include <typeindex>
#include <functional>

class ILoggerService {
public:
    virtual ~ILoggerService() = default;
    virtual void log(const std::string& msg) = 0;
};

class ConsoleLoggerService : public ILoggerService {
public:
    void log(const std::string& msg) override {
        std::cout << "[IOC-CONSOLE] " << msg << "\n";
    }
};

class IFileSystemService {
public:
    virtual ~IFileSystemService() = default;
    virtual bool exists(const std::string& path) = 0;
    virtual std::string readFile(const std::string& path) = 0;
};

class MockFileSystemService : public IFileSystemService {
public:
    bool exists(const std::string& path) override { return !path.empty(); }
    std::string readFile(const std::string& path) override {
        return "// Simulated source code payload from " + path;
    }
};

class ISecurityPolicyService {
public:
    virtual ~ISecurityPolicyService() = default;
    virtual bool validateToken(const std::string& token) = 0;
};

class EnterpriseSecurityPolicyService : public ISecurityPolicyService {
public:
    bool validateToken(const std::string& token) override {
        return token == "TOKEN_VALID_2026";
    }
};

class ICompilerPipeline {
public:
    virtual ~ICompilerPipeline() = default;
    virtual void compile(const std::string& sourceFile) = 0;
};

class StandardCompilerPipeline : public ICompilerPipeline {
private:
    std::shared_ptr<ILoggerService> logger;
    std::shared_ptr<IFileSystemService> fs;
    std::shared_ptr<ISecurityPolicyService> security;

public:
    StandardCompilerPipeline(std::shared_ptr<ILoggerService> l,
                             std::shared_ptr<IFileSystemService> f,
                             std::shared_ptr<ISecurityPolicyService> s)
        : logger(std::move(l)), fs(std::move(f)), security(std::move(s)) {}

    void compile(const std::string& sourceFile) override {
        logger->log("Verifying security policy for compile request...");
        if (!security->validateToken("TOKEN_VALID_2026")) {
            logger->log("ERROR: Security policy rejected compile request.");
            return;
        }

        logger->log("Reading file from filesystem: " + sourceFile);
        std::string src = fs->readFile(sourceFile);
        logger->log("Compiling AST. Total bytes: " + std::to_string(src.size()));
        logger->log("Compilation succeeded cleanly.");
    }
};

class DependencyInjectionContainer {
private:
    std::unordered_map<std::type_index, std::shared_ptr<void>> singletons;
    std::unordered_map<std::type_index, std::function<std::shared_ptr<void>()>> transientFactories;

public:
    template <typename Interface, typename Implementation>
    void registerSingleton() {
        singletons[std::type_index(typeid(Interface))] = std::make_shared<Implementation>();
    }

    template <typename Interface, typename Implementation>
    void registerTransient() {
        transientFactories[std::type_index(typeid(Interface))] = []() -> std::shared_ptr<void> {
            return std::make_shared<Implementation>();
        };
    }

    template <typename Interface>
    std::shared_ptr<Interface> resolve() {
        auto it = singletons.find(std::type_index(typeid(Interface)));
        if (it != singletons.end()) {
            return std::static_pointer_cast<Interface>(it->second);
        }
        auto tIt = transientFactories.find(std::type_index(typeid(Interface)));
        if (tIt != transientFactories.end()) {
            return std::static_pointer_cast<Interface>(tIt->second());
        }
        return nullptr;
    }

    DependencyInjectionContainer createChildScope() const {
        DependencyInjectionContainer child;
        child.singletons = this->singletons;
        child.transientFactories = this->transientFactories;
        return child;
    }

    size_t getRegisteredSingletonCount() const { return singletons.size(); }
    size_t getRegisteredTransientCount() const { return transientFactories.size(); }
};

int main() {
    DependencyInjectionContainer ioc;
    ioc.registerSingleton<ILoggerService, ConsoleLoggerService>();
    ioc.registerSingleton<IFileSystemService, MockFileSystemService>();
    ioc.registerSingleton<ISecurityPolicyService, EnterpriseSecurityPolicyService>();

    auto logger = ioc.resolve<ILoggerService>();
    auto fs = ioc.resolve<IFileSystemService>();
    auto security = ioc.resolve<ISecurityPolicyService>();

    StandardCompilerPipeline pipeline(logger, fs, security);
    pipeline.compile("main.cpp");

    std::cout << "\nResolving Transient Instances:\n";
    ioc.registerTransient<ILoggerService, ConsoleLoggerService>();
    auto loggerA = ioc.resolve<ILoggerService>();
    auto loggerB = ioc.resolve<ILoggerService>();
    std::cout << "Are transient instances distinct pointers? " << (loggerA != loggerB ? "YES" : "NO") << "\n";

    std::cout << "\nInspecting Child Scope Container:\n";
    auto childScope = ioc.createChildScope();
    std::cout << "Child Singletons Count: " << childScope.getRegisteredSingletonCount() << "\n";
    auto childLogger = childScope.resolve<ILoggerService>();
    if (childLogger) childLogger->log("Child scope resolved logger successfully.");

    auto childSecurity = childScope.resolve<ISecurityPolicyService>();
    std::cout << "Child Token Validation: "
              << (childSecurity && childSecurity->validateToken("TOKEN_VALID_2026") ? "PASSED" : "FAILED") << "\n";

    return 0;
}
