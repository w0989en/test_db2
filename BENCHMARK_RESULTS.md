# Db2 100 萬筆寫入實測

測試日期：2026-09-30 UTC。兩種方法各執行一輪，使用相同資料檔、相同欄位與沒有索引的空表。

| 方法 | 完整命令耗時（秒） | 寫入筆數 | 每秒筆數 |
| --- | ---: | ---: | ---: |
| Db2 原生 LOAD | 2.611 | 1,000,000 | 382,990 |
| Java JDBC 批次 INSERT | 6.962 | 1,000,000 | 143,636 |

本輪 LOAD 的吞吐量約為 JDBC 的 **2.67 倍**。這是此雲端環境的一次量測；其他硬體、索引、資料寬度與提交批量可能得到不同結果。

## 測試條件

- Db2 LUW 12.1.5.0（`special_85816`）、OpenJDK 21.0.12.1、IBM JDBC driver 12.1.5.0。
- 雲端容器限制為 4 顆 CPU、32 GiB 記憶體；磁碟容量 32 GB，Docker 儲存驅動為 `vfs`。Db2 映像合併成單層以符合磁碟空間限制；原始映像校驗通過後才匯入。
- 原始映像：`icr.io/db2_community/db2@sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6`。
- 同一份 DEL 檔：1,000,000 行、44,777,896 bytes。SHA-256：`5d483565bc48a7057b213669922c131e0447e9ddef4c9724d75bcc11e07f291e`。
- 欄位為 `ID BIGINT NOT NULL`、`PAYLOAD VARCHAR(64) NOT NULL`、`AMOUNT INTEGER NOT NULL`，兩張表都沒有索引。
- LOAD 使用伺服器可讀取的唯讀檔案掛載與 `NONRECOVERABLE`。JDBC 使用 `PreparedStatement.addBatch()`／`executeBatch()`，關閉 auto-commit，每 1,000 筆提交一次。
- JDBC 連到同一台機器的 `127.0.0.1:50000`。LOAD 與 JDBC 使用同一個 Db2 實例。

## 計時與正確性

CSV 的時間從命令呼叫到完成。LOAD 包含 Docker exec、Db2 連線與載入；JDBC 包含 JVM 啟動、連線、檔案解析、批次寫入與最後提交。Java 程式內部的寫入計時另為 6.630 秒。

產生資料、下載映像、啟動資料庫、編譯、建立空表與驗證查詢均排除於計時之外。測試前讀取一次資料檔，讓檔案進入快取。

LOAD 回報讀取、載入與提交均為 1,000,000 筆，略過、拒絕與刪除均為 0。兩張表的 `COUNT(*)` 都為 1,000,000，`EXCEPT ALL` 比對結果為 0 筆差異。ID 範圍為 1 到 1,000,000，合計為 500,000,500,000。

LOAD 的 `NONRECOVERABLE` 使用大量載入路徑，JDBC 使用一般交易日誌路徑，因此兩種方法的復原成本不同。

原始資料：[benchmark-results.csv](benchmark-results.csv)、[benchmark-output.txt](benchmark-output.txt)、[benchmark-validation.txt](benchmark-validation.txt)。
