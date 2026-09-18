from typing import Any


BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _direction_to_bias(direction: str | None) -> str:
    if direction == "LONG":
        return BULLISH
    if direction == "SHORT":
        return BEARISH
    return NEUTRAL


def _opposite(direction: str) -> str:
    if direction == BULLISH:
        return BEARISH
    if direction == BEARISH:
        return BULLISH
    return NEUTRAL


def _structure_bias(structure: dict[str, Any] | None) -> str:
    if not structure:
        return NEUTRAL

    bias = structure.get("bias", NEUTRAL)

    if bias in (BULLISH, BEARISH):
        return bias

    return NEUTRAL


def _latest_sweep(liquidity: dict[str, Any] | None):
    if not liquidity:
        return None

    sweeps = liquidity.get("sweeps", [])

    if not sweeps:
        return None

    return sweeps[-1]


def _get_sweep_direction(sweep: dict[str, Any] | None) -> str:
    if not sweep:
        return NEUTRAL

    direction = sweep.get("direction", NEUTRAL)

    if direction in (BULLISH, BEARISH):
        return direction

    return NEUTRAL


def _get_price_action_direction(
    price_action: dict[str, Any] | None,
) -> str:
    if not price_action:
        return NEUTRAL

    direction = price_action.get("direction", NEUTRAL)

    if direction in (BULLISH, BEARISH):
        return direction

    return NEUTRAL


def _get_sr_context(
    levels: dict[str, Any] | None,
    direction: str,
) -> dict[str, Any]:
    if not levels:
        return {
            "state": "NO_CONTEXT",
            "zone": None,
            "reason": "S/R data unavailable.",
        }

    zones = levels.get("relevant_zones", [])

    if not zones:
        return {
            "state": "NO_CONTEXT",
            "zone": None,
            "reason": "No relevant S/R zone.",
        }

    # For LONG we prefer support.
    # For SHORT we prefer resistance.
    preferred = []

    for zone in zones:
        kind = str(zone.get("kind", "")).upper()

        if direction == BULLISH and kind == "SUPPORT":
            preferred.append(zone)

        elif direction == BEARISH and kind == "RESISTANCE":
            preferred.append(zone)

    if not preferred:
        return {
            "state": "NEUTRAL",
            "zone": None,
            "reason": "Relevant zones exist but no directional S/R context.",
        }

    # Prefer strongest zone.
    preferred.sort(
        key=lambda z: float(z.get("strength", 0)),
        reverse=True,
    )

    zone = preferred[0]

    return {
        "state": "ALIGNED",
        "zone": zone,
        "reason": (
            "Price is interacting with directional "
            "support/resistance context."
        ),
    }


def _structure_event_alignment(
    structure: dict[str, Any] | None,
    direction: str,
) -> dict[str, Any]:
    if not structure:
        return {
            "state": "NO_DATA",
            "score": 0,
            "evidence": [],
        }

    evidence = []
    score = 0

    bos = structure.get("bos", [])
    choch = structure.get("choch", [])

    if bos:
        latest_bos = bos[-1]
        bos_direction = latest_bos.get("direction", NEUTRAL)

        if bos_direction == direction:
            score += 10
            evidence.append(
                f"Latest BOS supports {direction.lower()} structure."
            )

    if choch:
        latest_choch = choch[-1]
        choch_direction = latest_choch.get(
            "direction",
            NEUTRAL,
        )

        if choch_direction == direction:
            score += 5
            evidence.append(
                f"Latest CHoCH supports {direction.lower()} structure."
            )

    return {
        "state": "ALIGNED" if score > 0 else "NEUTRAL",
        "score": score,
        "evidence": evidence,
    }


