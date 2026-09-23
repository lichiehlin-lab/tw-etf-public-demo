from collections import defaultdict,deque
from dataclasses import dataclass
from decimal import Decimal as D
from datetime import date

@dataclass
class Position:
    units: D
    cost: D
    market_value: D | None
    unrealized_pnl: D | None

@dataclass
class PortfolioSnapshot:
    positions: dict
    realized_pnl: D
    dividends: D
    fees: D
    market_value: D | None
    total_pnl: D | None
    bought: D
    sold: D

def calculate_portfolio(transactions,prices,actions,as_of=None):
    as_of=as_of or date.max
    lots=defaultdict(deque); realized=D(0); bought=D(0); sold=D(0); dividends=D(0); fees=D(0)
    # Same-day splits precede trades. Same-day trades preserve input order.
    events=[(a.effective_date,0,i,a) for i,a in enumerate(actions) if a.effective_date<=as_of]
    events += [(t.trade_date,1,i,t) for i,t in enumerate(transactions) if t.trade_date<=as_of]
    for _,kind,_,event in sorted(events,key=lambda x:x[:3]):
        queue=lots[event.key]
        if kind==0:
            for lot in queue: lot[0]*=event.unit_ratio
            continue
        tx=event
        if tx.type=='BUY':
            cost=tx.units*tx.unit_price+tx.fee
            queue.append([tx.units,cost]); bought+=cost
        elif tx.type=='SELL':
            if sum((lot[0] for lot in queue),D(0))<tx.units: raise ValueError(f'{tx.key.code} {tx.trade_date} 賣出超過可用庫存')
            left=tx.units; consumed=D(0)
            while left:
                lot=queue[0]; take=min(left,lot[0]); cost=lot[1]*take/lot[0]
                lot[0]-=take; lot[1]-=cost; left-=take; consumed+=cost
                if lot[0]==0: queue.popleft()
            proceeds=tx.units*tx.unit_price-tx.fee-tx.tax
            sold+=proceeds; realized+=proceeds-consumed
        elif tx.type=='DIVIDEND' and tx.status=='RECEIVED': dividends+=tx.cash_amount
        elif tx.type=='FEE' and tx.status=='RECEIVED': fees+=tx.cash_amount
    positions={}
    for key,queue in lots.items():
        units=sum((x[0] for x in queue),D(0)); cost=sum((x[1] for x in queue),D(0))
        if not units: continue
        price=prices.get(key)
        if hasattr(price,'day'):
            quote=price
            price=quote.close if quote.day<=as_of and quote.status=='CURRENT' else None
            if price is not None:
                for action in actions:
                    if action.key==key and quote.day<action.effective_date<=as_of:
                        price/=action.unit_ratio
        value=units*price if price is not None else None
        positions[key]=Position(units,cost,value,value-cost if value is not None else None)
    complete=all(p.market_value is not None for p in positions.values())
    total=sum((p.market_value for p in positions.values()),D(0)) if complete else None
    pnl=total+sold+dividends-bought-fees if total is not None else None
    return PortfolioSnapshot(positions,realized,dividends,fees,total,pnl,bought,sold)
