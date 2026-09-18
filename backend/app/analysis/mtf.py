import pandas as pd

from .indicators import add_indicators
from .structure import analyze_structure


# ============================================================
# MTF ENGINE V2
#
# Fixed default hierarchy:
#
# 4H  -> MACRO BIAS
# 1H  -> MAJOR STRUCTURE
# 15M -> SETUP / RETRACEMENT
# 5M  -> ENTRY CONFIRMATION
#
# Important:
# This engine does NOT predict price.
# It combines deterministic timeframe evidence.
# ============================================================


DEFAULT_HIERARCHY = ["4h", "1h", "15m", "5m"]


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _safe_float(value):
    try:
        if pd.notna(value):
            return float(value)
    except Exception:
        pass

    return None


def _opposite(direction):
    if direction == "BULLISH":
        return "BEARISH"

    if direction == "BEARISH":
        return "BULLISH"

    return "NEUTRAL"


def _direction_from_ema(close, ema20, ema50):
    if (
        close is None
        or ema20 is None
        or ema50 is None
    ):
        return "NEUTRAL"

    if close > ema20 > ema50:
        return "BULLISH"

    if close < ema20 < ema50:
        return "BEARISH"

    return "NEUTRAL"


def _structure_direction(structure):
    bias = structure.get(
        "bias",
        "NEUTRAL",
    )

    if bias in ("BULLISH", "BEARISH"):
        return bias

    return "NEUTRAL"


# ------------------------------------------------------------
# Timeframe analysis
# ------------------------------------------------------------

def timeframe_analysis(df, timeframe):

    if df is None or len(df) < 100:

        return {
            "timeframe": timeframe,
            "status": "INSUFFICIENT_DATA",

            "bias": "NEUTRAL",
            "structure_bias": "NEUTRAL",
            "external_bias": "NEUTRAL",
            "internal_bias": "NEUTRAL",

            "ema_bias": "NEUTRAL",

            "structure_strength": 0,

            "last_close": None,
            "ema20": None,
            "ema50": None,
            "ema200": None,

            "last_swing": None,
            "last_bos": None,
            "last_choch": None,

            "protected_high": None,
            "protected_low": None,

            "swing_count": 0,
            "external_swing_count": 0,
            "internal_swing_count": 0,
            "bos_count": 0,
            "choch_count": 0,
            "internal_bos_count": 0,

            "role": None,
            "state": "DATA_UNAVAILABLE",
        }

    d = add_indicators(
        df.copy()
    )

    structure = analyze_structure(d)

    last = d.iloc[-1]

    close = _safe_float(
        last.get("close")
    )

    ema20 = _safe_float(
        last.get("ema_20")
    )

    ema50 = _safe_float(
        last.get("ema_50")
    )

    ema200 = _safe_float(
        last.get("ema_200")
    )

    ema_bias = _direction_from_ema(
        close,
        ema20,
        ema50,
    )

    structure_bias = _structure_direction(
        structure
    )

    external_bias = structure.get(
        "external_bias",
        structure_bias,
    )

    internal_bias = structure.get(
        "internal_bias",
        "NEUTRAL",
    )

    # --------------------------------------------------------
    # Primary bias
    #
    # Structure has priority over EMA.
    # EMA is contextual evidence only.
    # --------------------------------------------------------

    if structure_bias != "NEUTRAL":
        final_bias = structure_bias

    else:
        final_bias = ema_bias

    # --------------------------------------------------------
    # Detect lower-timeframe pullback
    #
    # Example:
    # Structure = BEARISH
    # EMA       = BULLISH
    #
    # This is NOT automatically a bullish reversal.
    # It can represent a retracement.
    # --------------------------------------------------------

    state = "ALIGNED"

    if (
        structure_bias in ("BULLISH", "BEARISH")
        and ema_bias in ("BULLISH", "BEARISH")
    ):

        if ema_bias == structure_bias:
            state = "ALIGNED"

        else:
            state = "RETRACEMENT"

    elif structure_bias in ("BULLISH", "BEARISH"):

        state = "STRUCTURE_ONLY"

    elif ema_bias in ("BULLISH", "BEARISH"):

        state = "EMA_ONLY"

    else:

        state = "NEUTRAL"

    swings = structure.get(
        "swings",
        [],
    )

    bos = structure.get(
        "bos",
        [],
    )

    choch = structure.get(
        "choch",
        [],
    )

    internal_bos = structure.get(
        "internal_bos",
        [],
    )

    return {

        "timeframe": timeframe,

        "status": "OK",

        "bias": final_bias,

        "structure_bias":
            structure_bias,

        "external_bias":
            external_bias,

        "internal_bias":
            internal_bias,

        "ema_bias":
            ema_bias,

        "structure_strength":
            structure.get(
                "strength",
                0,
            ),

        "last_close":
            close,

        "ema20":
            ema20,

        "ema50":
            ema50,

        "ema200":
            ema200,

        "last_swing":
            structure.get(
                "last_swing"
            ),

        "last_bos":
            structure.get(
                "last_bos"
            ),

        "last_choch":
            structure.get(
                "last_choch"
            ),

        "protected_high":
            structure.get(
                "protected_high"
            ),

        "protected_low":
            structure.get(
                "protected_low"
            ),

        "swing_count":
            structure.get(
                "swing_count",
                len(swings),
            ),

        "external_swing_count":
            structure.get(
                "external_swing_count",
                0,
            ),

        "internal_swing_count":
            structure.get(
                "internal_swing_count",
                0,
            ),

        "bos_count":
            structure.get(
                "bos_count",
                len(bos),
            ),

        "choch_count":
            structure.get(
                "choch_count",
                len(choch),
            ),

        "internal_bos_count":
            structure.get(
                "internal_bos_count",
                len(internal_bos),
            ),

        # New V2 context
        "state": state,

        "role": None,
    }


