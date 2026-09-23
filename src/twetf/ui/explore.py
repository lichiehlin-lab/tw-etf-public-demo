import streamlit as st
from decimal import Decimal as D
from ..services.research import ResearchService
from .common import choose_etf

def render(repo, public=False):
    st.write('先依商品條件縮小範圍，再查看來源及歷史。')
    query=st.text_input('搜尋代碼或名稱',placeholder='例如 0050、科技、債券')
    a,b,c=st.columns(3)
    exchange=a.selectbox('掛牌市場',['全部','TWSE','TPEx'])
    category=b.selectbox('商品類別',['全部']+sorted({e.category for e in repo.etfs()}))
    region=c.selectbox('投資地區',['全部','臺灣','海外','待核實'])
    with st.expander('更多篩選'):
        ordinary=st.checkbox('只顯示一般 TWD ETF（排除槓桿、反向與期貨）',value=True)
        cap=st.number_input('價格上限（0 表示不限）',min_value=0.0,value=float(repo.setting('price_cap',0)),step=10.0)
        turnover=st.number_input('20 日平均成交金額下限',min_value=0.0,step=1000000.0)
        age=st.number_input('最少掛牌天數',min_value=0,step=30)
        dividends=st.checkbox('已有配息公告紀錄')
    filters={'ordinary':ordinary,'exchange':None if exchange=='全部' else exchange,'category':None if category=='全部' else category,
             'region':None if region=='全部' else region,'price_max':D(str(cap)) if cap else None,'min_turnover':D(str(turnover)),'min_age_days':age,'distributing':dividends}
    items=ResearchService(repo).search_etfs(query,filters)
    rows=[]
    for e in items:
        p=repo.latest_price(e.key)
        rows.append({'代碼':e.key.code,'名稱':e.name,'市場':e.key.exchange,'類型':e.category,'地區':e.region,'幣別':e.currency,
                     '收盤價':str(p.close) if p else '尚無資料','資料日':str(p.day) if p else '—','掛牌日':str(e.listing_date or '待核實')})
    st.caption(f'符合條件 {len(rows)} 檔；價格高低僅作篩選，不影響品質評分。')
    if rows: st.dataframe(rows,hide_index=True,width='stretch')
    else: st.info('尚無資料或沒有符合條件的 ETF。')
    if public: return
    st.subheader('管理觀察清單')
    key=choose_etf(repo,key='watch_etf')
    if key:
        a,b=st.columns(2)
        if a.button('加入觀察清單'): repo.add_to_watchlist(key);st.success('已加入')
        if b.button('移出觀察清單'): repo.remove_from_watchlist(key);st.success('已移出')
