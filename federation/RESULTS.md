# Db2 Federation UTF-8／Big5 測試結果

**結論：查詢可成功，但直接查詢會靜默替代 Big5 無法表示的字元。`𠮷`、`😀` 與補充測試的 `堃` 在舊端實際存成 `C8FE`，UTF-8 用戶端顯示為 `�`，不是 `?`。由新端 VIEW 計算後傳回的 UTF-8 HEX 則完整一致。**

本次依測試計畫建立本機實驗環境，未連接實際新舊 DW。建置及測試於 2026-10-21 10:35:00（Asia/Taipei，UTC+8）開始，以下原始證據來自這次實際執行，目錄使用 UTC 時戳 [20261021T023500Z](evidence/20261021T023500Z)。

## 測試環境

| 項目 | 實測設定 |
|---|---|
| Db2 | Linux x86_64，12.1.5.0，SQL12015，Fix Pack 0，special_85816 |
| 容器 | `db2-bench-1m`，既有 `db2-bench-compact:verified` 映像 |
| 舊端資料庫 | `FOLD950`，Database Code Page 950，Code Set BIG5，Territory TW |
| 新端資料庫 | `FNEW1208`，Database Code Page 1208，Code Set UTF-8，Territory TW |
| Federation | `FEDERATED=YES`；DRDA wrapper（`libdb2drda.so`）；`NEW_DW_SERVER`，TYPE DB2/UDB，VERSION 12.1 |
| 傳輸 | 同一容器、同一 instance 的兩個資料庫，經 TCP/IP `127.0.0.1:50000`、alias `RNEW1208`，實際使用 Federation Nickname |
| 工具 | Linux Db2 CLP；`DB2CODEPAGE=1208`、`LANG=en_US.UTF-8`；未使用 SQLDBx |
| 欄位編碼 | catalog 確認 `N_UTF8_CHAR.TEST_TEXT` 與 `LOCAL_CAPTURE.TEST_TEXT` 的 CODEPAGE 均為 950 |

環境配置見 [02_environment.log](evidence/20261021T023500Z/02_environment.log)，wrapper、server 與欄位資訊見 [11_metadata.log](evidence/20261021T023500Z/11_metadata.log)。

## 原始 TC01–TC06 結果（五筆資料）

| 案例 | 實際結果（UTF-8 用戶端顯示） | 返回筆數 | SQLCODE | SQLSTATE | 判定 |
|---|---|---:|---:|---|---|
| [TC01](evidence/20261021T023500Z/TC01.log) 一般字元 | `ABC123`、`王小明` | 2 | 0 | 00000 | 一般字元正確 |
| [TC02](evidence/20261021T023500Z/TC02.log) 難字 | `𠮷` → `�` | 1 | 0 | 00000 | 查詢成功，字元失真 |
| [TC03](evidence/20261021T023500Z/TC03.log) 混合難字 | `陳𠮷祥` → `陳�祥` | 1 | 0 | 00000 | 一般中文字保留，難字替代 |
| [TC04](evidence/20261021T023500Z/TC04.log) Emoji | `😀` → `�` | 1 | 0 | 00000 | 查詢成功，字元失真 |
| [TC05](evidence/20261021T023500Z/TC05.log) 整批查詢 | 五筆全數返回，難字及 Emoji 同樣替代 | 5 | 0 | 00000 | 整批完成，文字完整性不通過 |
| [TC06](evidence/20261021T023500Z/TC06.log) UTF-8 HEX | 五筆 ID／HEX 與新端原始值一致 | 5 | 0 | 00000 | HEX 傳遞通過 |

上述 SELECT 的 SQLCA `sqlwarn` 欄位皆空白，沒有轉換警告；未出現原測試文件列舉的 -330、-332、-334 或 -1822。不能依 SQLCODE=0 或沒有警告認定文字完整。

## 本地儲存位元組

逐筆將 Nickname 結果寫入 `FOLD950.TESTCP.LOCAL_CAPTURE`，再對此本地表計算 `HEX(TEST_TEXT)`。五次 INSERT 的 SQLCODE 均為 0；HEX 不經 Nickname，避免運算被推送至來源。

