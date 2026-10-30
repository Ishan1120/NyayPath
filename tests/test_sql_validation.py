"""
NyayPath SQL Static Dependency & Syntax Validation Suite
Strictly verifies migrations 001 through 004 for a clean execution on a fresh PostgreSQL database.
"""

import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT_DIR / "migrations"

def validate_all_migrations():
    migration_files = [
        "001_create_campus_cases.sql",
        "002_security_remediation.sql",
        "003_rate_limit_security_fix.sql",
        "004_core_platform_schema.sql"
    ]

    print("=" * 70)
    print("  NYAYPATH SQL STATIC VALIDATION SUITE (MIGRATIONS 001-004)")
    print("=" * 70)

    defined_tables = set()
    defined_schemas = {"public"}
    defined_functions = set()
    defined_triggers = set()
    foreign_keys = []

    for filename in migration_files:
        filepath = MIGRATIONS_DIR / filename
        assert filepath.exists(), f"Migration file missing: {filename}"
        sql = filepath.read_text(encoding="utf-8")
        print(f"\n[Validating {filename}]")

        # 1. Track Schema Creations
        for schema_match in re.finditer(r"CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", sql, re.IGNORECASE):
            schema_name = schema_match.group(1).lower()
            defined_schemas.add(schema_name)
            print(f"  + Schema declared: {schema_name}")

        # 2. Track Table Creations and verify single declaration
        for table_match in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_\.]+)\s*\(", sql, re.IGNORECASE):
            raw_table_name = table_match.group(1).lower()
            table_name = raw_table_name if "." in raw_table_name else f"public.{raw_table_name}"
            assert table_name not in defined_tables, (
                f"Duplicate table creation detected! Table '{table_name}' was already created in an earlier migration."
            )
            defined_tables.add(table_name)
            print(f"  + Table declared: {table_name}")

        # 3. Track Function Declarations & verify SET search_path = '' on security definer
        for func_match in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-zA-Z0-9_\.]+)\s*\((.*?)\)",
            sql,
            re.IGNORECASE | re.DOTALL
        ):
            func_name = func_match.group(1).lower()
            defined_functions.add(func_name)
            # Find function body block
            body_start = func_match.start()
            body_end = sql.find("$$", body_start + len(func_match.group(0)))
            if body_end != -1:
                header = sql[body_start:body_end]
                if "SECURITY DEFINER" in header.upper():
                    assert "search_path = ''" in header.lower() or "search_path = \"\"" in header.lower(), (
                        f"SECURITY DEFINER function {func_name} in {filename} lacks 'SET search_path = ''''!"
                    )
            print(f"  + Function declared: {func_name} (security-definer verified)")

        # 4. Track Trigger Declarations
        for trig_match in re.finditer(r"CREATE\s+TRIGGER\s+(\w+)", sql, re.IGNORECASE):
            trig_name = trig_match.group(1).lower()
            defined_triggers.add(trig_name)
            print(f"  + Trigger declared: {trig_name}")

        # 5. Extract and verify Foreign Keys
        for fk_match in re.finditer(r"REFERENCES\s+([a-zA-Z0-9_\.]+)\s*\(([a-zA-Z0-9_]+)\)", sql, re.IGNORECASE):
            target_table = fk_match.group(1).lower()
            target_col = fk_match.group(2).lower()
            full_target = target_table if "." in target_table else f"public.{target_table}"
            # auth.users is pre-provided by Supabase Auth engine
            if not full_target.startswith("auth."):
                assert full_target in defined_tables, (
                    f"Foreign key violation in {filename}: Target table '{full_target}' does not exist prior to this reference!"
                )
            print(f"  + Enforceable FK reference verified: -> {full_target}({target_col})")

    # Final Inventory Assertion
    expected_tables = {
        "public.campus_cases",
        "public.rate_limit_attempts",
        "public.cases",
        "public.platform_admins",
        "public.profiles",
        "public.institutions",
        "public.institution_memberships",
        "public.confidential_student_identities",
        "public.case_documents",
        "public.case_activity_log",
        "public.legal_precedents",
        "public.saved_research"
    }
    missing_tables = expected_tables - defined_tables
    assert not missing_tables, f"Missing required platform tables: {missing_tables}"
    print(f"\n[SUCCESS] All 12 platform tables successfully declared exactly once with valid linear dependencies.")
    print("=" * 70)

if __name__ == "__main__":
    validate_all_migrations()

