import numpy as np
import random
import websockets
import asyncio
import json
from itertools import product
import os

POPULATION_FILE = "population_data.json"
POPULATION_SIZE = 15
NUM_GENERATIONS = 500
ELITE_COUNT = 2
MUTATION_RATE = 0.1
ANGLE_SPLITS = 8
GENOME_LENGTH = len(list(product([0, 1], repeat=4))) * ANGLE_SPLITS  # 16 * splits = 128


class BattlePainterGA:
    def __init__(self, server_uri="ws://localhost:9080/agent-client"):
        self.server_uri = server_uri
        self.done = False
        self.counter = 0
        self.population = [{"genome": self.generate_random_genome(), "fitness": None} for _ in range(POPULATION_SIZE)]
        self.fitness_scores = [0] * POPULATION_SIZE
        self.current_genome_index = 0
        self.generation = 0
        self.action_table = {}
        self.load_population()
        self.resume_progress()

        self.action_map = {
            0: "LEFT",
            1: "RIGHT",
            2: "FORWARD"
        }

    def generate_random_genome(self, length=GENOME_LENGTH, action_space=(0, 1, 2)):
        return [random.choice(action_space) for _ in range(length)]

    def generate_all_keys(self, angle_splits=ANGLE_SPLITS):
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

    def normalise_quads_multi_max(self, quad1, quad2, quad3, quad4):
        quads = [quad1, quad2, quad3, quad4]
        max_value = max(quads)
        return tuple(1 if q == max_value else 0 for q in quads)

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

    def evolve_population(self):
        # Sort by fitness (descending)
        sorted_population = sorted(self.population, key=lambda x: x["fitness"] or 0, reverse=True)
        elites = sorted_population[:ELITE_COUNT]
        # Print elites
        print("\n--- Elites Preserved ---")
        for i, elite in enumerate(elites):
            print(f"Elite {i + 1}: Fitness = {elite['fitness']}, Genome (first 10 genes) = {elite['genome'][:10]}...")

        new_population = elites[:]
        while len(new_population) < POPULATION_SIZE:
            parent1 = random.choice(elites)["genome"]
            parent2 = random.choice(sorted_population)["genome"]
            child = self.crossover(parent1, parent2)
            child = self.mutate(child)
            new_population.append({"genome": child, "fitness": None})

        self.population = new_population
        self.fitness_scores = [0] * POPULATION_SIZE
        print("\nPopulation evolved to next generation.")

    def crossover(self, parent1, parent2):
        point = random.randint(1, GENOME_LENGTH - 1)
        return parent1[:point] + parent2[point:]

    def mutate(self, genome):
        return [
            gene if random.random() > MUTATION_RATE else random.choice([0, 1, 2])
            for gene in genome
        ]

    def print_population_status(self):
        print("\n--- Current Population Status ---")
        for i, individual in enumerate(self.population):
            fitness = individual["fitness"]
            status = f"Fitness: {fitness}" if fitness is not None else "Not calculated"
            print(f"Genome {i + 1}: {status}")

    def save_population(self):
        sorted_pop = sorted(
            self.population,
            key=lambda x: x["fitness"] if x["fitness"] is not None else -1,
            reverse=True
        )
        with open(POPULATION_FILE, "w") as f:
            json.dump(sorted_pop, f, indent=2)

    def load_population(self):
        if os.path.exists(POPULATION_FILE):
            with open(POPULATION_FILE, "r") as f:
                self.population = json.load(f)
            print(f"Population loaded from file with {len(self.population)} individuals.")
            
            if len(self.population) > POPULATION_SIZE:
                # Sort descending, treating None fitness as lowest
                self.population.sort(key=lambda x: x["fitness"] if x["fitness"] is not None else -1, reverse=True)
                self.population = self.population[:POPULATION_SIZE]
                print("Sorted and truncated population to retain best individuals.")
            # Pad with new individuals if needed
            while len(self.population) < POPULATION_SIZE:
                self.population.append({"genome": self.generate_random_genome(), "fitness": None})
                print("Added new random genome to match updated POPULATION_SIZE.")
            
        else:
            print("No saved population found. Starting new.")
            self.population = [{"genome": self.generate_random_genome(), "fitness": None} for _ in range(POPULATION_SIZE)]

    def resume_progress(self):
        for i, individual in enumerate(self.population):
            if individual["fitness"] is None:
                self.current_genome_index = i
                return
        self.current_genome_index = POPULATION_SIZE  # triggers evolution
        print("All genomes evaluated. Ready to evolve.")

    async def game_loop(self):
        keys = self.generate_all_keys()

        while self.generation < NUM_GENERATIONS:
            print(f"\n=== Generation {self.generation + 1} ===")
            while self.current_genome_index < POPULATION_SIZE:
                genome = self.population[self.current_genome_index]["genome"]
                self.action_table = self.build_action_table(genome, keys)
                print(self.action_table)
                self.done = False

                async with websockets.connect(self.server_uri) as websocket:
                    while not self.done:
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
                            decision = self.get_action(quads, degree, ANGLE_SPLITS)
                            await websocket.send(json.dumps({"action": self.action_map.get(decision, "FORWARD")}))

                        elif game_data["event"] == "GAME_OVER":
                            coverage = game_data["coverage"]
                            self.population[self.current_genome_index]["fitness"] = coverage
                            print(f"Genome {self.current_genome_index + 1} completed with fitness {coverage}")
                            self.save_population()
                            self.print_population_status()
                            await websocket.send(json.dumps({"action": "RESET"}))
                            self.done = True
                            self.current_genome_index += 1

            self.evolve_population()
            self.generation += 1
            self.current_genome_index = 0

    def run(self):
        asyncio.run(self.game_loop())


if __name__ == "__main__":
    agent = BattlePainterGA()
    agent.run()
