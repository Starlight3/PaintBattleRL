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

# Neural network (same as DQN)
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

# Flatten and restore weights
def get_flat_weights(model):
    return torch.cat([p.data.view(-1) for p in model.parameters()])

def set_flat_weights(model, flat):
    pointer = 0
    for param in model.parameters():
        numel = param.numel()
        param.data.copy_(flat[pointer:pointer + numel].view(param.size()))
        pointer += numel

# Get grid coordinates
def get_grid_coordinates(x, y, bounds, grid_size):
    """
    Maps the player's (x, y) position to grid coordinates.
    """
    # Normalize the player's position within the bounds
    norm_x = (x - bounds["left"]) / (bounds["right"] - bounds["left"])
    norm_y = (y - bounds["top"]) / (bounds["bottom"] - bounds["top"])

    # Calculate grid indices
    col = int(norm_x * grid_size)
    row = int(norm_y * grid_size)

    # Ensure indices are within grid bounds
    col = min(max(col, 0), grid_size - 1)
    row = min(max(row, 0), grid_size - 1)

    return row, col

# Coverage calculation
def coverage(grid):
    """
    Computes the percentage of covered cells in the grid.
    """
    # If grid is a torch tensor, convert to numpy
    if not isinstance(grid, np.ndarray):
        grid = grid.cpu().numpy()

    # If grid has 3 channels (e.g., RGB), consider a cell filled if any channel is non-zero
    if len(grid.shape) == 3:
        filled = (grid.sum(axis=2) != 0).sum()
    else:
        # For single-channel grid
        filled = (grid != 0).sum()

    total = grid.shape[0] * grid.shape[1]
    return (filled / total) * 100

# Process game state
prev_pos = [0.0, 0.0]
GRID_SIZE = 30  # Example grid size

def process_state(game_data, bounds):
    global prev_pos, grid

    player = game_data["player"]
    x = player["x"]
    y = player["y"]

    # Get the grid coordinates
    row, col = get_grid_coordinates(x, y, bounds, GRID_SIZE)

    # Update grid (mark the cell as visited)
    grid[row, col] = 1

    # Calculate the change in position
    dx = x - prev_pos[0]
    dy = y - prev_pos[1]
    prev_pos = [x, y]

    # Calculate the degree and whether the player can draw
    degree = player["degree"] / 360.0
    can_draw = 1.0 if player["canDraw"] else 0.0

    # Compute the coverage
    coverage_value = coverage(grid)

    # Return the state vector including coverage
    return np.array([x, y, dx, dy, degree, can_draw, coverage_value], dtype=np.float32)

# Get action
def select_action(model, state):
    state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(device)
    with torch.no_grad():
        q_values = model(state_tensor)
    return torch.argmax(q_values).item()

# Evaluate individual
async def evaluate(weights, server_uri, bounds):
    state_size = 7
    action_size = 3
    model = GAAgentNN(state_size, action_size).to(device)
    set_flat_weights(model, torch.tensor(weights, dtype=torch.float32))

    # Initialize the grid (empty)
    global grid
    grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.uint8)

    try:
        async with websockets.connect(server_uri) as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                if data["event"] == "STATE_UPDATE":
                    state = process_state(data, bounds)
                    action_index = select_action(model, state)
                    actions = ["LEFT", "RIGHT", "FORWARD"]
                    await websocket.send(json.dumps({"action": actions[action_index]}))
                elif data["event"] == "GAME_OVER":
                    coverage = data["coverage"] / 100.0
                    break
            return coverage * 100.0  # return fitness
    except:
        return 0.0

# GA functions
def crossover(parent1, parent2):
    point = random.randint(1, len(parent1) - 1)
    print(f"  Crossover at point {point}")
    return np.concatenate((parent1[:point], parent2[point:]))

def mutate(weights, rate=0.2):
    mutation = np.random.randn(*weights.shape) * rate
    print(f"  Mutation applied with rate {rate}")
    return weights + mutation

# Main GA loop
async def run_ga():
    state_size = 7
    action_size = 3
    pop_size = 10
    generations = 20
    server_uri = "ws://localhost:9080/agent-client"
    bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}

    dummy_model = GAAgentNN(state_size, action_size)
    weight_dim = get_flat_weights(dummy_model).shape[0]
    population = [np.random.randn(weight_dim) for _ in range(pop_size)]

    # Resume from saved model if available
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

        # Save best model
        best_weights = torch.tensor(best_individual)
        torch.save(best_weights, "best_model.pt")

        print("Top 2 individuals:")
        for idx, (fit, ind) in enumerate(ranked[:2]):
            print(f"  #{idx+1}: Fitness={fit:.2f}% | Sample weights[:5]={ind[:5]}")

        elites = [ind for _, ind in ranked[:2]]
        new_population = elites[:]
        while len(new_population) < pop_size:
            p1, p2 = random.sample(elites, 2)
            print("Generating new child...")
            child = mutate(crossover(p1, p2))
            new_population.append(child)
        population = new_population

# Run best model only
async def run_best_model(path="best_model.pt"):
    state_size = 7
    action_size = 3
    server_uri = "ws://localhost:9080/agent-client"
    bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}

    model = GAAgentNN(state_size, action_size).to(device)
    weights = torch.load(path)
    set_flat_weights(model, weights)

    async with websockets.connect(server_uri) as websocket:
        await websocket.send(json.dumps({"action": "RESET"}))
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)
            if data["event"] == "STATE_UPDATE":
                state = process_state(data, bounds)
                action_index = select_action(model, state)
                action = ["LEFT", "RIGHT", "FORWARD"][action_index]
                await websocket.send(json.dumps({"action": action}))
            elif data["event"] == "GAME_OVER":
                print(f"Coverage: {data['coverage']}%")
                break

# Entry point
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        asyncio.run(run_best_model())
    else:
        asyncio.run(run_ga())
