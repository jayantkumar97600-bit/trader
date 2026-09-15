from __future__ import annotations

from typing import Any
import math

import numpy as np
import pandas as pd


# ============================================================
# MARKET STRUCTURE ENGINE V4.16
# ============================================================
#
# V4.16 = V4.15 logic + performance optimization
#
# Preserved:
#   - Confirmed swings only
#   - HH / HL / LH / LL
#   - Internal + External structure
#   - BOS
#   - CHoCH
#   - Current structural regime
#   - HL-only bullish protection
#   - LH-only bearish protection
#   - Current-leg reconstruction
#   - Internal BOS filters
#   - No lookahead for completed swings
#
# Optimizations:
#   - NumPy arrays instead of repeated df.iloc()
#   - ATR cached once
#   - Vectorized swing detection
#   - Vectorized break detection
#   - No repeated full-list scans for previous pivots
#   - Precomputed previous same-kind pivot
# ============================================================


# ============================================================
# PARAMETERS
# ============================================================

SWING_LEFT = 4
SWING_RIGHT = 4

MIN_REVERSAL_ATR = 1.25
MIN_PROMINENCE_ATR = 2.0

MIN_PIVOT_GAP = 6

MIN_EXTERNAL_LEG_ATR = 2.5
MIN_EXTERNAL_GAP = 25

MERGE_DISTANCE_ATR = 0.60

BREAK_BUFFER_ATR = 0.15
MIN_BOS_DISPLACEMENT_ATR = 0.75

MIN_EVENT_GAP = 4

MAX_PROTECTED_DISTANCE_ATR = 8.0

INTERNAL_BREAK_BUFFER_ATR = 0.20
MIN_INTERNAL_BOS_DISPLACEMENT_ATR = 1.00
MIN_INTERNAL_EVENT_GAP = 8

MIN_INTERNAL_PIVOT_GAP = 4


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        x = float(value)

        if not math.isfinite(x):
            return default

        return x

    except Exception:
        return default


def _timestamp(
    df: pd.DataFrame,
    index: int,
):

    if "timestamp" not in df.columns:
        return None

    try:
        return df.iloc[index]["timestamp"]
    except Exception:
        return None


# ============================================================
# ARRAY PREPARATION
# ============================================================

