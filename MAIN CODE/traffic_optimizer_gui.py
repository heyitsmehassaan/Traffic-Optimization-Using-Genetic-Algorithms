import tkinter as tk
from tkinter import ttk
import random
import time
from typing import List
import threading
from PIL import Image, ImageTk
from simple_traffic_optimizer import SimpleTrafficOptimizer
import math

class Car:
    def __init__(self, canvas, x, y, direction, lane, intersection_id):
        self.canvas = canvas
        self.size = 15
        self.direction = direction
        self.lane = lane
        self.intersection_id = intersection_id
        self.passed_intersection = False
        
        # Minimum spacing between cars
        self.min_spacing = 30
        
        if direction == 'NS':
            points = self.create_car_points(x, y, vertical=True)
            color = 'blue'
        else:
            points = self.create_car_points(x, y, vertical=False)
            color = 'red'
            
        self.shape = canvas.create_polygon(points, fill=color, outline='black')
        
        self.x = x
        self.y = y
        self.speed = 4  # Increased speed
        self.waiting = False
        self.stop_line = None
        self.stuck_time = 0  # Add stuck time counter

    def create_car_points(self, x, y, vertical=True):
        if vertical:
            # Car pointing down
            points = [
                x - self.size/2, y - self.size/2,  # Left top
                x + self.size/2, y - self.size/2,  # Right top
                x + self.size/2, y + self.size/2,  # Right bottom
                x, y + self.size,                  # Bottom point
                x - self.size/2, y + self.size/2   # Left bottom
            ]
        else:
            # Car pointing right
            points = [
                x - self.size/2, y - self.size/2,  # Left top
                x + self.size, y,                  # Right point
                x - self.size/2, y + self.size/2   # Left bottom
            ]
        return points

    def set_stop_line(self, x, y):
        if self.direction == 'NS':
            self.stop_line = y - 20 if self.lane == 'incoming' else y + 20
        else:
            self.stop_line = x - 20 if self.lane == 'incoming' else x + 20

    def move(self, light_state, other_cars):
        # Reset stuck counter if moving
        if not self.waiting:
            self.stuck_time = 0
            
        should_stop = light_state != 'GREEN' and not self.passed_intersection
        
        # Check for collision with other cars
        too_close = False
        for car in other_cars:
            if car != self and not car.passed_intersection:
                if self.would_collide(car):
                    too_close = True
                    break
        
        if self.direction == 'NS':
            if (should_stop and self.y + self.speed >= self.stop_line) or too_close:
                self.waiting = True
                self.stuck_time += 1
                return self.stuck_time < 200  # Remove if stuck too long
            
            if light_state == 'GREEN':
                self.waiting = False
            
            if not self.waiting:
                self.y += self.speed
                self.canvas.move(self.shape, 0, self.speed)
                
                if self.y > self.stop_line:
                    self.passed_intersection = True
                
                if self.y > self.stop_line + 80:  # Increased removal distance
                    return False
                
        else:  # EW
            if (should_stop and self.x + self.speed >= self.stop_line) or too_close:
                self.waiting = True
                self.stuck_time += 1
                return self.stuck_time < 200  # Remove if stuck too long
            
            if light_state == 'GREEN':
                self.waiting = False
            
            if not self.waiting:
                self.x += self.speed
                self.canvas.move(self.shape, self.speed, 0)
                
                if self.x > self.stop_line:
                    self.passed_intersection = True
                
                if self.x > self.stop_line + 80:  # Increased removal distance
                    return False
        
        return True

    def check_bounds(self):
        coords = self.canvas.coords(self.shape)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if (min(coords[::2]) > canvas_width or max(coords[::2]) < 0 or
            min(coords[1::2]) > canvas_height or max(coords[1::2]) < 0):
            self.canvas.delete(self.shape)
            return False
        return True

    def would_collide(self, other_car):
        if self.direction != other_car.direction:
            return False
            
        if self.direction == 'NS':
            # More strict collision detection for NS traffic
            return (abs(self.y - other_car.y) < self.min_spacing * 1.2 and 
                   abs(self.x - other_car.x) < self.size)
        else:
            # More strict collision detection for EW traffic
            return (abs(self.x - other_car.x) < self.min_spacing * 1.2 and 
                   abs(self.y - other_car.y) < self.size)

