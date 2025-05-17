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

# Process game state
def process_state(game_data, bounds):
    player = game_data["player"]
    x = player["x"] / bounds["right"]
    y = player["y"] / bounds["bottom"]
    degree = player["degree"] / 360.0
    can_draw = 1.0 if player["canDraw"] else 0.0
    coverage = game_data["coverage"] / 100.0
    return np.array([x, y, degree, can_draw, coverage], dtype=np.float32)

# Get action
def select_action(model, state):
    state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(device)
    with torch.no_grad():
        q_values = model(state_tensor)
    return torch.argmax(q_values).item()

# Evaluate individual
async def evaluate(weights, server_uri, bounds):
    state_size = 5
    action_size = 3
    model = GAAgentNN(state_size, action_size).to(device)
    set_flat_weights(model, torch.tensor(weights, dtype=torch.float32))

    try:
        async with websockets.connect(server_uri) as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            coverage = 0.0
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                if data["event"] == "STATE_UPDATE"or data["event"] == "INITIAL_STATE":
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

def mutate(weights, rate=0.4):
    mutation = np.random.randn(*weights.shape) * rate
    print(f"  Mutation applied with rate {rate}")
    return weights + mutation

# Main GA loop
async def run_ga():
    state_size = 5
    action_size = 3
    pop_size = 100
    generations = 200000
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
    state_size = 5
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
            if data["event"] == "STATE_UPDATE" or data["event"] == "INITIAL_STATE":
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
