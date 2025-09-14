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
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('headless-dql')

# Set device to cuda if available, otherwise cpu
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

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
        self.memory = deque(maxlen=10000)  # Increased memory size for headless training
        self.gamma = 0.95    # discount rate
        self.epsilon = 1.0   # exploration rate
        self.epsilon_min = 0.05  # Minimum exploration rate
        self.epsilon_decay = 0.99  # Slower decay
        self.learning_rate = 0.005
        
        # Q-Network and Target Network
        self.model = DQN(state_size, action_size).to(device)
        self.target_model = DQN(state_size, action_size).to(device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # Initialize target network with model weights
        self.update_target_model()

    def update_target_model(self):
        # Copy weights from model to target_model
        self.target_model.load_state_dict(self.model.state_dict())

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        
        # Convert numpy array to PyTorch tensor
        state_tensor = torch.FloatTensor(state).to(device)
        self.model.eval()
        with torch.no_grad():
            act_values = self.model(state_tensor)
        self.model.train()
        return torch.argmax(act_values).item()

    def replay(self, batch_size):
        if len(self.memory) < batch_size:
            return
        
        # Sample batch from memory
        minibatch = random.sample(self.memory, batch_size)
        
        # Extract batch data
        states = torch.FloatTensor(np.vstack([e[0] for e in minibatch])).to(device)
        actions = torch.LongTensor(np.array([e[1] for e in minibatch])).to(device)
        rewards = torch.FloatTensor(np.array([e[2] for e in minibatch])).to(device)
        next_states = torch.FloatTensor(np.vstack([e[3] for e in minibatch])).to(device)
        dones = torch.FloatTensor(np.array([e[4] for e in minibatch])).to(device)
        
        # Compute current Q values
        curr_q_values = self.model(states).gather(1, actions.unsqueeze(1))
        
        # Compute next Q values using target network
        with torch.no_grad():
            next_q_values = self.target_model(next_states).max(1)[0]
        
        # Compute target Q values
        target_q_values = rewards + (1 - dones) * self.gamma * next_q_values
        
        # Compute loss
        loss = F.mse_loss(curr_q_values.squeeze(), target_q_values)
        
        # Optimize the model
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        # Update epsilon for exploration-exploitation trade-off
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def load(self, name):
        self.model.load_state_dict(torch.load(name, map_location=device))
        self.model.eval()
        # Update target model with loaded weights
        self.update_target_model()
        print(f"Model loaded from {name}")

    def save(self, name):
        torch.save(self.model.state_dict(), name)
        print(f"Model saved to {name}")


class HeadlessBattlePainterRL:
    def __init__(self, server_uri="ws://localhost:9080/agent-client", model_path=None, start_epsilon=None):
        # Game state dimensions: 
        # - x, y, degree, can_draw, coverage, plus 4 density values (local, medium, far, overall)
        self.state_size = 9
        
        # Actions: LEFT, RIGHT, FORWARD
        self.action_size = 3
        self.agent = DQNAgent(self.state_size, self.action_size)
        self.batch_size = 128  # Increased batch size for faster learning
        self.server_uri = server_uri
        self.target_update_freq = 5  # Update target network every 5 episodes
        self.player_radius = 25

        # Load model if path is provided
        if model_path:
            self.agent.load(model_path)
            
            # Optionally set epsilon (exploration rate) if provided
            if start_epsilon is not None:
                self.agent.epsilon = start_epsilon
                print(f"Set epsilon to {start_epsilon}")

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
        
        # Canvas grid tracking
        self.grid_resolution = 30  # Match the same resolution as the server
        self.grid_width = self.bounds["right"] // self.grid_resolution
        self.grid_height = self.bounds["bottom"] // self.grid_resolution
        self.canvas = np.zeros((self.grid_resolution, self.grid_resolution), dtype=np.bool_)
        
        # Episode tracking
        self.episode = 0
        self.max_episodes = 100000  # Much larger number for headless training
        
        # For saving best models
        self.best_coverage = 0
        
        # For handling training progress
        self.recent_coverages = deque(maxlen=100)
        self.start_time = time.time()
        self.last_save_time = time.time()
        self.save_interval = 60  # Save model every minute
        
        # Extract episode number from model path if available
        if model_path:
            match = re.search(r'battle_painter_model_(\d+)_(\d+)\.pt', model_path)
            if match:
                self.episode = int(match.group(1)) + 1
                self.best_coverage = int(match.group(2)) / 100
                print(f"Starting from episode {self.episode} with best coverage {self.best_coverage*100:.2f}%")

    def sync_canvas(self, player_x, player_y):
        """Approximate canvas state based on player position"""
        # NOT USED IN THIS VERSION
        # use this to estimate density information
        rows = len(self.canvas)
        cols = len(self.canvas[0])
        cell_size = self.grid_width * self.grid_height
        grid_col = int(player_x // cell_size)
        grid_row = int(player_y // cell_size)

        radius_to_cover = self.player_radius // cell_size
        for dr in range(-radius_to_cover, radius_to_cover + 1):
            for dc in range(-radius_to_cover, radius_to_cover + 1):
                r = grid_row + dr
                c = grid_col + dc
                if 0 <= r < rows and 0 <= c < cols:
                    self.canvas[r, c] = True
    
    def calculate_density_metrics(self, player_x, player_y):
        """Calculate density metrics at different ranges from player"""
        # Convert player position to grid coordinates
        grid_x = int(player_x / self.grid_resolution)
        grid_y = int(player_y / self.grid_resolution)
        
        # Define ranges for density calculation
        local_radius = 5   # Very close to player
        medium_radius = 10  # Medium range
        far_radius = 15     # Farther areas
        
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
            # self.sync_canvas(player['x'], player['y'])
            
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

    def calculate_reward(self, current_coverage, previous_coverage, local_density, medium_density, far_density, overall_density):
        """Calculate reward based on coverage difference and local density"""
        # Basic reward is the improvement in coverage
        coverage_reward = (current_coverage - previous_coverage) * 100
        
        # Extract density metrics from state
        #_, _, _, _, _, local_density, medium_density, far_density, _ = current_state[0]
        
        # Lower density means more empty space to fill
        # Reward the agent for moving to areas with lower paint density
        density_reward = 0
        
        # Strong reward for painting in low-density areas
        if coverage_reward > 0:
            # Strong reward for painting in low-density areas
            local_reward = 2.0 * (1.0 - local_density) * coverage_reward
            
            # Medium reward for heading toward low-density areas nearby
            medium_reward = 1.0 * (1.0 - medium_density) * coverage_reward
            
            # Slight reward for strategic positioning toward emptier regions
            far_reward = 0.5 * (1.0 - far_density) * coverage_reward
            
            # Factor in overall progress - as game progresses, finding unpainted areas becomes more valuable
            progress_factor = 1.0 + overall_density  # Increases as more of the canvas is painted
            
            # Combine density rewards with progress weighting
            density_reward = progress_factor * (local_reward + medium_reward + far_reward)
        
        # New reward combines coverage improvement and density-based exploration
        total_reward = coverage_reward + density_reward
        
        # Add bonus for higher coverage
        if current_coverage > self.best_coverage:
            total_reward += 5  # Bonus for achieving new best
        
        # Add small penalty for not improving coverage
        if total_reward <= 0:
            total_reward -= 0.1
        
        return total_reward

    async def game_loop(self):
        """Main game loop to connect with the headless game server"""
        reconnect_delay = 2  # Initial reconnect delay in seconds
        max_reconnect_delay = 30  # Maximum reconnect delay
        with open('training_coverage.csv', 'w', newline='') as f:
            f.write("episode,final_coverage,avg_coverage,best_coverage,epsilon,episodes_per_sec\n")
            
        while self.episode < self.max_episodes:
            try:
                logger.info(f"Attempting to connect to server at {self.server_uri}")
                
                # Add explicit timeout to connection attempt
                try:
                    websocket = await asyncio.wait_for(
                        websockets.connect(self.server_uri), 
                        timeout=10  # 10-second timeout
                    )
                except asyncio.TimeoutError:
                    logger.error("Connection attempt timed out. Retrying...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                    continue
                
                async with websocket:
                    logger.info(f"Connected to game server. Starting episode {self.episode + 1}")
                    # Reset reconnect delay on successful connection
                    reconnect_delay = 2
                    
                    self.done = False
                    self.current_coverage = 0
                    self.previous_coverage = 0
                    
                    # Reset canvas at the beginning of each episode
                    self.canvas = np.zeros((self.grid_height, self.grid_width), dtype=np.bool_)
                    
                    # Game session loop
                    while not self.done:
                        try:
                            # Receive game state with timeout
                            message = await asyncio.wait_for(websocket.recv(), timeout=5)
                            game_data = json.loads(message)
                            logger.debug(f"Received: {game_data['event']}")
                            
                            # Process game state
                            if game_data["event"] == "STATE_UPDATE" or game_data["event"] == "INITIAL_STATE":
                                self.current_state = self.process_state(game_data)
                                self.current_coverage = game_data["coverage"] / 100.0
                                
                                # Extract local density for reward calculation
                                local_density = self.current_state[0][5] if self.current_state is not None else 0
                                medium_density = self.current_state[0][6] if self.current_state is not None else 0
                                far_density = self.current_state[0][7] if self.current_state is not None else 0
                                overall_density = self.current_state[0][8] if self.current_state is not None else 0
                                
                                # If we have a previous state, we can learn from it
                                if self.previous_state is not None and self.previous_action is not None:
                                    reward = self.calculate_reward(
                                        self.current_coverage, 
                                        self.previous_coverage,
                                        local_density, 
                                        medium_density, 
                                        far_density, 
                                        overall_density
                                    )
                                    self.agent.remember(self.previous_state, self.previous_action, reward, 
                                                       self.current_state, self.done)
                                    
                                    # Train more frequently - batch training
                                    if len(self.agent.memory) > self.batch_size:
                                        self.agent.replay(self.batch_size)
                                
                                # Choose action based on current state
                                action_index = self.agent.act(self.current_state)
                                action = self.get_action_from_index(action_index)
                                
                                # Send action to game
                                logger.debug(f"Sending action: {action}")
                                await websocket.send(json.dumps({"action": action}))
                                
                                # Update previous state and action
                                self.previous_state = self.current_state
                                self.previous_action = action_index
                                self.previous_coverage = self.current_coverage                                    
                                
                            elif game_data["event"] == "GAME_OVER":
                                self.done = True
                                final_coverage = game_data["coverage"] / 100.0
                                
                                # Store coverage for running average
                                self.recent_coverages.append(final_coverage)
                                
                                # Final learning step with done=True
                                if self.previous_state is not None and self.previous_action is not None:
                                    # Extract local density for reward calculation
                                    local_density = self.current_state[0][5] if self.current_state is not None else 0
                                    medium_density = self.current_state[0][6] if self.current_state is not None else 0
                                    far_density = self.current_state[0][7] if self.current_state is not None else 0
                                    overall_density = self.current_state[0][8] if self.current_state is not None else 0
                                    
                                    reward = self.calculate_reward(
                                        final_coverage, 
                                        self.previous_coverage,
                                        local_density, 
                                        medium_density, 
                                        far_density, 
                                        overall_density
                                    )
                                    # Create a dummy next state (doesn't matter as done=True)
                                    next_state = np.zeros((1, self.state_size))
                                    self.agent.remember(self.previous_state, self.previous_action, reward, 
                                                      next_state, self.done)
                                    
                                    # Final training step for this episode
                                    if len(self.agent.memory) > self.batch_size:
                                        self.agent.replay(self.batch_size)
                                
                                # Update best coverage if needed
                                print (final_coverage)
                                if final_coverage > self.best_coverage:
                                    self.best_coverage = final_coverage
                                    # Save immediately on new best
                                    self.agent.save(f"battle_painter_model_{self.episode}_{int(final_coverage * 100)}.pt")
                                    logger.info(f"New best model saved with coverage {final_coverage * 100:.2f}%")
                                
                                # Print progress every 10 episodes
                                if self.episode % 10 == 0:
                                    avg_coverage = sum(self.recent_coverages) / len(self.recent_coverages) if self.recent_coverages else 0
                                    elapsed = time.time() - self.start_time
                                    eps_per_sec = self.episode / elapsed if elapsed > 0 else 0
                                    with open('training_coverage.csv', 'a', newline='') as f:
                                        f.write(f"{self.episode},"
                                                f"{final_coverage*100:.2f},"
                                                f"{avg_coverage*100:.2f},"
                                                f"{self.best_coverage*100:.2f},"
                                                f"{self.agent.epsilon:.4f},"
                                                f"{eps_per_sec:.2f}\n")
                                
                                # Periodically save model regardless of performance
                                # current_time = time.time()
                                # if current_time - self.last_save_time > self.save_interval:
                                #     self.agent.save(f"battle_painter_latest.pt")
                                #     self.last_save_time = current_time
                                #     logger.info(f"Periodic save at episode {self.episode}")
                                
                                # Update target model periodically
                                if self.episode % self.target_update_freq == 0:
                                    self.agent.update_target_model()
                                
                                # Reset for next episode
                                self.episode += 1
                                
                                # Send reset command to start a new game
                                if self.episode < self.max_episodes:
                                    logger.debug("Sending RESET command")
                                    await websocket.send(json.dumps({"action": "RESET"}))
                        
                        except asyncio.TimeoutError:
                            logger.warning("Timeout while waiting for game message. Reconnecting...")
                            break
                        
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}. Message: {message}")
                            # Continue the loop - try to recover
                            continue
                            
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}. Retrying in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
            
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
    
    def run(self):
        """Start the RL agent"""
        try:
            asyncio.run(self.game_loop())
        except KeyboardInterrupt:
            logger.info("Training interrupted. Saving final model...")
            self.agent.save(f"battle_painter_interrupted_ep{self.episode}.pt")


def find_best_model():
    """Find the best model based on coverage percentage in the filename"""
    model_files = glob.glob("battle_painter_model_*.pt")
    if not model_files:
        logger.info("No saved models found.")
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
    
    parser = argparse.ArgumentParser(description='Headless Battle Painter RL Agent')
    parser.add_argument('--model', type=str, help='Path to the model file to load')
    parser.add_argument('--server', type=str, default='ws://localhost:9080/agent-client', 
                        help='WebSocket server URI')
    parser.add_argument('--epsilon', type=float, help='Starting epsilon value (exploration rate)')
    args = parser.parse_args()
    
    # If no model specified, try to find the best one
    model_path = args.model
    if not model_path:
        model_path = find_best_model()
    
    # Create and run the agent
    battle_painter_rl = HeadlessBattlePainterRL(
        server_uri=args.server,
        model_path=model_path,
        start_epsilon=args.epsilon
    )
    battle_painter_rl.run()