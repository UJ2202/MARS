#!/usr/bin/env python3
"""Check database tables."""

from sqlalchemy import create_engine, inspect


def main():
    # Create database connection
    engine = create_engine("sqlite:///cmbagent.db")
    
    # Get inspector
    inspector = inspect(engine)
    
    # List all tables
    tables = inspector.get_table_names()
    
    print(f"\n{'='*80}")
    print(f"TABLES IN DATABASE: {len(tables)}")
    print(f"{'='*80}\n")
    
    for table in sorted(tables):
        print(f"  📊 {table}")
        
        # Get columns for this table
        columns = inspector.get_columns(table)
        for col in columns:
            print(f"      - {col['name']} ({col['type']})")
        print()


if __name__ == "__main__":
    main()
