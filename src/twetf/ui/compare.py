import streamlit as st
from ..services.research import ResearchService
from ..analytics.ranking import BALANCED,GROWTH
from .common import render_metric,fmt

def render(repo, public=False):
    items=repo.etfs()
    if not items: st.info('尚無資料，請先更新官方名錄。');return
    labels={f'{e.key.code} {e.name} · {e.key.exchange}':e.key for e in items}
    selected=st.multiselect('選取 2–5 檔 ETF',list(labels),max_selections=5)
    month=st.select_slider('比較期間（月）',options=[1,3,6,12,24],value=12)
    svc=ResearchService(repo)
    if len(selected)>=2:
        try:
            comparison=svc.compare([labels[x] for x in selected])
            st.caption(f'共同截至日：{comparison.end_day or "資料不足"}｜21／63／126／252／504 個可用交易日')
            for col,item in zip(st.columns(len(selected)),comparison.items):
                with col:
                    st.subheader(item.etf.key.code);st.write(item.etf.name)
                    render_metric(item.return_basis[month],item.returns[month],True)
                    render_metric('12 月最大回撤',item.drawdown,True)
                    render_metric('12 月年化波動',item.volatility,True)
                    render_metric('20 日平均成交金額',item.liquidity)
                    render_metric('年度費用率',item.expense,True)
                    render_metric('正式折溢價',item.premium,True)
        except ValueError as exc: st.warning(str(exc))
    else: st.info('選取至少 2 檔以開始比較。')
    st.divider();st.subheader('同類研究排序')
    profile=st.radio('權重方案',['均衡','成長'] if public else ['均衡','成長','自訂'],horizontal=True)
    weights=BALANCED if profile=='均衡' else GROWTH if profile=='成長' else repo.setting('weights',BALANCED)
    st.caption('只在同群組、同日、五項資料齊全且至少 10 檔時評分。歷史排名不是預期報酬。')
    if st.button('計算研究排序'):
        ranked=svc.rankings(weights)
        st.dataframe([{'ETF':r.item.identity,'群組':r.item.group,'截至日':str(r.item.end_day),'總分':fmt(r.score),'狀態':r.reason or '完整',**{k:str(v) for k,v in r.parts.items()}} for r in ranked],hide_index=True,width='stretch')
    with st.expander('評分公式與權重'):
        st.write(weights);st.write('各指標以同群組平均名次轉成 0–100 百分位；報酬與流動性高較佳，回撤絕對值、波動、費用低較佳。總分為百分位加權平均。')
