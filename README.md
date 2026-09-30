# Db2：1000 萬筆檔案寫入效能比較

使用同一份 1000 萬行 DEL 檔、相同欄位且沒有索引的兩張空表，比較 Db2 原生 `LOAD` 與 Java JDBC 批次 `INSERT`。JDBC 預設每 1,000 筆執行批次並提交一次，可用命令參數指定批次大小。兩張表各自核對 `COUNT(*) = 10000000`。

需求：可用的 Docker daemon、Python 3、Java 21、`curl`、`openssl`、`rg`，以及能存取 `icr.io`、`dd2.icr.io` 與 Maven Central 的網路。Db2 容器使用固定 digest 的 IBM Db2 12.1.5 映像，建立 `BENCHDB`。本機資料、驅動及容器密碼都放在 Git 忽略的目錄。

```bash
cd /workspace/test_db2
chmod +x setup.sh start_db2.sh prepare_db2_image.sh run_benchmark.sh
./run_benchmark.sh
```

要測試每 10,000 筆執行批次並提交一次，執行 `./run_benchmark.sh 10000`。CSV 的 `batch_size` 記錄 JDBC 批次及提交筆數，LOAD 此欄留白。

`setup.sh` 下載 IBM JDBC 驅動、核對 Maven Central 公布的 SHA-1，並編譯 Java 程式。`start_db2.sh` 只在本機容器不存在時建立它，並等待資料庫可連線。每次執行 `run_benchmark.sh` 都會重建兩張空表，再由 Java 重新產生 1000 萬行 `data/rows.del`。原生 `LOAD` 需要伺服器能讀取檔案，因此容器以唯讀方式掛載 `data/`。兩個方法都讀取同一份檔案。

Docker 使用 `vfs` 時，`prepare_db2_image.sh` 會先核對完整映像的內容 digest，再將檔案系統合併成單層匯入，以避免多層副本耗盡磁碟。此步驟需要從 GitHub 下載 crane 0.20.3 並核對官方 SHA-256。其他 Docker 儲存驅動直接載入原始映像。

兩種方法成功完成並驗證筆數後，腳本會寫出 `benchmark-results.csv`。`LOAD` 列的 `seconds` 是 `file_write_seconds` 與 `db_load_seconds` 的總和：前者從呼叫 Java 開始，到檔案寫完、同步到磁碟並設好讀取權限；後者從呼叫 Docker 開始，到 Db2 `LOAD` 完成。JDBC 列的 `seconds` 從呼叫 Java 開始，到讀取同一份檔案並完成所有批次提交。空白的分段欄位不適用於 JDBC。建立容器、編譯、建表及查詢驗證不計時。

`LOAD` 走 Db2 大量載入路徑，JDBC 走一般交易日誌路徑；而且 `LOAD` 的總時間依需求包含產檔，JDBC 的時間不含產檔。比較時應留意這些範圍差異。若需要穩定的吞吐量估計，可在同一台機器上重複執行數次。

已完成的實測結果與測試條件見 [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)。
