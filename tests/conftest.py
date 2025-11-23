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
    # Mock psycopg2.connect
    with patch('psycopg2.connect') as mock_connect, \
         patch('psycopg2.extras.execute_values') as mock_execute_values:
        
        # Create mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Set up cursor context manager
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None
        
        # Set up connection context manager
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        mock_conn.commit.return_value = None
        
        # Mock connection attributes
        mock_conn.encoding = 'UTF8'
        mock_cursor.connection = mock_conn
        
        mock_connect.return_value = mock_conn
        
        # Mock cursor methods
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.return_value = None
        mock_execute_values.return_value = None
        
        yield mock_cursor
