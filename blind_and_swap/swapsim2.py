import copy, sys, random

LOG_LEVEL = [None]
FUNCTION = (lambda: 0).__class__

DEFAULTS = {
    'width': 2048,
    'rounds': 4096,
    'swaps_per_round': 31,
    'log_level': 1,
    'offline_percent': 0 # offline_percent of the validators will be offline and not shuffle
}

def merge_probs(*probs):
    """
    Given two dictionaries with probabilities flatten them into a single one:

    In : merge_probs({0: 0.5, 30: 0.5}, {1: 1})
    Out: {0: 0.25, 30: 0.25, 1: 0.5}
    """

    L = len(probs)
    #if isinstance(probs[0], list):
    #    return [sum(prob[i]) / len(probs)
    o = {}
    for prob in probs:
        for k,v in prob.items():
            o[k] = o.get(k, 0) + v / L
    return o

def simplify_dict(obj):
    o = {}
    for x in sorted(obj.keys(), key=lambda z: obj[z], reverse=True)[:4]:
        o[x] = round(obj[x], 3)
    if sum(o.values()) < 1:
        o['other'] = round(obj[x], 3)
    return o

def log(contents, level):
    if level <= LOG_LEVEL[0]:
        if isinstance(contents, FUNCTION):
            contents = contents()
        print(contents)

def run(width, rounds, swaps_per_round, offline_percent):
    """
    Do a full run of the protocol

    Return a list that contains anonymity set probabilites for each round's proposer.
    """
    extract_positions = [random.randrange(width) for _ in range(rounds + swaps_per_round)]
    extract_offsets = [random.randrange(width//2) * 2 + 1 for _ in range(rounds + swaps_per_round)]
    array = [{i: 1} for i in range(width)]
    output = []
    if bin(width).count('1') != 1:
        raise Exception("Width must be a power of 2")
    if bin(swaps_per_round + 1).count('1') != 1:
        raise Exception("swaps_per_round must be a power of 2 minus 1")
    log_swaps = len(bin(swaps_per_round + 1)) - 3

    for r in range(rounds):
        if r % 500  == 0:
            log("Round {}".format(r), 1)
            # log(" ------ ", 3)

        # Do fault injection (offline shufflers)
        if random.random() < float(offline_percent)/100: # offline 50% of the time
            continue

        # Iterate over each layer of the tree
        for depth in range(log_swaps):
            # Figure out index to shuffle and shuffle offset
            pivot = extract_positions[r - depth - 1]
            offset = extract_offsets[r - depth - 1]
            log("Depth {}: pivot {} offset {}".format(depth, pivot, offset), 2)

            # For each layer of the tree, do the right amount of swaps
            for i in range(2**depth):
                L = (pivot + offset * i) % width
                R = (pivot + offset * (i + 2**depth)) % width
                log("Swapping {} and {}".format(L, R), 2)
                # Merge their probabilities
                new_prob = merge_probs(array[L], array[R])
                array[L] = new_prob
                array[R] = new_prob

        # Add a new element to the shuffling list
        extraction_index = extract_positions[r]
        # Save the probabilities of the proposer to `output`
        output.append(array[extraction_index])
        array[extraction_index] = {width+r: 1}

        log("New index: {}, Index: {}, offset: {}".format(width+r, extraction_index, extract_offsets[r]), 2)
        log(lambda: [simplify_dict(x) for x in array], 3)

    return output

def test(width, rounds, swaps_per_round, offline_percent):
    thresholds = []

    outputs = run(width, rounds, swaps_per_round, offline_percent)

    # Loop over each proposer
    for proposer_probs in outputs:
        # Sort it such that most deanonymized candidates for this proposer sit on top
        top_probs = sorted(proposer_probs.values(), reverse=True)
        await_count = sum(top_probs) * 0.2

        for i in range(len(top_probs)):
            await_count -= top_probs[i]
            # Find the threshold and register the *number of validators* that we need to take offline to have a 20% chance
            if await_count <= 0:
                log("Dealing with proposer (threshold: {}) with the following probs: {}".format(i+1, top_probs), 3)
                thresholds.append(i+1)
                break

    return thresholds

if __name__ == '__main__':
    args = {}
    for x in sys.argv:
        if '=' in x:
            prefix, postfix = x[:x.index('=')], x[x.index('=')+1:]
            args[prefix] = int(postfix)
    for arg, val in DEFAULTS.items():
        if arg not in args:
            print("Arg {} defaulted to {}".format(arg, val))
            args[arg] = val
    LOG_LEVEL[0] = args['log_level']

    # Run the simulation
    thresholds = test(args['width'], args['rounds'], args['swaps_per_round'], args['offline_percent'])

#    for i in range(0, args['rounds'], 10):
#        print("After {} rounds, need to DoS {} validators for 20% chance of killing proposer".format(i, thresholds[i]))
    second_half = thresholds[len(thresholds)//2:]
    print("Params [width: {}, rounds: {}, swaps: {}, offline: {}]".format(args['width'], args['rounds'], args['swaps_per_round'], args['offline_percent']))
    print("Average 20%-diffusion of proposer: {}".format(sum(second_half) / len(second_half)))
    print("Frequency of 20%-diffusion = 1: {}".format(second_half.count(1) / len(second_half)))
