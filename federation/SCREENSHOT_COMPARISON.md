# 與現場 SQLDBx 操作結果的差異分析

現場截圖顯示：舊端 ICBCDW（標示 CP950）匯出 IDCI0037，再於 UTF-8 的 MEGADW 以 `CODEPAGE 950` 載入；回到舊端透過 Nickname 與 UNION ALL View 查詢時，「堃」仍正常顯示。截圖沒有提供實際字元 HEX、catalog CODEPAGE、Db2／驅動版本或造字設定，因此尚不能確定與本機結果不同的原因。

本機實測的結論限於 Db2 12.1.5、目前 DRDA 與轉碼設定。現場顯示結果不能直接用來證明或否定本機結果，須先核對是否為同一個 Unicode 字元及相同轉換路徑。

## 已確認的測試差異

| 項目 | 現場截圖 | 本機原測試 |
|---|---|---|
| 資料來源 | 原本已存在於舊端 CP950，經 export／load 遷移 | 直接在 UTF-8 資料庫插入 Unicode literal |
| 「堃」的實際值 | 只有畫面字形，沒有 HEX | U+5803，UTF-8 `E5A083` |
| 工具 | SQLDBx，驅動與連線編碼未提供 | Db2 CLP，DB2CODEPAGE=1208 |
| 欄位 | 舊表 CHAR(76)、新表 CHAR(114)、Nickname／View CHAR(228) | 原測試 VARCHAR(100)，另補測下列 CHAR 路徑 |
| 驗證方式 | 成功寫入與正常顯示 | 同時核對來源 HEX、查詢 SQLCA、舊端本地儲存 HEX 與來源前後完整性 |

從 CP950 資料出發的來回轉換，與直接寫入新的 Unicode 字元是不同測試。但「來源不同」本身還不能證明根因；如果兩邊真的都是 U+5803、相同資料型態及相同轉碼設定，仍需解釋為何轉換結果不同。

## 補測 CHAR 與 UNION ALL

2026-10-21 17:35:49（Asia/Taipei）補測；完整證據在 [20261021T093549Z_char_path](evidence/20261021T093549Z_char_path)。

| 物件 | 資料庫 | 實測型態／長度 | catalog CODEPAGE |
|---|---|---|---:|
| T_CHAR_PATH.TEST_TEXT | UTF-8 新端 | CHAR(114) | 1208 |
| T_OLD_CHAR_PATH.TEST_TEXT | Big5 舊端 | CHAR(76) | 950 |
| N_CHAR_PATH.TEST_TEXT | Big5 舊端 | CHAR(228) | 950 |
| V_CHAR_UNION.TEST_TEXT | Big5 舊端 | CHAR(228) | 950 |

來源保留兩筆對照資料：`王小明` 與 `堃`。Nickname、UNION ALL 的 SELECT 均成功。將 UNION ALL 結果寫入舊端實體表後，從本地表計算去除 CHAR 尾端補空白後的 HEX：

| 分支 | 字元 | 舊端儲存 HEX | 顯示 |
|---|---|---|---|
| LOCAL | 王小明 | A4FDA470A9FA | 王小明 |
| REMOTE | 王小明 | A4FDA470A9FA | 王小明 |
| LOCAL | 堃 | C8FE | � |
| REMOTE | 堃 | C8FE | � |

來源「堃」前後均為 `E5A083`。見 [來源](evidence/20261021T093549Z_char_path/03_source_before.log)、[欄位 metadata](evidence/20261021T093549Z_char_path/07_metadata.log)、[本地儲存](evidence/20261021T093549Z_char_path/06_capture.log) 及 [results.json](evidence/20261021T093549Z_char_path/results.json)。

補測的 LOCAL CHAR(76) 表是從 Nickname 寫入，因此「堃」在寫入時已經替代；它用來驗證型態與 UNION ALL，並非現場原始 CP950 位元組的重建。沒有拿到現場原始 bytes，也未宣稱已重現其 export／load 過程。首次清空尚無資料的驗證表出現 SQLCODE=100；其後 INSERT 與 SELECT 成功。

這次補測證明：本機也有與截圖相同的 114→228 長度變化，但 CHAR 與 UNION ALL 不會讓本機 U+5803 變成可完整傳遞。需要繼續核對現場字元碼位與環境設定。

## 如何解讀截圖的長度與編碼欄

- `LOAD ... CODEPAGE 950` 指示載入工具如何解讀輸入檔案 bytes；它不會改變資料庫的 Code Page，也不會替往後的 Nickname SELECT 擴充字元對應。
- 76→114 看起來是搬遷時依常見 Big5 中文 2 bytes、UTF-8 中文 3 bytes 預留長度；是否由工具調整，須看建表 DDL，不能僅憑截圖判斷為 Db2 自動行為。
- 本機實際重現 CHAR(114)→Nickname CHAR(228)。這是跨碼頁欄位長度映射的預留容量，不表示每個字元的實際 bytes 都增加一倍，也不代表字元可被目標碼頁表示。
- UNION ALL 的兩側為 CHAR(76) 與 CHAR(228)，本機結果欄位為 CHAR(228)。
- 遠端表採 UTF-8，不代表舊端 Nickname 欄位也保留 UTF-8。本機 Nickname 與 View 的 CODEPAGE 都是 950。截圖的「UTF8」「CP950+UTF8」可能在描述資料來源，不能當作結果欄位實際編碼的證據，應讀 SYSCAT.COLUMNS。

## 最小現場查證資料

第一步請在兩邊**直接連到原始表所在的資料庫**，針對同一筆資料取得 HEX。以數字主鍵或其他可穩定傳送的條件定位，不要用舊端難字 literal 當條件。

```sql
-- 請替換 schema、欄位及主鍵條件；在新、舊資料庫各執行一次。
SELECT <主鍵欄位>,
       <文字欄位>,
       HEX(RTRIM(<文字欄位>)) AS STORED_HEX
FROM <SCHEMA>.IDCI0037
WHERE <主鍵條件>;
```

若新端欄位確認是 UTF-8 CHAR/VARCHAR，U+5803 的對應 bytes 應為 `E5A083`。整串有其他文字時應比對該字元的位置。若顯示為「堃」卻是其他 Unicode 值，需查造字／私用區字元與字型對應；畫面相同不保證碼位相同。這是待驗證的可能性，尚無證據斷定現場使用了造字。

第二步在兩個資料庫查物件欄位資訊：

```sql
SELECT TABSCHEMA, TABNAME, COLNAME, TYPENAME, LENGTH, CODEPAGE
FROM SYSCAT.COLUMNS
WHERE TABSCHEMA = '<實際大寫SCHEMA>'
  AND TABNAME IN ('IDCI0037', 'IDCI0037_U8', '<實際VIEW名稱>')
ORDER BY TABNAME, COLNO;
```

第三步記錄兩邊 `db2level`、`GET DB CFG` 的實際 code page、SQLDBx／驅動版本與 Unicode／ANSI 連線方式，以及是否有自訂轉碼表、造字或字型設定。若新端確為 U+5803 而回到舊端仍完整，這些轉碼及連線差異才是下一步比較重點。

如需確認現場舊端實際收到的字元，應在隔離測試 schema 將 Nickname 結果寫入本地表，再對本地表算 HEX。直接執行 `HEX(Nickname欄位)` 可能被推送到遠端，不能單憑它判定舊端已保留原字元。

本機補測重跑：首次執行 `python3 federation/compare_char_path.py --setup`，已建置後執行 `python3 federation/compare_char_path.py`。需要先完成主測試環境與「堃」資料準備。
