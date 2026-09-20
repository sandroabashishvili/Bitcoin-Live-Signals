"""Domain-neutral indicator series calculations shared by Spot and Futures."""

from __future__ import annotations

from math import fabs


def ema_series(values: list[float], period: int) -> list[float | None]:
    series: list[float | None] = []
    multiplier = 2 / (period + 1)
    ema_value: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period:
            series.append(None)
            continue
        if ema_value is None:
            ema_value = sum(values[index + 1 - period : index + 1]) / period
        else:
            ema_value = ((value - ema_value) * multiplier) + ema_value
        series.append(ema_value)
    return series


def rsi_series(closes: list[float], period: int) -> list[float | None]:
    series: list[float | None] = [None]
    gains: list[float] = []
    losses: list[float] = []
    avg_gain: float | None = None
    avg_loss: float | None = None

    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

        if index < period:
            series.append(None)
            continue

        if avg_gain is None or avg_loss is None:
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
        else:
            avg_gain = ((avg_gain * (period - 1)) + gains[-1]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[-1]) / period

        if avg_loss == 0:
            series.append(100.0)
            continue

        rs = avg_gain / avg_loss
        series.append(100 - (100 / (1 + rs)))

    return series


def atr_series(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float | None]:
    true_ranges: list[float] = []
    for index in range(len(closes)):
        if index == 0:
            tr = highs[index] - lows[index]
        else:
            tr = max(
                highs[index] - lows[index],
                fabs(highs[index] - closes[index - 1]),
                fabs(lows[index] - closes[index - 1]),
            )
        true_ranges.append(tr)

    series: list[float | None] = []
    atr_value: float | None = None
    for index, tr in enumerate(true_ranges):
        if index + 1 < period:
            series.append(None)
            continue
        if atr_value is None:
            atr_value = sum(true_ranges[index + 1 - period : index + 1]) / period
        else:
            atr_value = ((atr_value * (period - 1)) + tr) / period
        series.append(atr_value)
    return series


def macd_series(closes: list[float]) -> tuple[list[float | None], list[float | None]]:
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    macd_line: list[float | None] = []
    for fast, slow in zip(ema12, ema26):
        if fast is None or slow is None:
            macd_line.append(None)
        else:
            macd_line.append(fast - slow)

    signal_series: list[float | None] = []
    multiplier = 2 / (9 + 1)
    signal_value: float | None = None
    macd_values_only: list[float] = []
    for value in macd_line:
        if value is None:
            signal_series.append(None)
            continue
        macd_values_only.append(value)
        if len(macd_values_only) < 9:
            signal_series.append(None)
            continue
        if signal_value is None:
            signal_value = sum(macd_values_only[-9:]) / 9
        else:
            signal_value = ((value - signal_value) * multiplier) + signal_value
        signal_series.append(signal_value)
    return macd_line, signal_series


def adx_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    tr_list: list[float] = []
    plus_dm_list: list[float] = [0.0]
    minus_dm_list: list[float] = [0.0]

    for index in range(len(closes)):
        if index == 0:
            tr_list.append(highs[index] - lows[index])
            continue
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_dm_list.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm_list.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        tr_list.append(
            max(
                highs[index] - lows[index],
                fabs(highs[index] - closes[index - 1]),
                fabs(lows[index] - closes[index - 1]),
            )
        )

    adx_values: list[float | None] = []
    plus_di_values: list[float | None] = []
    minus_di_values: list[float | None] = []
    dx_values: list[float] = []
    smoothed_tr: float | None = None
    smoothed_plus_dm: float | None = None
    smoothed_minus_dm: float | None = None
    adx_value: float | None = None

    for index in range(len(closes)):
        if index + 1 < period:
            adx_values.append(None)
            plus_di_values.append(None)
            minus_di_values.append(None)
            continue

        if smoothed_tr is None:
            smoothed_tr = sum(tr_list[index + 1 - period : index + 1])
            smoothed_plus_dm = sum(plus_dm_list[index + 1 - period : index + 1])
            smoothed_minus_dm = sum(minus_dm_list[index + 1 - period : index + 1])
        else:
            assert smoothed_plus_dm is not None
            assert smoothed_minus_dm is not None
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_list[index]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm_list[index]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm_list[index]

        if not smoothed_tr:
            plus_di = 0.0
            minus_di = 0.0
        else:
            plus_di = (smoothed_plus_dm / smoothed_tr) * 100
            minus_di = (smoothed_minus_dm / smoothed_tr) * 100

        plus_di_values.append(plus_di)
        minus_di_values.append(minus_di)

        di_sum = plus_di + minus_di
        dx = 0.0 if di_sum == 0 else (fabs(plus_di - minus_di) / di_sum) * 100
        dx_values.append(dx)

        if len(dx_values) < period:
            adx_values.append(None)
            continue
        if adx_value is None:
            adx_value = sum(dx_values[-period:]) / period
        else:
            adx_value = ((adx_value * (period - 1)) + dx) / period
        adx_values.append(adx_value)

    return adx_values, plus_di_values, minus_di_values


def atr_spike_threshold(series: list[float | None], index: int, multiplier: float) -> float | None:
    if index <= 0:
        return None
    start = max(0, index - 7)
    previous_values = [value for value in series[start:index] if value is not None]
    if len(previous_values) < 3:
        return None
    ordered = sorted(previous_values)
    mid = len(ordered) // 2
    median = (ordered[mid - 1] + ordered[mid]) / 2.0 if len(ordered) % 2 == 0 else ordered[mid]
    return median * multiplier


def macd_trend(macd: float | None, signal: float | None) -> str | None:
    if macd is None or signal is None:
        return None
    return "Bullish" if macd >= signal else "Bearish"


def macd_histogram(macd_line: list[float | None], signal_line: list[float | None], index: int) -> list[float]:
    values: list[float] = []
    start = max(0, index - 2)
    for item_index in range(start, index + 1):
        macd = macd_line[item_index]
        signal = signal_line[item_index]
        if macd is None or signal is None:
            continue
        values.append(round(macd - signal, 5))
    return values


def atr_spike(atr: float | None, prev_atr: float | None) -> bool | None:
    if atr is None or prev_atr is None or prev_atr <= 0:
        return None
    return atr > prev_atr * 1.2


def ema_slope(series: list[float | None], index: int) -> float | None:
    if index == 0:
        return None
    current = series[index]
    previous = series[index - 1]
    if current is None or previous is None:
        return None
    return round(current - previous, 5)


def adx_slope(adx: float | None, prev_adx: float | None) -> float | None:
    if adx is None or prev_adx is None:
        return None
    return round(adx - prev_adx, 5)


def atr_growth_20(series: list[float | None], index: int) -> float | None:
    if index < 20:
        return None
    current = series[index]
    baseline = series[index - 20]
    if current is None or baseline is None or baseline == 0:
        return None
    return round((current - baseline) / baseline, 5)
