import pandas as pd
from .indicators import add_indicators
from .structure import analyze_structure


def timeframe_analysis(df, timeframe):

    if df is None or len(df) < 100:
        return {
            "timeframe": timeframe,
            "status": "INSUFFICIENT_DATA",
            "bias": "NEUTRAL",
            "structure_bias": "NEUTRAL",
            "external_bias": "NEUTRAL",
            "internal_bias": "NEUTRAL",
            "structure_strength": 0,
            "last_bos": None,
            "last_choch": None,
        }

    d = add_indicators(df.copy())

    structure = analyze_structure(d)

    last = d.iloc[-1]

    def val(name):
        x = last.get(name)
        try:
            return float(x) if pd.notna(x) else None
        except Exception:
            return None

    close = val("close")
    ema20 = val("ema_20")
    ema50 = val("ema_50")
    ema200 = val("ema_200")

    ema_bias = "NEUTRAL"

    if (
        close is not None
        and ema20 is not None
        and ema50 is not None
    ):
        if close > ema20 > ema50:
            ema_bias = "BULLISH"

        elif close < ema20 < ema50:
            ema_bias = "BEARISH"

    structure_bias = structure.get(
        "bias",
        "NEUTRAL"
    )

    final_bias = (
        structure_bias
        if structure_bias != "NEUTRAL"
        else ema_bias
    )

    swings = structure.get("swings", [])
    bos = structure.get("bos", [])
    choch = structure.get("choch", [])
    internal_bos = structure.get(
        "internal_bos",
        []
    )

    return {

        "timeframe": timeframe,

        "status": "OK",

        "bias": final_bias,

        "structure_bias":
            structure_bias,

        "external_bias":
            structure.get(
                "external_bias",
                structure_bias
            ),

        "internal_bias":
            structure.get(
                "internal_bias",
                "NEUTRAL"
            ),

        "ema_bias":
            ema_bias,

        "structure_strength":
            structure.get(
                "strength",
                0
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

        # IMPORTANT:
        # Actual counts, not UI truncation.
        "swing_count":
            structure.get(
                "swing_count",
                len(swings)
            ),

        "external_swing_count":
            structure.get(
                "external_swing_count",
                0
            ),

        "internal_swing_count":
            structure.get(
                "internal_swing_count",
                0
            ),

        "bos_count":
            structure.get(
                "bos_count",
                len(bos)
            ),

        "choch_count":
            structure.get(
                "choch_count",
                len(choch)
            ),

        "internal_bos_count":
            structure.get(
                "internal_bos_count",
                len(internal_bos)
            ),
    }


def analyze_mtf(frames, hierarchy):

    results = {}

    for tf in hierarchy:

        df = frames.get(tf)

        if df is None:

            results[tf] = {
                "timeframe": tf,
                "status": "DATA_UNAVAILABLE",
                "bias": "NEUTRAL",
            }

            continue

        results[tf] = timeframe_analysis(
            df,
            tf
        )

    # --------------------------------------------------------
    # HTF gets higher weight
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

        weight = weights.get(tf, 1.0)

        available_weight += weight

        if result["bias"] == "BULLISH":
            bullish_weight += weight

        elif result["bias"] == "BEARISH":
            bearish_weight += weight

    if available_weight == 0:

        weighted_bias = "NEUTRAL"
        alignment = 0

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
        alignment = 0

    directional = [
        results[tf]["bias"]
        for tf in hierarchy
        if (
            results.get(tf, {}).get(
                "status"
            ) == "OK"
            and results[tf].get("bias")
            in ("BULLISH", "BEARISH")
        )
    ]

    bullish_count = directional.count(
        "BULLISH"
    )

    bearish_count = directional.count(
        "BEARISH"
    )

    if weighted_bias == "BULLISH":

        agreement = (
            bullish_count
            / max(len(directional), 1)
        )

    elif weighted_bias == "BEARISH":

        agreement = (
            bearish_count
            / max(len(directional), 1)
        )

    else:

        agreement = 0

    return {

        "hierarchy": hierarchy,

        "timeframes": results,

        "weighted_bias":
            weighted_bias,

        "bullish_weight":
            round(
                bullish_weight,
                2
            ),

        "bearish_weight":
            round(
                bearish_weight,
                2
            ),

        "alignment":
            round(
                alignment,
                3
            ),

        "agreement":
            round(
                agreement,
                3
            ),

        "directional_timeframes":
            directional,

        "description":
            "Higher timeframe bias → structural context → setup timeframe → entry timeframe",
    }