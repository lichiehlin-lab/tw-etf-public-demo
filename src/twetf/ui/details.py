from dataclasses import asdict
import streamlit as st
import plotly.graph_objects as go
from ..services.research import ResearchService
from ..analytics.returns import total_return_series
from .common import choose_etf,render_metric

def render(repo, public=False):
    key=choose_etf(repo,key='detail_etf')
    if not key: return
    view=ResearchService(repo).details(key)
    st.subheader(f'{key.code} {view.etf.name}')
    st.caption(f'{key.exchange}｜{view.etf.category}｜{view.etf.region}｜{view.etf.currency}')
    if view.etf.currency!='TWD': st.warning('此外幣商品僅列名錄，不支援報酬比較或持倉合計。');return
    a,b,c=st.columns(3)
    with a: render_metric('盤後收盤價',view.latest_price)
    with b: render_metric('正式折溢價',view.premium,True)
    with c: render_metric('12 個月 '+view.return_basis[12],view.returns[12],True)
    prices=repo.prices(key)
    if prices:
        fig=go.Figure(go.Scatter(x=[p.day for p in prices],y=[float(p.close) for p in prices],mode='lines',name='原始收盤價',line={'color':'#087f8c','width':2.5}))
        fig.update_layout(height=340,xaxis_title='交易日',yaxis_title='新臺幣／單位',margin={'l':20,'r':20,'t':20,'b':20})
        st.plotly_chart(fig,width='stretch')
        if len(prices)>1:
            complete=repo.coverage_contains(key,prices[0].day,prices[-1].day)
            points=total_return_series(prices,repo.distributions(key) if complete else [],repo.actions(key))
            fig=go.Figure(go.Scatter(x=[p.day for p in points],y=[float((p.wealth-1)*100) for p in points],name='含息' if complete else '價格',line={'color':'#3760aa'}))
            fig.update_layout(height=260,yaxis_title='累積報酬 %',title='含息累積報酬' if complete else '價格累積報酬（配息史完整性未確認）')
            st.plotly_chart(fig,width='stretch')
    st.caption('含息假設除息日收盤再投入，不含個人費稅。海外標的的價格與 NAV 可能有時區差。')
    for title,records in [('配息公告',repo.distributions(key)),('正式 NAV／估計 NAV',repo.navs(key)),('拆分紀錄',repo.actions(key)),('費用揭露',repo.facts(key))]:
        with st.expander(title):
            if records: st.dataframe([{k:str(v) for k,v in asdict(x).items() if k!='key'} for x in records],hide_index=True)
            else: st.info('尚無可核實資料。' if public else '尚無可核實資料；可於設定匯入附來源公告。')
    st.caption('商品配息公告不代表個人已收到現金。' if public else '商品配息公告不代表個人已收到現金，個人實收須另行記帳。')
