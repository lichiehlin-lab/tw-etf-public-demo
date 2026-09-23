import streamlit as st

def fmt(value,percent=False):
    if value is None: return '資料不足'
    return f'{value*100:,.2f}%' if percent else f'{value:,.2f}'

def render_metric(label,metric,percent=False):
    st.metric(label,fmt(metric.value,percent))
    st.caption(f'期間 {metric.start_day or "—"} ～ {metric.end_day or "—"}｜{metric.status}')
    if metric.missing_reason: st.caption(metric.missing_reason)
    if metric.source: st.caption(f'來源：{metric.source}')

def choose_etf(repo,label='選擇 ETF',key='etf'):
    etfs=repo.etfs()
    if not etfs:
        st.info('尚無資料，請先更新官方名錄。'); return None
    mapping={f'{e.key.code} {e.name} · {e.key.exchange}':e.key for e in etfs}
    selected=st.selectbox(label,list(mapping),key=key)
    return mapping[selected]
