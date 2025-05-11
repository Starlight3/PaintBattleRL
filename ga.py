# Updated GA-based BattlePainter Agent with fitness penalties instead of random actions
import numpy as np
import random
import websockets
import asyncio
import json

# Genetic Algorithm for BattlePainter
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

    def crossover(self, parent1, parent2):  # One-point crossover
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
        self.current_coverage = 0
        self.done = False
        self.generation = 0
        self.individual = 0
        self.action_cooldown = 0
        self.cooldown_threshold = 5
        self.action_history = []
        self.last_action = None
        self.action_repeat_count = 0
        self.max_repeats = 3
        self.prev_coverage = 0.0

    def process_state(self, game_data):
        if game_data["event"] == "STATE_UPDATE":
            player = game_data["player"]
            x = player["x"] / self.bounds["right"]
            y = player["y"] / self.bounds["bottom"]
            degree = player["degree"] / 360.0
            can_draw = 1.0 if player["canDraw"] else 0.0
            coverage = game_data["coverage"] / 100.0
            return np.reshape([x, y, degree, can_draw, coverage], [1, self.state_size])
        return None

    def get_action_from_index(self, action_index):
        return ["LEFT", "RIGHT", "FORWARD"][action_index]

    def select_action(self, state, policy):
        action_values = np.dot(policy, state.flatten())
        action = np.argmax(action_values)

        # Track repeated actions
        if self.last_action is not None and action == self.last_action:
            self.action_repeat_count += 1
        else:
            self.action_repeat_count = 1  # count current action
            self.last_action = action

        # Penalize excessive repeats without coverage improvement
        if self.action_repeat_count >= self.max_repeats:
            if self.current_coverage - self.prev_coverage < 0.001:
                print("Penalty: Excessive repeated action without coverage improvement.")
                self.ga.fitness_scores[self.individual] -= 0.01

        # Detect oscillation between LEFT and RIGHT
        if len(self.action_history) >= 3:
            last_three = self.action_history[-3:]
            if set(last_three) == {0, 1}:
                print("Penalty: Oscillation detected.")
                self.ga.fitness_scores[self.individual] -= 0.01

        # Enforce cooldown on direction change
        if self.action_cooldown > 0 and action in [0, 1]:
            print("Penalty: Direction change during cooldown.")
            self.ga.fitness_scores[self.individual] -= 0.01
            action = 2  # Prefer FORWARD
        if action in [0, 1]:
            self.action_cooldown = self.cooldown_threshold
        else:
            self.action_cooldown = max(0, self.action_cooldown - 1)

        self.action_history.append(action)
        return action

    async def game_loop(self):
        while self.generation < self.ga.generations:
            for i, policy in enumerate(self.ga.population):
                try:
                    async with websockets.connect(self.server_uri) as websocket:
                        print(f"Generation {self.generation}, Individual {i + 1}")
                        total_coverage = 0
                        steps = 0
                        self.done = False
                        self.individual = i
                        self.action_cooldown = 0
                        self.action_history.clear()
                        self.last_action = None
                        self.action_repeat_count = 0
                        self.prev_coverage = 0.0

                        while not self.done:
                            message = await websocket.recv()
                            game_data = json.loads(message)

                            if game_data["event"] == "STATE_UPDATE":
                                state = self.process_state(game_data)
                                self.current_coverage = game_data["coverage"] / 100.0
                                action_index = self.select_action(state, policy)
                                action = self.get_action_from_index(action_index)

                                await websocket.send(json.dumps({"action": action}))
                                self.prev_coverage = self.current_coverage
                                total_coverage = self.current_coverage
                                print(f"[Gen {self.generation} | Ind {i+1}] Action: {action} | Coverage: {self.current_coverage:.2f}")

                            elif game_data["event"] == "GAME_OVER":
                                self.done = True
                                self.ga.set_fitness(i, total_coverage)
                                print(f"Individual {i + 1} finished with coverage: {total_coverage * 100:.2f}%")
                                if i < self.ga.population_size - 1:
                                    await websocket.send(json.dumps({"action": "RESET"}))

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