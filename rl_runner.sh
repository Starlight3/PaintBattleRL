#!/bin/bash

# Battle Painter RL Runner
# Usage: ./run.sh [start|stop|inference]

WEBSOCKET_PID_FILE="websocket"
HTTP_PID_FILE="http"

# Kill process by PID file
kill_process() {
    local pidfile=$1
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
        fi
        rm -f "$pidfile"
    fi
}

# Kill processes on port
kill_port() {
    local port=$1
    local pids=$(lsof -ti :$port 2>/dev/null)
    for pid in $pids; do
        kill "$pid" 2>/dev/null
    done
}

start() {
    echo "Starting services..."
    
    # Clean up existing processes
    kill_process "$WEBSOCKET_PID_FILE"
    kill_process "$HTTP_PID_FILE"
    kill_port 9080
    kill_port 8000
    
    # Start WebSocket server
    python3 websocket.py &
    echo $! > "$WEBSOCKET_PID_FILE"
    
    # Start HTTP server
    python3 -m http.server 8000 &
    echo $! > "$HTTP_PID_FILE"
    
    sleep 2
    echo "Services started. Open http://localhost:8000 in browser"
}

stop() {
    echo "Stopping services..."
    kill_process "$WEBSOCKET_PID_FILE"
    kill_process "$HTTP_PID_FILE"
    kill_port 9080
    kill_port 8000
    echo "Services stopped"
}

inference() {
    echo "Running inference..."
    python3 dql.py
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    inference)
        inference
        ;;
    *)
        echo "Usage: $0 {start|stop|inference}"
        exit 1
        ;;
esac