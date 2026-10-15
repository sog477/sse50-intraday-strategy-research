"""Render CSV study outputs without loading market data."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('reports/research'))
    args = parser.parse_args()
    summary = json.loads((args.out / 'summary.json').read_text(encoding='utf-8'))
    spread = pd.read_csv(args.out / 'intraday_spread.csv')
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, kind, title in zip(axes[:2], ['obi_return', 'volume_shock_volatility'], ['30s midpoint return by L1 imbalance', 'Future 30s volatility after volume shock']):
        result = summary['comparisons']['afternoon'][kind]
        ax.bar(result['groups'], [result['equal_stock_mean_a'], result['equal_stock_mean_b']], color=['#17837c', '#e3a248'])
        ax.axhline(0, color='#444', lw=.6)
        ax.set_ylabel('basis points (bp)')
        ax.set_title(title)
    axes[2].plot(spread.label, spread['median'], 'o-', color='#17837c')
    axes[2].set_title('Median stock spread by half-hour')
    axes[2].set_ylabel('bp')
    axes[2].tick_params(axis='x', rotation=45)
    fig.suptitle('SSE50 2026-09-23 | equal-stock afternoon means | no PnL claim')
    fig.tight_layout()
    fig.savefig(args.out / 'overview.png', dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