def _prepare_arrays(
    df: pd.DataFrame,
):
    """
    Prepare all frequently accessed columns once.

    This removes thousands of repeated df.iloc() calls.
    """

    high = pd.to_numeric(
        df["high"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    low = pd.to_numeric(
        df["low"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    close = pd.to_numeric(
        df["close"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    if "atr" in df.columns:

        atr = pd.to_numeric(
            df["atr"],
            errors="coerce",
        ).to_numpy(
            dtype=float
        )

    else:

        previous_close = np.empty_like(
            close
        )

        previous_close[0] = close[0]

        previous_close[1:] = close[:-1]

        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(
                    high
                    - previous_close
                ),
                np.abs(
                    low
                    - previous_close
                ),
            ),
        )

        atr = (
            pd.Series(tr)
            .rolling(
                14,
                min_periods=14,
            )
            .mean()
            .to_numpy(
                dtype=float
            )
        )

    # Fill missing ATR values.
    if np.any(
        ~np.isfinite(atr)
    ):

        valid = atr[
            np.isfinite(atr)
            & (atr > 0)
        ]

        fallback = (
            float(
                np.nanmedian(valid)
            )
            if len(valid)
            else 1.0
        )

        atr = np.where(
            np.isfinite(atr)
            & (atr > 0),
            atr,
            fallback,
        )

    return (
        high,
        low,
        close,
        atr,
    )


# ============================================================
# SWING OBJECT
# ============================================================

def _make_swing(
    df: pd.DataFrame,
    index: int,
    kind: str,
    pivot_type: str = "MINOR",
) -> dict[str, Any]:

    if kind == "HIGH":
        price = _safe_float(
            df["high"].iloc[index]
        )
    else:
        price = _safe_float(
            df["low"].iloc[index]
        )

    confirmation_index = (
        index + SWING_RIGHT
    )

    return {
        "index": int(index),

        "confirmation_index": int(
            confirmation_index
        ),

        "timestamp": _timestamp(
            df,
            index,
        ),

        "confirmation_timestamp": (
            _timestamp(
                df,
                confirmation_index,
            )
            if confirmation_index < len(df)
            else None
        ),

        "kind": kind,

        "price": price,

        "type": None,

        "pivot_type": pivot_type,
    }


# ============================================================
# RAW CONFIRMED PIVOTS - VECTORIZED
# ============================================================

def _raw_pivots(
    df: pd.DataFrame,
    left: int = SWING_LEFT,
    right: int = SWING_RIGHT,
) -> list[dict[str, Any]]:

    n = len(df)

    if n < (
        left
        + right
        + 5
    ):
        return []

    high, low, close, atr = (
        _prepare_arrays(df)
    )

    # --------------------------------------------------------
    # Rolling extrema.
    #
    # This replaces the Python loop over every candle.
    # --------------------------------------------------------

    highs = pd.Series(
        high
    )

    lows = pd.Series(
        low
    )

    window = (
        left
        + right
        + 1
    )

    rolling_high = (
        highs
        .rolling(
            window=window,
            center=True,
            min_periods=window,
        )
        .max()
        .to_numpy()
    )

    rolling_low = (
        lows
        .rolling(
            window=window,
            center=True,
            min_periods=window,
        )
        .min()
        .to_numpy()
    )

    valid_start = left

    valid_end = n - right

    high_indices = np.flatnonzero(
        (
            high
            >= rolling_high
        )
        & np.isfinite(
            rolling_high
        )
    )

    low_indices = np.flatnonzero(
        (
            low
            <= rolling_low
        )
        & np.isfinite(
            rolling_low
        )
    )

    high_indices = high_indices[
        (
            high_indices
            >= valid_start
        )
        & (
            high_indices
            < valid_end
        )
    ]

    low_indices = low_indices[
        (
            low_indices
            >= valid_start
        )
        & (
            low_indices
            < valid_end
        )
    ]

    pivots = []

    # --------------------------------------------------------
    # Build objects only for actual pivots.
    # --------------------------------------------------------

    for i in high_indices:

        i = int(i)

        pivots.append(
            {
                "index": i,
                "confirmation_index": (
                    i + right
                ),
                "timestamp": (
                    _timestamp(
                        df,
                        i,
                    )
                ),
                "confirmation_timestamp": (
                    _timestamp(
                        df,
                        i + right,
                    )
                    if i + right < n
                    else None
                ),
                "kind": "HIGH",
                "price": float(
                    high[i]
                ),
                "type": None,
                "pivot_type": "MINOR",
            }
        )

    for i in low_indices:

        i = int(i)

        pivots.append(
            {
                "index": i,
                "confirmation_index": (
                    i + right
                ),
                "timestamp": (
                    _timestamp(
                        df,
                        i,
                    )
                ),
                "confirmation_timestamp": (
                    _timestamp(
                        df,
                        i + right,
                    )
                    if i + right < n
                    else None
                ),
                "kind": "LOW",
                "price": float(
                    low[i]
                ),
                "type": None,
                "pivot_type": "MINOR",
            }
        )

    pivots.sort(
        key=lambda x:
            x["index"]
    )

    return pivots


# ============================================================
# CLEAN PIVOTS
# ============================================================

def _clean_pivots(
    df: pd.DataFrame,
    pivots: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if not pivots:
        return []

    _, _, _, atr = (
        _prepare_arrays(df)
    )

    cleaned = []

    for pivot in pivots:

        if not cleaned:

            cleaned.append(
                pivot
            )

            continue

        previous = cleaned[-1]

        # ----------------------------------------------------
        # Same kind:
        # retain more extreme pivot.
        # ----------------------------------------------------

        if (
            pivot["kind"]
            == previous["kind"]
        ):

            if pivot["kind"] == "HIGH":

                if (
                    pivot["price"]
                    > previous["price"]
                ):
                    cleaned[-1] = pivot

            else:

                if (
                    pivot["price"]
                    < previous["price"]
                ):
                    cleaned[-1] = pivot

            continue

        # ----------------------------------------------------
        # Opposite pivot.
        # ----------------------------------------------------

        gap = (
            pivot["index"]
            - previous["index"]
        )

        if gap < MIN_PIVOT_GAP:

            idx = min(
                max(
                    pivot["index"],
                    0,
                ),
                len(atr) - 1,
            )

            current_atr = (
                atr[idx]
            )

            if (
                not np.isfinite(
                    current_atr
                )
                or current_atr <= 0
            ):
                continue

            movement = abs(
                pivot["price"]
                - previous["price"]
            )

            if (
                movement
                < current_atr
                * MIN_REVERSAL_ATR
            ):
                continue

        cleaned.append(
            pivot
        )

    return cleaned


# ============================================================
# CLASSIFY HH / HL / LH / LL
# ============================================================

def _classify_swings(
    pivots: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    previous_high = None
    previous_low = None

    result = []

    for pivot in pivots:

        p = dict(pivot)

        if p["kind"] == "HIGH":

            if previous_high is None:

                p["type"] = "HH"

            elif (
                p["price"]
                > previous_high["price"]
            ):

                p["type"] = "HH"

            else:

                p["type"] = "LH"

            previous_high = p

        else:

            if previous_low is None:

                p["type"] = "HL"

            elif (
                p["price"]
                > previous_low["price"]
            ):

                p["type"] = "HL"

            else:

                p["type"] = "LL"

            previous_low = p

        result.append(
            p
        )

    return result


# ============================================================
# EXTERNAL STRUCTURE
# ============================================================

def _select_external_swings(
    df: pd.DataFrame,
    swings: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if not swings:
        return []

    _, _, _, atr = (
        _prepare_arrays(df)
    )

    external = []

    last_external = None

    for swing in swings:

        idx = swing["index"]

        current_atr = (
            atr[idx]
            if 0 <= idx < len(atr)
            else 0.0
        )

        if (
            not np.isfinite(
                current_atr
            )
            or current_atr <= 0
        ):
            continue

        if last_external is None:

            p = dict(swing)

            p["pivot_type"] = (
                "EXTERNAL"
            )

            external.append(p)

            last_external = p

            continue

        gap = (
            idx
            - last_external["index"]
        )

        distance = abs(
            swing["price"]
            - last_external["price"]
        )

        meaningful_distance = (
            distance
            >= current_atr
            * MIN_EXTERNAL_LEG_ATR
        )

        meaningful_gap = (
            gap
            >= MIN_EXTERNAL_GAP
        )

        if (
            meaningful_distance
            or (
                meaningful_gap
                and distance
                >= current_atr
                * MIN_PROMINENCE_ATR
            )
        ):

            p = dict(swing)

            p["pivot_type"] = (
                "EXTERNAL"
            )

            external.append(p)

            last_external = p

    external = _classify_swings(
        external
    )

    for p in external:
        p["pivot_type"] = (
            "EXTERNAL"
        )

    return external


# ============================================================
# INTERNAL STRUCTURE
# ============================================================

def _select_internal_swings(
    swings: list[dict[str, Any]],
    external: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    external_indices = {
        x["index"]
        for x in external
    }

    result = []

    for swing in swings:

        if (
            swing["index"]
            in external_indices
        ):
            continue

        p = dict(swing)

        p["pivot_type"] = (
            "INTERNAL"
        )

        result.append(p)

    return result


# ============================================================
# FAST BREAK DETECTOR
# ============================================================

def _find_break(
    df: pd.DataFrame,
    level: float,
    direction: str,
    start_index: int,
    buffer_atr: float = BREAK_BUFFER_ATR,
    min_displacement: float = (
        MIN_BOS_DISPLACEMENT_ATR
    ),
    arrays=None,
) -> dict[str, Any] | None:

    if start_index >= len(df):
        return None

    if arrays is None:

        _, _, close, atr = (
            _prepare_arrays(df)
        )

    else:

        close = arrays[2]
        atr = arrays[3]

    start = max(
        0,
        int(start_index),
    )

    c = close[start:]
    a = atr[start:]

    valid = (
        np.isfinite(c)
        & np.isfinite(a)
        & (a > 0)
    )

    if direction == "BULLISH":

        broken = (
            c
            > (
                level
                + a
                * buffer_atr
            )
        )

    else:

        broken = (
            c
            < (
                level
                - a
                * buffer_atr
            )
        )

    displacement = (
        np.abs(c - level)
        / np.maximum(
            a,
            1e-12,
        )
    )

    valid &= (
        displacement
        >= min_displacement
    )

    candidates = np.flatnonzero(
        broken & valid
    )

    if len(candidates) == 0:
        return None

    local_index = int(
        candidates[0]
    )

    index = (
        start
        + local_index
    )

    return {
        "index": int(index),

        "timestamp": _timestamp(
            df,
            index,
        ),

        "direction": direction,

        "broken_level": float(
            level
        ),

        "close": float(
            close[index]
        ),

        "displacement_atr": round(
            float(
                displacement[
                    local_index
                ]
            ),
            3,
        ),
    }


# ============================================================
# EXTERNAL STATE MACHINE
# ============================================================

def _external_state_machine(
    df: pd.DataFrame,
    external: list[dict[str, Any]],
):

    if not external:

        return (
            "NEUTRAL",
            [],
            [],
            None,
            None,
        )

    arrays = _prepare_arrays(
        df
    )

    highs = [
        x
        for x in external
        if x["kind"] == "HIGH"
    ]

    lows = [
        x
        for x in external
        if x["kind"] == "LOW"
    ]

    events = []

    retired_highs = set()
    retired_lows = set()

    last_event_index = -10_000

    protected_high = None
    protected_low = None

    regime = "NEUTRAL"

    # --------------------------------------------------------
    # Precompute latest HL / LH lookup.
    # This eliminates repeated list comprehensions.
    # --------------------------------------------------------

    hl_by_index = []
    lh_by_index = []

    latest_hl = None
    latest_lh = None

    for pivot in external:

        if (
            pivot["kind"] == "LOW"
            and pivot["type"] == "HL"
        ):
            latest_hl = pivot

        if (
            pivot["kind"] == "HIGH"
            and pivot["type"] == "LH"
        ):
            latest_lh = pivot

        hl_by_index.append(
            latest_hl
        )

        lh_by_index.append(
            latest_lh
        )

    # Map pivot index -> latest qualifying protection
    latest_hl_map = {}
    latest_lh_map = {}

    latest_hl = None
    latest_lh = None

    for pivot in external:

        if (
            pivot["kind"] == "LOW"
            and pivot["type"] == "HL"
        ):
            latest_hl = pivot

        if (
            pivot["kind"] == "HIGH"
            and pivot["type"] == "LH"
        ):
            latest_lh = pivot

        latest_hl_map[
            pivot["index"]
        ] = latest_hl

        latest_lh_map[
            pivot["index"]
        ] = latest_lh

    # --------------------------------------------------------
    # Chronological state machine.
    # --------------------------------------------------------

    for i, pivot in enumerate(
        external
    ):

        pivot_index = pivot[
            "index"
        ]

        # ====================================================
        # BULLISH
        # ====================================================

        if regime == "BULLISH":

            if pivot["kind"] == "HIGH":

                if (
                    pivot_index
                    in retired_highs
                ):
                    continue

                br = _find_break(
                    df,
                    pivot["price"],
                    "BULLISH",
                    pivot[
                        "confirmation_index"
                    ],
                    arrays=arrays,
                )

                if br is not None:

                    if (
                        br["index"]
                        - last_event_index
                        >= MIN_EVENT_GAP
                    ):

                        event = dict(br)

                        event[
                            "event"
                        ] = "BOS"

                        event[
                            "source_swing_index"
                        ] = pivot_index

                        event[
                            "source_swing_type"
                        ] = pivot["type"]

                        events.append(
                            event
                        )

                        retired_highs.add(
                            pivot_index
                        )

                        last_event_index = (
                            br["index"]
                        )

                        # Latest HL before BOS.
                        candidate = None

                        for x in reversed(
                            external[: i + 1]
                        ):

                            if (
                                x["kind"]
                                == "LOW"
                                and x["type"]
                                == "HL"
                                and x["index"]
                                < br["index"]
                            ):
                                candidate = x
                                break

                        protected_low = (
                            candidate
                        )

            # ------------------------------------------------
            # Protected HL break = CHoCH
            # ------------------------------------------------

            if (
                protected_low
                is not None
            ):

                br = _find_break(
                    df,
                    protected_low[
                        "price"
                    ],
                    "BEARISH",
                    protected_low[
                        "confirmation_index"
                    ],
                    arrays=arrays,
                )

                if br is not None:

                    if (
                        br["index"]
                        - last_event_index
                        >= MIN_EVENT_GAP
                    ):

                        event = dict(br)

                        event[
                            "event"
                        ] = "CHoCH"

                        event[
                            "source_swing_index"
                        ] = protected_low[
                            "index"
                        ]

                        event[
                            "source_swing_type"
                        ] = protected_low[
                            "type"
                        ]

                        events.append(
                            event
                        )

                        retired_lows.add(
                            protected_low[
                                "index"
                            ]
                        )

                        last_event_index = (
                            br["index"]
                        )

                        regime = (
                            "BEARISH"
                        )

                        protected_high = None
                        protected_low = None

        # ====================================================
        # BEARISH
        # ====================================================

        elif regime == "BEARISH":

            if pivot["kind"] == "LOW":

                if (
                    pivot_index
                    in retired_lows
                ):
                    continue

                br = _find_break(
                    df,
                    pivot["price"],
                    "BEARISH",
                    pivot[
                        "confirmation_index"
                    ],
                    arrays=arrays,
                )

                if br is not None:

                    if (
                        br["index"]
                        - last_event_index
                        >= MIN_EVENT_GAP
                    ):

                        event = dict(br)

                        event[
                            "event"
                        ] = "BOS"

                        event[
                            "source_swing_index"
                        ] = pivot_index

                        event[
                            "source_swing_type"
                        ] = pivot["type"]

                        events.append(
                            event
                        )

                        retired_lows.add(
                            pivot_index
                        )

                        last_event_index = (
                            br["index"]
                        )

                        # Latest LH before BOS.
                        candidate = None

                        for x in reversed(
                            external[: i + 1]
                        ):

                            if (
                                x["kind"]
                                == "HIGH"
                                and x["type"]
                                == "LH"
                                and x["index"]
                                < br["index"]
                            ):
                                candidate = x
                                break

                        protected_high = (
                            candidate
                        )

            # ------------------------------------------------
            # Protected LH break = CHoCH
            # ------------------------------------------------

            if (
                protected_high
                is not None
            ):

                br = _find_break(
                    df,
                    protected_high[
                        "price"
                    ],
                    "BULLISH",
                    protected_high[
                        "confirmation_index"
                    ],
                    arrays=arrays,
                )

                if br is not None:

                    if (
                        br["index"]
                        - last_event_index
                        >= MIN_EVENT_GAP
                    ):

                        event = dict(br)

                        event[
                            "event"
                        ] = "CHoCH"

                        event[
                            "source_swing_index"
                        ] = protected_high[
                            "index"
                        ]

                        event[
                            "source_swing_type"
                        ] = protected_high[
                            "type"
                        ]

                        events.append(
                            event
                        )

                        retired_highs.add(
                            protected_high[
                                "index"
                            ]
                        )

                        last_event_index = (
                            br["index"]
                        )

                        regime = (
                            "BULLISH"
                        )

                        protected_high = None
                        protected_low = None

        # ====================================================
        # INITIAL REGIME
        # ====================================================

        else:

            recent = external[
                max(0, i - 6):
                i + 1
            ]

            bullish = sum(
                x["type"]
                in ("HH", "HL")
                for x in recent
            )

            bearish = sum(
                x["type"]
                in ("LH", "LL")
                for x in recent
            )

            if (
                bullish > bearish
                and bullish >= 3
            ):

                regime = "BULLISH"

                candidate = None

                for x in reversed(
                    external[: i + 1]
                ):

                    if (
                        x["kind"]
                        == "LOW"
                        and x["type"]
                        == "HL"
                    ):
                        candidate = x
                        break

                protected_low = (
                    candidate
                )

            elif (
                bearish > bullish
                and bearish >= 3
            ):

                regime = "BEARISH"

                candidate = None

                for x in reversed(
                    external[: i + 1]
                ):

                    if (
                        x["kind"]
                        == "HIGH"
                        and x["type"]
                        == "LH"
                    ):
                        candidate = x
                        break

                protected_high = (
                    candidate
                )

    bos = [
        x
        for x in events
        if x["event"] == "BOS"
    ]

    choch = [
        x
        for x in events
        if x["event"] == "CHoCH"
    ]

    if events:

        latest = max(
            events,
            key=lambda x:
                x["index"],
        )

        regime = (
            "BULLISH"
            if latest["direction"]
            == "BULLISH"
            else
            "BEARISH"
            if latest["direction"]
            == "BEARISH"
            else regime
        )

    return (
        regime,
        bos,
        choch,
        protected_high,
        protected_low,
    )


# ============================================================
# CURRENT LEG RECONSTRUCTION
# ============================================================

def _reconstruct_current_protection(
    df: pd.DataFrame,
    external: list[dict[str, Any]],
    bias: str,
    last_bos: dict | None,
    last_choch: dict | None,
):

    if not external:
        return None, None

    _, _, close, atr = _prepare_arrays(df)

    current_index = len(df) - 1

    current_price = float(
        close[current_index]
    )

    current_atr = float(
        atr[current_index]
    )

    if (
        not math.isfinite(current_atr)
        or current_atr <= 0
    ):
        return None, None

    # --------------------------------------------------------
    # Find latest structural event.
    # --------------------------------------------------------

    candidates = []

    if last_bos is not None:
        candidates.append(last_bos)

    if last_choch is not None:
        candidates.append(last_choch)

    last_event = None

    if candidates:
        last_event = max(
            candidates,
            key=lambda x: x["index"],
        )

    event_index = (
        last_event["index"]
        if last_event is not None
        else 0
    )

    # --------------------------------------------------------
    # Only confirmed swings belonging to the current leg.
    # --------------------------------------------------------

    recent = [
        x
        for x in external
        if (
            x["confirmation_index"]
            <= current_index
            and x["index"]
            >= event_index
        )
    ]

    # If current leg has no confirmed swing,
    # use the latest confirmed structural context.
    if not recent:

        confirmed = [
            x
            for x in external
            if (
                x["confirmation_index"]
                <= current_index
            )
        ]

        recent = confirmed[-12:]

    # ========================================================
    # BULLISH STRUCTURE
    # ========================================================

    if bias == "BULLISH":

        # Bullish protection MUST be an HL.
        hl_candidates = [
            x
            for x in recent
            if (
                x["kind"] == "LOW"
                and x["type"] == "HL"
            )
        ]

        if not hl_candidates:
            return None, None

        candidate = max(
            hl_candidates,
            key=lambda x: x["index"],
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Bullish protected HL must be BELOW
        # current market price.
        # ----------------------------------------------------

        if candidate["price"] >= current_price:
            return None, None

        distance = abs(
            candidate["price"]
            - current_price
        )

        distance_atr = (
            distance
            / current_atr
        )

        if (
            distance_atr
            > MAX_PROTECTED_DISTANCE_ATR
        ):
            return None, None

        protected_low = dict(
            candidate
        )

        protected_low[
            "distance_from_price"
        ] = round(
            distance,
            5,
        )

        protected_low[
            "distance_atr"
        ] = round(
            distance_atr,
            3,
        )

        protected_low[
            "status"
        ] = "PROTECTED"

        protected_low[
            "protection_role"
        ] = "BULLISH_INVALIDATION"

        return None, protected_low

    # ========================================================
    # BEARISH STRUCTURE
    # ========================================================

    if bias == "BEARISH":

        # Bearish protection MUST be an LH.
        lh_candidates = [
            x
            for x in recent
            if (
                x["kind"] == "HIGH"
                and x["type"] == "LH"
            )
        ]

        if not lh_candidates:
            return None, None

        candidate = max(
            lh_candidates,
            key=lambda x: x["index"],
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Bearish protected LH must be ABOVE
        # current market price.
        # ----------------------------------------------------

        if candidate["price"] <= current_price:
            return None, None

        distance = abs(
            candidate["price"]
            - current_price
        )

        distance_atr = (
            distance
            / current_atr
        )

        if (
            distance_atr
            > MAX_PROTECTED_DISTANCE_ATR
        ):
            return None, None

        protected_high = dict(
            candidate
        )

        protected_high[
            "distance_from_price"
        ] = round(
            distance,
            5,
        )

        protected_high[
            "distance_atr"
        ] = round(
            distance_atr,
            3,
        )

        protected_high[
            "status"
        ] = "PROTECTED"

        protected_high[
            "protection_role"
        ] = "BEARISH_INVALIDATION"

        return protected_high, None

    return None, None

# ============================================================
# INTERNAL BOS - OPTIMIZED
# ============================================================

def _internal_structure_events(
    df: pd.DataFrame,
    internal: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if not internal:
        return []

    arrays = _prepare_arrays(
        df
    )

    events = []

    retired_highs = set()
    retired_lows = set()

    last_event_index = -10_000

    # --------------------------------------------------------
    # Previous same-kind pivot map.
    #
    # Old version repeatedly searched the entire list.
    # --------------------------------------------------------

    previous_same = {}

    last_high = None
    last_low = None

    for pivot in internal:

        idx = pivot["index"]

        if pivot["kind"] == "HIGH":

            previous_same[idx] = (
                last_high
            )

            last_high = pivot

        else:

            previous_same[idx] = (
                last_low
            )

            last_low = pivot

    # --------------------------------------------------------
    # Process pivots.
    # --------------------------------------------------------

    for pivot in internal:

        pivot_index = pivot[
            "index"
        ]

        previous = previous_same.get(
            pivot_index
        )

        if previous is not None:

            if (
                pivot_index
                - previous["index"]
                < MIN_INTERNAL_PIVOT_GAP
            ):
                continue

        if pivot["kind"] == "HIGH":

            if (
                pivot_index
                in retired_highs
            ):
                continue

            br = _find_break(
                df,
                pivot["price"],
                "BULLISH",
                pivot[
                    "confirmation_index"
                ],
                buffer_atr=(
                    INTERNAL_BREAK_BUFFER_ATR
                ),
                min_displacement=(
                    MIN_INTERNAL_BOS_DISPLACEMENT_ATR
                ),
                arrays=arrays,
            )

            if br is None:
                continue

            if (
                br["index"]
                - last_event_index
                < MIN_INTERNAL_EVENT_GAP
            ):
                continue

            event = dict(br)

            event[
                "event"
            ] = "INTERNAL_BOS"

            event[
                "source_swing_index"
            ] = pivot_index

            event[
                "source_swing_type"
            ] = pivot["type"]

            events.append(
                event
            )

            retired_highs.add(
                pivot_index
            )

            last_event_index = (
                br["index"]
            )

        else:

            if (
                pivot_index
                in retired_lows
            ):
                continue

            br = _find_break(
                df,
                pivot["price"],
                "BEARISH",
                pivot[
                    "confirmation_index"
                ],
                buffer_atr=(
                    INTERNAL_BREAK_BUFFER_ATR
                ),
                min_displacement=(
                    MIN_INTERNAL_BOS_DISPLACEMENT_ATR
                ),
                arrays=arrays,
            )

            if br is None:
                continue

            if (
                br["index"]
                - last_event_index
                < MIN_INTERNAL_EVENT_GAP
            ):
                continue

            event = dict(br)

            event[
                "event"
            ] = "INTERNAL_BOS"

            event[
                "source_swing_index"
            ] = pivot_index

            event[
                "source_swing_type"
            ] = pivot["type"]

            events.append(
                event
            )

            retired_lows.add(
                pivot_index
            )

            last_event_index = (
                br["index"]
            )

    events.sort(
        key=lambda x:
            x["index"]
    )

    return events


# ============================================================
# INTERNAL BIAS
# ============================================================

def _internal_bias(
    internal: list[dict[str, Any]],
) -> str:

    recent = internal[-12:]

    if not recent:
        return "NEUTRAL"

    bullish = sum(
        x["type"]
        in ("HH", "HL")
        for x in recent
    )

    bearish = sum(
        x["type"]
        in ("LH", "LL")
        for x in recent
    )

    if bullish > bearish:
        return "BULLISH"

    if bearish > bullish:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# STRUCTURE STRENGTH
# ============================================================

def _structure_strength(
    bias: str,
    external: list[dict[str, Any]],
    internal: list[dict[str, Any]],
    bos: list[dict[str, Any]],
    choch: list[dict[str, Any]],
    protected_high: dict | None,
    protected_low: dict | None,
    current_index: int,
) -> float:

    if bias == "NEUTRAL":
        return 0.0

    score = 0.0

    if len(external) >= 3:
        score += 15

    if len(external) >= 6:
        score += 10

    if len(external) >= 10:
        score += 5

    if len(internal) >= 5:
        score += 5

    recent_bos = [
        x
        for x in bos
        if (
            current_index
            - x["index"]
            <= 300
        )
    ]

    if recent_bos:

        latest_bos = recent_bos[-1]

        if (
            latest_bos["direction"]
            == bias
        ):
            score += 20
        else:
            score += 5

    recent_choch = [
        x
        for x in choch
        if (
            current_index
            - x["index"]
            <= 150
        )
    ]

    if recent_choch:

        latest_choch = (
            recent_choch[-1]
        )

        if (
            latest_choch["direction"]
            == bias
        ):
            score += 10
        else:
            score += 3

    protection = (
        protected_low
        if bias == "BULLISH"
        else protected_high
    )

    if protection is not None:

        distance_atr = _safe_float(
            protection.get(
                "distance_atr",
                999,
            ),
            999,
        )

        if distance_atr <= 3:
            score += 35

        elif distance_atr <= 5:
            score += 25

        elif distance_atr <= 8:
            score += 12

    return round(
        min(score, 100.0),
        2,
    )


# ============================================================
# PUBLIC ANALYSIS
# ============================================================

def analyze_structure(
    df: pd.DataFrame,
    left: int = SWING_LEFT,
    right: int = SWING_RIGHT,
) -> dict[str, Any]:

    required = {
        "open",
        "high",
        "low",
        "close",
    }

    missing = (
        required
        - set(df.columns)
    )

    if missing:

        return {
            "bias": "NEUTRAL",
            "external_bias": "NEUTRAL",
            "internal_bias": "NEUTRAL",
            "transition": "NEUTRAL",
            "strength": 0.0,
            "swings": [],
            "external_swings": [],
            "internal_swings": [],
            "bos": [],
            "choch": [],
            "internal_bos": [],
            "protected_high": None,
            "protected_low": None,
            "last_swing": None,
            "last_bos": None,
            "last_choch": None,
            "last_event": None,
            "current_structure": {},
            "error": (
                "Missing columns: "
                + ", ".join(
                    sorted(missing)
                )
            ),
        }

    if len(df) < (
        left
        + right
        + 30
    ):

        return {
            "bias": "NEUTRAL",
            "external_bias": "NEUTRAL",
            "internal_bias": "NEUTRAL",
            "transition": "NEUTRAL",
            "strength": 0.0,
            "swings": [],
            "external_swings": [],
            "internal_swings": [],
            "bos": [],
            "choch": [],
            "internal_bos": [],
            "protected_high": None,
            "protected_low": None,
            "last_swing": None,
            "last_bos": None,
            "last_choch": None,
            "last_event": None,
            "current_structure": {},
            "error": "Insufficient data.",
        }

    d = df.copy()

    # ========================================================
    # Prepare ATR once.
    # ========================================================

    high, low, close, atr = (
        _prepare_arrays(d)
    )

    if "atr" not in d.columns:

        d["atr"] = atr

    else:

        # Replace invalid ATR values only.
        existing_atr = (
            pd.to_numeric(
                d["atr"],
                errors="coerce",
            ).to_numpy(
                dtype=float
            )
        )

        existing_atr = np.where(
            (
                np.isfinite(
                    existing_atr
                )
                & (
                    existing_atr
                    > 0
                )
            ),
            existing_atr,
            atr,
        )

        d["atr"] = existing_atr

    # ========================================================
    # SWINGS
    # ========================================================

    raw = _raw_pivots(
        d,
        left,
        right,
    )

    cleaned = _clean_pivots(
        d,
        raw,
    )

    swings_list = _classify_swings(
        cleaned
    )

    # ========================================================
    # EXTERNAL / INTERNAL
    # ========================================================

    external = (
        _select_external_swings(
            d,
            swings_list,
        )
    )

    internal = (
        _select_internal_swings(
            swings_list,
            external,
        )
    )

    # ========================================================
    # EXTERNAL STATE
    # ========================================================

    (
        external_bias,
        bos,
        choch,
        protected_high,
        protected_low,
    ) = _external_state_machine(
        d,
        external,
    )

    last_bos = (
        bos[-1]
        if bos
        else None
    )

    last_choch = (
        choch[-1]
        if choch
        else None
    )

    # ========================================================
    # CURRENT LEG PROTECTION
    # ========================================================

    (
        reconstructed_high,
        reconstructed_low,
    ) = _reconstruct_current_protection(
        d,
        external,
        external_bias,
        last_bos,
        last_choch,
    )

    protected_high = (
        reconstructed_high
    )

    protected_low = (
        reconstructed_low
    )

    # ========================================================
    # INTERNAL BOS
    # ========================================================

    internal_bos = (
        _internal_structure_events(
            d,
            internal,
        )
    )

    internal_bias = (
        _internal_bias(
            internal
        )
    )

    # ========================================================
    # FINAL BIAS
    # ========================================================

    if external_bias in (
        "BULLISH",
        "BEARISH",
    ):

        bias = external_bias

    else:

        bias = internal_bias

    # ========================================================
    # TRANSITION
    # ========================================================

    if last_choch is not None:

        transition = (
            last_choch[
                "direction"
            ]
        )

    else:

        transition = bias

    # ========================================================
    # ALL EVENTS
    # ========================================================

    all_events = []

    for event in bos:

        e = dict(event)

        e["event"] = "BOS"

        all_events.append(e)

    for event in choch:

        e = dict(event)

        e["event"] = "CHoCH"

        all_events.append(e)

    all_events.sort(
        key=lambda x:
            x["index"]
    )

    last_event = (
        all_events[-1]
        if all_events
        else None
    )

    # ========================================================
    # CURRENT MARKET
    # ========================================================

    current_index = (
        len(d) - 1
    )

    current_price = float(
        close[current_index]
    )

    current_atr = float(
        atr[current_index]
    )

    if bias == "BULLISH":

        active_protection = (
            protected_low
        )

    elif bias == "BEARISH":

        active_protection = (
            protected_high
        )

    else:

        active_protection = None

    protection_status = (
        "CURRENT_PROTECTED_LEVEL"
        if active_protection
        is not None
        else
        "NO_CURRENT_PROTECTED_LEVEL"
    )

    # ========================================================
    # CURRENT LEG START
    # ========================================================

    current_leg_start = (
        last_event["index"]
        if last_event is not None
        else (
            external[-1]["index"]
            if external
            else None
        )
    )

    # ========================================================
    # STRENGTH
    # ========================================================

    strength = (
        _structure_strength(
            bias=bias,
            external=external,
            internal=internal,
            bos=bos,
            choch=choch,
            protected_high=(
                protected_high
            ),
            protected_low=(
                protected_low
            ),
            current_index=current_index,
        )
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    return {

        "bias": bias,

        "external_bias": (
            external_bias
        ),

        "internal_bias": (
            internal_bias
        ),

        "transition": transition,

        "strength": strength,

        "swings": swings_list,

        "external_swings": (
            external
        ),

        "internal_swings": (
            internal
        ),

        "swing_count": len(
            swings_list
        ),

        "external_swing_count": len(
            external
        ),

        "internal_swing_count": len(
            internal
        ),

        "bos": bos,

        "choch": choch,

        "internal_bos": (
            internal_bos
        ),

        "bos_count": len(
            bos
        ),

        "choch_count": len(
            choch
        ),

        "internal_bos_count": len(
            internal_bos
        ),

        "last_swing": (
            swings_list[-1]
            if swings_list
            else None
        ),

        "last_bos": last_bos,

        "last_choch": last_choch,

        "last_event": last_event,

        "protected_high": (
            protected_high
        ),

        "protected_low": (
            protected_low
        ),

        "current_structure": {

            "regime": bias,

            "external_regime": (
                external_bias
            ),

            "internal_regime": (
                internal_bias
            ),

            "transition": transition,

            "current_index": (
                current_index
            ),

            "current_price": (
                current_price
            ),

            "current_atr": (
                current_atr
            ),

            "current_leg_start": (
                current_leg_start
            ),

            "protection_status": (
                protection_status
            ),

            "protected_level": (
                active_protection
            ),

            "last_structural_event": (
                last_event
            ),
        },

        "methodology": {

            "engine": (
                "Market Structure Engine V4.16"
            ),

            "optimization": (
                "Cached arrays + vectorized "
                "pivot and break detection"
            ),

            "swing_left": left,

            "swing_right": right,

            "confirmed_swings_only": True,

            "external_structure": True,

            "internal_structure": True,

            "bos": (
                "Close-based structural break "
                "with ATR displacement filter"
            ),

            "choch": (
                "Protected HL/LH structural "
                "level break"
            ),

            "bullish_protection": (
                "HL only"
            ),

            "bearish_protection": (
                "LH only"
            ),

            "current_leg_reconstruction": True,

            "internal_bos_filter": True,

            "max_current_protection_distance_atr": (
                MAX_PROTECTED_DISTANCE_ATR
            ),

            "prediction": False,

            "lookahead_on_completed_history": False,
        },
    }


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def swings(
    df: pd.DataFrame,
    left: int = SWING_LEFT,
    right: int = SWING_RIGHT,
):

    pivots = _raw_pivots(
        df,
        left,
        right,
    )

    high_indices = [
        x["index"]
        for x in pivots
        if x["kind"] == "HIGH"
    ]

    low_indices = [
        x["index"]
        for x in pivots
        if x["kind"] == "LOW"
    ]

    return (
        high_indices,
        low_indices,
    )