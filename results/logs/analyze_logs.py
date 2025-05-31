import re
import sys

def extract_best_fitness(filename):
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return

    generation_pattern = re.compile(r"=== Generation (\d+) ===")
    fitness_pattern = re.compile(r"Fitness = ([\d.]+)%")

    target_generations = set([1] + list(range(10, 101, 10)))
    best_fitness_by_generation = {}

    current_gen = None
    current_fitnesses = []

    for line in lines:
        gen_match = generation_pattern.search(line)
        if gen_match:
            if current_gen in target_generations and current_fitnesses:
                best_fitness_by_generation[current_gen] = max(current_fitnesses)
            current_gen = int(gen_match.group(1))
            current_fitnesses = []
        else:
            fit_match = fitness_pattern.search(line)
            if fit_match and current_gen is not None:
                current_fitnesses.append(float(fit_match.group(1)))

    if current_gen in target_generations and current_fitnesses:
        best_fitness_by_generation[current_gen] = max(current_fitnesses)

    # Print header
    print("Generation\tFitness")
    for gen in sorted(best_fitness_by_generation.keys()):
        print(f"{gen}\t{best_fitness_by_generation[gen]:.2f}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_data.py <filename>")
    else:
        extract_best_fitness(sys.argv[1])
