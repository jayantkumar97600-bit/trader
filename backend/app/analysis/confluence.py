from typing import Any


def _direction_to_bias(direction: str | None) -> str:
    if direction == "LONG":
        return "BULLISH"

    if direction == "SHORT":
        return "BEARISH"

    return "NEUTRAL"


def _structure_direction(structure: dict[str, Any]) -> str:
    bias = structure.get("bias", "NEUTRAL")

    if bias in ("BULLISH", "BEARISH"):
        return bias

    return "NEUTRAL"


def _recent_sweep(liquidity: dict[str, Any]):
    sweeps = liquidity.get("sweeps", [])

    if not sweeps:
        return None

    return sweeps[-1]


def analyze_confluence(
    structures: dict[str, dict[str, Any]],
    liquidity: dict[str, Any],
    timeframe: str = "15m",
):
    """
    Deterministic Structure + Liquidity Confluence Engine.

    No prediction is made here.

    The engine only combines verified observations:
        - timeframe structure
        - liquidity location
        - confirmed liquidity sweeps

    Output is evidence, not probability.
    """

    if not structures:
        return {
            "bias": "NEUTRAL",
            "status": "CONFLICTED",
            "score": 0,
            "evidence": [],
            "warnings": ["No structure data available."],
        }

    # ---------------------------------------------------------
    # STRUCTURE BIASES
    # ---------------------------------------------------------

    structure_biases = {}

    for tf, structure in structures.items():
        if structure is None:
            continue

        structure_biases[tf] = _structure_direction(
            structure
        )

    bullish_count = sum(
        x == "BULLISH"
        for x in structure_biases.values()
    )

    bearish_count = sum(
        x == "BEARISH"
        for x in structure_biases.values()
    )

    # ---------------------------------------------------------
    # STRUCTURE CONSENSUS
    # ---------------------------------------------------------

    if bullish_count > bearish_count:
        structure_bias = "BULLISH"

    elif bearish_count > bullish_count:
        structure_bias = "BEARISH"

    else:
        structure_bias = "NEUTRAL"

    # ---------------------------------------------------------
    # LIQUIDITY
    # ---------------------------------------------------------

    recent_sweep = _recent_sweep(
        liquidity
    )

    sweep_bias = "NEUTRAL"

    if recent_sweep:
        sweep_bias = recent_sweep.get(
            "direction",
            "NEUTRAL"
        )

    # ---------------------------------------------------------
    # CONFLUENCE SCORING
    # ---------------------------------------------------------

    score = 0

    evidence = []

    warnings = []

    # Higher-timeframe structure.
    htf_frames = [
        tf for tf in ("4h", "1h")
        if tf in structure_biases
    ]

    htf_bullish = sum(
        structure_biases[tf] == "BULLISH"
        for tf in htf_frames
    )

    htf_bearish = sum(
        structure_biases[tf] == "BEARISH"
        for tf in htf_frames
    )

    if htf_bullish > htf_bearish:
        score += 25

        evidence.append(
            "Higher-timeframe structure is bullish."
        )

    elif htf_bearish > htf_bullish:
        score += 25

        evidence.append(
            "Higher-timeframe structure is bearish."
        )

    else:
        warnings.append(
            "Higher-timeframe structure is conflicted."
        )

    # ---------------------------------------------------------
    # SELECTED TIMEFRAME STRUCTURE
    # ---------------------------------------------------------

    selected_structure = structures.get(
        timeframe
    )

    selected_bias = (
        _structure_direction(
            selected_structure
        )
        if selected_structure
        else "NEUTRAL"
    )

    if selected_bias == structure_bias:
        score += 20

        evidence.append(
            f"{timeframe} structure agrees with "
            f"the broader structural bias."
        )

    elif selected_bias != "NEUTRAL":
        warnings.append(
            f"{timeframe} structure conflicts with "
            f"the broader structural bias."
        )

    # ---------------------------------------------------------
    # LIQUIDITY SWEEP
    # ---------------------------------------------------------

    if recent_sweep:

        if sweep_bias == structure_bias:

            score += 30

            evidence.append(
                "Recent confirmed liquidity sweep "
                "agrees with structure."
            )

        else:

            score += 5

            warnings.append(
                "Recent liquidity sweep conflicts "
                "with structural bias."
            )

    else:

        warnings.append(
            "No confirmed recent liquidity sweep."
        )

    # ---------------------------------------------------------
    # BOS / CHoCH
    # ---------------------------------------------------------

    if selected_structure:

        bos = selected_structure.get(
            "bos",
            []
        )

        choch = selected_structure.get(
            "choch",
            []
        )

        if bos:

            latest_bos = bos[-1]

            bos_direction = latest_bos.get(
                "direction",
                "NEUTRAL"
            )

            if bos_direction == structure_bias:

                score += 15

                evidence.append(
                    f"Latest {timeframe} BOS agrees "
                    "with structural bias."
                )

        if choch:

            latest_choch = choch[-1]

            choch_direction = latest_choch.get(
                "direction",
                "NEUTRAL"
            )

            if choch_direction == structure_bias:

                score += 10

                evidence.append(
                    f"Latest {timeframe} CHoCH agrees "
                    "with structural bias."
                )

    # ---------------------------------------------------------
    # FINAL BIAS
    # ---------------------------------------------------------

    if structure_bias == "BULLISH":
        final_bias = "BULLISH"

    elif structure_bias == "BEARISH":
        final_bias = "BEARISH"

    else:
        final_bias = "NEUTRAL"

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    if final_bias == "NEUTRAL":

        status = "CONFLICTED"

    elif score >= 70:

        status = "STRONG_CONFLUENCE"

    elif score >= 50:

        status = "PARTIAL_CONFLUENCE"

    else:

        status = "WEAK_CONFLUENCE"

    # ---------------------------------------------------------
    # FINAL OUTPUT
    # ---------------------------------------------------------

    return {
        "bias": final_bias,

        "status": status,

        "score": min(score, 100),

        "structure_bias": structure_bias,

        "structure_timeframes": structure_biases,

        "liquidity_sweep": recent_sweep,

        "evidence": evidence,

        "warnings": warnings,

        "methodology": {
            "type":
                "Deterministic evidence combination",

            "score_meaning":
                "Confluence evidence score, not win probability",

            "liquidity":
                "Confirmed sweep only",

            "structure":
                "Confirmed swing structure",

            "prediction":
                "None",
        },
    }