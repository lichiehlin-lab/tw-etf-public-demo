# 台股 ETF 研究室｜公開展示版

ETF 名錄搜尋、盤後行情、商品詳情與 2–5 檔歷史比較。訪客唯讀，不提供個人交易紀錄、檔案上傳、資料庫還原或會員功能。

## Streamlit Community Cloud 部署

1. 建立 GitHub 儲存庫（建議 `tw-etf-public-demo`），把本部署包的檔案放在儲存庫根目錄。
2. 開啟 https://share.streamlit.io/ ，完成登入，選 **Create app**。
3. Repository：選取剛建立的儲存庫；Branch：`main`；Main file path：`public_app.py`。
4. Advanced settings：選 **Python 3.12**。本展示版不需要 secrets 或 API 金鑰。
5. Deploy。部署完成後可分享 `https://你的名稱.streamlit.app`。

上傳的是此精簡部署包，不要上傳個人版目錄中的 `.venv`、`.runtime`、資料庫、備份或 secrets。公開入口只有 `public_app.py`。

## 本機預覽

```sh
python -m pip install -r requirements.txt
python -m streamlit run public_app.py --server.address 127.0.0.1
```

## 資料與更新

- 包含已核對的 2026-09-22 官方行情快照及 ETF 名錄，用於首次載入或外部來源暫時不可用。
- 有人瀏覽時最多每小時檢查一次官方更新，所有訪客共用更新節流。來源失敗保留舊資料與原日期。
- 市場快取位於系統暫存目錄；雲端重啟後從公開快照及官方來源重建。沒有個人資料儲存在此快取。
- Streamlit Community Cloud 的本機儲存不保證永久保存。長期歷史需另建持久化的公開市場資料源；本版本缺歷史時直接顯示資料不足。
- 本站不轉播 MIS 盤中行情，提供官方即時行情連結。個人免費瀏覽與對外轉播的授權不同。
- 缺正式 NAV、完整配息史、費用或價格歷史時，不生成假折溢價、含息績效或總分。

## 來源

- [臺灣證券交易所 OpenAPI](https://openapi.twse.com.tw/)
- [證券櫃檯買賣中心 OpenAPI](https://www.tpex.org.tw/openapi/)
- [官方證券編碼名錄](https://isin.twse.com.tw/isin/C_public.jsp?strMode=2)
- [政府資料開放授權條款](https://data.gov.tw/license)
- [證交所交易資訊使用說明](https://www.twse.com.tw/zh/products/information/qa.html)

此為獨立研究展示，非交易所官方服務。歷史績效不代表未來報酬，配息率不等於總報酬。
