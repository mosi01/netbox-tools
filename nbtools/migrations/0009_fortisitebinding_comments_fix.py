"""
0009_fortisitebinding_comments_fix.py

Manual migration for the nbtools plugin.

Purpose
-------
Fix the FortiSiteBinding.comments database column so that object creation
does not fail with:

    IntegrityError:
    null value in column "comments" of relation "nbtools_fortisitebinding"
    violates not-null constraint

Why this migration is needed
----------------------------
Even though the form now posts a comments field, the current runtime path
is still reaching PostgreSQL with comments=NULL for FortiSiteBinding
inserts. To stabilise the plugin immediately, this migration:

1. Converts any existing NULL comments values to an empty string
2. Sets a database default of '' for the comments column
3. Drops the NOT NULL constraint so inserts with NULL no longer fail

This is a database-side compatibility fix and is appropriate as a manual
migration when automatic model/form fixes have not resolved the issue.

NetBox/Django note
------------------
NetBox documents that database schema changes are managed through Django
migrations and that manual intervention may sometimes be required for more
complex changes. After adding this file, run the normal `migrate` command.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """
    Manual migration to fix the FortiSiteBinding.comments column.
    """

    # ------------------------------------------------------------------
    # IMPORTANT:
    # Replace "0008_forti_site_binding" below if your latest migration
    # in nbtools has a different number/name.
    # ------------------------------------------------------------------
    dependencies = [
        ("nbtools", "0008_forti_site_binding"),
    ]

    operations = [
        migrations.RunSQL(
            # ----------------------------------------------------------
            # Forward migration
            # ----------------------------------------------------------
            sql=[
                # Ensure no existing rows contain NULL comments
                """
                UPDATE nbtools_fortisitebinding
                SET comments = ''
                WHERE comments IS NULL;
                """,

                # Set a database default for future inserts
                """
                ALTER TABLE nbtools_fortisitebinding
                ALTER COLUMN comments SET DEFAULT '';
                """,

                # Allow NULL to prevent current insert failures
                # (safe pragmatic fix for the current environment)
                """
                ALTER TABLE nbtools_fortisitebinding
                ALTER COLUMN comments DROP NOT NULL;
                """,
            ],

            # ----------------------------------------------------------
            # Reverse migration
            # ----------------------------------------------------------
            reverse_sql=[
                # Normalize any NULLs before restoring NOT NULL
                """
                UPDATE nbtools_fortisitebinding
                SET comments = ''
                WHERE comments IS NULL;
                """,

                # Restore NOT NULL if rolling back
                """
                ALTER TABLE nbtools_fortisitebinding
                ALTER COLUMN comments SET NOT NULL;
                """,

                # Remove the default if rolling back
                """
                ALTER TABLE nbtools_fortisitebinding
                ALTER COLUMN comments DROP DEFAULT;
                """,
            ],
        ),
    ]
