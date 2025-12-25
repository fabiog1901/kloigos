SQLITE_DB = "kloigos.sqlite"
# range_size dictates how many ports are allocated per each compute_unit
RANGE_SIZE = 200

# the last CPU ID of the compute unit dictates what ports_range the unit receives.
# For example, if the cpus are 0,2, we look up 2 in the map to find the start port range is 2400
# then the range is 2400-(2400 + RANGE_SIZE).
# This ensure that there are no ports overlapping even on very large servers
# This is what the mapping looks like:
# {
#     '0': 2000,
#     '1': 2200,
#     '2': 2400,
#     ...,
#     '254': 52800,
#     '255': 53000
# }
CPU_PORTS_MAP = {f"{k}": 2000 + i * RANGE_SIZE for i, k in enumerate(range(256))}
