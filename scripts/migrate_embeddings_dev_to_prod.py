#!/usr/bin/env python3
"""
Migrate embeddings from dev database to prod database.

This script copies all embeddings from the dev database to the prod database,
ensuring that UAT-validated embeddings are promoted to production without
regenerating them (which could introduce slight variations due to model
non-determinism or data changes).

Usage:
    python scripts/migrate_embeddings_dev_to_prod.py [--dry-run] [--batch-size 100]

Prerequisites:
    - Dev and prod database credentials configured
    - psycopg2 installed: pip install psycopg2-binary
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import execute_batch, Json


def get_db_connection(db_url: str):
    """Create database connection from URL."""
    return psycopg2.connect(db_url)


def get_row_count(conn, table: str = "embeddings") -> int:
    """Get total row count from table."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def fetch_embeddings_batch(
    conn, 
    table: str = "embeddings",
    offset: int = 0,
    limit: int = 100
) -> List[tuple]:
    """Fetch a batch of embeddings from source database."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, content, embedding, metadata, created_at
            FROM {table}
            ORDER BY created_at, id
            LIMIT %s OFFSET %s
            """,
            (limit, offset)
        )
        return cur.fetchall()


def clear_target_table(conn, table: str = "embeddings"):
    """Clear all rows from target table."""
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table} CASCADE")
        conn.commit()


def insert_embeddings_batch(
    conn,
    rows: List[tuple],
    table: str = "embeddings"
):
    """Insert batch of embeddings into target database."""
    # Convert metadata dict to Json for proper JSONB handling
    processed_rows = []
    for row in rows:
        id_val, content, embedding, metadata, created_at = row
        # Convert dict to psycopg2.extras.Json for JSONB column
        processed_rows.append((id_val, content, embedding, Json(metadata) if isinstance(metadata, dict) else metadata, created_at))
    
    with conn.cursor() as cur:
        execute_batch(
            cur,
            f"""
            INSERT INTO {table} (id, content, embedding, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                created_at = EXCLUDED.created_at
            """,
            processed_rows,
            page_size=100
        )
        conn.commit()


def verify_migration(source_conn, target_conn, table: str = "embeddings") -> Dict[str, int]:
    """Verify that migration was successful."""
    source_count = get_row_count(source_conn, table)
    target_count = get_row_count(target_conn, table)
    
    # Check a sample of IDs match
    with source_conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {table} ORDER BY created_at LIMIT 10")
        sample_ids = [row[0] for row in cur.fetchall()]
    
    with target_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE id = ANY(%s)", (sample_ids,))
        matching_count = cur.fetchone()[0]
    
    return {
        "source_count": source_count,
        "target_count": target_count,
        "sample_size": len(sample_ids),
        "matching_sample": matching_count
    }


def migrate_embeddings(
    source_db_url: str,
    target_db_url: str,
    dry_run: bool = False,
    batch_size: int = 100,
    clear_target: bool = True
):
    """
    Migrate embeddings from source (dev) to target (prod) database.
    
    Args:
        source_db_url: Connection string for source database (dev)
        target_db_url: Connection string for target database (prod)
        dry_run: If True, only report what would be done
        batch_size: Number of rows to process per batch
        clear_target: If True, truncate target table before migration
    """
    print("=" * 80)
    print("EMBEDDINGS MIGRATION: DEV → PROD")
    print("=" * 80)
    
    # Connect to databases
    print("\n1. Connecting to databases...")
    try:
        source_conn = get_db_connection(source_db_url)
        target_conn = get_db_connection(target_db_url)
        print("   ✓ Connected to source (dev)")
        print("   ✓ Connected to target (prod)")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        sys.exit(1)
    
    try:
        # Get source row count
        print("\n2. Analyzing source database...")
        source_count = get_row_count(source_conn)
        print(f"   Source embeddings: {source_count} rows")
        
        if source_count == 0:
            print("   ⚠ Warning: Source database has no embeddings!")
            return
        
        # Get target row count
        target_count_before = get_row_count(target_conn)
        print(f"   Target embeddings (before): {target_count_before} rows")
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made")
            print(f"   Would migrate {source_count} embeddings from dev to prod")
            if clear_target and target_count_before > 0:
                print(f"   Would clear {target_count_before} existing rows in prod")
            return
        
        # Clear target if requested
        if clear_target and target_count_before > 0:
            print(f"\n3. Clearing target database ({target_count_before} rows)...")
            clear_target_table(target_conn)
            print("   ✓ Target database cleared")
        else:
            print("\n3. Skipping target clear (will upsert)")
        
        # Migrate in batches
        print(f"\n4. Migrating embeddings (batch size: {batch_size})...")
        offset = 0
        total_migrated = 0
        
        while offset < source_count:
            # Fetch batch from source
            rows = fetch_embeddings_batch(source_conn, offset=offset, limit=batch_size)
            
            if not rows:
                break
            
            # Insert into target
            insert_embeddings_batch(target_conn, rows)
            
            total_migrated += len(rows)
            offset += batch_size
            
            progress = (offset / source_count) * 100
            print(f"   Progress: {total_migrated}/{source_count} rows ({progress:.1f}%)")
        
        print(f"   ✓ Migrated {total_migrated} embeddings")
        
        # Verify migration
        print("\n5. Verifying migration...")
        verification = verify_migration(source_conn, target_conn)
        print(f"   Source count: {verification['source_count']}")
        print(f"   Target count: {verification['target_count']}")
        print(f"   Sample verification: {verification['matching_sample']}/{verification['sample_size']} IDs match")
        
        if verification['source_count'] == verification['target_count']:
            print("   ✓ Migration successful!")
        else:
            print("   ⚠ Warning: Row counts don't match!")
        
    finally:
        source_conn.close()
        target_conn.close()
        print("\n6. Database connections closed")
    
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate embeddings from dev to prod database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of rows to process per batch (default: 100)"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear target table, only upsert"
    )
    parser.add_argument(
        "--source-url",
        default=os.getenv("DEV_DATABASE_URL"),
        help="Source (dev) database URL (default: from DEV_DATABASE_URL env)"
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("PROD_DATABASE_URL"),
        help="Target (prod) database URL (default: from PROD_DATABASE_URL env)"
    )
    parser.add_argument(
        "--skip-confirmation",
        action="store_true",
        help="Skip interactive confirmation (for automated execution)"
    )
    
    args = parser.parse_args()
    
    # Validate database URLs
    if not args.source_url:
        print("Error: Source database URL not provided")
        print("Set DEV_DATABASE_URL environment variable or use --source-url")
        sys.exit(1)
    
    if not args.target_url:
        print("Error: Target database URL not provided")
        print("Set PROD_DATABASE_URL environment variable or use --target-url")
        sys.exit(1)
    
    # Safety check - require explicit confirmation for prod
    if not args.dry_run and not args.skip_confirmation:
        print("⚠️  WARNING: You are about to modify the PRODUCTION database!")
        print(f"   Source: {args.source_url[:50]}...")
        print(f"   Target: {args.target_url[:50]}...")
        
        if not args.no_clear:
            print("   Action: CLEAR target and copy all embeddings")
        else:
            print("   Action: UPSERT embeddings (keep existing)")
        
        response = input("\nType 'yes' to continue: ")
        if response.lower() != "yes":
            print("Migration cancelled")
            sys.exit(0)
    
    # Run migration
    migrate_embeddings(
        source_db_url=args.source_url,
        target_db_url=args.target_url,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        clear_target=not args.no_clear
    )


if __name__ == "__main__":
    main()