# ------------------------------------------------------------
# Assign timeframe roles
# ------------------------------------------------------------

def _assign_roles(results, hierarchy):

    roles = [
        "MACRO_BIAS",
        "MAJOR_STRUCTURE",
        "SETUP",
        "ENTRY_CONFIRMATION",
    ]

    for i, tf in enumerate(hierarchy):

        if tf not in results:
            continue

        role = (
            roles[i]
            if i < len(roles)
            else "CONTEXT"
        )

        results[tf]["role"] = role


# ------------------------------------------------------------
# Determine macro bias
#
# IMPORTANT:
# Highest timeframe is the anchor.
# Lower timeframes cannot override 4H macro bias.
# ------------------------------------------------------------

def _macro_bias(results, hierarchy):

    if not hierarchy:
        return "NEUTRAL"

    highest_tf = hierarchy[0]

    highest = results.get(
        highest_tf
    )

    if not highest:
        return "NEUTRAL"

    if highest.get("status") != "OK":
        return "NEUTRAL"

    bias = highest.get(
        "structure_bias",
        "NEUTRAL",
    )

    if bias in ("BULLISH", "BEARISH"):
        return bias

    return highest.get(
        "bias",
        "NEUTRAL",
    )


# ------------------------------------------------------------
# Classify lower timeframe relationship
# ------------------------------------------------------------

