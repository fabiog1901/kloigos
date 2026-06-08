def to_cpu_set(cpu_range: str) -> str:
    """
    Returns the CPU set represented by cpu_range.

    Examples:
      "0-3" -> "0,1,2,3"
      "0-7:2" -> "0,2,4,6"
    """
    start, end, step = parse_cpu_range(cpu_range)
    return ",".join(str(x) for x in range(start, end + 1, step))


def parse_cpu_range(cpu_range: str) -> tuple[int, int, int]:
    """Parse start-end[:step], where step defaults to 1."""
    raw = cpu_range.strip()
    if not raw:
        raise ValueError("cpu_range is empty")

    step = 1
    if ":" in raw:
        raw, raw_step = raw.split(":", 1)
        step = int(raw_step)
        if step <= 0:
            raise ValueError(f"Invalid step: {step} in {cpu_range}")

    if "-" not in raw:
        start = end = int(raw)
        return start, end, step

    raw_start, raw_end = raw.split("-", 1)
    start, end = int(raw_start), int(raw_end)
    if end < start:
        raise ValueError(f"Invalid cpu_range (end < start): {cpu_range}")

    return start, end, step
