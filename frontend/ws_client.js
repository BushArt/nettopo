/**
 * NetTopo WebSocket Client
 *
 * Handles WebSocket connection, reconnection logic, and event dispatching.
 * Completely separate from graph rendering logic.
 */
const NetTopoClient = (function() {
    const WS_URL = 'ws://localhost:8765';

    const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];
    let reconnectAttempt = 0;
    let socket = null;
    let shouldReconnect = true;
    const eventHandlers = {};

    /**
     * Register event handler for event type
     */
    function on(eventType, callback) {
        if (!eventHandlers[eventType]) {
            eventHandlers[eventType] = [];
        }
        eventHandlers[eventType].push(callback);
    }

    /**
     * Dispatch event to all registered handlers
     */
    function dispatch(event) {
        const handlers = eventHandlers[event.type] || [];
        handlers.forEach(handler => handler(event));
    }

    /**
     * Connect to WebSocket server
     */
    function connect() {
        console.log(`[NetTopo] Connecting to ${WS_URL}`);

        socket = new WebSocket(WS_URL);

        socket.onopen = function() {
            console.log(`[NetTopo] Connected`);
            reconnectAttempt = 0;
            dispatch({ type: 'connected' });
        };

        socket.onmessage = function(msg) {
            try {
                const event = JSON.parse(msg.data);
                dispatch(event);
            } catch (e) {
                console.error(`[NetTopo] Invalid JSON received: ${msg.data}`);
            }
        };

        socket.onclose = function() {
            console.log(`[NetTopo] Disconnected`);
            dispatch({ type: 'disconnected' });

            if (shouldReconnect) {
                const delay = RECONNECT_DELAYS[Math.min(reconnectAttempt, RECONNECT_DELAYS.length - 1)];
                console.log(`[NetTopo] Reconnecting in ${delay}ms`);
                setTimeout(connect, delay);
                reconnectAttempt++;
            }
        };

        socket.onerror = function(error) {
            console.error(`[NetTopo] WebSocket error`);
        };
    }

    /**
     * Send event to server
     */
    function send(event) {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(event));
        }
    }

    /**
     * Start scan
     */
    function startScan(subnet, profile = 'quick') {
        send({
            type: 'start_scan',
            subnet: subnet,
            profile: profile
        });
    }

    /**
     * Disconnect client
     */
    function disconnect() {
        shouldReconnect = false;
        if (socket) {
            socket.close();
        }
    }

    // Auto connect on page load
    document.addEventListener('DOMContentLoaded', connect);

    // Public API
    return {
        connect,
        disconnect,
        on,
        send,
        startScan
    };
})();

// Export for global access
window.NetTopoClient = NetTopoClient;