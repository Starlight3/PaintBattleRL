import numpy as np
import random
import websockets
import asyncio
import json
from itertools import product
import os
import csv
import logging
from dataclasses import dataclass, asdict
from datetime import datetime


def write_to_csv(file_path, headers, rows):
    """
    Writes rows to a CSV file. If the file does not exist, it creates it and writes the headers first.
    
    Parameters:
        file_path (str): Path to the CSV file.
        headers (list): List of column names.
        rows (list of list): Data rows to write.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    write_headers = not os.path.exists(file_path)
    
    with open(file_path, mode='a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if write_headers:
            writer.writerow(headers)
        writer.writerows(rows)

@dataclass
class GAConfig:
    mutation_rate: float
    population_size: int
    angle_splits: int
    crossover_method: str
    log_suffix: str

    def to_dict(self):
        return asdict(self)

class BattlePainterGA:
    def __init__(self, config: GAConfig, server_uri="ws://localhost:9080/agent-client"):
        self.config = config
        self.server_uri = server_uri
        self.model_dir = os.path.join("bestModels", config.log_suffix)
        self.log_dir = os.path.join("logs", config.log_suffix)
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.logger = self.setup_logger()

        self.population_file = os.path.join(self.model_dir, "population.json")
        self.population = [{"genome": self.generate_random_genome(), "fitness": None}
                           for _ in range(self.config.population_size)]
        self.current_genome_index = 0
        self.generation = 0
        self.done = False

        self.keys = self.generate_all_keys()
        self.action_table = {}
        self.load_population()
        self.resume_progress()

        self.action_map = {0: "LEFT", 1: "RIGHT", 2: "FORWARD"}

        self.genome_length = len(self.keys)

    def setup_logger(self):
        logger = logging.getLogger(f"GA-{self.config.log_suffix}")
        logger.setLevel(logging.INFO)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        handler = logging.FileHandler(os.path.join(self.log_dir, f"{self.config.log_suffix}_{timestamp}.log"))
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        logger.addHandler(handler)
        logger.propagate = False
        return logger

    def generate_random_genome(self, action_space=(0, 1, 2)):
        return [random.choice(action_space) for _ in range(len(list(product([0, 1], repeat=4))) * self.config.angle_splits)]

    def generate_all_keys(self):
        angles = [i * (360 // self.config.angle_splits) for i in range(self.config.angle_splits)]
        quads = list(product([0, 1], repeat=4))
        return [(q1, q2, q3, q4, angle) for (q1, q2, q3, q4) in quads for angle in angles]

    def build_action_table(self, genome):
        if len(genome) != len(self.keys):
            raise ValueError("Genome length mismatch.")
        return dict(zip(self.keys, genome))

    def snap_degree_to_nearest_sector(self, degree):
        parts = self.config.angle_splits
        return round(degree / (360 / parts)) * (360 // parts) % 360

    def normalise_quads_multi_max(self, quad1, quad2, quad3, quad4):
        quads = [quad1, quad2, quad3, quad4]
        max_val = max(quads)
        return tuple(1 if q == max_val else 0 for q in quads)

    def convertGrid(self, grid, x, y):
        q1 = q2 = q3 = q4 = 0
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if i < y and j < x: q1 += grid[i][j]
                elif i < y and j >= x: q2 += grid[i][j]
                elif i >= y and j < x: q3 += grid[i][j]
                elif i >= y and j >= x: q4 += grid[i][j]
        return self.normalise_quads_multi_max(q1, q2, q3, q4)

    def get_action(self, quads, degree):
        key = (*quads, self.snap_degree_to_nearest_sector(degree))
        return self.action_table.get(key, 2)

    def crossover(self, p1, p2):
        if self.config.crossover_method == "uniform":
            return [random.choice([g1, g2]) for g1, g2 in zip(p1, p2)]
        elif self.config.crossover_method == "one_point":
            point = random.randint(1, len(p1) - 1)
            return p1[:point] + p2[point:]
        else:
            raise ValueError(f"Unsupported crossover method: {self.config.crossover_method}")

    def mutate(self, genome):
        return [
            gene if random.random() > self.config.mutation_rate else random.choice([0, 1, 2])
            for gene in genome
        ]

    def evolve_population(self):
        elites = sorted(self.population, key=lambda x: x["fitness"] or 0, reverse=True)[:2]
        new_pop = elites[:]
        while len(new_pop) < self.config.population_size:
            parent1 = random.choice(elites)["genome"]
            parent2 = random.choice(self.population)["genome"]
            child = self.mutate(self.crossover(parent1, parent2))
            new_pop.append({"genome": child, "fitness": None})
        self.population = new_pop
        self.logger.info("Evolved to next generation.")

    def save_population(self):
        with open(self.population_file, "w") as f:
            json.dump(self.population, f, indent=2)

    def load_population(self):
        if os.path.exists(self.population_file):
            with open(self.population_file, "r") as f:
                self.population = json.load(f)
            while len(self.population) < self.config.population_size:
                self.population.append({"genome": self.generate_random_genome(), "fitness": None})
        else:
            self.population = [{"genome": self.generate_random_genome(), "fitness": None}
                               for _ in range(self.config.population_size)]

    def resume_progress(self):
        for i, individual in enumerate(self.population):
            if individual["fitness"] is None:
                self.current_genome_index = i
                return
        self.current_genome_index = self.config.population_size

    async def game_loop(self, num_generations=1):
        best_fitness = 0
        for generation in range(num_generations):
            self.logger.info(f"Starting Generation {generation + 1}")
            while self.current_genome_index < self.config.population_size:
                genome = self.population[self.current_genome_index]["genome"]
                self.action_table = self.build_action_table(genome)

                async with websockets.connect(self.server_uri) as websocket:
                    self.done = False
                    while not self.done:
                        message = await websocket.recv()
                        data = json.loads(message)

                        if data["event"] == "STATE_UPDATE":
                            px, py = data["player"]["x"], data["player"]["y"]
                            degree = data["player"]["degree"]
                            strideX = data["strideX"]
                            strideY = data["strideY"]
                            grid = data["grid"]

                            quads = self.convertGrid(grid, int(px / strideX), int(py / strideY))
                            decision = self.get_action(quads, degree)
                            await websocket.send(json.dumps({"action": self.action_map.get(decision)}))

                        elif data["event"] == "GAME_OVER":
                            fitness = data["coverage"]
                            if fitness > best_fitness:
                                best_fitness = fitness
                            self.population[self.current_genome_index]["fitness"] = fitness
                            self.logger.info(f"Genome {self.current_genome_index + 1} Fitness: {fitness}")
                            await websocket.send(json.dumps({"action": "RESET"}))
                            self.current_genome_index += 1
                            self.save_population()
                            self.done = True

            self.evolve_population()
            self.current_genome_index = 0
        return best_fitness

# Entry point for multiple configurations
async def run_experiments():
    file_path = "logs/experiment_results.csv"
    headers = ["Config", "BestFitness"]
    mutation_rates = [0.05, 0.1, 0.2, 0.3]
    population_size = 10
    angle_splits = 8
    crossover_method = "uniform"
    generations = 100

    for mr in mutation_rates:
        config = GAConfig(
            mutation_rate=mr,
            population_size=population_size,
            angle_splits=angle_splits,
            crossover_method=crossover_method,
            log_suffix=f"mutation_{str(mr).replace('.', '_')}"
        )
        ga = BattlePainterGA(config)
        fitness = await ga.game_loop(num_generations=generations)
        write_to_csv(file_path, headers, [[f"mutation_{config.mutation_rate}", fitness]])
    #angle split experiment
    config = GAConfig(
        mutation_rate=0.2,
        population_size=population_size,
        angle_splits=16,
        crossover_method=crossover_method,
        log_suffix=f"angles_{str(16).replace('.', '_')}"
    )
    ga = BattlePainterGA(config)
    fitness = await ga.game_loop(num_generations=generations)
    write_to_csv(file_path, headers, [[f"angles_{config.angle_splits}", fitness]])
    #population experiment
    config = GAConfig(
        mutation_rate=0.2,
        population_size=20,
        angle_splits=8,
        crossover_method=crossover_method,
        log_suffix=f"population_{str(20).replace('.', '_')}"
    )
    ga = BattlePainterGA(config)
    fitness = await ga.game_loop(num_generations=generations)
    write_to_csv(file_path, headers, [["population_{config.population_size}", fitness]])
    

if __name__ == "__main__":
    asyncio.run(run_experiments())
