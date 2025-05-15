# GA-based BattlePainter Agent with grid-cell-based coverage tracking
import numpy as np
import random
import websockets
import asyncio
import json

class GAAgent:
    def __init__(self, state_size, action_size, population_size=10, mutation_rate=0.01, generations=10):
        self.state_size = state_size
        self.action_size = action_size
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.generations = generations
        self.population = [self.random_policy() for _ in range(population_size)]
        self.fitness_scores = [0.0] * population_size
        self.best_policy = None

    def random_policy(self):
        return np.random.randn(self.action_size, self.state_size)

    def act(self, state, policy):
        action_values = np.dot(policy, state.flatten())
        return np.argmax(action_values)

    def mutate(self, policy):
        mutation = np.random.randn(*policy.shape) * self.mutation_rate
        return policy + mutation

    def crossover(self, parent1, parent2):
        flat1 = parent1.flatten()
        flat2 = parent2.flatten()
        point = random.randint(1, len(flat1) - 1)
        child_flat = np.concatenate((flat1[:point], flat2[point:]))
        child = child_flat.reshape(parent1.shape)
        return self.mutate(child)

    def select_parents(self):
        sorted_indices = np.argsort(self.fitness_scores)[::-1]
        return [self.population[i] for i in sorted_indices[:2]]

    def evolve(self):
        parents = self.select_parents()
        new_population = [parents[0], parents[1]]
        while len(new_population) < self.population_size:
            new_population.append(self.crossover(parents[0], parents[1]))
        self.population = new_population

    def set_fitness(self, index, fitness):
        self.fitness_scores[index] = fitness

    def update_best(self):
        best_index = np.argmax(self.fitness_scores)
        self.best_policy = self.population[best_index]

class BattlePainterGA:
    def __init__(self, server_uri="ws://localhost:9080/agent-client"):
        self.state_size = 5
        self.action_size = 3
        self.ga = GAAgent(self.state_size, self.action_size)
        self.server_uri = server_uri
        self.bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}
        self.current_state = None
        self.done = False
        self.generation = 0
        self.individual = 0
        self.grid_size = 10
        self.visited_cells = set()

    def get_grid_coordinates(self, x, y, bounds, grid_size):
        norm_x = (x - bounds["left"]) / (bounds["right"] - bounds["left"])
        norm_y = (y - bounds["top"]) / (bounds["bottom"] - bounds["top"])
        col = int(norm_x * grid_size)
        row = int(norm_y * grid_size)
        col = min(max(col, 0), grid_size - 1)
        row = min(max(row, 0), grid_size - 1)
        return row, col

    def get_coverage_from_visited(self):
        total_cells = self.grid_size * self.grid_size
        return len(self.visited_cells) / total_cells

    def process_state(self, game_data):
        if game_data["event"] == "STATE_UPDATE":
            player = game_data["player"]
            x = player["x"] / self.bounds["right"]
            y = player["y"] / self.bounds["bottom"]
            degree = player["degree"] / 360.0
            can_draw = 1.0 if player["canDraw"] else 0.0
            coverage = self.get_coverage_from_visited()
            return np.reshape([x, y, degree, can_draw, coverage], [1, self.state_size])
        return None

    def get_action_from_index(self, action_index):
        return ["LEFT", "RIGHT", "FORWARD"][action_index]

    def select_action(self, state, policy):
        action_values = np.dot(policy, state.flatten())
        return np.argmax(action_values)

    async def game_loop(self):
        while self.generation < self.ga.generations:
            for i, policy in enumerate(self.ga.population):
                try:
                    async with websockets.connect(self.server_uri) as websocket:
                        print(f"Generation {self.generation}, Individual {i + 1}")
                        self.done = False
                        self.individual = i
                        self.visited_cells.clear()

                        while not self.done:
                            message = await websocket.recv()
                            game_data = json.loads(message)

                            if game_data["event"] == "STATE_UPDATE":
                                # Track visited cells
                                player = game_data["player"]
                                x = player["x"]
                                y = player["y"]
                                row, col = self.get_grid_coordinates(x, y, self.bounds, self.grid_size)
                                self.visited_cells.add((row, col))

                                # Update state and coverage
                                state = self.process_state(game_data)
                                if state is None:
                                    continue

                                coverage = self.get_coverage_from_visited()
                                action_index = self.select_action(state, policy)
                                action = self.get_action_from_index(action_index)

                                await websocket.send(json.dumps({"action": action}))
                                print(f"[Gen {self.generation} | Ind {i+1}] Action: {action} | Coverage: {coverage:.2f}")

                            elif game_data["event"] == "GAME_OVER":
                                self.done = True
                                final_coverage = self.get_coverage_from_visited()
                                self.ga.set_fitness(i, final_coverage)
                                print(f"Individual {i + 1} finished with coverage: {final_coverage * 100:.2f}%")
                                await websocket.send(json.dumps({"action": "RESET"}))
                                await asyncio.sleep(0.5)  # Give server time to reset (tweak as needed)
                                #if i < self.ga.population_size - 1:
                                #    await websocket.send(json.dumps({"action": "RESET"}))

                except Exception as e:
                    print(f"Error with individual {i + 1}: {e}")
                    await asyncio.sleep(1)

            self.ga.update_best()
            print(f"Best coverage in generation {self.generation}: {np.max(self.ga.fitness_scores) * 100:.2f}%")
            self.ga.evolve()
            self.generation += 1

    def run(self):
        asyncio.run(self.game_loop())

if __name__ == "__main__":
    agent = BattlePainterGA()
    agent.run()
