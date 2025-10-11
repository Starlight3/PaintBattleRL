import numpy as np
import random
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from collections import deque
import websockets
import asyncio
import json
import math
import glob
import os
import re
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('battle-painter-inference')

# Set device to cuda if available, otherwise cpu
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Using device: {device}")

class DQN(nn.Module):
    def __init__(self, state_size, action_size):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(state_size, 64)  # Increased network capacity for enhanced state
        self.fc2 = nn.Linear(64, 64)
        self.fc3 = nn.Linear(64, action_size)
        
    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


class DQNAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = 0.95    # discount rate (not used in inference)
        self.epsilon = 0.95  # Small epsilon for minimal exploration during visualization
        self.learning_rate = 0.005  # Not used in inference
        self.episode = 0
        self.max_episodes = 1000

        # Q-Network and Target Network (only model is used for inference)
        self.model = DQN(state_size, action_size).to(device)
        
    def act(self, state):
        # Add minimal exploration for visualization
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        
        # Convert numpy array to PyTorch tensor
        state_tensor = torch.FloatTensor(state).to(device)
        self.model.eval()
        with torch.no_grad():
            act_values = self.model(state_tensor)
        return torch.argmax(act_values).item()

    def load(self, name):
        self.model.load_state_dict(torch.load(name, map_location=device))
        # self.model.eval()  # Set model to evaluation mode
        logger.info(f"Model loaded from {name}")


class BattlePainterInference:
    def __init__(self, server_uri="ws://localhost:9080/agent-client", model_path=None):
        # Game state dimensions: x, y, degree, can_draw, coverage, plus 4 density features
        self.state_size = 9
        # Actions: LEFT, RIGHT, FORWARD
        self.action_size = 3
        self.agent = DQNAgent(self.state_size, self.action_size)
        self.server_uri = server_uri
        
        # Game bounds
        self.bounds = {
            "top": 0,
            "right": 600,
            "bottom": 600,
            "left": 0
        }
        
        # Current game state tracking
        self.current_state = None
        self.previous_state = None
        self.previous_action = None
        self.previous_coverage = 0
        self.current_coverage = 0
        self.done = False
        
        # Canvas grid tracking for density features
        self.grid_resolution = 30
        self.grid_width = self.bounds["right"] // self.grid_resolution
        self.grid_height = self.bounds["bottom"] // self.grid_resolution
        self.canvas = np.zeros((self.grid_resolution, self.grid_resolution), dtype=np.bool_)
        
        # Episode tracking
        self.episode = 0
        self.max_episodes = 1000 # Set to 1 for visualization, can be increased for multiple runs
        
        # For tracking best performance during visualization
        self.best_coverage = 0
        
        # Load model 
        self.agent.load(model_path)
        # match = re.search(r'battle_painter_model_(\d+)_(\d+)\.pt', model_path)
        # if match:
        #     self.episode = int(match.group(1)) + 1
        #     self.best_coverage = int(match.group(2)) / 100
        #     print(f"Loaded model {self.episode} with best coverage {self.best_coverage*100:.2f}%")
    
    def calculate_density_metrics(self, player_x, player_y):
        """Calculate density metrics at different ranges from player"""
        # Convert player position to grid coordinates
        grid_x = int(player_x / self.grid_resolution)
        grid_y = int(player_y / self.grid_resolution)
        
        # Define ranges for density calculation
        local_radius = 5   # Very close to player
        medium_radius = 10  # Medium range
        far_radius = 20     # Farther areas
        
        # Calculate densities
        local_density = self.get_region_density(grid_x, grid_y, local_radius)
        medium_density = self.get_region_density(grid_x, grid_y, medium_radius)
        far_density = self.get_region_density(grid_x, grid_y, far_radius)
        overall_density = np.sum(self.canvas) / (self.grid_width * self.grid_height)
        
        return local_density, medium_density, far_density, overall_density
    
    def get_region_density(self, center_x, center_y, radius):
        """Calculate paint density in a circular region"""
        total_cells = 0
        painted_cells = 0
        
        # Check cells in a square region (for simplicity)
        for y in range(max(0, center_y - radius), min(self.grid_height, center_y + radius + 1)):
            for x in range(max(0, center_x - radius), min(self.grid_width, center_x + radius + 1)):
                # Check if point is within circle radius
                dx = x - center_x
                dy = y - center_y
                if dx*dx + dy*dy <= radius*radius:
                    total_cells += 1
                    if self.canvas[y, x]:
                        painted_cells += 1
        
        # Avoid division by zero
        if total_cells == 0:
            return 0
            
        return painted_cells / total_cells

    def process_state(self, game_data):
        """Process game state data into a format for the neural network"""
        if game_data["event"] == "STATE_UPDATE" or game_data["event"] == "INITIAL_STATE":
            player = game_data["player"]
            # Normalize values to [0,1] range
            x = player["x"] / self.bounds["right"]
            y = player["y"] / self.bounds["bottom"]
            # Normalize degree to [0,1]
            degree = player["degree"] / 360.0
            can_draw = 1.0 if player["canDraw"] else 0.0
            coverage = game_data["coverage"] / 100.0  # Normalize to [0,1]
            
            # Use game data to get canvas state
            self.canvas = game_data["canvas"]
            # Convert canvas to numpy array
            self.canvas = np.array(game_data["canvas"], dtype=np.bool_)
            
            # Calculate density metrics
            local_density, medium_density, far_density, overall_density = self.calculate_density_metrics(
                player["x"], player["y"]
            )
            
            # Return state with density information
            return np.reshape([
                x, y, degree, can_draw, coverage,
                local_density, medium_density, far_density, overall_density
            ], [1, self.state_size])
        
        return None

    def get_action_from_index(self, action_index):
        """Convert action index to action command"""
        actions = ["LEFT", "RIGHT", "FORWARD"]
        return actions[action_index]

    async def game_loop(self):
        """Main game loop to connect with the browser game"""
        while self.episode < self.max_episodes:
            try:
                async with websockets.connect(self.server_uri) as websocket:
                    logger.info(f"Connected to game server.")
                    self.done = False
                    self.current_coverage = 0
                    self.previous_coverage = 0
                    
                    # Reset canvas at the beginning of each episode
                    self.canvas = np.zeros((self.grid_height, self.grid_width), dtype=np.bool_)
                    
                    # Game session loop
                    while not self.done:
                        # Receive game state
                        message = await websocket.recv()
                        game_data = json.loads(message)
                        
                        # Process game state
                        if game_data["event"] == "STATE_UPDATE":
                            self.current_state = self.process_state(game_data)
                            self.current_coverage = game_data["coverage"] / 100.0
                            
                            # Choose action based on current state
                            action_index = self.agent.act(self.current_state)
                            action = self.get_action_from_index(action_index)
                            
                            # Send action to game
                            await websocket.send(json.dumps({"action": action}))
                            
                            # Update tracking variables (not used for learning)
                            self.previous_state = self.current_state
                            self.previous_action = action_index
                            self.previous_coverage = self.current_coverage
                            
                        elif game_data["event"] == "GAME_OVER":
                            self.done = True
                            final_coverage = game_data["coverage"] / 100.0
                            
                            logger.info(f"Episode {self.episode + 1} finished with coverage: {final_coverage * 100:.2f}%")
                            
                            # Reset for next episode
                            self.episode += 1
                            
                            # Send reset command to start a new game
                            if self.episode < self.max_episodes:
                                await websocket.send(json.dumps({"action": "RESET"}))
                                return
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed. Retrying...")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(2)
        
    def run(self):
        """Start the inference agent"""
        try:
            asyncio.run(self.game_loop())
        except KeyboardInterrupt:
            logger.info("Visualization stopped.")


