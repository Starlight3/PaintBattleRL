import os
import asyncio
import websockets
import json
import csv
import neat
import pickle
import numpy as np

# Global settings
SERVER_URI = "ws://localhost:9080/agent-client"
BOUNDS = {"top": 0, "right": 800, "bottom": 600, "left": 0}
STATE_SIZE = 4
ACTION_SIZE = 3

def process_state(game_data):
    player = game_data["player"]
    x = player["x"] / BOUNDS["right"]
    y = player["y"] / BOUNDS["bottom"]
    degree = player["degree"] / 360.0
    coverage = game_data["coverage"] / 100.0
    return [x, y, degree, coverage]

def select_action(output):
    return ["LEFT", "RIGHT", "FORWARD"][np.argmax(output)]

async def evaluate_genome(genome, config):
    net = neat.nn.FeedForwardNetwork.create(genome, config)
    try:
        async with websockets.connect(SERVER_URI) as websocket:
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)

                if data["event"] == "STATE_UPDATE":
                    state = process_state(data)
                    output = net.activate(state)
                    action = select_action(output)
                    await websocket.send(json.dumps({"action": action}))

                elif data["event"] == "GAME_OVER":
                    return data["coverage"]
    except Exception as e:
        print(f"Evaluation error: {e}")
        return 0.0  # Penalise error

async def run_neat_and_log(config_path, config_name):
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path
    )

    population = neat.Population(config)
    best_genome = None
    best_fitness = -1

    # Evaluate each genome
    for generation in range(100):  # You may increase generations
        genomes = list(population.population.items())
        for genome_id, genome in genomes:
            fitness = await evaluate_genome(genome, config)
            genome.fitness = fitness

            if fitness > best_fitness:
                best_fitness = fitness
                best_genome = genome

        population.reporters.end_generation(config, population, generation)

    # Save best model
    os.makedirs("results/neat_models", exist_ok=True)
    model_path = f"results/neat_models/{config_name}_best_genome.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(best_genome, f)

    # Log result
    os.makedirs("results", exist_ok=True)
    result_path = "results/test_result_neat_real_game.csv"
    header_needed = not os.path.exists(result_path)
    with open(result_path, "a", newline="") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow(["config", "best_fitness", "network_structure"])

        # Extract structure from the best genome
        node_count = len(best_genome.nodes)
        conn_count = sum(1 for _, cg in best_genome.connections.items() if cg.enabled)
        structure_info = f"nodes:{node_count}, connections:{conn_count}"

        writer.writerow([config_name, best_fitness, structure_info])


    print(f"\nBest fitness for {config_name}: {best_fitness}")
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    config_folder = "configs"
    config_files = [f for f in os.listdir(config_folder) if f.endswith(".txt")]

    for config_file in config_files:
        config_path = os.path.join(config_folder, config_file)
        config_name = os.path.splitext(config_file)[0]  # "mutation_0.1.txt" → "mutation_0.1"
        print(f"\n=== Running config: {config_name} ===")
        asyncio.run(run_neat_and_log(config_path=config_path, config_name=config_name))