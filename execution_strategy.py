"""Fixed 30-second execution policies on independent historical shadow branches.

No parameter fitting, position opening/closing strategy or future-state decisions.
Opportunity marking is reported separately from real simulated fills and fees.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json

from orderbook import cents, parse_time, price_str
from simulator import HistoricalSession, clock, ms_stamp, stamp_ms

THRESHOLD = 0.6
HORIZON_MS = 30_000
INTERVAL_MS = 1_000
POLICIES = [('immediate', '立即主动'), ('passive', '被动等待30秒'), ('imbalance', '盘口信号切换')]


def quote(session):
    b, a = session.book._best('B'), session.book._best('S')
    if b is None or a is None or b >= a:
        return None
    bv, av = session.book.levels['B'][b], session.book.levels['S'][a]
    if bv + av <= 0:
        return None
    return {'bid': b, 'ask': a, 'mid': (b + a) / 2, 'obi': (bv - av) / (bv + av),
            'bid_volume': bv, 'ask_volume': av}


def valid_child_quantity(symbol, side, quantity):
    if side == 'S':
        return quantity > 0
    return quantity >= 200 if str(symbol).startswith('688') else quantity > 0 and quantity % 100 == 0


def result_for(session, policy, label, side, quantity, initial, protection, start_ms, decisions):
    sign = 1 if side == 'B' else -1
    filled = sum(o.quantity - o.remaining for o in session.orders)
    remaining = quantity - filled
    notional = sum(o.notional_cents for o in session.orders)
    fees = sum(o.fees_cents for o in session.orders)
    terminal = quote(session)
    filled_cost = sign * (notional - filled * initial['mid']) + fees
    marked_cost = (filled_cost + sign * remaining * (terminal['mid'] - initial['mid'])) if terminal else (filled_cost if not remaining else None)
    last_fill_ms = stamp_ms(parse_time(session.fills[-1]['time'])) if session.fills else None
    return {
        'policy': policy, 'label': label, 'filled': filled, 'remaining': remaining,
        'completion_pct': filled / quantity * 100, 'status': 'COMPLETED' if not remaining else 'INCOMPLETE',
        'average_fill_price': round(notional / filled / 100, 6) if filled else None,
        'notional_yuan': notional / 100, 'fees_yuan': fees / 100,
        'fees_breakdown_yuan': {k: sum(session.fees.total(o.notional_cents, side)[k] for o in session.orders) / 100
                                for k in ('commission', 'transfer', 'stamp')},
        'filled_cost_yuan': round(filled_cost / 100, 6),
        'filled_cost_bp': filled_cost / (filled * initial['mid']) * 10000 if filled else None,
        'task_marked_cost_yuan': round(marked_cost / 100, 6) if marked_cost is not None else None,
        'task_marked_cost_bp': marked_cost / (quantity * initial['mid']) * 10000 if marked_cost is not None else None,
        'first_fill_wait_ms': stamp_ms(parse_time(session.fills[0]['time'])) - start_ms if session.fills else None,
        'completion_time_ms': last_fill_ms - start_ms if not remaining else None,
        'children': len(session.orders), 'filled_children': sum(o.notional_cents > 0 for o in session.orders),
        'protection': price_str(protection), 'orders': session.state()['orders'], 'fills': list(session.fills),
        'decisions': decisions, 'final_clock': clock(session.time),
    }


def compare_execution(source: HistoricalSession, side: str, quantity: int, protection=None,
                      sellable: int = 0, fill_model: str = 'with_residual'):
    if side not in ('B', 'S'):
        raise ValueError('方向必须为B或S')
    if type(quantity) is not int or not valid_child_quantity(source.symbol, side, quantity):
        raise ValueError('任务数量无效：主板买入须为100股整数倍，科创板买入至少200股')
    maximum = 50000 if str(source.symbol).startswith('688') else 1000000
    if quantity > maximum:
        raise ValueError(f'本实验每笔任务最多{maximum}股，与主动五档申报上限一致')
    if side == 'S' and (type(sellable) is not int or sellable < quantity):
        raise ValueError('卖出任务须声明足额期初可卖持仓，不使用当天买入数量')
    if fill_model not in ('tape_only', 'with_residual'):
        raise ValueError('未知被动成交模型')
    start_ms = stamp_ms(source.time)
    deadline = start_ms + HORIZON_MS
    if not ((34200000 <= start_ms and deadline < 41400000) or
            (46800000 <= start_ms and deadline < 53820000)):
        raise ValueError('起点及之后30秒须完整处于同一连续竞价时段（结束时刻前）')
    initial = quote(source)
    if initial is None:
        raise ValueError('当前缺少有效双边报价')
    try:
        cap = cents(protection) if protection not in (None, '') else (initial['ask'] + 2 if side == 'B' else max(1, initial['bid'] - 2))
    except (ArithmeticError, TypeError) as exc:
        raise ValueError('保护价须为正数且精确到分') from exc
    sign = 1 if side == 'B' else -1
    results = []
    for policy, label in POLICIES:
        session = source.fork_market(allow_residual_fills=fill_model == 'with_residual')
        decisions = []
        urgent = policy == 'immediate'
        for elapsed in range(0, HORIZON_MS + 1, INTERVAL_MS):
            session.advance(ms_stamp(start_ms + elapsed))
            filled = sum(o.quantity - o.remaining for o in session.orders)
            remaining = quantity - filled
            q = quote(session)
            signed = sign * q['obi'] if q else None
            record = {'clock': clock(session.time), 'elapsed_ms': elapsed,
                      'obi': q['obi'] if q else None, 'signed_obi': signed,
                      'bid': price_str(q['bid']) if q else None, 'ask': price_str(q['ask']) if q else None,
                      'remaining_before': remaining}
            if not remaining:
                record.update(action='已完成', remaining_after=0)
                decisions.append(record)
                # All policies share the same deadline mark, including early completions.
                session.advance(ms_stamp(deadline))
                break
            if policy == 'imbalance' and signed is not None and signed >= THRESHOLD:
                urgent = True
            due = elapsed == HORIZON_MS
            active = urgent or due
            legal = valid_child_quantity(source.symbol, side, remaining)
            if due and session.active:
                session.cancel()
            if active and legal:
                if session.active:
                    session.cancel()
                before = len(session.fills)
                # Same fixed cap for every child and policy; five price levels, IOC remainder.
                session.submit(side, 'FIVE_CANCEL', remaining, protection=price_str(cap))
                record['action'] = ('到期主动处理' if due else '信号触发主动' if policy == 'imbalance' else '立即/持续主动')
                record['new_fill_count'] = len(session.fills) - before
            elif active and not legal:
                record['action'] = ('剩余买量不足合法重报单位；到期保留未完成' if due else
                                    '剩余买量不足合法重报单位，保留原排队单' if session.active else
                                    '剩余买量不足合法重报单位，无法新报')
            elif elapsed == 0:
                own = q['bid'] if side == 'B' else q['ask']
                p = min(own, cap) if side == 'B' else max(own, cap)
                session.submit(side, 'LIMIT', remaining, price=price_str(p))
                record['action'] = '本方最优限价排队' if p == own else '保护价限价排队'
            else:
                record['action'] = '保留原价排队'
            record['remaining_after'] = quantity - sum(o.quantity - o.remaining for o in session.orders)
            decisions.append(record)
            if record['remaining_after'] == 0:
                session.advance(ms_stamp(deadline))
                break
        results.append(result_for(session, policy, label, side, quantity, initial, cap, start_ms, decisions))
    comparable = all(r['remaining'] == 0 for r in results)
    winner = min(results, key=lambda r: r['filled_cost_bp'])['policy'] if comparable else None
    lowest = min(r['filled_cost_bp'] for r in results) if comparable else None
    return {
        'strategy_version': 1, 'symbol': source.symbol, 'side': side, 'quantity': quantity,
        'declared_initial_sellable': sellable if side == 'S' else None,
        'start': clock(source.time), 'deadline': clock(ms_stamp(deadline)), 'threshold': THRESHOLD,
        'horizon_seconds': 30, 'decision_interval_ms': INTERVAL_MS, 'assumed_order_latency_ms': 0,
        'initial_mid': initial['mid'] / 100, 'initial_obi': initial['obi'],
        'protection': price_str(cap), 'fill_model': fill_model, 'fees': asdict(source.fees),
        'results': results, 'all_completed': comparable, 'lowest_completed_cost_policy': winner,
        'lowest_completed_cost_policies': [r['policy'] for r in results if abs(r['filled_cost_bp'] - lowest) < 1e-8] if comparable else [],
        'model_notes': [
            '三个独立情景从当前历史簿分叉，使用各自虚拟容量；不修改手动会话或汇总成组合收益。',
            '阈值0.6，每秒观察；一旦转为主动模式，此后每秒重试剩余量；保护价全程固定。',
            '主动单使用最优五档、保护价内即时成交，余量撤销；被动原价保留至切换或截止。',
            '费用按实际子委托分别计提最低佣金；部分成交后不足合法买入单位的余量不强制补报。',
            '已成交成本含实际模拟费用；任务标记成本另将剩余量按截止中间价计机会成本，未视为成交、未计假设补单费用。',
            '只有三组都全部完成才比较含费实际成本；单日固定历史路径、零冲击、零指令延迟，不能视为盈利验证。',
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=Path(__file__).resolve().parent / 'sse50_20260923')
    p.add_argument('--symbol', type=int, default=601688)
    p.add_argument('--at', default='10:00:00')
    p.add_argument('--side', choices=['B', 'S'], default='B')
    p.add_argument('--quantity', type=int, default=100)
    p.add_argument('--protection', default=None)
    p.add_argument('--sellable', type=int, default=0)
    p.add_argument('--fill-model', choices=['tape_only', 'with_residual'], default='with_residual')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    session = HistoricalSession.from_data(args.data, args.symbol)
    session.advance(parse_time(args.at))
    result = compare_execution(session, args.side, args.quantity, args.protection, args.sellable, args.fill_model)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)


if __name__ == '__main__':
    main()
