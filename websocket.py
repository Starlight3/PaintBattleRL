import asyncio
import websockets
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('battle-painters-server')

class BattlePainterServer:
    def __init__(self, host="localhost", port=9080):
        self.host = host
        self.port = port
        # Connection storage
        self.game_connection = None
        self.agent_connection = None

    async def handler(self, websocket):
        """Handle WebSocket connections based on path"""

        logger.info(f"New connection from {websocket.remote_address} on path {websocket.request.path}")
        path = websocket.request.path
        if path == "/rl-agent":
            # This is a connection from the game
            await self.game_handler(websocket)
        elif path == "/agent-client":
            # This is a connection from the RL agent
            await self.agent_handler(websocket)
        else:
            logger.warning(f"Unknown path: {path}")
            await websocket.close(1008, "Unsupported path")

    async def game_handler(self, websocket):
        """Handle WebSocket connection from the game"""
        logger.info(f"Game connected from {websocket.remote_address}")
        self.game_connection = websocket
        
        try:
            async for message in websocket:
                # Forward game state to the RL agent
                if self.agent_connection:
                    await self.agent_connection.send(message)
                    # logger.debug(f"Forwarded game state: {message[:100]}...")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Game connection closed")
        finally:
            self.game_connection = None

    async def agent_handler(self, websocket):
        """Handle WebSocket connection from the RL agent"""
        logger.info(f"RL agent connected from {websocket.remote_address}")
        self.agent_connection = websocket
        
        try:
            async for message in websocket:
                # Forward agent actions to the game
                if self.game_connection:
                    await self.game_connection.send(message)
                    data = json.loads(message)
                    print (data)
                    logger.info(f"Agent action: {data['action']}")
        except websockets.exceptions.ConnectionClosed as e:
            print (e)
            logger.info("RL agent connection closed")
        finally:
            self.agent_connection = None

    async def start_server(self):
        """Start the WebSocket server"""
        server = await websockets.serve(
            lambda ws: self.handler(ws),
            self.host, 
            self.port
        )
        
        logger.info(f"WebSocket server started at ws://{self.host}:{self.port}")
        logger.info(f"Game endpoint: ws://{self.host}:{self.port}/rl-agent")
        logger.info(f"Agent endpoint: ws://{self.host}:{self.port}/agent-client")
        
        # Keep the server running
        await server.wait_closed()

    def run(self):
        """Run the server"""
        asyncio.run(self.start_server())


if __name__ == "__main__":
    server = BattlePainterServer()
    server.run()