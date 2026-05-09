import random

import numpy as np
import math
from numpy.matrixlib.defmatrix import matrix
from pandas.io.pytables import Selection



# ======================================INPUT=============================================
def get_float(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("  ⚠  Please enter a valid number.")


def get_int(prompt, min_val=None, max_val=None):
    while True:
        try:
            val = int(input(prompt))
            if min_val is not None and val < min_val:
                print(f"  ⚠  Must be at least {min_val}.")
            elif max_val is not None and val > max_val:
                print(f"  ⚠  Must be at most {max_val}.")
            else:
                return val
        except ValueError:
            print("  ⚠  Please enter a whole number.")


[3, 1, 4, 0, 5, 2, 0, 6, 0]
# Route 1: depot → 3 → 1 → 4 → depot
# Route 2: depot → 5 → 2 → depot
# Route 3: depot → 6 → depot


# ======================================GRAPH=============================================
#graphs 🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿🗿
def CreateGraph(): # DONE ✅
    depotx = get_float("Enter the X of the depot: ")
    depoty = get_float("Enter the Y of the depot: ")
    nodes = [(depotx, depoty)]
    num_customer = get_int("Enter number of customers: ")

    choice = input("Enter 1 if you are too lazy enough to move inches to enter the input else enter what ever: ")

    if choice == '1':
        ranges = get_int("At least enter a range in positive : ")
        ranges = abs(ranges) # you might be stupid so just in case
        for i in range(num_customer):
            x = random.randint(ranges * -1, ranges)
            y = random.randint(ranges * -1, ranges)
            nodes.append((x, y))
    else:
        for i in range(num_customer):
            x = get_float("Enter the X of the customer {i + 1}: ")
            y = get_float("Enter the Y of the customer {i + 1}: ")
            nodes.append((x, y))
    n = len(nodes)

    #using numpy to make the matrix
    matrix_graph =  np.zeros((n,n))
    #calculate the weight which is the distance
    for i in range(n):
        for j in range(n):
            dx = nodes[i][0] - nodes[j][0]
            dy = nodes[i][1] - nodes[j][1]
            matrix_graph[i][j] = (dx**2 + dy**2) ** 0.5
    return num_customer , matrix_graph


def GetCustomerDemand(numberOfCustomers):
    listDemand = []
    totalDemand = 0
    maxDemand = -1
    listDemand.append(0)
    for i in range(1, numberOfCustomers + 1):
        temp = get_int(f"Enter Customer ({i}) demand: ", 1)
        maxDemand = max(temp, maxDemand)
        totalDemand += temp
        listDemand.append(temp)
    return listDemand, totalDemand, maxDemand





# ======================================MAKE POP=============================================
#Chromosome 🧬🧬🧬🧬🧬🧬🧬🧬🧬
def chromosome(N_CLIENTS):
    clients_order = list(range(1,N_CLIENTS +1))
    random.shuffle(clients_order)
    return clients_order


def insert_zeros(solution,  demand,  N_VEHICLES,  V_CAPACITY):
    n = N_VEHICLES - 1
    sum = 0
    new_chromosome = []
    route = []
    i = 0
    while i < len(solution) and n > 0:
        curr_demand = demand[solution[i]]                                        # CHANGE
        curr_client = solution[i]

        if sum + curr_demand <= V_CAPACITY:
            new_chromosome.append(curr_client)
            sum += curr_demand
            i += 1
        else:
            sum = 0
            # new_chromosome.extend(route)
            new_chromosome.append(0)
            n -= 1

    if i == len(solution):
        new_chromosome.append(0)
        return new_chromosome

    new_chromosome.extend(solution[i:])
    new_chromosome.append(0)
    return new_chromosome


def final_validation(solution, N_clients):
    sum = 0
    for item in solution:
        if item != 0:
            sum += 1
    return sum == N_clients


# initialization for population #  👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦👨‍👩‍👧‍👦
def initialization_population(pop_size, demand, N_VEHICLES,  V_CAPACITY, customers_num):
    population = []
    size = 0
    while (size != pop_size):
        individual = chromosome(customers_num)
        individual = insert_zeros(individual, demand,  N_VEHICLES,  V_CAPACITY)
        population.append(individual)
        size += 1
    return population




# ======================================FITNESS=============================================
# 🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻🏃🏻
def fitness(chromosome, matrix_graph, demands, vehicle_capacity):

    total_distance = 0
    current_load = 0
    over_load = 0
    prev = 0   # start from depot

    for customer in chromosome:

        if customer == 0:
            total_distance += matrix_graph[prev][0]   # return to depot
            prev = 0
            current_load = 0
            continue

        customer_demand = demands[customer]

        if current_load + customer_demand > vehicle_capacity:
            over_load += 1

        total_distance += matrix_graph[prev][customer]

        current_load += customer_demand
        prev = customer

    if prev != 0:
        total_distance += matrix_graph[prev][0]

    penalty = over_load * 1000   #

    return 1.0 / (total_distance + penalty)







# ======================================SELECTION=============================================
def selection(population, fitness_score, k=3):
    # pick k random indices from the population to compete
    selection_ix = random.sample(range(len(population)), k)

    # get fitness
    def get_fitness(ix):
        return fitness_score[ix]

    # best is an index
    best = max(selection_ix, key=get_fitness)

    # return the individual
    return population[best]





# ======================================CROSS OVER=============================================
def remove_zeros(parent):
    return [gene for gene in parent if gene != 0]


# save zero positions
def get_zero_positions(parent):
    return [i for i, gene in enumerate(parent) if gene == 0]


# restore zeros in saved positions
def restore_zeros(child, zero_positions):
    child_with_zeros = child[:]
    for pos in zero_positions:
        child_with_zeros.insert(pos, 0)
    return child_with_zeros


# validate chromosome
def validate_solution(solution, demand, capacity):
    current_load = 0
    for gene in solution:
        if gene == 0:
            current_load = 0
        else:
            current_load += demand[gene - 1]
            if current_load > capacity:
                return False
    return True


# main order crossover
def order_crossover(parent1, parent2, demand, capacity):
    zero_positions_p1 = get_zero_positions(parent1)
    zero_positions_p2 = get_zero_positions(parent2)
    p1 = remove_zeros(parent1)
    p2 = remove_zeros(parent2)
    size = len(p1)
    start = random.randint(0, size - 2)
    end = random.randint(start + 1, size - 1)
    child = [None] * size
    # copy segment from parent1
    for i in range(start, end + 1):
        child[i] = p1[i]
    # fill remaining from parent2
    p2_index = 0
    for i in range(size):
        if child[i] is None:
            while p2[p2_index] in child:
                p2_index += 1
            child[i] = p2[p2_index]
            p2_index += 1
            # try restoring p1 zero positions
    child_p1 = restore_zeros(child, zero_positions_p1)
    if validate_solution(child_p1, demand, capacity):
        return child_p1
    # try restoring p2 zero positions
    child_p2 = restore_zeros(child, zero_positions_p2)
    if validate_solution(child_p2, demand, capacity):
        return child_p2

    x = random.randint(1, 2)
    if x == 1:
        return child_p1
    else:
        return child_p2








# ======================================MUTATION=============================================
def inversion_mutation(individual, mutation_rate=0.2):
    if random.random() > mutation_rate:
        return individual

    core = individual[
        :-1]  # remove the last zero and work only on the remaining elements # everything except the last zero

    mutated_core = core[:]  # Copy

    if len(mutated_core) < 2:
        return individual

    idx1, idx2 = sorted(random.sample(range(len(mutated_core)), 2))

    mutated_core[idx1:idx2 + 1] = mutated_core[idx1:idx2 + 1][
        ::-1]  # idx1=1 , idx2=3 --> #[0, 2, 3, 1]  --> #→ [2,3,1]
    # [::-1]  reverse the list         --> # [1,3,2]

    return mutated_core + [0]  # add a zero at the end


def mutate_population(population):
    new_population = []
    for individual in population:
        new_individual = inversion_mutation(individual, mutation_rate=0.2)
        new_population.append(new_individual)
    return new_population




