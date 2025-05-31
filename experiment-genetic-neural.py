import numpy as np
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
import asyncio
import websockets
import json
import os
import csv
import logging
from datetime import datetime

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

def get_flat_weights(model):
    return torch.cat([p.data.view(-1) for p in model.parameters()])

def set_flat_weights(model, flat):
    pointer = 0
    for param in model.parameters():
        numel = param.numel()
        param.data.copy_(flat[pointer:pointer + numel].view(param.size()))
        pointer += numel

def process_state(game_data, bounds):
    player = game_data["player"]
    x = player["x"] / bounds["right"]
    y = player["y"] / bounds["bottom"]
    degree = player["degree"] / 360.0
    coverage = game_data["coverage"] / 100.0
    return np.array([x, y, degree, coverage], dtype=np.float32)

def select_action(model, state):
    state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(device)
    with torch.no_grad():
        q_values = model(state_tensor)
    return torch.argmax(q_values).item()

async def evaluate(weights, server_uri, bounds):
    state_size = 4
    action_size = 3
    model = GAAgentNN(state_size, action_size).to(device)
    set_flat_weights(model, torch.tensor(weights, dtype=torch.float32))

    try:
        async with websockets.connect(server_uri) as websocket:
            coverage = 0.0
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
                    coverage = data["coverage"]
                    break
            return coverage
    except:
        return 0.0

def crossover(p1, p2, method="uniform"):
    if method == "single_point":
        point = random.randint(1, len(p1) - 1)
        return np.concatenate((p1[:point], p2[point:]))
    else:  # uniform
        mask = np.random.rand(len(p1)) > 0.5
        return np.where(mask, p1, p2)

def mutate(weights, rate=0.05):
    return weights + np.random.randn(*weights.shape) * rate

def setup_logger(log_path):
    logger = logging.getLogger("GA")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    fh = logging.FileHandler(log_path)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger

async def run_ga(config_name, mutation_rate=0.05, population_size=10, crossover_type="uniform", generations=100):
    state_size = 4
    action_size = 3
    server_uri = "ws://localhost:9080/agent-client"
    bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}

    os.makedirs("results/logs", exist_ok=True)
    os.makedirs("results/models", exist_ok=True)

    log_path = f"results/logs/{config_name}.log"
    model_path = f"results/models/{config_name}.pt"

    logger = setup_logger(log_path)
    logger.info(f"Running config: mutation={mutation_rate}, pop={population_size}, crossover={crossover_type}")

    model_template = GAAgentNN(state_size, action_size)
    weight_dim = get_flat_weights(model_template).shape[0]
    population = [np.random.randn(weight_dim) for _ in range(population_size)]

    best_fitness = 0.0
    best_individual = None

    for gen in range(generations):
        logger.info(f"=== Generation {gen+1} ===")
        fitnesses = []
        for i, individual in enumerate(population):
            fitness = await evaluate(individual, server_uri, bounds)
            logger.info(f"Individual {i+1}: Fitness = {fitness:.2f}%")
            fitnesses.append(fitness)

        ranked = sorted(zip(fitnesses, population), key=lambda x: -x[0])
        if ranked[0][0] > best_fitness:
            best_fitness = ranked[0][0]
            best_individual = ranked[0][1]

        elites = [ind for _, ind in ranked[:2]]
        new_population = elites[:]
        while len(new_population) < population_size:
            p1, p2 = random.sample(elites, 2)
            child = mutate(crossover(p1, p2, crossover_type), rate=mutation_rate)
            new_population.append(child)
        population = new_population

    torch.save(torch.tensor(best_individual), model_path)
    logger.info(f"Best fitness overall: {best_fitness:.2f}%")
    return config_name, best_fitness

async def main():
    configs = []

    # Mutation tests
    for rate in [0.01, 0.05, 0.1]:
        configs.append((f"mutation_{rate}", rate, 10, "uniform"))

    # Population tests
    for pop in [10, 20]:
        configs.append((f"population_{pop}", 0.05, pop, "uniform"))

    # Crossover tests
    for cross in ["uniform", "single_point"]:
        configs.append((f"crossover_{cross}", 0.05, 10, cross))

    os.makedirs("results", exist_ok=True)

    results_csv_path = "results/results.csv"
    write_header = not os.path.exists(results_csv_path)

    with open(results_csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["config", "best_fitness"])

        for config_name, rate, pop, cross in configs:
            config_id, fitness = await run_ga(
                config_name,
                mutation_rate=rate,
                population_size=pop,
                crossover_type=cross
            )

            writer.writerow([config_id, fitness])
            f.flush()

if __name__ == "__main__":
    asyncio.run(main())
