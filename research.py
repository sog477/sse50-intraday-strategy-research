"""Prespecified single-day microstructure study; no parameter search or PnL claim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit import stamp_ms
from orderbook import dataset_date


def lookup(times: np.ndarray, targets: np.ndarray) -> np.ndarray:
    return np.searchsorted(times, targets, side='right') - 1


def clustered_difference(frame: pd.DataFrame, group: str, a: str, b: str, outcome: str) -> dict:
    """Equal-weight stock effects, crossed stock / clock-block bootstrap.

    This quantifies within-day uncertainty only, not independent-day evidence.
    """
    subset = frame[frame[group].isin([a, b])].dropna(subset=[outcome]).copy()
    if subset.empty:
        return {'groups': [a, b], 'stocks': 0}
    symbols = sorted(subset.symbol.unique())
    blocks = sorted(subset.clock_block.unique())
    symbol_index = {s: i for i, s in enumerate(symbols)}
    block_index = {s: i for i, s in enumerate(blocks)}
    sums = np.zeros((2, len(symbols), len(blocks)))
    counts = np.zeros_like(sums)
    for (label, symbol, block), part in subset.groupby([group, 'symbol', 'clock_block']):
        index = 0 if label == a else 1
        sums[index, symbol_index[symbol], block_index[block]] = part[outcome].sum()
        counts[index, symbol_index[symbol], block_index[block]] = len(part)
    aggregate_n = counts.sum(axis=2)
    eligible = (aggregate_n[0] >= 5) & (aggregate_n[1] >= 5)
    if not eligible.any():
        return {'groups': [a, b], 'stocks': 0, 'observations': len(subset)}
    means = sums.sum(axis=2) / np.maximum(aggregate_n, 1)
    effect = float((means[0, eligible] - means[1, eligible]).mean())
    rng = np.random.default_rng(20260923)
    simulated = []
    for _ in range(1000):
        stock_weights = rng.multinomial(len(symbols), np.ones(len(symbols)) / len(symbols))
        block_weights = rng.multinomial(len(blocks), np.ones(len(blocks)) / len(blocks))
        den = counts @ block_weights
        avg = (sums @ block_weights) / np.maximum(den, 1)
        good = eligible & (den[0] > 0) & (den[1] > 0) & (stock_weights > 0)
        if good.any():
            simulated.append(np.average(avg[0, good] - avg[1, good], weights=stock_weights[good]))
    return {'groups': [a, b], 'stocks': int(eligible.sum()), 'observations': len(subset),
            'eligible_observations': int(counts[:, eligible, :].sum()),
            'equal_stock_mean_a': float(means[0, eligible].mean()),
            'equal_stock_mean_b': float(means[1, eligible].mean()),
            'difference_a_minus_b': effect,
            'within_day_95pct_interval': np.quantile(simulated, [.025, .975]).tolist()}


def prepare(data: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    date = dataset_date(data)
    quotes = pd.read_parquet(data / f'snp_{date}.parquet', columns=[
        'Symbol', 'Time', 'BidPrice1', 'AskPrice1', 'BidVolume1', 'AskVolume1', 'AccVolume'])
    raw_records = len(quotes)
    quotes['ms'] = quotes.Time.map(stamp_ms)
    quotes['session'] = np.select([
        (quotes.Time >= 93000000) & (quotes.Time < 113000000),
        (quotes.Time >= 130000000) & (quotes.Time < 145700000)], [0, 1], default=-1)
    quotes['bid'] = np.rint(quotes.BidPrice1.astype(float) * 100).astype(int)
    quotes['ask'] = np.rint(quotes.AskPrice1.astype(float) * 100).astype(int)
    valid = (quotes.session >= 0) & (quotes.bid > 0) & (quotes.ask > quotes.bid)
    valid &= (quotes.BidVolume1 > 0) & (quotes.AskVolume1 > 0)
    quotes = quotes[valid].sort_values(['Symbol', 'ms']).copy()
    quotes['mid'] = (quotes.bid + quotes.ask) / 200
    quotes['spread_ticks'] = quotes.ask - quotes.bid
    quotes['spread_bp'] = (quotes.ask - quotes.bid) / 100 / quotes.mid * 10000
    quotes['obi'] = (quotes.BidVolume1 - quotes.AskVolume1) / (quotes.BidVolume1 + quotes.AskVolume1)
    quotes['l1_depth_shares'] = quotes.BidVolume1 + quotes.AskVolume1
    quotes['l1_depth_value'] = quotes.l1_depth_shares * quotes.mid
    # These blocks use clock time. They preserve contemporaneous market-wide dependence.
    quotes['clock_block'] = quotes.ms // 600000
    quotes['half_hour'] = quotes.ms // 1800000
    quotes.attrs['raw_records'] = raw_records
    trades = pd.read_parquet(data / f'exe_{date}.parquet', columns=['Symbol', 'Time', 'Volume', 'BSFlag'])
    trades['ms'] = trades.Time.map(stamp_ms)
    return quotes, trades


def features(quotes: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    all_rows = []
    trade_groups = {symbol: group.sort_values('ms') for symbol, group in trades.groupby('Symbol')}
    for symbol, stock in quotes.groupby('Symbol'):
        # Snapshot timestamp anomaly excluded by audit, before observing outcomes.
        if symbol == 601166:
            continue
        tape = trade_groups[symbol]
        trade_times = tape.ms.to_numpy()
        buys = np.r_[0, np.cumsum(np.where(tape.BSFlag.to_numpy() == 66, tape.Volume, 0), dtype=np.int64)]
        sells = np.r_[0, np.cumsum(np.where(tape.BSFlag.to_numpy() == 83, tape.Volume, 0), dtype=np.int64)]
        total = np.r_[0, np.cumsum(tape.Volume.to_numpy(), dtype=np.int64)]
        for session, part in stock.groupby('session'):
            part = part.copy()
            times = part.ms.to_numpy()
            mids = part.mid.to_numpy()
            n = len(part)
            future = lookup(times, times + 30000)
            past = lookup(times, times - 30000)
            valid_future = (times[future] - times >= 26000) & (times[future] - times <= 30000)
            valid_past = (past >= 0) & (times - times[np.maximum(past, 0)] <= 34000)
            forward = (mids[future] / mids - 1) * 10000
            backward = (mids / mids[np.maximum(past, 0)] - 1) * 10000
            returns = np.r_[0., np.diff(np.log(mids)) * 10000]
            squared = np.cumsum(returns ** 2)
            future_rv = np.sqrt(np.maximum(0, squared[future] - squared))
            previous_rv = np.sqrt(np.maximum(0, squared - squared[np.maximum(past, 0)]))
            indices_now = np.searchsorted(trade_times, times, side='right')
            indices_prev = np.searchsorted(trade_times, times - 30000, side='right')
            indices_base = np.searchsorted(trade_times, times - 330000, side='right')
            vol30 = total[indices_now] - total[indices_prev]
            baseline = (total[indices_prev] - total[indices_base]) / 10
            buy30 = buys[indices_now] - buys[indices_prev]
            sell30 = sells[indices_now] - sells[indices_prev]
            flow = np.divide(buy30 - sell30, buy30 + sell30, out=np.zeros(n), where=(buy30 + sell30) > 0)
            shock = np.divide(vol30, baseline, out=np.full(n, np.nan), where=baseline > 0)
            # Sampling uses only the clock: at least 30s apart within each stock/session.
            keep = []
            next_time = -1
            for i, time in enumerate(times):
                if time >= next_time and valid_future[i]:
                    keep.append(i)
                    next_time = time + 30000
            part['future30_bp'] = np.where(valid_future, forward, np.nan)
            part['previous30_bp'] = np.where(valid_past, backward, np.nan)
            part['future_rv30_bp'] = np.where(valid_future, future_rv, np.nan)
            part['previous_rv30_bp'] = np.where(valid_past, previous_rv, np.nan)
            part['vol30'] = vol30
            part['volume_shock'] = np.where(times - times[0] >= 330000, shock, np.nan)
            part['flow30'] = flow
            part['signed_future30_bp'] = np.sign(flow) * forward
            part['directional_impact_ticks'] = np.where(valid_past, np.sign(flow) * (mids - mids[np.maximum(past, 0)]) * 100, np.nan)
            part['obi_bucket'] = np.select([part.obi >= .8, part.obi <= -.8], ['buy-heavy', 'sell-heavy'], default='other')
            part['shock_bucket'] = np.select([part.volume_shock >= 3, part.volume_shock.between(.5, 1.5)], ['shock>=3', 'normal0.5-1.5'], default='other')
            candidate = (np.abs(flow) >= .6) & (part.volume_shock >= 2)
            part['absorption_bucket'] = np.select([
                candidate & (part.directional_impact_ticks <= 0),
                candidate & (part.directional_impact_ticks >= 1)], ['no-progress', 'progress>=1tick'], default='other')
            part['up'] = (part.future30_bp > 0).astype(float)
            part['down'] = (part.future30_bp < 0).astype(float)
            part['reverse'] = (part.signed_future30_bp < 0).astype(float)
            part['symbol'] = symbol
            all_rows.append(part.iloc[keep].copy())
        print(f'research {symbol}', flush=True)
    return pd.concat(all_rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('sse50_20260923'))
    parser.add_argument('--out', type=Path, default=Path('reports/research'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    quotes, trades = prepare(args.data)
    sample = features(quotes, trades)
    sample.to_parquet(args.out / 'sample_features.parquet', index=False)
    descriptive = []
    for period, subset in [('morning', sample[sample.session == 0]), ('afternoon', sample[sample.session == 1])]:
        for grouping, outcome in [('obi_bucket', 'future30_bp'), ('shock_bucket', 'future_rv30_bp'), ('absorption_bucket', 'signed_future30_bp')]:
            for label, group in subset.groupby(grouping):
                descriptive.append({'period': period, 'grouping': grouping, 'group': label,
                                    'n': len(group), 'stocks': group.symbol.nunique(),
                                    'outcome_mean_bp': group[outcome].mean(), 'outcome_median_bp': group[outcome].median(),
                                    'up_probability': group.up.mean(), 'down_probability': group.down.mean(),
                                    'reverse_probability': group.reverse.mean(), 'spread_median_bp': group.spread_bp.median()})
    pd.DataFrame(descriptive).to_csv(args.out / 'conditional_results.csv', index=False, encoding='utf-8-sig')
    comparisons = {}
    for period, subset in [('morning', sample[sample.session == 0]), ('afternoon', sample[sample.session == 1])]:
        comparisons[period] = {
            'obi_return': clustered_difference(subset, 'obi_bucket', 'buy-heavy', 'sell-heavy', 'future30_bp'),
            'obi_up_probability': clustered_difference(subset, 'obi_bucket', 'buy-heavy', 'sell-heavy', 'up'),
            'volume_shock_volatility': clustered_difference(subset, 'shock_bucket', 'shock>=3', 'normal0.5-1.5', 'future_rv30_bp'),
            'volume_shock_previous_volatility': clustered_difference(subset, 'shock_bucket', 'shock>=3', 'normal0.5-1.5', 'previous_rv30_bp'),
            'absorption_signed_return': clustered_difference(subset, 'absorption_bucket', 'no-progress', 'progress>=1tick', 'signed_future30_bp')}
    spread = quotes.groupby(['Symbol', 'half_hour']).spread_bp.median().groupby('half_hour').agg(['median', 'mean', 'min', 'max']).reset_index()
    spread['label'] = spread.half_hour.map(lambda i: f'{int(i)//2:02d}:{30*(int(i)%2):02d}')
    spread.to_csv(args.out / 'intraday_spread.csv', index=False, encoding='utf-8-sig')
    tick = quotes.groupby('Symbol').agg(median_price=('mid', 'median'), median_spread_bp=('spread_bp', 'median'),
                                      median_l1_depth_shares=('l1_depth_shares', 'median'),
                                      median_l1_depth_value=('l1_depth_value', 'median'), median_spread_ticks=('spread_ticks', 'median'))
    tick.to_csv(args.out / 'stock_liquidity.csv', encoding='utf-8-sig')
    summary = {'date': dataset_date(args.data), 'quotes_raw': quotes.attrs['raw_records'], 'quotes_valid': len(quotes), 'quote_stocks': int(quotes.Symbol.nunique()),
               'predictive_stocks': int(sample.symbol.nunique()), 'nonoverlap_samples': len(sample),
               'assumed_observation_lag_ms': 1000,
               'target': 'future 30s midpoint from last quote available <= target; quote age <=4s, same session',
               'timing': 'all features assumed available 1s after quote/event timestamps; alignment search never used',
               'excluded_predictive_stock': 601166, 'fixed_thresholds': {'obi': .8, 'volume_shock': 3, 'flow': .6, 'absorption_volume_shock': 2},
               'bootstrap': '1000 crossed stock/10-minute clock-block resamples, seed20260923, >=5 observations per group/stock',
               'comparisons': comparisons, 'median_spread_bp_all_quotes': float(quotes.spread_bp.median()),
               'single_tick_fraction': float((quotes.spread_ticks == 1).mean()),
               'notes': 'Single day; morning/afternoon split is intraday holdout only. Zero changes count as neither up nor down. No trade PnL, fees or queue fills inferred.'}
    summary['liquidity_by_price'] = {}
    for label, subset in [('price<10', tick[tick.median_price < 10]), ('price>=100', tick[tick.median_price >= 100])]:
        summary['liquidity_by_price'][label] = {'stocks': len(subset), **subset.median().to_dict()}
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