| ID | 新端原始文字 | 新端 UTF-8 HEX | 舊端本地 Big5 HEX | 舊端位元組數 | 用戶端顯示 |
|---:|---|---|---|---:|---|
| 1 | ABC123 | `414243313233` | `414243313233` | 6 | ABC123 |
| 2 | 王小明 | `E78E8BE5B08FE6988E` | `A4FDA470A9FA` | 6 | 王小明 |
| 3 | 𠮷 | `F0A0AEB7` | `C8FE` | 2 | � |
| 4 | 陳𠮷祥 | `E999B3F0A0AEB7E7A5A5` | `B3AFC8FEB2BB` | 6 | 陳�祥 |
| 5 | 😀 | `F09F9880` | `C8FE` | 2 | � |

證據見 [09_local_hex.log](evidence/20261021T023500Z/09_local_hex.log)。CLP 輸出的 `�` 為 U+FFFD、UTF-8 位元組為 `EFBFBD`；這和舊端本地儲存的 `C8FE` 分屬不同編碼階段。

兩個不同來源字元均存成相同的 `C8FE`，原始字元差異已遺失。因此，這個結果不能解釋為單純的字型或畫面顯示問題，也不能從替代值可靠還原來源字元。

## 來源完整性與 HEX 通道

[06_source_before.log](evidence/20261021T023500Z/06_source_before.log) 與 [10_source_after.log](evidence/20261021T023500Z/10_source_after.log) 的五筆 ID／UTF-8 HEX 完全相同，來源資料未修改。TC06 的五筆 ID／HEX 亦完全相符，四項自動核對皆為 `true`，見 [results.json](evidence/20261021T023500Z/results.json)。

TC06 的 HEX 由來源 VIEW 先計算，再以 ASCII 文字通過 Nickname。本次驗證的是這五筆資料以 HEX 保留原始位元組；一般 VARCHAR Nickname 仍會轉碼失真。若採用 HEX 方式，應在支援 UTF-8 的接收端解 HEX 並按 UTF-8 解碼，保留 ID 對應。

## 補充 TC07：「堃」（U+5803）

於 2026-10-21 17:05:40（Asia/Taipei，UTC+8）在同一實驗環境加入 ID=6、CASE_NAME=`KUN`、TEST_TEXT=`堃`，並完整重跑 TC01–TC07。本次六筆資料的證據位於 [20261021T090540Z](evidence/20261021T090540Z)。

| 檢查 | 實測結果 | 證據 |
|---|---|---|
| 新端來源值 | `堃`；UTF-8 HEX 為 `E5A083`（3 位元組） | [06_source_before.log](evidence/20261021T090540Z/06_source_before.log) |
| TC07 Nickname 查詢 | 返回一筆，文字為 `�`；SQLCODE=0、SQLSTATE=00000，SQLCA 無警告 | [TC07.log](evidence/20261021T090540Z/TC07.log) |
| 舊端本地儲存 | ID=6 的 HEX 為 `C8FE`（2 位元組）；文字顯示為 `�` | [09_local_hex.log](evidence/20261021T090540Z/09_local_hex.log) |
| TC06 原始 HEX 通道 | ID=6 正確返回 `E5A083` | [TC06.log](evidence/20261021T090540Z/TC06.log) |
| 查詢後來源值 | `堃` 與 `E5A083` 保持不變 | [10_source_after.log](evidence/20261021T090540Z/10_source_after.log) |

七個 SELECT 的 SQLCODE 均為 0、SQLSTATE 均為 00000；TC05 與 TC06 各返回六筆。六次寫入舊端本地驗證表的 INSERT 也皆成功。六筆來源前後與預期 HEX 完全一致，TC06 的六筆 ID／HEX 與來源完全一致，四項自動核對皆為 `true`，見 [results.json](evidence/20261021T090540Z/results.json)。

**因此，「堃」在本次 Db2 Code Page 950 路徑也無法完整保留。** 此案例涵蓋 Unicode BMP 內的三位元組 UTF-8 漢字。來源完整性比較以新增第六筆後、開始查詢前的資料為基準；測試準備階段的新增紀錄另存於 [05a_add_kun.log](evidence/20261021T090540Z/05a_add_kun.log)。

## 適用範圍

上述結論適用於本次 Db2 12.1.5、DRDA、950／1208、VARCHAR 與 CLP 條件。實際 DW 的 Db2 版本、Fix Pack、作業系統、wrapper 選項與 SQLDBx／驅動尚未提供，需在相對應環境重跑；不能假定其他版本也都使用 `C8FE` 或都不報錯。

二進位傳輸、長字串容量與正式應用整合未在本次驗證範圍。所有新建及寫入資料均位於本次專用資料庫與 `TESTCP` schema。

重跑方式見 [README.md](README.md)，腳本見 [run_tests.py](run_tests.py)。
