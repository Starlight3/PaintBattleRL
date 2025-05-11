PB.initWebSocket = function() {
    // Initialize WebSocket connection
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//localhost:9080/rl-agent`;
    // const wsUrl = `${wsProtocol}//${window.location.host}/rl-agent`;
    
    PB.socket = new WebSocket(wsUrl);
    
    PB.socket.onopen = function() {
        console.log('WebSocket connection established');
        
        // Send initial state to break potential deadlock
        PB.sendGameState({
          event: 'INITIAL_STATE',
          player: {
            x: 400,  // midX
            y: 300,  // midY
            degree: 225,
            canDraw: true
          },
          coverage: 0
        });
      };
    
    PB.socket.onclose = function() {
      console.log('WebSocket connection closed');
    };
    
    PB.socket.onerror = function(error) {
      console.error('WebSocket error:', error);
    };
    
    // Handle commands from the RL agent
    PB.socket.onmessage = function(event) {
      const message = JSON.parse(event.data);
      
      // Process commands from the RL agent
      switch(message.action) {
        case 'LEFT':
          // Turn left
          PB.keys[37] = true;
          PB.keys[39] = false;
          break;
        case 'RIGHT':
          // Turn right
          PB.keys[37] = false;
          PB.keys[39] = true;
          break;
        case 'FORWARD':
          // Keep going straight
          PB.keys[37] = false;
          PB.keys[39] = false;
          break;
        case 'RESET':
          // Reset the game
          location.reload();
          break;
      }
    };
    
    // Send game state to the RL agent at regular intervals
    PB.sendGameState = function(gameData) {
      if (PB.socket && PB.socket.readyState === WebSocket.OPEN) {
        PB.socket.send(JSON.stringify(gameData));
      }
    };
  };