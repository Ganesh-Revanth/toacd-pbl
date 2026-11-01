#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <functional>
#include <iomanip>

enum class OrderState { CREATED, VALIDATED, PAYMENT_PENDING, FULFILLED, CANCELLED, REFUNDED };

inline const char* stateName(OrderState s) {
    switch (s) {
        case OrderState::CREATED:         return "CREATED";
        case OrderState::VALIDATED:       return "VALIDATED";
        case OrderState::PAYMENT_PENDING: return "PAYMENT_PENDING";
        case OrderState::FULFILLED:       return "FULFILLED";
        case OrderState::CANCELLED:       return "CANCELLED";
        case OrderState::REFUNDED:        return "REFUNDED";
        default: return "UNKNOWN";
    }
}

struct OrderTransition {
    OrderState from;
    std::string event;
    OrderState to;
    std::function<bool()> guard;
    std::function<void()> action;
};

class OrderStateMachine {
private:
    std::string orderId;
    OrderState currentState;
    std::vector<OrderTransition> transitions;
    std::vector<std::string> auditTrail;
    std::map<OrderState, std::function<void()>> onEnterStateHooks;
    std::map<OrderState, std::function<void()>> onExitStateHooks;

public:
    explicit OrderStateMachine(std::string id)
        : orderId(std::move(id)), currentState(OrderState::CREATED) {
        auditTrail.push_back("Order created in initial state: CREATED");
        setupTransitions();
    }

    void registerEnterHook(OrderState s, std::function<void()> hook) {
        onEnterStateHooks[s] = std::move(hook);
    }

    void registerExitHook(OrderState s, std::function<void()> hook) {
        onExitStateHooks[s] = std::move(hook);
    }

    void triggerEvent(const std::string& event) {
        for (const auto& t : transitions) {
            if (t.from == currentState && t.event == event) {
                if (!t.guard || t.guard()) {
                    OrderState prev = currentState;
                    auto exitIt = onExitStateHooks.find(prev);
                    if (exitIt != onExitStateHooks.end() && exitIt->second) exitIt->second();

                    if (t.action) t.action();

                    currentState = t.to;
                    auditTrail.push_back("Transition: " + std::string(stateName(prev)) +
                                         " -> " + std::string(stateName(currentState)) +
                                         " on event '" + event + "'");

                    auto enterIt = onEnterStateHooks.find(currentState);
                    if (enterIt != onEnterStateHooks.end() && enterIt->second) enterIt->second();
                    return;
                }
            }
        }
        auditTrail.push_back("Invalid event '" + event + "' rejected in state " + stateName(currentState));
    }

    bool canTrigger(const std::string& event) const {
        for (const auto& t : transitions) {
            if (t.from == currentState && t.event == event) {
                return !t.guard || t.guard();
            }
        }
        return false;
    }

    OrderState getState() const { return currentState; }

    void printHistory() const {
        std::cout << "\n================ ORDER STATE WORKFLOW ================\n";
        std::cout << "Order ID     : " << orderId << "\n";
        std::cout << "Current State: " << stateName(currentState) << "\n";
        std::cout << "Workflow Audit Log:\n";
        for (const auto& log : auditTrail) {
            std::cout << "  * " << log << "\n";
        }
        std::cout << "======================================================\n";
    }

private:
    void setupTransitions() {
        transitions.push_back({OrderState::CREATED, "validate", OrderState::VALIDATED, nullptr,
                               []() { std::cout << "  [Action] Inventory hold locked.\n"; }});
        transitions.push_back({OrderState::VALIDATED, "request_payment", OrderState::PAYMENT_PENDING, nullptr,
                               []() { std::cout << "  [Action] Payment gateway invoice generated.\n"; }});
        transitions.push_back({OrderState::PAYMENT_PENDING, "payment_success", OrderState::FULFILLED, nullptr,
                               []() { std::cout << "  [Action] Receipt emailed to customer.\n"; }});
        transitions.push_back({OrderState::PAYMENT_PENDING, "payment_fail", OrderState::CANCELLED, nullptr,
                               []() { std::cout << "  [Action] Payment gateway timeout notification.\n"; }});
        transitions.push_back({OrderState::VALIDATED, "cancel", OrderState::CANCELLED, nullptr,
                               []() { std::cout << "  [Action] Inventory reservation released.\n"; }});
        transitions.push_back({OrderState::FULFILLED, "refund_request", OrderState::REFUNDED, nullptr,
                               []() { std::cout << "  [Action] Initiated payment reversal.\n"; }});
        transitions.push_back({OrderState::CREATED, "cancel", OrderState::CANCELLED, nullptr,
                               []() { std::cout << "  [Action] Order cancelled before validation.\n"; }});
        transitions.push_back({OrderState::VALIDATED, "escalate_review", OrderState::VALIDATED, nullptr,
                               []() { std::cout << "  [Action] Order sent to supervisor queue.\n"; }});
    }
};

int main() {
    OrderStateMachine order("ORD-9874");

    order.registerEnterHook(OrderState::VALIDATED, []() {
        std::cout << ">>> Hook: Order is now verified and address validated.\n";
    });
    order.registerEnterHook(OrderState::FULFILLED, []() {
        std::cout << ">>> Hook: Shipping dispatch label printed.\n";
    });

    std::cout << "Can trigger 'validate'? " << (order.canTrigger("validate") ? "YES" : "NO") << "\n";
    order.triggerEvent("validate");

    std::cout << "Can trigger 'refund_request' prematurely? " << (order.canTrigger("refund_request") ? "YES" : "NO") << "\n";

    order.triggerEvent("request_payment");
    order.triggerEvent("payment_success");
    order.triggerEvent("cancel"); // Invalid transition in fulfilled state
    order.triggerEvent("refund_request");

    std::cout << "\nAttempting Order Re-Open / Duplicate Action:\n";
    order.triggerEvent("request_payment"); // Invalid in refunded state
    order.triggerEvent("validate"); // Invalid

    std::cout << "Final Verified State: " << stateName(order.getState()) << "\n";
    std::cout << "Is Order in Terminal State? "
              << (order.getState() == OrderState::REFUNDED || order.getState() == OrderState::CANCELLED ? "YES" : "NO") << "\n";

    order.printHistory();
    return 0;
}
