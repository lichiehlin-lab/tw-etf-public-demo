import os
import streamlit as st
from ..services.public_market import PublicMarketStore, public_data_path

PAGES = ['總覽', '探索', 'ETF 詳情', '比較', '資料來源與狀態']

@st.cache_resource
def market_store(path):
    return PublicMarketStore(path)

def main():
    st.set_page_config(page_title='台股 ETF 研究室｜公開展示', page_icon='📊', layout='wide')
    st.markdown('''<style>.block-container{padding-top:2rem;max-width:1450px}h1{letter-spacing:-.035em}div[data-testid="stMetric"]{background:white;padding:18px;border-radius:12px;border:1px solid #e3e9ee}.eyebrow{letter-spacing:.16em;font-size:12px;color:#087f8c;font-weight:700}</style>''', unsafe_allow_html=True)
    store = market_store(str(public_data_path()))
    with st.spinner('載入官方盤後資料…'):
        status = store.refresh(offline=bool(os.getenv('TWETF_OFFLINE')))
    repo = store.reader()
    try:
        with st.sidebar:
            st.markdown('### ETF 研究室')
            st.caption('PUBLIC RESEARCH · 公開展示')
            if st.session_state.get('public_navigation') not in PAGES:
                st.session_state['public_navigation'] = PAGES[0]
            page = st.radio('導覽', PAGES, key='public_navigation', label_visibility='collapsed')
            st.divider()
            st.caption('官方盤後資料 · 所有人唯讀\n\n伺服器每小時最多更新一次，有人瀏覽時檢查。')
            st.link_button('查看官方即時行情 ↗', 'https://mis.twse.com.tw/stock/index.jsp')
            st.caption('本展示站不收集或儲存個人交易紀錄。')
        st.markdown('<div class="eyebrow">TAIWAN ETF / PUBLIC RESEARCH</div>', unsafe_allow_html=True)
        st.title('看懂 ETF，從資料開始。' if page == '總覽' else page)
        if page == '總覽':
            st.write('查詢臺灣掛牌 ETF、並排比較歷史指標，追溯每項資料的來源與日期。')
            etfs = repo.etfs()
            prices = [repo.latest_price(e.key) for e in etfs]
            prices = [p for p in prices if p]
            cols = st.columns(3)
            cols[0].metric('ETF 名錄', len(etfs))
            cols[1].metric('有盤後行情', len(prices))
            cols[2].metric('最新資料日', str(max(p.day for p in prices)) if prices else '尚無資料')
            st.info('這是公開研究展示版。行情為盤後資料；盤中即時行情請前往證交所官方網站。')
            if not status:
                st.caption(f'目前使用已核實快照：{repo.setting("public_snapshot_day", "—")}，不是即時行情。')
            else:
                st.caption(f'最近更新嘗試：{status.get("attempt_at", "—")}｜{status.get("state", "—")}')
            def go(destination): st.session_state['public_navigation'] = destination
            a, b = st.columns(2)
            a.button('探索 ETF', on_click=go, args=('探索',), width='stretch', type='primary')
            b.button('開始比較', on_click=go, args=('比較',), width='stretch')
            st.subheader('先了解資料，再比較表現')
            st.write('價格報酬與含息報酬分開呈現；缺少完整歷史、正式 NAV 或費用揭露時，會直接顯示資料不足。')
        elif page == '探索':
            from .explore import render
            render(repo, public=True)
        elif page == 'ETF 詳情':
            from .details import render
            render(repo, public=True)
        elif page == '比較':
            from .compare import render
            render(repo, public=True)
        else:
            st.subheader('資料新鮮度與來源')
            if status:
                st.write(f'{status.get("attempt_at", "—")}｜{status.get("state", "—")}')
                for note in status.get('notes', []): st.warning(note)
            runs = repo.rows('sync_runs')
            if runs: st.dataframe(runs, hide_index=True, width='stretch')
            else: st.info(f'來源快照資料日：{repo.setting("public_snapshot_day", "—")}；尚無線上同步紀錄。')
            st.markdown('''- [上市 OpenAPI](https://openapi.twse.com.tw/)
- [上櫃 OpenAPI](https://www.tpex.org.tw/openapi/)
- [官方即時行情](https://mis.twse.com.tw/stock/index.jsp)
- [資料開放授權條款](https://data.gov.tw/license)''')
            st.caption('來源：臺灣證券交易所、證券櫃檯買賣中心。本站獨立整理展示，非交易所官方網站。')
            st.write('正式 NAV、完整配息史、年度費用與長期價格歷史尚未齊備時，不會產生假折溢價、含息績效或評分。雲端重啟可重建公開市場快取；本機個人資料不會載入此站。')
        st.divider()
        st.caption('歷史績效不代表未來報酬；配息率不等於總報酬。資訊僅供研究，來源日期與缺漏原因請一併閱讀。')
    finally:
        repo.conn.close()
