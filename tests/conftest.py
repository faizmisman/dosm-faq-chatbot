import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path so 'app' package resolves
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Mock DATABASE_URL for tests that don't have database access
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")

@pytest.fixture(autouse=True)
def mock_database_operations():
    """Mock database operations for tests without real database."""
    with patch('psycopg2.connect') as mock_connect:
        # Create mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn
        
        # Mock cursor.fetchall() to return empty results by default
        mock_cursor.fetchall.return_value = []
        
        yield mock_cursor