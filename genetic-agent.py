import asyncio
import websockets
import json
import random
import logging
import os
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genetic-agent")

# Constants (adjustable)
GENOME_MIN_LENGTH = 10
GENOME_MAX_LENGTH = 10000
POPULATION_SIZE = 100
GENERATIONS = 200
MUTATION_RATE = 0.1
ACTIONS = ["LEFT", "RIGHT", "FORWARD"]
WEBSOCKET_URI = "ws://localhost:9080/agent-client"
BEST_GENOME_PATH = "best_genome.json"

def random_genome():
    length = random.randint(GENOME_MIN_LENGTH, GENOME_MAX_LENGTH)
    return [random.choice(ACTIONS) for _ in range(length)]

def mutate(genome):
    new_genome = []
    for gene in genome:
        if random.random() < MUTATION_RATE:
            op = random.choice(["replace", "delete", "insert"])
            if op == "replace":
                new_genome.append(random.choice(ACTIONS))
            elif op == "delete":
                continue  # skip this gene
            elif op == "insert":
                new_genome.append(random.choice(ACTIONS))
                new_genome.append(gene)
        else:
            new_genome.append(gene)
    # Optional: keep genome within min/max length bounds
    return new_genome[:GENOME_MAX_LENGTH]

def crossover(parent1, parent2):
    max_length = max(len(parent1), len(parent2))
    child = []
    for i in range(max_length):
        gene1 = parent1[i] if i < len(parent1) else random.choice(ACTIONS)
        gene2 = parent2[i] if i < len(parent2) else random.choice(ACTIONS)
        child.append(random.choice([gene1, gene2]))
    return child

def save_genome(genome, path=BEST_GENOME_PATH):
    with open(path, "w") as f:
        json.dump(genome, f)
    logger.info(f"Saved best genome to {path}")

def load_best_genome(path=BEST_GENOME_PATH):
    if os.path.exists(path):
        with open(path, "r") as f:
            genome = json.load(f)
        logger.info(f"Loaded best genome from {path}")
        return genome
    else:
        logger.info("No saved genome found.")
        return None

async def evaluate_genome(genome):
    async with websockets.connect(WEBSOCKET_URI) as websocket:
        await websocket.recv()

        for action in genome:
            await websocket.send(json.dumps({"action": action}))
            message = await websocket.recv()
            data = json.loads(message)

            if data["event"] == "GAME_OVER":
                return data["coverage"]

        return 0.0  # fallback

async def evolve():
    # Try loading previous best genome
    best_loaded = load_best_genome()
    population = [best_loaded] if best_loaded else []
    while len(population) < POPULATION_SIZE:
        population.append(random_genome())

    best_overall_fitness = 0.0  # Initialize best fitness

    for generation in range(GENERATIONS):
        logger.info(f"Generation {generation + 1}/{GENERATIONS}")
        scored_population = []

        for i, genome in enumerate(population):
            logger.info(f"Evaluating genome {i + 1}/{POPULATION_SIZE}")
            fitness = await evaluate_genome(genome)
            scored_population.append((fitness, genome))
            logger.info(f" -> Fitness: {fitness:.2f}")

        # Sort by fitness
        scored_population.sort(reverse=True, key=lambda x: x[0])

        # Keep top 20%
        elite_count = POPULATION_SIZE // 5
        next_generation = [genome for _, genome in scored_population[:elite_count]]

        # Reproduce
        while len(next_generation) < POPULATION_SIZE:
            parent1 = random.choice(scored_population)[1]
            parent2 = random.choice(scored_population)[1]
            child = mutate(crossover(parent1, parent2))
            next_generation.append(child)

        population = next_generation
        best_fitness = scored_population[0][0]
        logger.info(f"Best fitness this generation: {best_fitness:.2f}")

        # Save best genome
        if best_fitness > best_overall_fitness:
            best_overall_fitness = best_fitness
            save_genome(scored_population[0][1])

if __name__ == "__main__":
    try:
        asyncio.run(evolve())
    except KeyboardInterrupt:
        logger.info("Genetic algorithm interrupted.")