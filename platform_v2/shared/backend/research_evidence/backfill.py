"""Bounded-page candle recovery, never synthetic decisions or orderflow recovery."""
from __future__ import annotations

from urllib.parse import urlencode
from .runtime import ACTIVE, acquisition_origin


def interval_ms(timeframe):
    units = {'m':60000,'h':3600000,'d':86400000}
    value = int(timeframe[:-1]) * units[timeframe[-1]]
    if value <= 0:
        raise ValueError(timeframe)
    return value


def fetch_closed_range(client, endpoint, *, symbol, timeframe, start_open_ms, end_open_ms, limit=500):
    """Inclusive open-time range. Return only verified contiguous closed pages.

    Empty, short, duplicate/nonadvancing, malformed or gapped responses raise;
    partial pages are still acquisition evidence, not falsely marked complete.
    Caller must bound end_open_ms to an already closed candle.
    """
    step = interval_ms(timeframe)
    if not 1 <= limit <= 500 or start_open_ms % step or end_open_ms % step:
        raise ValueError('unaligned recovery range or invalid page limit')
    from .ledger import now_ms
    if end_open_ms + step > now_ms():
        raise ValueError('recovery endpoint is not closed')
    cursor = start_open_ms
    result = []
    with acquisition_origin('BACKFILLED'):
        while cursor <= end_open_ms:
            page_end = min(end_open_ms, cursor+(limit-1)*step)
            count = (page_end-cursor)//step+1
            url = endpoint+'?'+urlencode({'symbol':symbol,'interval':timeframe,
                'startTime':cursor,'endTime':page_end+step-1,'limit':limit})
            payload = client.get_json(url)
            if not isinstance(payload,list) or len(payload) != count:
                raise ValueError('incomplete candle recovery page')
            for index,row in enumerate(payload):
                expected = cursor+index*step
                if not isinstance(row,list) or len(row)<7 or int(row[0]) != expected or int(row[6]) != expected+step-1:
                    raise ValueError('gapped or malformed candle recovery page')
            result.extend(payload)
            cursor = page_end+step
    return result


def recover_missing_tail(client, endpoint, *, existing, current, symbol, timeframe):
    """Opt-in recovery of trailing AND internal missing closed-candle ranges."""
    import os
    attempt = ACTIVE.get()
    if not attempt or os.environ.get('SSH_RESEARCH_BACKFILL') != '1' or not current:
        return []
    step = interval_ms(timeframe)
    known = sorted({int(row['timestamp']) for row in existing+current})
    if not existing and os.environ.get('SSH_RESEARCH_ACTIVATION_CLOSE_MS'):
        epoch_open = int(os.environ['SSH_RESEARCH_ACTIVATION_CLOSE_MS'])+1-900000
        first = epoch_open//step*step
        if first < known[0]:
            known.insert(0, first-step)
    ranges = [(left+step,right-step) for left,right in zip(known,known[1:]) if right-left>step]
    recovered = []
    for start,end in ranges:
        try:
            rows = fetch_closed_range(client,endpoint,symbol=symbol,timeframe=timeframe,
                                      start_open_ms=start,end_open_ms=end)
        except Exception as exc:
            attempt.safe(attempt.event,'market_acquisition_events','BACKFILL_INCOMPLETE',
                {'symbol':symbol,'timeframe':timeframe,'start_open_ms':start,'end_open_ms':end,
                 'error_type':type(exc).__name__,'origin':'BACKFILLED'})
            continue
        recovered.extend(rows)
        attempt.safe(attempt.event,'market_acquisition_events','BACKFILL_COMPLETE',
            {'symbol':symbol,'timeframe':timeframe,'start_open_ms':start,'end_open_ms':end,
             'count':len(rows),'origin':'BACKFILLED'})
    return recovered
