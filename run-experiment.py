import asyncio
import websockets
import json
import random
import logging
import os
from datetime import datetime
from itertools import product
import itertools


# Constants (not fixed, used as defaults)
ACTIONS = ["LEFT", "RIGHT", "FORWARD"]
WEBSOCKET_URI = "ws://localhost:9080/agent-client"
BEST_GENOME_PATH = "best_genome.json"
LOG_DIR = "logs"
MODEL_DIR = "bestModels"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)


# Setup logging
logger = logging.getLogger("genetic-agent")
logger.setLevel(logging.INFO)
log_handler = logging.FileHandler(os.path.join(LOG_DIR, "experiment.log"))
log_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
logger.addHandler(log_handler)

# Mutation (fixed-length version)
def mutate(genome, mutation_rate):
    return [
        gene if random.random() > mutation_rate else random.choice(ACTIONS)
        for gene in genome
    ]

# Crossover methods
def uniform_crossover(parent1, parent2):
    max_length = max(len(parent1), len(parent2))
    return [random.choice([
        parent1[i] if i < len(parent1) else random.choice(ACTIONS),
        parent2[i] if i < len(parent2) else random.choice(ACTIONS)
    ]) for i in range(max_length)]

def one_point_crossover(parent1, parent2):
    point = random.randint(1, min(len(parent1), len(parent2)) - 1)
    return parent1[:point] + parent2[point:]

def save_genome(genome, path):
    path = MODEL_DIR+"/bestGenome_"+path+".json"
    with open(path, "w") as f:
        json.dump(genome, f)
    logger.info(f"Saved best genome to {path}")

def load_best_genome(path):
    path =  MODEL_DIR+"/bestGenome_"+path+".json"
    if os.path.exists(path):
        with open(path, "r") as f:
            genome = json.load(f)
        logger.info(f"Loaded best genome from {path}")
        return genome
    else:
        logger.info("No saved genome found.")
        return None

def random_genome(length):
    return [random.choice(ACTIONS) for _ in range(length)]

async def evaluate_genome(genome):
    try:
        async with websockets.connect(WEBSOCKET_URI) as websocket:
            await websocket.recv()
            
            genome_cycle = itertools.cycle(genome)
            while True:
                action = next(genome_cycle)
                await websocket.send(json.dumps({"action": action}))
                message = await websocket.recv()
                data = json.loads(message)

                if data["event"] == "GAME_OVER":
                    await websocket.send(json.dumps({"action": "RESET"}))
                    return float(data.get("coverage", 0.0))

    except Exception as e:
        logger.error(f"Error evaluating genome: {e}")
        return 0.0

async def evolve(config):
    genome_length = config["genome_length"]
    mutation_rate = config["mutation_rate"]
    population_size = config["population_size"]
    generations = config["generations"]
    crossover_method = config["crossover_method"]
    elite_count = config["elites"]
    log_suffix = config.get("log_suffix", "default")

    log_path = os.path.join(LOG_DIR, f"log_{log_suffix}.txt")
    file_handler = logging.FileHandler(log_path)
    logger.addHandler(file_handler)

    # Initialise population
    best_model_fileName = f"_g{genome_length}_m{mutation_rate}_p{population_size}_{crossover_method}_gen{generations}_e{elite_count}_{log_suffix}"
    best_loaded = load_best_genome(best_model_fileName)
    population = [best_loaded] if best_loaded else []
    while len(population) < population_size:
        population.append(random_genome(genome_length))

    best_overall_fitness = 0.0

    with open(os.path.join(LOG_DIR, "summary.csv"), "a") as summary_file:
        for generation in range(generations):
            logger.info(f"Generation {generation + 1}/{generations}")
            scored_population = []

            for i, genome in enumerate(population):
                fitness = await evaluate_genome(genome)
                scored_population.append((fitness, genome))
                logger.info(f"Genome {i + 1}: Fitness {fitness:.2f}")

            scored_population.sort(reverse=True, key=lambda x: x[0])
            next_generation = [genome for _, genome in scored_population[:elite_count]]

            while len(next_generation) < population_size:
                parent1 = random.choice(scored_population)[1]
                parent2 = random.choice(scored_population)[1]

                if crossover_method == "uniform":
                    child = uniform_crossover(parent1, parent2)
                else:
                    child = one_point_crossover(parent1, parent2)

                child = mutate(child, mutation_rate)
                child = child[:genome_length]  # Ensure fixed length
                next_generation.append(child)

            population = next_generation
            best_fitness = scored_population[0][0]

            logger.info(f"Best fitness: {best_fitness:.2f}")

            if best_fitness > best_overall_fitness:
                best_overall_fitness = best_fitness
                best_genome = scored_population[0][1]
                if best_genome is not None:
                    save_genome(best_genome,best_model_fileName)

        summary_file.write(f"{log_suffix},{genome_length},{mutation_rate},{population_size},{crossover_method},{generations},{best_overall_fitness:.2f}\n")
        logger.info(f"Summary logged for config {log_suffix}")
        logger.removeHandler(file_handler)
        file_handler.close()

if __name__ == "__main__": 
    async def main():
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--batch", action="store_true", help="Run experiments for multiple configs")
        args, unknown = parser.parse_known_args()

        if args.batch:
            generations = 100

            # 1. Genome length experiment
            for i, gl in enumerate([100, 200]):
                config = {
                    "config_name":"genomeLengthTest",
                    "genome_length": gl,
                    "mutation_rate": 0.1,
                    "population_size": 10,
                    "generations": generations,
                    "crossover_method": "uniform",
                    "elites":2,
                    "log_suffix": f"length{i}_{gl}"
                }
                await evolve(config)

            # 2. Mutation rate experiment
            for i, mr in enumerate([0.01, 0.05, 0.1, 0.2]):
                config = {
                    "config_name":"mutationRateTest",
                    "genome_length": 100,
                    "mutation_rate": mr,
                    "population_size": 10,
                    "generations": generations,
                    "crossover_method": "uniform",
                    "elites":2,
                    "log_suffix": f"mut{i}_{mr}"
                }
                await evolve(config)
            # 3. Population rate experiment
            pop_elite_pairs = [(10, 1), (25, 2), (50, 3), (100, 5)]
            for i, (pop, elites) in enumerate(pop_elite_pairs):
                config = {
                    "config_name": "pop_eliteTest",
                    "genome_length": 100,
                    "mutation_rate": 0.1,
                    "population_size": pop,
                    "generations": generations,
                    "crossover_method": "uniform",
                    "elites": elites,
                    "log_suffix": f"pop{i}_p{pop}_e{elites}"
                }
                await evolve(config)
            # 4. Cross over experiment
            for i, cross in enumerate(["uniform","one-point"]):
                config = {
                    "config_name":"crossoverTest",
                    "genome_length": 100,
                    "mutation_rate": 0.1,
                    "population_size": 10,
                    "generations": generations,
                    "crossover_method": cross,
                    "elites":2,
                    "log_suffix": f"crossover{i}_{cross}"
                }
                await evolve(config)

        else:
            parser = argparse.ArgumentParser()
            parser.add_argument("--genome_length", type=int, default=100)
            parser.add_argument("--mutation_rate", type=float, default=0.1)
            parser.add_argument("--population_size", type=int, default=50)
            parser.add_argument("--generations", type=int, default=200)
            parser.add_argument("--crossover_method", choices=["uniform", "one_point"], default="uniform")
            parser.add_argument("--log_suffix", type=str, default=datetime.now().strftime("%Y%m%d%H%M%S"))
            args = parser.parse_args()
            config = vars(args)
            await evolve(config)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Evolution interrupted.")
