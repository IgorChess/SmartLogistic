from decimal import ROUND_HALF_UP, Decimal


def weight_category(total_weight_t: float) -> str:
    w = Decimal(str(total_weight_t)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if w >= 30:
        return "G20T"
    if w >= 10:
        return "FTL"
    if w >= 5:
        return "10T"
    if w >= Decimal("2.5"):
        return "5T"
    if w >= Decimal("0.5"):
        return "L5T"
    return "OTH"


def volume_category(total_volume_m3: float) -> str:
    return "FTL" if 0 < total_volume_m3 <= 120 else "OTH"


def body_group(std_id: int | None) -> str:
    return {56: "Tent", 4: "Reefer", 2: "Isotherm", 15: "Flatbed"}.get(std_id, "Other")


def parse_region(full_name_local: str | None) -> str | None:
    if not full_name_local or "," not in full_name_local:
        return None
    return full_name_local.split(",", 1)[1].strip() or None
