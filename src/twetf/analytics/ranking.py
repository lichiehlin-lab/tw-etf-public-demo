from dataclasses import dataclass,field
from decimal import Decimal as D
from collections import defaultdict

BALANCED={'return':30,'drawdown':25,'volatility':20,'liquidity':15,'expense':10}
GROWTH={'return':40,'drawdown':25,'volatility':10,'liquidity':15,'expense':10}

def validate_weights(weights):
    if set(weights)!=set(BALANCED) or sum(weights.values())!=100 or any(type(v)!=int or v<0 for v in weights.values()):
        raise ValueError('五個權重須為非負整數且合計 100')

@dataclass(frozen=True)
class RankInput:
    identity: str
    group: str
    end_day: object
    observations: int
    expense_definition: str
    annual_return: D | None
    drawdown: D | None
    volatility: D | None
    liquidity: D | None
    expense: D | None
    start_day: object = None

@dataclass
class RankedETF:
    item: RankInput
    score: D | None = None
    parts: dict = field(default_factory=dict)
    reason: str = '同群組、同日且五項完整的合格商品不足 10 檔'

def rank_cohort(items,weights):
    validate_weights(weights)
    result=[RankedETF(x) for x in items]; groups=defaultdict(list)
    for r in result:
        x=r.item
        if x.observations>=252 and x.group and '待核實' not in x.group and x.expense_definition and all(v is not None for v in (x.annual_return,x.drawdown,x.volatility,x.liquidity,x.expense)):
            groups[(x.group,x.start_day,x.end_day,x.expense_definition)].append(r)
    for cohort in groups.values():
        n=len(cohort)
        if n<10: continue
        for name in weights:
            attr='annual_return' if name=='return' else name
            values=[getattr(r.item,attr) for r in cohort]
            if name=='drawdown': values=[abs(v) for v in values]
            if name in ('drawdown','volatility','expense'): values=[-v for v in values]
            for r,value in zip(cohort,values):
                below=sum(v<value for v in values); ties=sum(v==value for v in values)
                rank=D(below)+D(ties+1)/2
                r.parts[name]=100*(rank-1)/(n-1)
        for r in cohort:
            r.score=sum((r.parts[k]*v/100 for k,v in weights.items()),D(0)).quantize(D('0.1'))
            r.reason=''
    return result
