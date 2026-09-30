# Db2 1000 萬筆寫入實測

測試日期：2026-09-30 UTC。兩種方法各執行一輪，使用相同資料檔、相同欄位與沒有索引的空表。

| 方法 | 總耗時（秒） | Java 寫檔（秒） | Db2 LOAD（秒） | 寫入筆數 | 每秒筆數 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Db2 原生 LOAD（含 Java 產檔） | 5.945 | 1.243 | 4.703 | 10,000,000 | 1,682,002 |
| Java JDBC 批次 INSERT | 79.057 | — | — | 10,000,000 | 126,492 |

本輪含產檔的 LOAD 總吞吐量約為 JDBC 的 **13.3 倍**。這是此雲端環境的一次量測；`LOAD` 的總時間包含 Java 寫檔，JDBC 的時間只包含讀取現有檔案與寫入資料庫，因此兩列的工作範圍不同。

## 測試條件

- Db2 LUW 12.1.5.0（`special_85816`）、OpenJDK 21.0.12.1、IBM JDBC driver 12.1.5.0。
- 雲端容器限制為 4 顆 CPU、32 GiB 記憶體；磁碟容量 32 GB，Docker 儲存驅動為 `vfs`。Db2 映像合併成單層以符合磁碟空間限制；原始映像校驗通過後才匯入。
- 原始映像：`icr.io/db2_community/db2@sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6`。
- 同一份 DEL 檔：10,000,000 行、457,778,898 bytes。SHA-256：`b6af673198bb2d01c583db12afd310c4951e825ec7b5886f6a5ef86d0151bd1d`。
- 欄位為 `ID BIGINT NOT NULL`、`PAYLOAD VARCHAR(64) NOT NULL`、`AMOUNT INTEGER NOT NULL`，兩張表都沒有索引。
- LOAD 使用伺服器可讀取的唯讀檔案掛載與 `NONRECOVERABLE`。JDBC 使用 `PreparedStatement.addBatch()`／`executeBatch()`，關閉 auto-commit，每 1,000 筆提交一次。
- JDBC 連到同一台機器的 `127.0.0.1:50000`。LOAD 與 JDBC 使用同一個 Db2 實例。

## 計時與正確性

CSV 的 `file_write_seconds` 從呼叫 Java 產檔開始，到檔案寫完、`FileChannel.force(true)` 同步、原子替換舊檔，並設好檔案讀取權限。`db_load_seconds` 包含 Docker exec、Db2 連線與載入。LOAD 的 `seconds` 是兩段的總和；JDBC 的 `seconds` 包含 JVM 啟動、連線、檔案解析、批次寫入與最後提交。Java 程式內部的產檔與 JDBC 插入計時分別為 1.178 秒與 78.746 秒。

下載映像、啟動資料庫、編譯、建立空表與驗證查詢均排除於計時之外。產檔是 LOAD 計時的第一段，沒有在 LOAD 前預讀資料檔。

LOAD 回報讀取、載入與提交均為 10,000,000 筆，略過、拒絕與刪除均為 0。兩張表的 `COUNT(*)` 都為 10,000,000；雙向 `EXCEPT ALL` 都沒有差異。兩表 ID 範圍均為 1 到 10,000,000，合計為 50,000,005,000,000。分段及總耗時分別四捨五入到毫秒，因此顯示值相加可能差 0.001 秒。

LOAD 的 `NONRECOVERABLE` 使用大量載入路徑，JDBC 使用一般交易日誌路徑，因此兩種方法的復原成本不同。

原始資料：[benchmark-results.csv](benchmark-results.csv)、[benchmark-output.txt](benchmark-output.txt)、[benchmark-validation.txt](benchmark-validation.txt)。
