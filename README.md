# Db2：100 萬筆檔案寫入效能比較

使用同一份 100 萬行 DEL 檔、相同欄位且沒有索引的兩張空表，比較 Db2 原生 `LOAD` 與 Java JDBC 批次 `INSERT`。JDBC 每 1,000 筆執行批次並提交一次。結果包含完整命令執行時間、筆數與每秒筆數；兩張表各自核對 `COUNT(*) = 1000000`。

需求：可用的 Docker daemon、Python 3、Java 21、`curl`、`openssl`，以及能存取 `icr.io`、`dd2.icr.io` 與 Maven Central 的網路。Db2 容器使用 IBM 的 `icr.io/db2_community/db2:latest` 映像，建立 `BENCHDB`。本機資料、驅動及容器密碼都放在 Git 忽略的目錄。

```bash
cd /workspace/test_db2
chmod +x setup.sh start_db2.sh run_benchmark.sh
./run_benchmark.sh
```

`setup.sh` 產生 100 萬行資料、下載 IBM JDBC 驅動、核對 Maven Central 公布的 SHA-1，並編譯 Java 程式。`start_db2.sh` 只在本機容器不存在時建立它，並等待資料庫可連線。再次執行 `run_benchmark.sh` 會重建兩張空表。原生 `LOAD` 需要伺服器能讀取檔案，因此容器以唯讀方式掛載 `data/`。兩個方法都讀取 `data/rows.del`。

兩種方法成功完成並驗證筆數後，腳本會寫出 `benchmark-results.csv`。`LOAD` 走 Db2 大量載入路徑，JDBC 走一般交易日誌路徑；兩者的行為本來就不同。結果適合比較這兩種實際匯入方式，不代表所有資料型別、索引或提交批量的表現。若需要穩定的吞吐量估計，可在同一台機器上重複執行數次，避開首次建立容器與資料檔的時間。
