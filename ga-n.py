import numpy as np
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
import asyncio
import websockets
import json
import os
import sys

# Device configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Neural network
class GAAgentNN(nn.Module):
    def __init__(self, state_size, action_size):
        super(GAAgentNN, self).__init__()
        self.fc1 = nn.Linear(state_size, 24)
        self.fc2 = nn.Linear(24, 24)
        self.fc3 = nn.Linear(24, action_size)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)

# Grid settings
GRID_ROWS = 30
GRID_COLS = 30

def get_flat_weights(model):
    return torch.cat([p.data.view(-1) for p in model.parameters()])

def set_flat_weights(model, flat):
    pointer = 0
    for param in model.parameters():
        numel = param.numel()
        param.data.copy_(flat[pointer:pointer + numel].view(param.size()))
        pointer += numel

# Grid-based state processing
def process_state_grid(game_data, visited_cells, bounds):
    player = game_data["player"]
    x = player["x"]
    y = player["y"]

    # Convert to grid cell
    grid_x = int(x // (bounds["right"] / GRID_COLS))
    grid_y = int(y // (bounds["bottom"] / GRID_ROWS))

    # Normalize grid location
    norm_x = grid_x / GRID_COLS
    norm_y = grid_y / GRID_ROWS

    visited_cells.add((grid_x, grid_y))

    degree = player["degree"] / 360.0
    can_draw = 1.0 if player["canDraw"] else 0.0
    coverage_ratio = len(visited_cells) / (GRID_ROWS * GRID_COLS)

    return np.array([norm_x, norm_y, degree, can_draw, coverage_ratio], dtype=np.float32)

def select_action(model, state):
    state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(device)
    with torch.no_grad():
        q_values = model(state_tensor)
    return torch.argmax(q_values).item()

# Evaluate an individual
async def evaluate(weights, server_uri, bounds):
    state_size = 5
    action_size = 3
    model = GAAgentNN(state_size, action_size).to(device)
    set_flat_weights(model, torch.tensor(weights, dtype=torch.float32))

    visited_cells = set()
    try:
        async with websockets.connect(server_uri) as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                if data["event"] == "STATE_UPDATE":
                    state = process_state_grid(data, visited_cells, bounds)
                    action_index = select_action(model, state)
                    actions = ["LEFT", "RIGHT", "FORWARD"]
                    await websocket.send(json.dumps({"action": actions[action_index]}))
                elif data["event"] == "GAME_OVER":
                    break
        return len(visited_cells) / (GRID_ROWS * GRID_COLS) * 100.0
    except Exception as e:
        print(f"Evaluation error: {e}")
        return 0.0

def crossover(parent1, parent2):
    point = random.randint(1, len(parent1) - 1)
    return np.concatenate((parent1[:point], parent2[point:]))

def mutate(weights, rate=0.2):
    mutation = np.random.randn(*weights.shape) * rate
    return weights + mutation

# Main GA loop
async def run_ga():
    state_size = 5
    action_size = 3
    pop_size = 10
    generations = 20
    server_uri = "ws://localhost:9080/agent-client"
    bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}

    dummy_model = GAAgentNN(state_size, action_size)
    weight_dim = get_flat_weights(dummy_model).shape[0]
    population = [np.random.randn(weight_dim) for _ in range(pop_size)]

    if os.path.exists("best_model.pt"):
        print("Resuming from saved best model...")
        best_weights = torch.load("best_model.pt")
        population[0] = best_weights.numpy()

    for gen in range(generations):
        print(f"\n=== Generation {gen+1} ===")
        fitnesses = []
        for i, individual in enumerate(population):
            print(f"Evaluating Individual {i+1}/{len(population)}")
            score = await evaluate(individual, server_uri, bounds)
            fitnesses.append(score)
            print(f"  Fitness: {score:.2f}%")

        ranked = sorted(zip(fitnesses, population), key=lambda x: -x[0])
        best_score = ranked[0][0]
        best_individual = ranked[0][1]
        print(f"Best fitness in generation: {best_score:.2f}%")

        best_weights = torch.tensor(best_individual)
        torch.save(best_weights, "best_model.pt")

        elites = [ind for _, ind in ranked[:2]]
        new_population = elites[:]
        while len(new_population) < pop_size:
            p1, p2 = random.sample(elites, 2)
            child = mutate(crossover(p1, p2))
            new_population.append(child)
        population = new_population

# Run best model
async def run_best_model(path="best_model.pt"):
    state_size = 5
    action_size = 3
    server_uri = "ws://localhost:9080/agent-client"
    bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}

    model = GAAgentNN(state_size, action_size).to(device)
    weights = torch.load(path)
    set_flat_weights(model, weights)

    visited_cells = set()

    async with websockets.connect(server_uri) as websocket:
        await websocket.send(json.dumps({"action": "RESET"}))
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)
            if data["event"] == "STATE_UPDATE":
                state = process_state_grid(data, visited_cells, bounds)
                action_index = select_action(model, state)
                action = ["LEFT", "RIGHT", "FORWARD"][action_index]
                await websocket.send(json.dumps({"action": action}))
            elif data["event"] == "GAME_OVER":
                print(f"Coverage: {len(visited_cells)} cells ({len(visited_cells) / (GRID_ROWS * GRID_COLS) * 100:.2f}%)")
                break

# Entry point
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        asyncio.run(run_best_model())
    else:
        asyncio.run(run_ga())
