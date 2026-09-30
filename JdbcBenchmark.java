import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Locale;

public class JdbcBenchmark {
    private static final String COLUMNS =
            "(ID BIGINT NOT NULL, PAYLOAD VARCHAR(64) NOT NULL, AMOUNT INTEGER NOT NULL)";

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            throw new IllegalArgumentException("Usage: JdbcBenchmark prepare | count TABLE | insert FILE BATCH_SIZE");
        }
        String url = required("DB2_URL");
        String user = required("DB2_USER");
        String password = required("DB2_PASSWORD");
        Class.forName("com.ibm.db2.jcc.DB2Driver");
        try (Connection connection = DriverManager.getConnection(url, user, password)) {
            switch (args[0]) {
                case "prepare" -> {
                    if (args.length != 1) throw new IllegalArgumentException("prepare takes no arguments");
                    prepare(connection);
                    System.out.println("prepared=BENCH_LOAD,BENCH_JDBC");
                }
                case "count" -> {
                    if (args.length != 2) throw new IllegalArgumentException("count requires a table name");
                    System.out.println(count(connection, allowedTable(args[1])));
                }
                case "insert" -> {
                    if (args.length != 3) throw new IllegalArgumentException("insert requires FILE BATCH_SIZE");
                    insert(connection, Path.of(args[1]), Integer.parseInt(args[2]));
                }
                default -> throw new IllegalArgumentException("Unknown command: " + args[0]);
            }
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is required");
        return value;
    }

    private static String allowedTable(String table) {
        if (!table.equals("BENCH_LOAD") && !table.equals("BENCH_JDBC")) {
            throw new IllegalArgumentException("Unsupported table: " + table);
        }
        return table;
    }

    private static void prepare(Connection connection) throws SQLException {
        for (String table : new String[] {"BENCH_LOAD", "BENCH_JDBC"}) {
            try (PreparedStatement exists = connection.prepareStatement(
                    "SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ?")) {
                exists.setString(1, table);
                try (ResultSet result = exists.executeQuery()) {
                    result.next();
                    if (result.getInt(1) != 0) {
                        try (Statement statement = connection.createStatement()) {
                            statement.executeUpdate("DROP TABLE " + table);
                        }
                    }
                }
            }
            try (Statement statement = connection.createStatement()) {
                statement.executeUpdate("CREATE TABLE " + table + " " + COLUMNS);
            }
        }
    }

    private static long count(Connection connection, String table) throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery("SELECT COUNT(*) FROM " + table)) {
            result.next();
            return result.getLong(1);
        }
    }

    private static void insert(Connection connection, Path file, int batchSize) throws Exception {
        if (batchSize < 1) throw new IllegalArgumentException("BATCH_SIZE must be positive");
        connection.setAutoCommit(false);
        long rows = 0;
        long started = System.nanoTime();
        try (BufferedReader input = Files.newBufferedReader(file, StandardCharsets.US_ASCII);
             PreparedStatement insert = connection.prepareStatement(
                     "INSERT INTO BENCH_JDBC (ID, PAYLOAD, AMOUNT) VALUES (?, ?, ?)")) {
            String line;
            while ((line = input.readLine()) != null) {
                int first = line.indexOf(',');
                int second = line.indexOf(',', first + 1);
                if (first < 1 || second <= first + 1 || line.indexOf(',', second + 1) >= 0) {
                    throw new IllegalArgumentException("Invalid DEL row at line " + (rows + 1));
                }
                long id = Long.parseLong(line.substring(0, first));
                if (id != rows + 1) throw new IllegalArgumentException("Unexpected ID at line " + (rows + 1));
                insert.setLong(1, id);
                insert.setString(2, line.substring(first + 1, second));
                insert.setInt(3, Integer.parseInt(line.substring(second + 1)));
                insert.addBatch();
                rows++;
                if (rows % batchSize == 0) {
                    insert.executeBatch();
                    connection.commit();
                }
            }
            if (rows % batchSize != 0) {
                insert.executeBatch();
                connection.commit();
            }
        } catch (Exception failure) {
            connection.rollback();
            throw failure;
        }
        double seconds = (System.nanoTime() - started) / 1_000_000_000.0;
        System.out.printf(Locale.ROOT, "inserted=%d elapsed_seconds=%.3f rows_per_second=%.0f%n",
                rows, seconds, rows / seconds);
    }
}
