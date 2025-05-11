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

# Set device to cuda if available, otherwise cpu
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class DQN(nn.Module):
    def __init__(self, state_size, action_size):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(state_size, 24)
        self.fc2 = nn.Linear(24, 24)
        self.fc3 = nn.Linear(24, action_size)
        
    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


class DQNAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.memory = deque(maxlen=5000)  # Increased memory size
        self.gamma = 0.95    # discount rate
        self.epsilon = 1.0   # exploration rate
        self.epsilon_min = 0.05  # Higher min epsilon
        self.epsilon_decay = 0.99  # Slower decay
        self.learning_rate = 0.005  # Increased learning rate
        
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
        self.model.load_state_dict(torch.load(name))
        self.model.eval()
        # Update target model with loaded weights
        self.update_target_model()
        print(f"Model loaded from {name}")

    def save(self, name):
        torch.save(self.model.state_dict(), name)
        print(f"Model saved to {name}")


class BattlePainterRL:
    def __init__(self, server_uri="ws://localhost:9080/agent-client", model_path=None, start_epsilon=None):
        # Game state dimensions: x, y, degree, can_draw, coverage
        self.state_size = 5
        # Actions: LEFT, RIGHT, FORWARD
        self.action_size = 3
        self.agent = DQNAgent(self.state_size, self.action_size)
        self.batch_size = 64 # Increased from 32 to 64 for better training stability
        self.server_uri = server_uri
        self.target_update_freq = 5  # Update every 5 episodes instead of 10
        
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
            "right": 800,
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
        
        # Episode tracking
        self.episode = 0
        self.max_episodes = 1000
        
        # For saving best models
        self.best_coverage = 0
        
        # Extract episode number from model path if available
        if model_path:
            match = re.search(r'battle_painter_model_(\d+)_(\d+)\.pt', model_path)
            if match:
                self.episode = int(match.group(1)) + 1
                self.best_coverage = int(match.group(2)) / 100
                print(f"Starting from episode {self.episode} with best coverage {self.best_coverage*100:.2f}%")

    def process_state(self, game_data):
        """Process game state data into a format for the neural network"""
        if game_data["event"] == "STATE_UPDATE":
            player = game_data["player"]
            # Normalize values to [0,1] range
            x = player["x"] / self.bounds["right"]
            y = player["y"] / self.bounds["bottom"]
            # Normalize degree to [0,1]
            degree = player["degree"] / 360.0
            can_draw = 1.0 if player["canDraw"] else 0.0
            coverage = game_data["coverage"] / 100.0  # Normalize to [0,1]
            
            return np.reshape([x, y, degree, can_draw, coverage], [1, self.state_size])
        
        return None

    def get_action_from_index(self, action_index):
        """Convert action index to action command"""
        actions = ["LEFT", "RIGHT", "FORWARD"]
        return actions[action_index]

    def calculate_reward(self, current_coverage, previous_coverage):
        """Calculate reward based on coverage difference"""
        # Basic reward is the improvement in coverage
        coverage_reward = (current_coverage - previous_coverage) * 100
        
        # Add bonus for higher coverage
        if current_coverage > self.best_coverage:
            self.best_coverage = current_coverage
            coverage_reward += 5  # Bonus for achieving new best
        
        # Add small penalty for not improving coverage
        if coverage_reward <= 0:
            coverage_reward -= 0.1
        
        return coverage_reward

    async def game_loop(self):
        """Main game loop to connect with the browser game"""
        while self.episode < self.max_episodes:
            try:
                async with websockets.connect(self.server_uri) as websocket:
                    print(f"Connected to game server. Starting episode {self.episode + 1}")
                    self.done = False
                    self.current_coverage = 0
                    self.previous_coverage = 0
                    
                    # Game session loop
                    while not self.done:
                        # Receive game state
                        message = await websocket.recv()
                        game_data = json.loads(message)
                        print (game_data)

                        # Process game state
                        if game_data["event"] == "STATE_UPDATE":
                            self.current_state = self.process_state(game_data)
                            self.current_coverage = game_data["coverage"] / 100.0
                            
                            # If we have a previous state, we can learn from it
                            if self.previous_state is not None and self.previous_action is not None:
                                reward = self.calculate_reward(self.current_coverage, self.previous_coverage)
                                self.agent.remember(self.previous_state, self.previous_action, reward, 
                                                   self.current_state, self.done)
                                
                                # Train more frequently - lower threshold for training
                                if len(self.agent.memory) > self.batch_size // 2:
                                    self.agent.replay(self.batch_size)
                            
                            # Choose action based on current state
                            action_index = self.agent.act(self.current_state)
                            action = self.get_action_from_index(action_index)
                            
                            # Send action to game
                            await websocket.send(json.dumps({"action": action}))
                            
                            # Update previous state and action
                            self.previous_state = self.current_state
                            self.previous_action = action_index
                            self.previous_coverage = self.current_coverage
                            
                        elif game_data["event"] == "GAME_OVER":
                            self.done = True
                            final_coverage = game_data["coverage"] / 100.0
                            
                            # Final learning step with done=True
                            if self.previous_state is not None and self.previous_action is not None:
                                reward = self.calculate_reward(final_coverage, self.previous_coverage)
                                # Create a dummy next state (doesn't matter as done=True)
                                next_state = np.zeros((1, self.state_size))
                                self.agent.remember(self.previous_state, self.previous_action, reward, 
                                                  next_state, self.done)
                            
                            print(f"Episode {self.episode + 1} finished with coverage: {final_coverage * 100:.2f}%")
                            
                            # Save model if this is the best performance
                            if final_coverage >= self.best_coverage:
                                self.best_coverage = final_coverage
                                self.agent.save(f"battle_painter_model_{self.episode}_{int(final_coverage * 100)}.pt")
                                print(f"New best model saved with coverage {final_coverage * 100:.2f}%")
                            
                            # Update target model more frequently
                            if self.episode % self.target_update_freq == 0:
                                self.agent.update_target_model()
                                print("Target model updated")
                            
                            # Reset for next episode
                            self.episode += 1
                            
                            # Send reset command to start a new game
                            if self.episode < self.max_episodes:
                                await websocket.send(json.dumps({"action": "RESET"}))
                    
            except websockets.exceptions.ConnectionClosed as e:
                print(f"{e} \nConnection closed. Retrying...")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(2)
    
    def run(self):
        """Start the RL agent"""
        asyncio.run(self.game_loop())


def find_best_model():
    """Find the best model based on coverage percentage in the filename"""
    model_files = glob.glob("battle_painter_model_*.pt")
    if not model_files:
        print("No saved models found.")
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
        print(f"Found best model: {best_model} with coverage {best_coverage}%")
    return best_model


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Battle Painter RL Agent')
    parser.add_argument('--model', type=str, help='Path to the model file to load')
    parser.add_argument('--server', type=str, default='ws://localhost:9080/agent-client', 
                        help='WebSocket server URI')
    args = parser.parse_args()
    
    # If no model specified, try to find the best one
    model_path = args.model
    if not model_path:
        model_path = find_best_model()
    
    # Create and run the agent
    battle_painter_rl = BattlePainterRL(
        server_uri=args.server,
        model_path=model_path,
    )
    battle_painter_rl.run()