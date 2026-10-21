# Db2 Federation UTF-8／Big5 實測

這組測試重現 Big5（Code Page 950）資料庫透過 DRDA Nickname 查詢 UTF-8（1208）資料庫的行為，涵蓋一般中文、難字、混合字串、Emoji、批次查詢與來源 HEX 傳遞。實測結果見 [RESULTS.md](RESULTS.md)。

## 初次建置

在專案根目錄啟動既有實驗容器，再建立測試環境：

```bash
./start_db2.sh
python3 federation/run_tests.py --setup
```

前提是本機 Docker socket 可用、容器的 Db2 已啟用 `FEDERATED=YES` 並監聽 TCP/IP 50000。腳本預設容器為 `db2-bench-1m`，可由 `DB2_TEST_CONTAINER` 指定；`.local/db2.env` 必須包含該容器的實驗帳號密碼。

`--setup` 建立 `FNEW1208`（UTF-8）及 `FOLD950`（BIG5），然後建立來源 TABLE／VIEW、TCP/IP catalog alias、DRDA wrapper、server、user mapping、nickname 與本地驗證表。資料庫名稱若已存在，腳本會停止，不會自動刪除或覆蓋。這個選項限初次執行。

## 重跑測試

```bash
python3 federation/run_tests.py
```

重跑只會清空並重新寫入本測試專用的 `FOLD950.TESTCP.LOCAL_CAPTURE`。來源資料保持不變，每次執行的 SQL、原始輸出與 `results.json` 寫入新的 `evidence/<UTC時戳>/`。

腳本固定使用 `unix:///var/run/docker.sock`，清除 Docker endpoint、context 與 TLS 選擇變數，保留既有 Docker 設定與 registry 憑證。

## 測試方式與判讀

SQL 使用 Linux Db2 CLP、`LANG=en_US.UTF-8` 與 `DB2CODEPAGE=1208`。用戶端編碼不會改變 Big5 資料庫編碼；資料庫設定、wrapper、server 與欄位 CODEPAGE 均另有證據。難字 literal 只送至 UTF-8 來源資料庫。

| 案例 | 驗證內容 |
|---|---|
| TC01 | `ABC123`、`王小明` |
| TC02 | `𠮷`（U+20BB7） |
| TC03 | `陳𠮷祥` |
| TC04 | `😀` |
| TC05 | 一次查詢五筆資料 |
| TC06 | 查詢由來源 VIEW 預先計算的 UTF-8 HEX |

接著逐筆將 Nickname 結果寫入 Big5 本地表，再計算該表的 `HEX(TEST_TEXT)`。這避免直接對 Nickname 計算 HEX 時，運算被推送至 UTF-8 遠端而誤判。

`results.json` 保留每個 SQL 的 CLP exit code、SQLCODE、SQLSTATE、返回筆數，以及本地儲存的文字、HEX 和長度。四項自動核對涵蓋來源前後 ID／HEX 與預期一致、來源不變，以及 TC06 ID／HEX 與來源一致。核對失敗會以非零狀態結束。

TC02–TC05 屬行為觀察，SQL 錯誤也會保留證據並繼續其他案例；不能只以腳本 exit code 或 SQLCODE=0 判定所有文字完整。請閱讀案例輸出及本地儲存的 HEX。

建立 server 的 `PASSWORD` 採雙引號識別字語法，user mapping 的 `REMOTE_PASSWORD` 採字串語法。腳本使用既有實驗環境檔中的密碼，輸出與 SQL 證據以 `<LAB_PASSWORD>` 遮蔽；佔位文字不能直接當成密碼執行。

`.log` 保留 Db2 輸出的原始位元組，SQLCA 分隔符號可能不是 UTF-8；`results.json` 為 UTF-8。