def _classify_relationship(
    macro_bias,
    result,
    role,
):

    if not result:
        return "DATA_UNAVAILABLE"

    if result.get("status") != "OK":
        return "DATA_UNAVAILABLE"

    structure_bias = result.get(
        "structure_bias",
        "NEUTRAL",
    )

    ema_bias = result.get(
        "ema_bias",
        "NEUTRAL",
    )

    bias = result.get(
        "bias",
        "NEUTRAL",
    )

    # --------------------------------------------------------
    # Highest timeframe
    # --------------------------------------------------------

    if role == "MACRO_BIAS":

        if bias == macro_bias:
            return "MACRO_ALIGNED"

        if bias == _opposite(macro_bias):
            return "MACRO_CONFLICT"

        return "MACRO_NEUTRAL"

    # --------------------------------------------------------
    # Lower timeframe aligned with macro
    # --------------------------------------------------------

    if structure_bias == macro_bias:

        if ema_bias == macro_bias:
            return "ALIGNED"

        if ema_bias == _opposite(macro_bias):
            return "PULLBACK_ENDING_OR_RETEST"

        return "STRUCTURE_ALIGNED"

    # --------------------------------------------------------
    # Lower timeframe opposite structure
    #
    # Do NOT call this reversal automatically.
    # --------------------------------------------------------

    if structure_bias == _opposite(
        macro_bias
    ):

        return "COUNTER_TREND"

    # --------------------------------------------------------
    # Structure neutral
    # --------------------------------------------------------

    if ema_bias == macro_bias:
        return "EMA_ALIGNED"

    if ema_bias == _opposite(macro_bias):
        return "COUNTER_TREND_EMA"

    return "NEUTRAL"


# ------------------------------------------------------------
# Build hierarchical interpretation
# ------------------------------------------------------------

def _build_hierarchy_state(
    results,
    hierarchy,
    macro_bias,
):

    state = {
        "macro_bias": macro_bias,

        "major_structure": "NEUTRAL",

        "setup_state": "NEUTRAL",

        "entry_state": "NEUTRAL",

        "trade_direction": (
            "LONG"
            if macro_bias == "BULLISH"
            else
            "SHORT"
            if macro_bias == "BEARISH"
            else None
        ),

        "decision": "NO TRADE",

        "relationships": {},
    }

    # --------------------------------------------------------
    # Assign relationships
    # --------------------------------------------------------

    for tf in hierarchy:

        result = results.get(tf)

        if not result:
            continue

        role = result.get(
            "role",
            "CONTEXT",
        )

        relationship = _classify_relationship(
            macro_bias,
            result,
            role,
        )

        result["relationship"] = relationship

        state["relationships"][tf] = relationship

    # --------------------------------------------------------
    # 1H = major structure
    # --------------------------------------------------------

    if len(hierarchy) >= 2:

        tf = hierarchy[1]

        r = results.get(tf)

        if r and r.get("status") == "OK":

            if r.get("structure_bias") == macro_bias:

                state[
                    "major_structure"
                ] = "ALIGNED"

            elif r.get("structure_bias") == _opposite(
                macro_bias
            ):

                state[
                    "major_structure"
                ] = "COUNTER_TREND"

            else:

                state[
                    "major_structure"
                ] = "NEUTRAL"

    # --------------------------------------------------------
    # 15M = setup
    # --------------------------------------------------------

    if len(hierarchy) >= 3:

        tf = hierarchy[2]

        r = results.get(tf)

        if r and r.get("status") == "OK":

            relationship = r.get(
                "relationship"
            )

            if relationship in (
                "ALIGNED",
                "STRUCTURE_ALIGNED",
                "PULLBACK_ENDING_OR_RETEST",
            ):

                state[
                    "setup_state"
                ] = relationship

            elif relationship in (
                "COUNTER_TREND",
                "COUNTER_TREND_EMA",
            ):

                state[
                    "setup_state"
                ] = "RETRACEMENT"

            else:

                state[
                    "setup_state"
                ] = "NEUTRAL"

    # --------------------------------------------------------
    # 5M = entry
    # --------------------------------------------------------

    if len(hierarchy) >= 4:

        tf = hierarchy[3]

        r = results.get(tf)

        if r and r.get("status") == "OK":

            relationship = r.get(
                "relationship"
            )

            if relationship in (
                "ALIGNED",
                "STRUCTURE_ALIGNED",
            ):

                state[
                    "entry_state"
                ] = "ALIGNED"

            elif relationship in (
                "PULLBACK_ENDING_OR_RETEST",
            ):

                state[
                    "entry_state"
                ] = "RETEST"

            elif relationship in (
                "COUNTER_TREND",
                "COUNTER_TREND_EMA",
            ):

                state[
                    "entry_state"
                ] = "COUNTER_TREND"

            else:

                state[
                    "entry_state"
                ] = "NEUTRAL"

    # --------------------------------------------------------
    # Final decision
    #
    # This is NOT the final trade generator.
    # It only describes MTF state.
    # --------------------------------------------------------

    if macro_bias == "NEUTRAL":

        state["decision"] = "NO TRADE"

    elif state["major_structure"] == "COUNTER_TREND":

        state["decision"] = (
            "WAIT_FOR_STRUCTURAL_CONFIRMATION"
        )

    elif state["setup_state"] == "RETRACEMENT":

        state["decision"] = (
            "WAIT_FOR_REENTRY_CONFIRMATION"
        )

    elif state["entry_state"] in (
        "COUNTER_TREND",
    ):

        state["decision"] = (
            "WAIT_FOR_ENTRY_CONFIRMATION"
        )

    elif state["entry_state"] in (
        "ALIGNED",
        "RETEST",
    ):

        state["decision"] = (
            "ENTRY_CONFIRMATION_POSSIBLE"
        )

    else:

        state["decision"] = (
            "WAIT_FOR_SETUP"
        )

    return state