def analyze_confluence(
    mtf: dict[str, Any] | None,
    structures: dict[str, dict[str, Any]] | None = None,
    liquidity: dict[str, Any] | None = None,
    levels: dict[str, Any] | None = None,
    price_action: dict[str, Any] | None = None,
    timeframe: str = "15m",
) -> dict[str, Any]:

    structures = structures or {}

    if not mtf:
        return {
            "status": "NO TRADE",
            "bias": NEUTRAL,
            "score": 0,
            "evidence": [],
            "warnings": [
                "MTF analysis unavailable."
            ],
        }

    # ---------------------------------------------------------
    # 1. AUTHORITATIVE MTF DIRECTION
    # ---------------------------------------------------------

    macro_bias = mtf.get("macro_bias", NEUTRAL)

    if macro_bias not in (BULLISH, BEARISH):
        return {
            "status": "NO TRADE",
            "bias": NEUTRAL,
            "score": 0,
            "evidence": [],
            "warnings": [
                "No authoritative macro direction."
            ],
        }

    direction = macro_bias

    evidence = []
    warnings = []

    score = 0

    # ---------------------------------------------------------
    # 2. MACRO STRUCTURE
    # ---------------------------------------------------------

    if macro_bias == direction:
        score += 25
        evidence.append(
            f"4H macro structure is {direction.lower()}."
        )

    # ---------------------------------------------------------
    # 3. 1H MAJOR STRUCTURE
    # ---------------------------------------------------------

    major_structure = mtf.get(
        "major_structure",
        NEUTRAL,
    )

    if major_structure == "ALIGNED":
        score += 20
        evidence.append(
            "1H major structure agrees with macro direction."
        )
    else:
        warnings.append(
            "1H major structure is not aligned."
        )

    # ---------------------------------------------------------
    # 4. 15M SETUP
    # ---------------------------------------------------------

    setup_state = mtf.get(
        "setup_state",
        NEUTRAL,
    )

    if setup_state == "PULLBACK_ENDING_OR_RETEST":
        score += 15
        evidence.append(
            "15M is in pullback/retest context."
        )

    elif setup_state == "ALIGNED":
        score += 15
        evidence.append(
            "15M setup is aligned with macro direction."
        )

    elif setup_state not in (NEUTRAL, None):
        warnings.append(
            f"15M setup state: {setup_state}."
        )

    # ---------------------------------------------------------
    # 5. 5M ENTRY STATE
    # ---------------------------------------------------------

    entry_state = mtf.get(
        "entry_state",
        NEUTRAL,
    )

    if entry_state in (
        "RETEST",
        "ENTRY_CONFIRMATION",
        "CONFIRMED",
    ):
        score += 10
        evidence.append(
            f"5M entry state is {entry_state}."
        )
    else:
        warnings.append(
            f"5M entry confirmation is not complete: {entry_state}."
        )

    # ---------------------------------------------------------
    # 6. STRUCTURE EVENTS
    # ---------------------------------------------------------

    selected_structure = structures.get(timeframe)

    event_result = _structure_event_alignment(
        selected_structure,
        direction,
    )

    score += event_result["score"]

    evidence.extend(event_result["evidence"])

    # ---------------------------------------------------------
    # 7. LIQUIDITY
    # ---------------------------------------------------------

    sweep = _latest_sweep(liquidity)
    sweep_direction = _get_sweep_direction(sweep)

    liquidity_state = "NONE"

    if sweep:
        if sweep_direction == direction:
            score += 15
            liquidity_state = "ALIGNED"

            evidence.append(
                "Recent confirmed liquidity sweep "
                "supports the directional bias."
            )

        elif sweep_direction == _opposite(direction):
            liquidity_state = "CONFLICTING"

            warnings.append(
                "Recent liquidity sweep conflicts with "
                "the macro direction."
            )

        else:
            liquidity_state = "NEUTRAL"

    else:
        warnings.append(
            "No confirmed recent liquidity sweep."
        )

    # ---------------------------------------------------------
    # 8. S/R CONTEXT
    # ---------------------------------------------------------

    sr = _get_sr_context(
        levels,
        direction,
    )

    sr_state = sr["state"]

    if sr_state == "ALIGNED":
        score += 10
        evidence.append(
            sr["reason"]
        )

    elif sr_state == "NO_CONTEXT":
        warnings.append(
            sr["reason"]
        )

    # ---------------------------------------------------------
    # 9. PRICE ACTION
    # ---------------------------------------------------------

    pa_direction = _get_price_action_direction(
        price_action
    )

    pa_score = float(
        price_action.get("score", 0)
        if price_action
        else 0
    )

    price_action_state = "NEUTRAL"

    if pa_direction == direction:
        score += min(10, pa_score)
        price_action_state = "ALIGNED"

        evidence.append(
            "Price action supports the directional bias."
        )

    elif pa_direction == _opposite(direction):
        price_action_state = "CONFLICTING"

        warnings.append(
            "Price action currently conflicts with "
            "the macro direction."
        )

    else:
        warnings.append(
            "Price action has no clear directional confirmation."
        )

    # ---------------------------------------------------------
    # FINAL SCORE
    # ---------------------------------------------------------

    score = min(float(score), 100.0)

    # ---------------------------------------------------------
    # FINAL DECISION
    # ---------------------------------------------------------

    mtf_decision = mtf.get(
        "decision",
        "WAIT_FOR_SETUP",
    )

    if mtf_decision == "NO TRADE":
        status = "NO TRADE"

    elif (
        liquidity_state == "CONFLICTING"
        or price_action_state == "CONFLICTING"
    ):
        status = "WAIT"

    elif score >= 80:
        status = "HIGH_CONFLUENCE"

    elif score >= 65:
        status = "GOOD_CONFLUENCE"

    elif score >= 50:
        status = "PARTIAL_CONFLUENCE"

    else:
        status = "WEAK_CONFLUENCE"

    # ---------------------------------------------------------
    # ENTRY READINESS
    # ---------------------------------------------------------

    entry_ready = (
        mtf_decision == "ENTRY_CONFIRMATION_POSSIBLE"
        and score >= 65
        and liquidity_state != "CONFLICTING"
        and price_action_state != "CONFLICTING"
    )

    if entry_ready:
        entry_status = "CONFIRMATION_READY"
    else:
        entry_status = "WAIT"

    return {
        "status": status,
        "bias": direction,
        "score": round(score, 2),

        "entry_ready": entry_ready,
        "entry_status": entry_status,

        "mtf": {
            "macro_bias": macro_bias,
            "major_structure": major_structure,
            "setup_state": setup_state,
            "entry_state": entry_state,
            "decision": mtf_decision,
        },

        "liquidity": {
            "state": liquidity_state,
            "recent_sweep": sweep,
            "direction": sweep_direction,
        },

        "sr": {
            "state": sr_state,
            "zone": sr.get("zone"),
        },

        "price_action": {
            "state": price_action_state,
            "direction": pa_direction,
            "score": pa_score,
        },

        "structure_events": event_result,

        "evidence": evidence,
        "warnings": warnings,

        "methodology": {
            "type": "Deterministic multi-layer confluence",
            "direction_source": "4H macro structure",
            "hierarchy": "4H -> 1H -> 15M -> 5M",
            "components": [
                "MTF structure",
                "Liquidity",
                "Support/Resistance",
                "Price Action",
                "BOS/CHoCH",
            ],
            "score_meaning": (
                "Confluence evidence score, not win probability."
            ),
            "prediction": "None",
            "win_probability": "Not calculated",
        },
    }