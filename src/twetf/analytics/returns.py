from dataclasses import dataclass
from decimal import Decimal as D
from statistics import stdev
from math import sqrt

@dataclass(frozen=True)
class ReturnPoint:
    day: object
    daily_return: D
    wealth: D

def daily_total_return(previous,current,dividend,unit_ratio):
    if min(previous,current,unit_ratio)<=0 or dividend<0: raise ValueError('價格及拆分比率须正數')
    return (current+dividend)/(previous/unit_ratio)-1

def total_return_series(prices,distributions,actions):
    prices=sorted(prices,key=lambda p:p.day)
    if len({p.day for p in prices})!=len(prices): raise ValueError('價格日期重複')
    result=[]; wealth=D(1)
    for previous,current in zip(prices,prices[1:]):
        if previous.key!=current.key or previous.currency!=current.currency: raise ValueError('商品與幣別必須一致')
        ratio=D(1)
        for a in actions:
            if a.key==current.key and previous.day<a.effective_date<=current.day: ratio*=a.unit_ratio
        dividend=sum((x.amount for x in distributions if x.key==current.key and x.ex_date==current.day and x.status=='CONFIRMED'),D(0))
        daily=daily_total_return(previous.close,current.close,dividend,ratio)
        wealth*=1+daily
        result.append(ReturnPoint(current.day,daily,wealth))
    return result

def premium(price,nav):
    if not price or not nav or not nav.formal or price.key!=nav.key or price.day!=nav.day or price.currency!=nav.currency or nav.value<=0 or nav.status!='CURRENT' or price.status!='CURRENT': return None
    return price.close/nav.value-1

def volatility_252(points):
    if len(points)<252: return None
    return D(str(stdev(float(x.daily_return) for x in points[-252:])*sqrt(252)))

def max_drawdown(points):
    if not points: return None
    peak=D(1); worst=D(0)
    for p in points:
        peak=max(peak,p.wealth); worst=min(worst,p.wealth/peak-1)
    return worst
