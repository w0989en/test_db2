#!/usr/bin/env python3
"""Compare CHAR(76)/CHAR(114), DRDA nickname expansion and UNION ALL."""
import argparse
from datetime import datetime, timezone
import json
import re
from run_tests import ROOT, CONTAINER, docker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true', help='Create comparison objects once')
    args = parser.parse_args()
    out = ROOT / 'evidence' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_char_path')
    out.mkdir(parents=True)
    results = []

    def sql(label, db, body):
        query = f'CONNECT TO {db};\n{body.strip()}\nCONNECT RESET;\nTERMINATE;\n'
        (out / f'{label}.sql').write_text(query, encoding='utf-8')
        p = docker('exec', '-i', '-u', 'db2inst1', CONTAINER, 'bash', '-lc',
                   '. "$HOME/sqllib/db2profile"; export DB2CODEPAGE=1208 LANG=en_US.UTF-8; db2 -a -tv',
                   input=query.encode())
        (out / f'{label}.log').write_bytes(p.stdout)
        output = p.stdout.decode('utf-8', errors='replace')
        codes = [int(v) for v in re.findall(r'sqlcode:\s*(-?\d+)', output)]
        results.append({'step': label, 'exit_code': p.returncode, 'sqlcodes': codes})
        print(label, p.returncode, codes, flush=True)
        if p.returncode >= 4 or any(c < 0 for c in codes):
            raise RuntimeError(f'Failed: {out / (label + ".log")}')
        return output

    if args.setup:
        sql('01_source_setup', 'FNEW1208', '''
CREATE TABLE TESTCP.T_CHAR_PATH (ID INTEGER NOT NULL PRIMARY KEY, TEST_TEXT CHAR(114));
INSERT INTO TESTCP.T_CHAR_PATH SELECT ID, TEST_TEXT FROM TESTCP.T_UTF8_CHAR WHERE ID IN (2, 6);
''')
        sql('02_federation_setup', 'FOLD950', '''
CREATE NICKNAME TESTCP.N_CHAR_PATH FOR NEW_DW_SERVER."TESTCP"."T_CHAR_PATH";
CREATE TABLE TESTCP.T_OLD_CHAR_PATH (ID INTEGER NOT NULL PRIMARY KEY, TEST_TEXT CHAR(76));
INSERT INTO TESTCP.T_OLD_CHAR_PATH SELECT ID, TEST_TEXT FROM TESTCP.N_CHAR_PATH;
CREATE VIEW TESTCP.V_CHAR_UNION AS
SELECT CAST('LOCAL' AS VARCHAR(6)) AS ORIGIN, ID, TEST_TEXT FROM TESTCP.T_OLD_CHAR_PATH
UNION ALL
SELECT CAST('REMOTE' AS VARCHAR(6)) AS ORIGIN, ID, TEST_TEXT FROM TESTCP.N_CHAR_PATH;
CREATE TABLE TESTCP.T_UNION_CAPTURE (ORIGIN VARCHAR(6), ID INTEGER, TEST_TEXT CHAR(228));
''')
    before = sql('03_source_before', 'FNEW1208', '''
SELECT ID, RTRIM(TEST_TEXT) AS TEXT_VALUE, HEX(RTRIM(TEST_TEXT)) AS UTF8_HEX FROM TESTCP.T_CHAR_PATH ORDER BY ID;
SELECT TABNAME, COLNAME, TYPENAME, LENGTH, CODEPAGE FROM SYSCAT.COLUMNS WHERE TABSCHEMA='TESTCP' AND TABNAME='T_CHAR_PATH' ORDER BY COLNO;
''')
    sql('04_nickname', 'FOLD950', 'SELECT ID, TEST_TEXT FROM TESTCP.N_CHAR_PATH ORDER BY ID;')
    sql('05_union', 'FOLD950', 'SELECT ORIGIN, ID, TEST_TEXT FROM TESTCP.V_CHAR_UNION ORDER BY ORIGIN, ID;')
    capture = sql('06_capture', 'FOLD950', '''
DELETE FROM TESTCP.T_UNION_CAPTURE;
INSERT INTO TESTCP.T_UNION_CAPTURE SELECT ORIGIN, ID, TEST_TEXT FROM TESTCP.V_CHAR_UNION;
SELECT ORIGIN, ID, RTRIM(TEST_TEXT) AS TEXT_VALUE, HEX(RTRIM(TEST_TEXT)) AS BIG5_HEX FROM TESTCP.T_UNION_CAPTURE ORDER BY ORIGIN, ID;
''')
    sql('07_metadata', 'FOLD950', '''
SELECT TABNAME, COLNAME, TYPENAME, LENGTH, CODEPAGE FROM SYSCAT.COLUMNS
WHERE TABSCHEMA='TESTCP' AND TABNAME IN ('T_OLD_CHAR_PATH', 'N_CHAR_PATH', 'V_CHAR_UNION', 'T_UNION_CAPTURE') ORDER BY TABNAME, COLNO;
''')
    after = sql('08_source_after', 'FNEW1208', 'SELECT ID, RTRIM(TEST_TEXT) AS TEXT_VALUE, HEX(RTRIM(TEST_TEXT)) AS UTF8_HEX FROM TESTCP.T_CHAR_PATH ORDER BY ID;')
    def source_rows(output):
        return dict(re.findall(r'^\s*(2|6)\s+\S+\s+([0-9A-F]+)\s*$', output, re.M))
    expected = {'2': 'E78E8BE5B08FE6988E', '6': 'E5A083'}
    rows = [{'origin': origin, 'id': int(row_id), 'text': text, 'big5_hex': hex_value}
            for origin, row_id, text, hex_value in re.findall(
                r'^\s*(LOCAL|REMOTE)\s+(2|6)\s+(\S+)\s+([0-9A-F]+)\s*$', capture, re.M)]
    validation = {'source_before_matches': source_rows(before) == expected,
                  'source_after_matches': source_rows(after) == expected,
                  'four_union_rows_captured': len(rows) == 4}
    (out / 'results.json').write_text(json.dumps({'results': results, 'local_capture': rows,
        'validation': validation,
        'scope': 'The local CHAR(76) table was filled via the nickname; it is not a reproduction of the other environment\'s original CP950 bytes.'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Evidence:', out, flush=True)
    print(json.dumps(rows, ensure_ascii=False), flush=True)
    if not all(validation.values()):
        raise SystemExit('Integrity validation failed')


if __name__ == '__main__':
    main()
