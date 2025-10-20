import numpy as np
import math
import random
import asyncio
import websockets
import json
import logging
from collections import deque

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('headless-battle-painters')

class HeadlessBattlePainters:
    """A headless version of the Battle Painters game for fast RL training"""
    
    def __init__(self, game_duration, fast_mode=True):
        # Game constants
        self.bounds = {"top": 0, "right": 600, "bottom": 600, "left": 0}
        self.player_radius = 25
        self.player_speed = 20
        self.turn_speed = 30
        self.game_duration = game_duration  # 10x faster than the original 6s
        self.fast_mode = fast_mode
        
        # Grid-based canvas representation for faster coverage calculation
        self.grid_resolution = 30  # Each cell is 10x10 pixels
        self.grid_width = self.bounds["right"] // self.grid_resolution
        self.grid_height = self.bounds["bottom"] // self.grid_resolution
        # Canvas tracks painted cells by different players [1,2,3,4]
        self.canvas = np.zeros((self.grid_height, self.grid_width), dtype=np.int8)
        # self.canvas = np.zeros((self.grid_height, self.grid_width), dtype=np.bool_)
        
        # Player state
        self.players = [
            {
                "x": 400 - 30,
                "y": 300 - 30,
                "degree": 225,
                "canDraw": True,
                "color": "purple",  # Player 1 (RL agent)
                "name": "Player 1"
            },
            {
                "x": 400 + 30,
                "y": 300 - 30,
                "degree": 315,
                "canDraw": True,
                "color": "#299EFE",  # Player 2 (computer)
                "name": "Player 2",
                "isComputer": True
            },
            {
                "x": 400 - 30,
                "y": 300 + 30,
                "degree": 135,
                "canDraw": True,
                "color": "#FDBC56",  # Player 3 (computer)
                "name": "Player 3",
                "isComputer": True
            },
            {
                "x": 400 + 30,
                "y": 300 + 30,
                "degree": 45,
                "canDraw": True,
                "color": "#67DB66",  # Player 4 (computer)
                "name": "Player 4",
                "isComputer": True
            }
        ]
        
        # Game state
        self.coverage = [0.0, 0.0, 0.0, 0.0]
        self.frame_counter = 0
        self.game_over = False
        self.max_frames = self.game_duration // 10  # 10ms per frame
        
        # WebSocket server for communication with the agent
        self.agent_connection = None
        self.reset_requested = False
        
        # Statistics for speed measurement
        self.episodes_completed = 0
        self.start_time = None
        self.last_stats_time = None
        
    async def start_server(self, host="localhost", port=9080):
        """Start the WebSocket server for agent communication"""
        # Add debug logging
        logger.info("Setting up WebSocket server...")
        
        # Create handler to process websocket connections
        async def handler(websocket):
            path = websocket.request.path
            logger.info(f"Received connection on path: {path}")
            if path == "/agent-client":
                await self.handler(websocket)
            else:
                logger.warning(f"Received connection with invalid path: {path}")
                await websocket.close(1008, "Invalid path")
        
        # Start the server
        self.server = await websockets.serve(handler, host, port)
        
        logger.info(f"Headless Battle Painters server started at ws://{host}:{port}/agent-client")
        return self.server
    
    async def handler(self, websocket):
        """Handle WebSocket communication with the agent"""
        logger.info(f"Agent connected from {websocket.remote_address}")
        self.agent_connection = websocket
        
        # Start measuring time for statistics
        import time
        self.start_time = time.time()
        self.last_stats_time = time.time()
        
        try:
            # Send initial state
            await self.send_initial_state()
            
            # Main game loop
            while True:
                # Process agent's action
                message = await websocket.recv()
                logger.debug(f"Received message: {message}")
                data = json.loads(message)
                action = data.get("action")
                
                if action == "RESET":
                    # Reset the game
                    logger.info("Reset requested by agent")
                    self.reset_game()
                    await self.send_initial_state()
                    continue
                
                # Apply action to game state
                self.apply_action(action)
                
                # Update game state
                self.update_game_state()
                
                # Send updated state
                if not self.game_over:
                    await self.send_state_update()
                else:
                    await self.send_game_over()
                    
                    # Track episodes for statistics
                    self.episodes_completed += 1
                    
                    # Print statistics every 10 episodes
                    if self.episodes_completed % 10 == 0:
                        self.print_statistics()
        
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Agent connection closed: {e}")
        except Exception as e:
            logger.error(f"Error in handler: {e}", exc_info=True)
        finally:
            self.agent_connection = None
    
    def apply_action(self, action):
        """Apply the agent's action to PLAYER 1 only"""
        player = self.players[0]  # Only control player 1
        
        if action == "LEFT":
            player["degree"] = (player["degree"] - self.turn_speed) % 360
        elif action == "RIGHT":
            player["degree"] = (player["degree"] + self.turn_speed) % 360
        elif action == "FORWARD":
            pass
    
    # TODO: This might not be used if we already have computer movement in code. Need to check
    def move_computer_players(self):
        """Move computer-controlled players randomly"""
        import random
        for i in range(1, 4):  # Players 2, 3, 4
            player = self.players[i]
            if player.get("isComputer", False):
                # Random turn
                turn = random.randint(-10, 10)
                player["degree"] = (player["degree"] + turn) % 360
    
    def move_player(self, player_index):
        """Move a specific player in its current direction"""
        player = self.players[player_index]
        
        # Convert degrees to radians
        radian = (player["degree"] * math.pi) / 180
        
        # Calculate new position
        new_x = player["x"] + math.cos(radian) * self.player_speed
        new_y = player["y"] + math.sin(radian) * self.player_speed
        
        # Apply bounds
        new_x = max(self.bounds["left"] + self.player_radius, 
                   min(self.bounds["right"] - self.player_radius, new_x))
        new_y = max(self.bounds["top"] + self.player_radius, 
                   min(self.bounds["bottom"] - self.player_radius, new_y))
        
        # Update player position
        player["x"] = new_x
        player["y"] = new_y
    
    def update_canvas(self, player_index):
        """Update the canvas with a specific player's paint"""
        player = self.players[player_index]
        
        if not player["canDraw"]:
            return
        
        # Convert player position to grid coordinates
        grid_x = int(player["x"] / self.grid_resolution)
        grid_y = int(player["y"] / self.grid_resolution)
        
        # Calculate radius in grid cells
        grid_radius = int(self.player_radius / self.grid_resolution) + 1
        
        # Paint a circle around the player in the grid
        # Mark with player_index + 1 (so player 0 paints value 1, etc.)
        for y in range(max(0, grid_y - grid_radius), min(self.grid_height, grid_y + grid_radius + 1)):
            for x in range(max(0, grid_x - grid_radius), min(self.grid_width, grid_x + grid_radius + 1)):
                # Check if point is within circle radius
                dx = (x - grid_x) * self.grid_resolution
                dy = (y - grid_y) * self.grid_resolution
                if dx*dx + dy*dy <= self.player_radius * self.player_radius:
                    self.canvas[y, x] = player_index + 1  # Mark which player painted
    
    
    def calculate_coverage(self):
        """Calculate the percentage of canvas covered by EACH player"""
        # TODO: Opportunity here to boost our reward function by using coverage for each player
        total_cells = self.grid_width * self.grid_height
        
        for player_idx in range(4):
            painted_cells = np.sum(self.canvas == (player_idx + 1))
            self.coverage[player_idx] = (painted_cells / total_cells) * 100.0
        
        return self.coverage[0]  # Return player 1's coverage for RL agent
    
    
    def update_game_state(self):
        """Update the game state for one frame"""
        # Move computer players first
        self.move_computer_players()
        
        # Move all players
        for i in range(4):
            self.move_player(i)
        
        # Update canvas with all players' paint
        for i in range(4):
            self.update_canvas(i)
        
        # Calculate coverage
        player1_coverage = self.calculate_coverage()
        
        # Update frame counter
        self.frame_counter += 1
        
        # Check if game is over
        if self.frame_counter >= self.max_frames:
            self.game_over = True
    
    def reset_game(self):
        """Reset the game state"""
        # Reset canvas
        self.canvas = np.zeros((self.grid_height, self.grid_width), dtype=np.int8)
        
        # Reset all players to starting positions
        self.players = [
            {
                "x": 400 - 30,
                "y": 300 - 30,
                "degree": 225,
                "canDraw": True,
                "color": "purple",
                "name": "Player 1"
            },
            {
                "x": 400 + 30,
                "y": 300 - 30,
                "degree": 315,
                "canDraw": True,
                "color": "#299EFE",
                "name": "Player 2",
                "isComputer": True
            },
            {
                "x": 400 - 30,
                "y": 300 + 30,
                "degree": 135,
                "canDraw": True,
                "color": "#FDBC56",
                "name": "Player 3",
                "isComputer": True
            },
            {
                "x": 400 + 30,
                "y": 300 + 30,
                "degree": 45,
                "canDraw": True,
                "color": "#67DB66",
                "name": "Player 4",
                "isComputer": True
            }
        ]
        
        # Reset game state
        self.coverage = [0.0, 0.0, 0.0, 0.0]
        self.frame_counter = 0
        self.game_over = False
    
    async def send_initial_state(self):
        """Send initial state to the agent"""
        if not self.agent_connection:
            return
        
        initial_state = {
            "event": "INITIAL_STATE",
            "player": self.players[0],  # Only send Player 1's state
            "coverage": 0,
            "canvas": self.canvas.tolist(),
            "all_players": self.players  # Optional: send all player positions
        }
        
        try:
            await self.agent_connection.send(json.dumps(initial_state))
            logger.debug("Sent initial state")
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
    
    async def send_state_update(self):
        """Send state update to the agent"""
        if not self.agent_connection:
            return
        
        state_update = {
            "event": "STATE_UPDATE",
            "player": self.players[0],  # Only Player 1 (RL agent)
            "coverage": self.coverage[0],  # Player 1's coverage
            "canvas": self.canvas.tolist(),
            "all_players": self.players  # Optional: all player positions
        }
        
        try:
            await self.agent_connection.send(json.dumps(state_update))
        except Exception as e:
            logger.error(f"Error sending state update: {e}")
    
    async def send_game_over(self):
        """Send game over event to the agent"""
        if not self.agent_connection:
            return
        
        game_over = {
            "event": "GAME_OVER",
            "coverage": self.coverage[0],  # Player 1's coverage
            "all_coverage": self.coverage  # All players' coverage
        }
        
        try:
            await self.agent_connection.send(json.dumps(game_over))
            logger.info(f"Game over - P1: {self.coverage[0]:.2f}%, P2: {self.coverage[1]:.2f}%, "
                       f"P3: {self.coverage[2]:.2f}%, P4: {self.coverage[3]:.2f}%")
        except Exception as e:
            logger.error(f"Error sending game over: {e}")
    
    def print_statistics(self):
        """Print training speed statistics"""
        import time
        current_time = time.time()
        elapsed = current_time - self.last_stats_time
        episodes_per_second = 10 / elapsed if elapsed > 0 else 0
        total_elapsed = current_time - self.start_time
        total_eps_per_second = self.episodes_completed / total_elapsed if total_elapsed > 0 else 0
        
        logger.info(f"Episodes: {self.episodes_completed}, "
                   f"Recent speed: {episodes_per_second:.2f} eps/s, "
                   f"Average speed: {total_eps_per_second:.2f} eps/s")
        
        self.last_stats_time = current_time


async def main():
    """Main function to run the headless battle painters server"""
    # Create the game environment
    game = HeadlessBattlePainters(game_duration=3000)  # 600 frames = 6 seconds (@10 fps) (like the original fast_mode)
    
    try:
        # Start the server
        server = await game.start_server()
        
        # Keep the server running
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt: 
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)