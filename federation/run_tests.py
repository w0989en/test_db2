#!/usr/bin/env python3
"""Run Db2 Federation UTF-8/Big5 tests in the existing local laboratory container."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
CONTAINER = os.environ.get("DB2_TEST_CONTAINER", "db2-bench-1m")
ENV = {k: v for k, v in os.environ.items() if k not in {
    "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]
EXPECTED = {1: "414243313233", 2: "E78E8BE5B08FE6988E", 3: "F0A0AEB7",
            4: "E999B3F0A0AEB7E7A5A5", 5: "F09F9880", 6: "E5A083"}


def docker(*args, input=None):
    return subprocess.run(DOCKER + list(args), input=input, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env=ENV)


def source_rows(output):
    return {int(row_id): hex_value for row_id, hex_value in re.findall(
        r"^\s*(\d+)\s+(?:ASCII|BIG5|UNICODE|MIXED|EMOJI|KUN)\s+\S+\s+([0-9A-F]+)\s*$",
        output, re.M)}


def local_rows(output):
    return [{"id": int(row_id), "case_name": name, "text": text,
             "big5_hex": hex_value, "byte_length": int(length)}
            for row_id, name, text, hex_value, length in re.findall(
                r"^\s*(\d+)\s+(ASCII|BIG5|UNICODE|MIXED|EMOJI|KUN)\s+(\S+)\s+([0-9A-F]+)\s+(\d+)\s*$",
                output, re.M)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true", help="Create databases and objects; use only for first setup")
    parser.add_argument("--add-kun", action="store_true", help="Add the 堃 test row to an existing five-row lab dataset")
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "evidence" / run_id
    out.mkdir(parents=True)
    results = []
    password = ""
    if args.setup:
        for line in (PROJECT / ".local/db2.env").read_text().splitlines():
            if line.startswith("DB2INST1_PASSWORD="):
                password = line.split("=", 1)[1]
        if not password:
            raise SystemExit("Missing existing lab password in .local/db2.env")

    def redact(data):
        return data.replace(password.encode(), b"<LAB_PASSWORD>") if password else data

    def save_results(**extra):
        (out / "results.json").write_text(json.dumps({
            "run_id": run_id, "container": CONTAINER,
            "source": "FNEW1208", "federation": "FOLD950",
            "expected_source_hex": EXPECTED, "results": results, **extra,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def command(label, shell):
        proc = docker("exec", "-u", "db2inst1", CONTAINER, "bash", "-lc",
                      '. "$HOME/sqllib/db2profile"; export DB2CODEPAGE=1208 LANG=en_US.UTF-8; ' + shell)
        (out / (label + ".log")).write_bytes(redact(proc.stdout))
        if proc.returncode:
            raise RuntimeError(f"{label} failed: see {out / (label + '.log')}")
        return proc

    def sql(label, db, statement, strict=True):
        text = f"CONNECT TO {db};\n{statement.strip()}\nCONNECT RESET;\nTERMINATE;\n"
        (out / (label + ".sql")).write_bytes(redact(text.encode()))
        proc = docker("exec", "-i", "-u", "db2inst1", CONTAINER, "bash", "-lc",
                      '. "$HOME/sqllib/db2profile"; export DB2CODEPAGE=1208 LANG=en_US.UTF-8; db2 -a -tv',
                      input=text.encode())
        data = redact(proc.stdout)
        (out / (label + ".log")).write_bytes(data)
        decoded = data.decode("utf-8", errors="replace")
        codes = [int(v) for v in re.findall(r"sqlcode:\s*(-?\d+)", decoded, re.I)]
        states = re.findall(r"sqlstate:\s*(\w{5})", decoded, re.I)
        results.append({"case": label, "exit_code": proc.returncode,
                        "sqlcodes": codes, "sqlstates": states,
                        "selected_rows": [int(v) for v in re.findall(r"(\d+) record\(s\) selected", decoded)]})
        save_results(status="running")
        print(f"{label}: exit={proc.returncode} sqlcodes={codes}", flush=True)
        if strict and (proc.returncode >= 4 or any(v < 0 for v in codes)):
            raise RuntimeError(f"{label} failed: see {out / (label + '.log')}")
        return decoded

    if args.setup:
        directory = command("00_directory_before", "db2 list db directory").stdout.decode(errors="replace")
        if re.search(r"Database (?:alias|name)\s*=\s*(?:FNEW1208|FOLD950|RNEW1208)\b", directory):
            raise SystemExit("Lab names already exist; inspect them and rerun without --setup. Nothing was dropped.")
        command("01_create_databases", 'db2 "CREATE DATABASE FNEW1208 USING CODESET UTF-8 TERRITORY TW" && db2 "CREATE DATABASE FOLD950 USING CODESET BIG5 TERRITORY TW"')
    command("02_environment", "db2level; uname -a; locale; db2set -all; db2 get dbm cfg; db2 get db cfg for FOLD950; db2 get db cfg for FNEW1208")
    if args.setup:
        sql("03_source_setup", "FNEW1208", """
CREATE SCHEMA TESTCP;
CREATE TABLE TESTCP.T_UTF8_CHAR (ID INTEGER NOT NULL PRIMARY KEY, CASE_NAME VARCHAR(30), TEST_TEXT VARCHAR(100));
INSERT INTO TESTCP.T_UTF8_CHAR VALUES
  (1, 'ASCII', 'ABC123'), (2, 'BIG5', '王小明'), (3, 'UNICODE', '𠮷'),
  (4, 'MIXED', '陳𠮷祥'), (5, 'EMOJI', '😀'), (6, 'KUN', '堃');
