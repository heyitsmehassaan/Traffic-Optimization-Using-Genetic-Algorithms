import random
from typing import List, Dict, Callable
import time

class SimpleTrafficOptimizer:
    def __init__(self):
        # Simulation parameters
        self.num_intersections = 4
        self.simulation_time = 100
        self.max_cars = 50
        
        # Traffic Light Timing Constraints
        self.min_green_time = 20
        self.max_green_time = 60
        self.min_yellow_time = 3
        self.max_yellow_time = 5
        self.min_red_time = 20
        self.max_red_time = 60

        # Genetic Algorithm parameters
        self.population_size = 30
        self.num_generations = 50
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8
        self.elite_size = 2

    class TrafficLight:
        def __init__(self, id):
            self.id = id
            self.queue_ns = 0
            self.queue_ew = 0
            self.state_ns = "RED"
            self.state_ew = "RED"
            self.ns_timing = [30, 3, 30]  # Default timing [green, yellow, red]
            self.ew_timing = [30, 3, 30]
            self.waiting_time_ns = 0
            self.waiting_time_ew = 0
            self.phase_time = 0

        def update(self) -> float:
            # Update phase time
            self.phase_time += 1
            
            # Calculate light states based on timing
            ns_cycle = self.phase_time % sum(self.ns_timing)
            ew_cycle = (self.phase_time + sum(self.ns_timing) // 2) % sum(self.ew_timing)
            
            # Update NS state
            if ns_cycle < self.ns_timing[0]:
                self.state_ns = "GREEN"
            elif ns_cycle < self.ns_timing[0] + self.ns_timing[1]:
                self.state_ns = "YELLOW"
            else:
                self.state_ns = "RED"
                
            # Update EW state
            if ew_cycle < self.ew_timing[0]:
                self.state_ew = "GREEN"
            elif ew_cycle < self.ew_timing[0] + self.ew_timing[1]:
                self.state_ew = "YELLOW"
            else:
                self.state_ew = "RED"
            
            # Generate random traffic
            new_cars_ns = random.randint(0, 3)
            new_cars_ew = random.randint(0, 3)
            
            # Add new cars to queues
            self.queue_ns += new_cars_ns
            self.queue_ew += new_cars_ew
            
            # Process cars based on light states
            if self.state_ns == "GREEN":
                cars_processed = min(3, self.queue_ns)
                self.queue_ns = max(0, self.queue_ns - cars_processed)
            
            if self.state_ew == "GREEN":
                cars_processed = min(3, self.queue_ew)
                self.queue_ew = max(0, self.queue_ew - cars_processed)
            
            # Calculate waiting time
            waiting_time = self.queue_ns + self.queue_ew
            
            return waiting_time

        def get_state(self) -> Dict:
            return {
                'ns_state': self.state_ns,
                'ew_state': self.state_ew,
                'queue_ns': self.queue_ns,
                'queue_ew': self.queue_ew,
                'ns_timing': f"{self.ns_timing[0]}/{self.ns_timing[1]}/{self.ns_timing[2]}",
                'ew_timing': f"{self.ew_timing[0]}/{self.ew_timing[1]}/{self.ew_timing[2]}"
            }

    def create_individual(self) -> List[int]:
        timing = []
        for _ in range(self.num_intersections):
            # North-South timings
            timing.extend([
                random.randint(self.min_green_time, self.max_green_time),
                random.randint(self.min_yellow_time, self.max_yellow_time),
                random.randint(self.min_red_time, self.max_red_time)
            ])
            # East-West timings
            timing.extend([
                random.randint(self.min_green_time, self.max_green_time),
                random.randint(self.min_yellow_time, self.max_yellow_time),
                random.randint(self.min_red_time, self.max_red_time)
            ])
        return timing

    def get_light_state(self, cycle_time: int, green_time: int, yellow_time: int, red_time: int) -> str:
        if cycle_time < green_time:
            return "GREEN"
        elif cycle_time < green_time + yellow_time:
            return "YELLOW"
        else:
            return "RED"

    def simulate_traffic(self, timing: List[int], gui_callback: Callable = None) -> float:
        lights = [self.TrafficLight(i) for i in range(self.num_intersections)]
        total_waiting_time = 0
        
        for t in range(self.simulation_time):
            current_state = []
            for i, light in enumerate(lights):
                base_idx = i * 6
                light.ns_timing = timing[base_idx:base_idx + 3]
                light.ew_timing = timing[base_idx + 3:base_idx + 6]
                
                # Update light states based on timing
                waiting_time = light.update()
                total_waiting_time += waiting_time
                current_state.append(light.get_state())
            
            if gui_callback and t % 5 == 0:
                if not gui_callback(-1, -total_waiting_time, current_state):
                    return float('-inf')
        
        return -total_waiting_time

    def optimize(self, gui_callback: Callable = None) -> tuple:
        # Initialize random population of timing solutions
        population = [self.create_individual() for _ in range(self.population_size)]
        best_solution = None
        best_fitness = float('-inf')
        
        # Main genetic algorithm loop
        for generation in range(self.num_generations):
            fitness_scores = []
            
            # Evaluate fitness of each individual
            for individual in population:
                fitness = self.simulate_traffic(individual, gui_callback)
                fitness_scores.append(fitness)
                
                # Track best solution found so far
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_solution = individual.copy()
            
            # Update GUI with generation info
            if gui_callback:
                if not gui_callback(generation, best_fitness, None):
                    break
            
            # Evolution step: Create new population
            new_population = []
            
            # Elitism: Preserve best solutions
            elite_indices = sorted(range(len(fitness_scores)), 
                                key=lambda i: fitness_scores[i], 
                                reverse=True)[:self.elite_size]
            for idx in elite_indices:
                new_population.append(population[idx].copy())
            
            # Create rest of population through selection, crossover, mutation
            while len(new_population) < self.population_size:
                parent1, parent2 = self.select_parents(population, fitness_scores)
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                new_population.append(child)
            
            population = new_population
            
            # Print progress
            print(f"Generation {generation}: Best Fitness = {best_fitness}")
        
        return best_solution, best_fitness

    def select_parents(self, population: List[List[int]], fitness_scores: List[float]) -> tuple:
        # Tournament selection
        tournament_size = 3
        # Select random candidates for two tournaments
        tournament_1 = random.sample(list(enumerate(fitness_scores)), tournament_size)
        tournament_2 = random.sample(list(enumerate(fitness_scores)), tournament_size)
        
        # Choose winners based on highest fitness
        parent1_idx = max(tournament_1, key=lambda x: x[1])[0]
        parent2_idx = max(tournament_2, key=lambda x: x[1])[0]
        
        return population[parent1_idx], population[parent2_idx]

    def crossover(self, parent1: List[int], parent2: List[int]) -> List[int]:
        # Skip crossover based on crossover rate
        if random.random() > self.crossover_rate:
            return parent1.copy()
        
        # Perform intersection-wise crossover
        child = []
        for i in range(0, len(parent1), 6):  # 6 values per intersection
            # Randomly choose timing values from either parent
            if random.random() < 0.5:
                child.extend(parent1[i:i+6])
            else:
                child.extend(parent2[i:i+6])
        return child

    def mutate(self, individual: List[int]) -> List[int]:
        # Attempt mutation on each timing value
        for i in range(len(individual)):
            if random.random() < self.mutation_rate:
                # Apply appropriate constraints based on timing type
                if i % 6 in [0, 3]:  # Green times
                    individual[i] = random.randint(self.min_green_time, self.max_green_time)
                elif i % 6 in [1, 4]:  # Yellow times
                    individual[i] = random.randint(self.min_yellow_time, self.max_yellow_time)
                else:  # Red times
                    individual[i] = random.randint(self.min_red_time, self.max_red_time)
        return individual