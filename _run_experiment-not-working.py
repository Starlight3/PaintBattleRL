from dataclasses import dataclass
import os
import logging
import random
import json
from itertools import product
import websockets
import asyncio

GENERATIONS = 10
MODEL_DIR = "bestModels"
LOG_DIR = "logs"
@dataclass
class GAConfig:
    mutation_rate: float
    population_size: int
    angle_splits: int
    crossover_method: str
    log_suffix: str

class GeneticAlgorithm:
    def __init__(self, config: GAConfig):
        self.config = config
        self.population = self.initialize_population()
        self.logger = self.setup_logger()
        self.action_map = {
            0: "LEFT",
            1: "RIGHT",
            2: "FORWARD"
        }

    def setup_logger(self):
        logger = logging.getLogger(f"GA_{self.config.log_suffix}")
        logger.setLevel(logging.INFO)
        log_filename = os.path.join("logs", f"log_{self.config.log_suffix}.txt")
        fh = logging.FileHandler(log_filename)
        formatter = logging.Formatter('%(asctime)s %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh) #how to close?
        return logger
    
    def initialize_population(self):
        return [self.random_genome() for _ in range(self.config.population_size)]
    
    def random_genome(self):
        GENOME_LENGTH = len(list(product([0, 1], repeat=4))) * self.config.angle_splits  
        return [random.choice([0, 1, 2]) for _ in range(GENOME_LENGTH)]
    
    def generate_all_keys(self, angle_splits):
        angles = [i * (360 // angle_splits) for i in range(angle_splits)]
        quads = list(product([0, 1], repeat=4))  # All 16 combinations
        return [(q1, q2, q3, q4, angle) for (q1, q2, q3, q4) in quads for angle in angles]

    def build_action_table(self, genome, keys):
        if len(genome) != len(keys):
            raise ValueError("Genome length does not match number of keys.")
        return {key: action for key, action in zip(keys, genome)}

    def get_action(self, quads, degree, parts):
        snapped_degree = self.snap_degree_to_nearest_sector(degree, parts)
        key = (*quads, snapped_degree)
        print(key, " " ,self.action_table.get(key, 2))
        return self.action_table.get(key, 2)
    

    def convertGrid(self, grid, x, y):
        quad1 = quad2 = quad3 = quad4 = 0
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if i < y and j < x:
                    quad1 += grid[i][j]
                elif i < y and j >= x:
                    quad2 += grid[i][j]
                elif i >= y and j < x:
                    quad3 += grid[i][j]
                elif i >= y and j >= x:
                    quad4 += grid[i][j]
        return self.normalise_quads_multi_max(quad1, quad2, quad3, quad4)

    def snap_degree_to_nearest_sector(self, degree, parts):
        if parts <= 0:
            raise ValueError("Number of parts must be greater than 0.")
        sector_size = 360 / parts
        snapped = round(degree / sector_size) * sector_size
        return snapped % 360


    def crossover(self, parent1, parent2):
        if self.config.crossover_method == "uniform":
            return [random.choice([g1, g2]) for g1, g2 in zip(parent1, parent2)]
        elif self.config.crossover_method == "one_point":
            point = random.randint(1, self.config.genome_length - 1)
            return parent1[:point] + parent2[point:]
        else:
            raise ValueError("Unknown crossover method.")
    def mutate(self, genome):
        return [
            gene if random.random() > self.config.mutation_rate else random.choice([0, 1, 2])
            for gene in genome
        ] 

    def save_genome(self, genome, path):
        path = MODEL_DIR+"/bestGenome_"+path+".json"
        with open(path, "w") as f:
            json.dump(genome, f)
        self.logger.info(f"Saved best genome to {path}")

    def evolve(self):
        best_fitness = None
        for generation in range(GENERATIONS):
            self.logger.info(f"Generation {generation + 1}")
            scored_population = [(self.evaluate_genome(genome), genome) for genome in self.population]
            scored_population.sort(reverse=True, key=lambda x: x[0])

            elites = [genome for _, genome in scored_population[:self.config.elite_count]]
            next_generation = elites.copy()

            while len(next_generation) < self.config.population_size:
                parent1 = random.choice(scored_population)[1]
                parent2 = random.choice(scored_population)[1]
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                next_generation.append(child)

            self.population = next_generation
            best_fitness = scored_population[0][0]

            self.logger.info(f"Best fitness: {best_fitness:.2f}")
            if best_fitness > best_overall_fitness:
                best_overall_fitness = best_fitness
                best_genome = scored_population[0][1]
                if best_genome is not None:
                    self.save_genome(best_genome, f"bestModels/model_{self.config.log_suffix}.json")
        return best_fitness

    async def evaluate_genome(self, genome):
        # Placeholder for actual evaluation logic
        async with websockets.connect(self.server_uri) as websocket:
            while True:
                message = await websocket.recv()
                game_data = json.loads(message)

                if game_data["event"] == "STATE_UPDATE":
                    player_data = game_data["player"]
                    x = player_data["x"]
                    y = player_data["y"]
                    degree = player_data["degree"]
                    strideX = game_data["strideX"]
                    strideY = game_data["strideY"]
                    grid = game_data["grid"]

                    quads = self.convertGrid(grid, int(x / strideX), int(y / strideY))
                    decision = self.get_action(quads, degree, self.config.angle_splits)
                    await websocket.send(json.dumps({"action": self.action_map.get(decision, "FORWARD")}))
                elif game_data["event"] == "GAME_OVER":
                    coverage = game_data["coverage"]
                    self.population[self.current_genome_index]["fitness"] = coverage
                    await websocket.send(json.dumps({"action": "RESET"}))
                    print(f"Genome {self.current_genome_index + 1} completed with fitness {coverage}")
                    return coverage

        return random.uniform(0, 100)
    
async def run_experiments():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Example: Varying mutation rates
    mutation_rates = [0.01, 0.05, 0.1, 0.2]
    for i, mr in enumerate(mutation_rates):
        config = GAConfig(
            mutation_rate=mr,
            population_size=10,
            angle_splits = 8,
            crossover_method="uniform",
            log_suffix=f"mutation_m_{mr}"
        )
        ga = GeneticAlgorithm(config)
        ga.evolve()

# Entry point
if __name__ == "__main__":
    asyncio.run(run_experiments())