CREATE VIEW TESTCP.V_UTF8_HEX AS SELECT ID, HEX(TEST_TEXT) AS UTF8_HEX FROM TESTCP.T_UTF8_CHAR;
""")
        command("04_catalog", "db2 catalog tcpip node UTF8NODE remote 127.0.0.1 server 50000 && db2 catalog database FNEW1208 as RNEW1208 at node UTF8NODE && db2 terminate")
        escaped = password.replace("'", "''")
        identifier = password.replace('"', '""')
        sql("05_federation_setup", "FOLD950", f"""
CREATE SCHEMA TESTCP;
CREATE WRAPPER DRDA;
CREATE SERVER NEW_DW_SERVER TYPE DB2/UDB VERSION '12.1' WRAPPER DRDA
  AUTHORIZATION \"db2inst1\" PASSWORD \"{identifier}\" OPTIONS (DBNAME 'RNEW1208');
CREATE USER MAPPING FOR USER SERVER NEW_DW_SERVER
  OPTIONS (REMOTE_AUTHID 'db2inst1', REMOTE_PASSWORD '{escaped}');
CREATE NICKNAME TESTCP.N_UTF8_CHAR FOR NEW_DW_SERVER.\"TESTCP\".\"T_UTF8_CHAR\";
CREATE NICKNAME TESTCP.N_UTF8_HEX FOR NEW_DW_SERVER.\"TESTCP\".\"V_UTF8_HEX\";
CREATE TABLE TESTCP.LOCAL_CAPTURE (ID INTEGER NOT NULL PRIMARY KEY, CASE_NAME VARCHAR(30), TEST_TEXT VARCHAR(100));
""")

    if args.add_kun:
        sql("05a_add_kun", "FNEW1208", """
INSERT INTO TESTCP.T_UTF8_CHAR (ID, CASE_NAME, TEST_TEXT)
SELECT 6, 'KUN', '堃' FROM SYSIBM.SYSDUMMY1
WHERE NOT EXISTS (SELECT 1 FROM TESTCP.T_UTF8_CHAR WHERE ID = 6);
""")

    source_select = "SELECT ID, CASE_NAME, TEST_TEXT, HEX(TEST_TEXT) AS UTF8_HEX FROM TESTCP.T_UTF8_CHAR ORDER BY ID;"
    before = sql("06_source_before", "FNEW1208", source_select)
    if source_rows(before) != EXPECTED:
        raise RuntimeError("Source baseline differs from expected ID/HEX values; older five-row labs need --add-kun")
    case_outputs = {}
    for label, statement in [
        ("TC01", "SELECT ID, TEST_TEXT FROM TESTCP.N_UTF8_CHAR WHERE ID IN (1, 2) ORDER BY ID;"),
        ("TC02", "SELECT ID, TEST_TEXT FROM TESTCP.N_UTF8_CHAR WHERE ID = 3;"),
        ("TC03", "SELECT ID, TEST_TEXT FROM TESTCP.N_UTF8_CHAR WHERE ID = 4;"),
        ("TC04", "SELECT ID, TEST_TEXT FROM TESTCP.N_UTF8_CHAR WHERE ID = 5;"),
        ("TC05", "SELECT ID, CASE_NAME, TEST_TEXT FROM TESTCP.N_UTF8_CHAR ORDER BY ID;"),
        ("TC06", "SELECT ID, UTF8_HEX FROM TESTCP.N_UTF8_HEX ORDER BY ID;"),
        ("TC07", "SELECT ID, TEST_TEXT FROM TESTCP.N_UTF8_CHAR WHERE ID = 6;"),
    ]:
        case_outputs[label] = sql(label, "FOLD950", statement, strict=False)

    # HEX over a physical local table cannot be pushed to the source database.
    sql("07_clear_local_capture", "FOLD950", "DELETE FROM TESTCP.LOCAL_CAPTURE;")
    for row_id in EXPECTED:
        sql(f"08_capture_{row_id}", "FOLD950", f"INSERT INTO TESTCP.LOCAL_CAPTURE SELECT ID, CASE_NAME, TEST_TEXT FROM TESTCP.N_UTF8_CHAR WHERE ID = {row_id};", strict=False)
    captured = sql("09_local_hex", "FOLD950", "SELECT ID, CASE_NAME, TEST_TEXT, HEX(TEST_TEXT) AS BIG5_HEX, LENGTH(TEST_TEXT) AS BYTE_LENGTH FROM TESTCP.LOCAL_CAPTURE ORDER BY ID;")
    after = sql("10_source_after", "FNEW1208", source_select)
    sql("11_metadata", "FOLD950", """
SELECT WRAPNAME, WRAPTYPE, LIBRARY FROM SYSCAT.WRAPPERS;
SELECT SERVERNAME, SERVERTYPE, SERVERVERSION FROM SYSCAT.SERVERS;
SELECT TABSCHEMA, TABNAME, COLNAME, TYPENAME, LENGTH, CODEPAGE FROM SYSCAT.COLUMNS WHERE TABSCHEMA='TESTCP' ORDER BY TABNAME, COLNO;
""")
    hex_rows = {int(row_id): hex_value for row_id, hex_value in re.findall(
        r"^\s*(\d+)\s+([0-9A-F]+)\s*$", case_outputs["TC06"], re.M)}
    validation = {"source_before_matches_expected": source_rows(before) == EXPECTED,
                  "source_after_matches_expected": source_rows(after) == EXPECTED,
                  "source_unchanged": source_rows(before) == source_rows(after),
                  "tc06_hex_matches_source": hex_rows == EXPECTED}
    save_results(status="completed", local_capture=local_rows(captured), validation=validation)
    print(f"Evidence: {out}", flush=True)
    print("Validation:", json.dumps(validation), flush=True)
    if not all(validation.values()):
        raise SystemExit("Source/HEX integrity validation failed; review results.json")


if __name__ == "__main__":
    main()