class IntersectionDisplay:
    def __init__(self, canvas, x, y, size=200, intersection_id=0):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.size = size
        self.intersection_id = intersection_id
        self.cars = []
        
        # Add timing variables
        self.current_phase = 0
        self.phase_time = 0
        self.timings = {
            'NS': [30, 3, 30],  # Green, Yellow, Red
            'EW': [30, 3, 30]   # Green, Yellow, Red
        }
        
        self.draw_intersection()
        self.draw_stop_lines()
        
        # Initialize traffic lights
        self.lights = {
            'NS': self.canvas.create_rectangle(
                x + size/2 - 15, y - 15,
                x + size/2 + 15, y + 15,
                fill='red'
            ),
            'EW': self.canvas.create_rectangle(
                x - 15, y + size/2 - 15,
                x + 15, y + size/2 + 15,
                fill='red'
            )
        }
        
        self.queue_displays = {
            'NS': self.canvas.create_text(
                x + size/2 + 30, y,
                text="NS: 0"
            ),
            'EW': self.canvas.create_text(
                x, y + size/2 + 30,
                text="EW: 0"
            )
        }
        
        # Add timing display
        self.timing_display = self.canvas.create_text(
            x, y - size/4,
            text="NS: G:30 Y:3 R:30\nEW: G:30 Y:3 R:30",
            anchor='center'
        )
        
        self.last_spawn_time = {'NS': 0, 'EW': 0}
        self.spawn_cooldown = 20  # Frames between spawn attempts

    def draw_intersection(self):
        # Road
        self.canvas.create_rectangle(
            self.x + self.size/2 - 20, self.y - self.size/2,
            self.x + self.size/2 + 20, self.y + self.size/2,
            fill='gray'
        )
        self.canvas.create_rectangle(
            self.x - self.size/2, self.y + self.size/2 - 20,
            self.x + self.size/2, self.y + self.size/2 + 20,
            fill='gray'
        )

    def draw_stop_lines(self):
        # North stop line
        self.canvas.create_line(
            self.x + self.size/2 - 20, self.y - 20,
            self.x + self.size/2 + 20, self.y - 20,
            fill='white', width=2
        )
        # South stop line
        self.canvas.create_line(
            self.x + self.size/2 - 20, self.y + 20,
            self.x + self.size/2 + 20, self.y + 20,
            fill='white', width=2
        )
        # East stop line
        self.canvas.create_line(
            self.x - 20, self.y + self.size/2 - 20,
            self.x - 20, self.y + self.size/2 + 20,
            fill='white', width=2
        )
        # West stop line
        self.canvas.create_line(
            self.x + 20, self.y + self.size/2 - 20,
            self.x + 20, self.y + self.size/2 + 20,
            fill='white', width=2
        )

    def update_lights(self, ns_state, ew_state):
        self.canvas.itemconfig(self.lights['NS'], fill=ns_state.lower())
        self.canvas.itemconfig(self.lights['EW'], fill=ew_state.lower())

    def update_queues(self, ns_queue, ew_queue):
        self.canvas.itemconfig(self.queue_displays['NS'], text=f"NS: {ns_queue}")
        self.canvas.itemconfig(self.queue_displays['EW'], text=f"EW: {ew_queue}")

    def update_timing(self, timing_text):
        self.canvas.itemconfig(self.timing_display, text=timing_text)

    def add_car(self, direction):
        # Add spacing check before creating new car
        if direction == 'NS':
            x = self.x + self.size/2
            y = self.y - self.size/2 - 40  # Increased starting distance
            
            # Check for existing cars in spawn area
            if any(car.direction == 'NS' and abs(car.y - y) < self.size * 1.5 
                  for car in self.cars):
                return
                
        else:
            x = self.x - self.size/2 - 40  # Increased starting distance
            y = self.y + self.size/2
            
            # Check for existing cars in spawn area
            if any(car.direction == 'EW' and abs(car.x - x) < self.size * 1.5 
                  for car in self.cars):
                return
        
        car = Car(self.canvas, x, y, direction, 'incoming', self.intersection_id)
        car.set_stop_line(self.x, self.y)
        self.cars.append(car)

    def update_cars(self, ns_state, ew_state):
        current_time = time.time() * 1000
        
        # Add new cars with strict spacing control
        if len(self.cars) < 10:  # Reduced max cars for better control
            # Check NS direction with strict spacing
            if (current_time - self.last_spawn_time['NS'] > self.spawn_cooldown and 
                random.random() < 0.12):
                if not any(car.direction == 'NS' and 
                          abs(car.y - (self.y - self.size/2)) < self.size 
                          for car in self.cars):
                    self.add_car('NS')
                    self.last_spawn_time['NS'] = current_time
            
            # Check EW direction with strict spacing
            if (current_time - self.last_spawn_time['EW'] > self.spawn_cooldown and 
                random.random() < 0.12):
                if not any(car.direction == 'EW' and 
                          abs(car.x - (self.x - self.size/2)) < self.size 
                          for car in self.cars):
                    self.add_car('EW')
                    self.last_spawn_time['EW'] = current_time
        
        # Update existing cars with collision prevention
        remaining_cars = []
        for car in self.cars:
            # Check if car can move without collision
            can_move = True
            for other_car in self.cars:
                if car != other_car and car.would_collide(other_car):
                    if not car.waiting:  # Only set waiting if not already waiting
                        car.waiting = True
                    can_move = False
                    break
            
            if can_move:
                car.waiting = False
            
            if car.move(ns_state if car.direction == 'NS' else ew_state, self.cars):
                remaining_cars.append(car)
            else:
                self.canvas.delete(car.shape)
        
        self.cars = remaining_cars
        
        # Update queue displays
        ns_queue = len([car for car in self.cars if car.direction == 'NS' and car.waiting])
        ew_queue = len([car for car in self.cars if car.direction == 'EW' and car.waiting])
        
        self.canvas.itemconfig(self.queue_displays['NS'], text=f"NS: {ns_queue}")
        self.canvas.itemconfig(self.queue_displays['EW'], text=f"EW: {ew_queue}")

    def can_add_car(self, direction):
        # Implementation of can_add_car method
        pass

    def update_timings(self, new_timings):
        if len(new_timings) >= 6:
            self.timings['NS'] = new_timings[0:3]
            self.timings['EW'] = new_timings[3:6]
            self.update_timing_display()

    def update_timing_display(self):
        text = f"NS: G:{self.timings['NS'][0]} Y:{self.timings['NS'][1]} R:{self.timings['NS'][2]}\n"
        text += f"EW: G:{self.timings['EW'][0]} Y:{self.timings['EW'][1]} R:{self.timings['EW'][2]}"
        self.canvas.itemconfig(self.timing_display, text=text)

    def update(self):
        self.phase_time += 1
        ns_state = self.get_light_state('NS')
        ew_state = self.get_light_state('EW')
        
        self.update_lights(ns_state, ew_state)
        self.update_cars(ns_state, ew_state)
        
        # Reset phase time if cycle complete
        total_cycle_time = sum(self.timings['NS'])
        if self.phase_time >= total_cycle_time:
            self.phase_time = 0
            self.current_phase = (self.current_phase + 1) % 2

    def get_light_state(self, direction):
        cycle_time = self.phase_time % sum(self.timings[direction])
        timings = self.timings[direction]
        
        if direction == 'NS':
            phase_offset = 0
        else:
            phase_offset = sum(self.timings['NS']) // 2
        
        adjusted_time = (cycle_time + phase_offset) % sum(timings)
        
        if adjusted_time < timings[0]:
            return 'GREEN'
        elif adjusted_time < timings[0] + timings[1]:
            return 'YELLOW'
        else:
            return 'RED'

    def get_queue_lengths(self):
        ns_queue = len([car for car in self.cars if car.direction == 'NS' and car.waiting])
        ew_queue = len([car for car in self.cars if car.direction == 'EW' and car.waiting])
        return [ns_queue, ew_queue]

class TrafficSimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Traffic Light Optimizer")
        self.root.geometry("1200x800")
        
        # Initialize optimizer
        self.optimizer = SimpleTrafficOptimizer()
        self.is_running = False
        
        # Initialize parameter variables
        self.param_vars = {
            "num_intersections": tk.StringVar(value="4"),
            "population_size": tk.StringVar(value="30"),
            "generations": tk.StringVar(value="50"),
            "mutation_rate": tk.StringVar(value="0.1"),
            "crossover_rate": tk.StringVar(value="0.8")
        }
        
        # Create main container with description
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Add description at the top
        self.add_description()
        
        # Create horizontal layout
        self.horizontal_container = ttk.Frame(self.main_container)
        self.horizontal_container.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Setup main components
        self.setup_control_panel()
        self.setup_visualization()

    def add_description(self):
        desc_frame = ttk.LabelFrame(self.main_container, text="How It Works", padding="10")
        desc_frame.pack(fill=tk.X, pady=(0, 10))
        
        description = """
        This simulator optimizes traffic light timings using a genetic algorithm.
        
        Color Guide:
        • Blue cars: North-South traffic
        • Red cars: East-West traffic
        • Traffic Light Colors: Red, Yellow, Green
        
        Queue Numbers:
        • NS: Number of cars waiting in North-South direction
        • EW: Number of cars waiting in East-West direction
        
        The algorithm tries to minimize total waiting time across all intersections.
        """
        
        ttk.Label(desc_frame, text=description, justify=tk.LEFT).pack()

    def setup_control_panel(self):
        self.control_frame = ttk.LabelFrame(self.horizontal_container, text="Control Panel", padding="10")
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Parameters frame
        params_frame = ttk.LabelFrame(self.control_frame, text="Simulation Parameters", padding="10")
        params_frame.pack(fill=tk.X, pady=5)
        
        param_descriptions = {
            "num_intersections": "Number of intersections to optimize",
            "population_size": "Number of solutions per generation",
            "generations": "Number of generations to run",
            "mutation_rate": "Probability of random changes (0-1)",
            "crossover_rate": "Probability of combining solutions (0-1)"
        }
        
        for var_name, description in param_descriptions.items():
            frame = ttk.Frame(params_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=f"{var_name.replace('_', ' ').title()}:").pack(side=tk.LEFT)
            ttk.Entry(frame, textvariable=self.param_vars[var_name], width=10).pack(side=tk.LEFT, padx=5)
            ttk.Label(frame, text=description, font=('Helvetica', 8)).pack(side=tk.LEFT)
        
        # Statistics frame
        self.stats_frame = ttk.LabelFrame(self.control_frame, text="Real-time Statistics", padding="10")
        self.stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_labels = {
            'generation': ttk.Label(self.stats_frame, text="Generation: 0"),
            'fitness': ttk.Label(self.stats_frame, text="Best Fitness: 0"),
            'current_waiting': ttk.Label(self.stats_frame, text="Current Waiting Time: 0")
        }
        
        for label in self.stats_labels.values():
            label.pack(anchor=tk.W, pady=2)
        
        # Control buttons
        buttons_frame = ttk.Frame(self.control_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(buttons_frame, text="Start Optimization", 
                  command=self.start_optimization).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Stop", 
                  command=self.stop_optimization).pack(side=tk.LEFT)

    def setup_visualization(self):
        viz_container = ttk.LabelFrame(self.horizontal_container, text="Traffic Simulation", padding="10")
        viz_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # Add scrollbars
        h_scrollbar = ttk.Scrollbar(viz_container, orient=tk.HORIZONTAL)
        v_scrollbar = ttk.Scrollbar(viz_container, orient=tk.VERTICAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create canvas with scrollbars
        self.canvas = tk.Canvas(viz_container, 
                              width=1000, 
                              height=800,
                              bg='white',
                              xscrollcommand=h_scrollbar.set,
                              yscrollcommand=v_scrollbar.set,
                              scrollregion=(0, 0, 1500, 1200))  # Increased scroll region
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        h_scrollbar.config(command=self.canvas.xview)
        v_scrollbar.config(command=self.canvas.yview)
        
        # Bind mouse wheel
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<Shift-MouseWheel>', self._on_shift_mousewheel)
        
        self.intersections = []
        self.create_intersection_grid()

    def _on_mousewheel(self, event):
        # Vertical scrolling
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mousewheel(self, event):
        # Horizontal scrolling
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_intersection_grid(self):
        num_intersections = int(self.param_vars["num_intersections"].get())
        grid_size = math.ceil(math.sqrt(num_intersections))
        
        # Increased spacing between intersections
        spacing_x = 400  # Increased from 300
        spacing_y = 350  # Increased from 250
        start_x = 200    # Adjusted starting position
        start_y = 150    # Adjusted starting position
        
        # Create intersections in a grid
        intersection_id = 0
        for row in range(grid_size):
            for col in range(grid_size):
                if intersection_id >= num_intersections:
                    break
                    
                x = start_x + col * spacing_x
                y = start_y + row * spacing_y
                
                intersection = IntersectionDisplay(self.canvas, x, y, 
                                                intersection_id=intersection_id)
                self.intersections.append(intersection)
                intersection_id += 1

    def update_gui(self, generation, best_fitness, current_state):
        if not self.is_running:
            return False
            
        try:
            # Update statistics
            if generation >= 0:
                self.stats_labels['generation'].config(text=f"Generation: {generation}")
            self.stats_labels['fitness'].config(text=f"Best Fitness: {-best_fitness:.2f}")
            
            # Calculate current waiting time
            current_waiting = sum(sum(lengths) for lengths in 
                                (intersection.get_queue_lengths() 
                                 for intersection in self.intersections))
            self.stats_labels['current_waiting'].config(
                text=f"Current Waiting Time: {current_waiting}")
            
            # Update each intersection
            for intersection in self.intersections:
                intersection.update()
            
            self.root.update()
            time.sleep(0.05)  # Small delay for visualization
            return True
            
        except Exception as e:
            print(f"GUI update error: {e}")
            return False
    
    def start_optimization(self):
        if not self.is_running:
            self.is_running = True
            self.canvas.delete("all")  # Clear the canvas
            self.create_intersection_grid()  # Create new grid
            
            # Update optimizer parameters
            try:
                self.optimizer.num_intersections = int(self.param_vars["num_intersections"].get())
                self.optimizer.population_size = int(self.param_vars["population_size"].get())
                self.optimizer.num_generations = int(self.param_vars["generations"].get())
                self.optimizer.mutation_rate = float(self.param_vars["mutation_rate"].get())
                self.optimizer.crossover_rate = float(self.param_vars["crossover_rate"].get())
                
                # Start optimization in a new thread
                threading.Thread(target=self.run_optimization, daemon=True).start()
            except Exception as e:
                print(f"Start optimization error: {e}")
                self.is_running = False
    
    def stop_optimization(self):
        self.is_running = False
    
    def run_optimization(self):
        try:
            best_solution, best_fitness = self.optimizer.optimize(
                gui_callback=self.update_gui)
            
            if self.is_running:
                # Update final timings
                for i, intersection in enumerate(self.intersections):
                    base_idx = i * 6
                    intersection.update_timings(
                        best_solution[base_idx:base_idx + 6])
                
                self.show_final_results(best_solution, best_fitness)
        except Exception as e:
            print(f"Optimization error: {e}")
            self.is_running = False
    
    def show_final_results(self, best_solution, best_fitness):
        results = tk.Toplevel(self.root)
        results.title("Optimization Results")
        results.geometry("400x600")
        
        ttk.Label(results, text="Final Results", 
                 font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        ttk.Label(results, 
                 text=f"Best Fitness: {-best_fitness:.2f}").pack()
        
        for i in range(self.optimizer.num_intersections):
            base_idx = i * 6
            frame = ttk.LabelFrame(results, text=f"Intersection {i+1}")
            frame.pack(pady=5, padx=10, fill=tk.X)
            
            # North-South timing
            ttk.Label(frame, text="North-South:").pack()
            ttk.Label(frame, 
                     text=f"Green: {best_solution[base_idx]} sec").pack()
            ttk.Label(frame, 
                     text=f"Yellow: {best_solution[base_idx + 1]} sec").pack()
            ttk.Label(frame, 
                     text=f"Red: {best_solution[base_idx + 2]} sec").pack()
            
            # East-West timing
            ttk.Label(frame, text="East-West:").pack()
            ttk.Label(frame, 
                     text=f"Green: {best_solution[base_idx + 3]} sec").pack()
            ttk.Label(frame, 
                     text=f"Yellow: {best_solution[base_idx + 4]} sec").pack()
            ttk.Label(frame, 
                     text=f"Red: {best_solution[base_idx + 5]} sec").pack()

def main():
    root = tk.Tk()
    app = TrafficSimulatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 