# ------------------------------------------------------------
# Main MTF engine
# ------------------------------------------------------------

def analyze_mtf(
    frames,
    hierarchy=None,
):

    # --------------------------------------------------------
    # Highest timeframe is always the first hierarchy element.
    #
    # Default = 4H
    # --------------------------------------------------------

    if not hierarchy:

        hierarchy = DEFAULT_HIERARCHY.copy()

    else:

        hierarchy = list(
            hierarchy
        )

    # --------------------------------------------------------
    # Validate hierarchy
    # --------------------------------------------------------

    if not hierarchy:

        return {
            "status": "NO_HIERARCHY",
            "hierarchy": [],
            "timeframes": {},
            "macro_bias": "NEUTRAL",
            "weighted_bias": "NEUTRAL",
            "decision": "NO TRADE",
        }

    # --------------------------------------------------------
    # Analyze every timeframe
    # --------------------------------------------------------

    results = {}

    for tf in hierarchy:

        df = frames.get(tf)

        if df is None:

            results[tf] = {
                "timeframe": tf,
                "status": "DATA_UNAVAILABLE",
                "bias": "NEUTRAL",
                "structure_bias": "NEUTRAL",
                "external_bias": "NEUTRAL",
                "internal_bias": "NEUTRAL",
                "ema_bias": "NEUTRAL",
                "structure_strength": 0,
                "role": None,
                "state": "DATA_UNAVAILABLE",
                "relationship": "DATA_UNAVAILABLE",
            }

            continue

        results[tf] = timeframe_analysis(
            df,
            tf,
        )

    # --------------------------------------------------------
    # Assign semantic roles
    # --------------------------------------------------------

    _assign_roles(
        results,
        hierarchy,
    )

    # --------------------------------------------------------
    # Highest timeframe macro bias
    # --------------------------------------------------------

    macro_bias = _macro_bias(
        results,
        hierarchy,
    )

    # --------------------------------------------------------
    # Relationship + state
    # --------------------------------------------------------

    hierarchy_state = _build_hierarchy_state(
        results,
        hierarchy,
        macro_bias,
    )

    # --------------------------------------------------------
    # Weighted evidence
    #
    # Kept for compatibility with existing routes.
    # It is NOT used to override macro bias.
    # --------------------------------------------------------

    weights = {}

    if len(hierarchy) == 4:

        weights = {
            hierarchy[0]: 4.0,
            hierarchy[1]: 3.0,
            hierarchy[2]: 2.0,
            hierarchy[3]: 1.0,
        }

    else:

        for i, tf in enumerate(hierarchy):

            weights[tf] = float(
                len(hierarchy) - i
            )

    bullish_weight = 0.0
    bearish_weight = 0.0
    available_weight = 0.0

    for tf in hierarchy:

        result = results.get(tf)

        if (
            not result
            or result.get("status") != "OK"
        ):
            continue

        weight = weights.get(
            tf,
            1.0,
        )

        available_weight += weight

        bias = result.get(
            "bias",
            "NEUTRAL",
        )

        if bias == "BULLISH":
            bullish_weight += weight

        elif bias == "BEARISH":
            bearish_weight += weight

    if available_weight == 0:

        weighted_bias = "NEUTRAL"
        alignment = 0.0

    elif bullish_weight > bearish_weight:

        weighted_bias = "BULLISH"

        alignment = (
            bullish_weight
            / available_weight
        )

    elif bearish_weight > bullish_weight:

        weighted_bias = "BEARISH"

        alignment = (
            bearish_weight
            / available_weight
        )

    else:

        weighted_bias = "NEUTRAL"
        alignment = 0.0

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # weighted_bias is retained for compatibility,
    # but macro_bias is the authoritative directional anchor.
    # --------------------------------------------------------

    directional = [
        results[tf]["bias"]
        for tf in hierarchy
        if (
            results.get(tf, {}).get(
                "status"
            ) == "OK"
            and results[tf].get("bias")
            in (
                "BULLISH",
                "BEARISH",
            )
        )
    ]

    bullish_count = directional.count(
        "BULLISH"
    )

    bearish_count = directional.count(
        "BEARISH"
    )

    if macro_bias == "BULLISH":

        agreement = (
            bullish_count
            / max(
                len(directional),
                1,
            )
        )

    elif macro_bias == "BEARISH":

        agreement = (
            bearish_count
            / max(
                len(directional),
                1,
            )
        )

    else:

        agreement = 0.0

    # --------------------------------------------------------
    # Macro alignment
    # --------------------------------------------------------

    macro_aligned_count = 0

    for tf in hierarchy:

        result = results.get(tf)

        if not result:
            continue

        if (
            result.get("status") == "OK"
            and
            result.get("bias") == macro_bias
        ):

            macro_aligned_count += 1

    macro_alignment = (
        macro_aligned_count
        / max(
            len(directional),
            1,
        )
        if macro_bias != "NEUTRAL"
        else 0.0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "status": "OK",

        "hierarchy":
            hierarchy,

        "timeframes":
            results,

        # Authoritative HTF direction
        "macro_bias":
            macro_bias,

        # Existing compatibility field
        "weighted_bias":
            weighted_bias,

        "bullish_weight":
            round(
                bullish_weight,
                2,
            ),

        "bearish_weight":
            round(
                bearish_weight,
                2,
            ),

        "alignment":
            round(
                alignment,
                3,
            ),

        "agreement":
            round(
                agreement,
                3,
            ),

        "macro_alignment":
            round(
                macro_alignment,
                3,
            ),

        "directional_timeframes":
            directional,

        # New V2 semantic interpretation
        "macro":
            macro_bias,

        "major_structure":
            hierarchy_state[
                "major_structure"
            ],

        "setup_state":
            hierarchy_state[
                "setup_state"
            ],

        "entry_state":
            hierarchy_state[
                "entry_state"
            ],

        "trade_direction":
            hierarchy_state[
                "trade_direction"
            ],

        "decision":
            hierarchy_state[
                "decision"
            ],

        "relationships":
            hierarchy_state[
                "relationships"
            ],

        "description":
            (
                "4H macro bias -> "
                "1H major structure -> "
                "15M setup -> "
                "5M entry confirmation"
            ),

        "methodology": {

            "type":
                "Hierarchical deterministic MTF analysis",

            "highest_timeframe":
                hierarchy[0],

            "default_highest_timeframe":
                "4h",

            "macro_rule":
                "Highest timeframe structure is the directional anchor.",

            "lower_timeframe_rule":
                (
                    "Lower timeframe disagreement is treated "
                    "as retracement/counter-trend context "
                    "until structural reversal is confirmed."
                ),

            "weighted_bias":
                (
                    "Compatibility evidence only; "
                    "does not override macro bias."
                ),

            "prediction":
                "None",

            "win_probability":
                "Not calculated",
        },
    }