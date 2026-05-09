import random

# remove all zeros
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
    
    # fallback
    return rebuild_routes(child, demand, capacity)
