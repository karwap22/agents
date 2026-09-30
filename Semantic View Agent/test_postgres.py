import unittest

from postgres import validate_read_only_sql


class ReadOnlySqlTests(unittest.TestCase):
    def test_allows_select_and_cte(self):
        self.assertEqual(validate_read_only_sql("WITH paid AS (SELECT 1) SELECT * FROM paid;"), "WITH paid AS (SELECT 1) SELECT * FROM paid")

    def test_blocks_writes_and_multiple_statements(self):
        for sql in ("DELETE FROM demo.orders", "WITH x AS (DELETE FROM demo.orders RETURNING *) SELECT * FROM x", "SELECT 1; DROP TABLE demo.orders"):
            with self.assertRaises(ValueError):
                validate_read_only_sql(sql)


if __name__ == "__main__":
    unittest.main()
