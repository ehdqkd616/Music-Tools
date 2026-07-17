import secrets


def new_id(prefix: str, n_bytes: int = 6) -> str:
    """§8 style IDs: med_a1b2c3, job_x7y8z9."""
    return f"{prefix}_{secrets.token_hex(n_bytes)}"