def find_best_model():
    """Find the best model based on coverage percentage in the filename"""
    model_files = glob.glob("battle_painter_model_*.pt")
    if not model_files:
        logger.error("No saved models found.")
        return None
    
    best_model = None
    best_coverage = -1
    best_episode = -1
    
    for model_file in model_files:
        match = re.search(r'battle_painter_model_(\d+)_(\d+)\.pt', model_file)
        if match:
            episode = int(match.group(1))
            coverage = int(match.group(2))
            
            if coverage > best_coverage or (coverage == best_coverage and episode > best_episode):
                best_coverage = coverage
                best_episode = episode
                best_model = model_file
    
    if best_model:
        logger.info(f"Found best model: {best_model} with coverage {best_coverage}%")
    return best_model


if __name__ == "__main__":
    import argparse
    import time
    # time.sleep(3)  # Allow time for server to start before connecting

    parser = argparse.ArgumentParser(description='Battle Painter Inference/Visualization')
    parser.add_argument('--model', type=str, help='Path to the model file to load')
    parser.add_argument('--server', type=str, default='ws://localhost:9080/agent-client', 
                        help='WebSocket server URI')
    args = parser.parse_args()
    
    # If no model specified, try to find the best one
    model_path = args.model
    if not model_path:
        model_path = find_best_model()
        
    if not model_path:
        logger.error("No model found. specify a model path.")
        exit(1)
    
    # Create and run the agent in inference mode
    battle_painter_inference = BattlePainterInference(
        server_uri=args.server,
        model_path=model_path
    )
    battle_painter_inference.run()