import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.types import (
    BigInteger,
    Boolean,
    Date,
    Numeric,
    Text,
)

# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.append(str(PROJECT_ROOT))


# ============================================================
# IMPORT DATABASE CONNECTION
# ============================================================

from src.database.connection import engine


# ============================================================
# FILE CONFIGURATION
# ============================================================

PROCESSED_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "sales_ads_inventory_clean.csv"
)

TABLE_NAME = "business_sales"


# ============================================================
# EXPECTED 45 COLUMNS
# ============================================================

EXPECTED_COLUMNS = [

    # -----------------------------
    # Business data
    # -----------------------------

    "sku",
    "unit_ordered",
    "gross_sales",
    "ad_spend",
    "ad_revenue",

    "tacos",
    "acos",
    "roas",

    "ad_orders",
    "ad_units",

    "cvr",

    "impression",
    "click",

    "ctr",
    "cpc",

    "organic_percentage",
    "organic_sale",

    # -----------------------------
    # Inventory
    # -----------------------------

    "fba_inv",
    "awd",
    "fba_other",
    "esq",
    "moc_sellable",
    "moc_wh",

    # -----------------------------
    # Dimensions
    # -----------------------------

    "country",
    "platform",
    "year_month",

    # -----------------------------
    # Standardized KPIs
    # -----------------------------

    "roas_standard",
    "roas_percentage",

    "acos_standard",
    "ctr_standard",
    "cvr_standard",
    "tacos_standard",

    # -----------------------------
    # Business anomaly flags
    # -----------------------------

    "flag_cvr_anomaly",
    "flag_high_acos",
    "flag_high_tacos",

    "flag_negative_organic_sales",
    "flag_negative_organic_percentage",

    "flag_ad_spend_zero_sales",
    "flag_ad_spend_zero_ad_revenue",

    "flag_inventory_risk",

    "flag_click_gt_impression",
    "flag_ad_orders_gt_units",

    "flag_no_activity",

    # -----------------------------
    # Overall quality
    # -----------------------------

    "quality_flag_count",
    "quality_status",
]


# ============================================================
# BOOLEAN COLUMNS
# ============================================================

BOOLEAN_COLUMNS = [

    "flag_cvr_anomaly",
    "flag_high_acos",
    "flag_high_tacos",

    "flag_negative_organic_sales",
    "flag_negative_organic_percentage",

    "flag_ad_spend_zero_sales",
    "flag_ad_spend_zero_ad_revenue",

    "flag_inventory_risk",

    "flag_click_gt_impression",
    "flag_ad_orders_gt_units",

    "flag_no_activity",
]


# ============================================================
# NUMERIC COLUMNS
# ============================================================

NUMERIC_COLUMNS = [

    "unit_ordered",
    "gross_sales",
    "ad_spend",
    "ad_revenue",

    "tacos",
    "acos",
    "roas",

    "ad_orders",
    "ad_units",

    "cvr",

    "impression",
    "click",

    "ctr",
    "cpc",

    "organic_percentage",
    "organic_sale",

    "fba_inv",
    "awd",
    "fba_other",
    "esq",
    "moc_sellable",
    "moc_wh",

    "roas_standard",
    "roas_percentage",

    "acos_standard",
    "ctr_standard",
    "cvr_standard",
    "tacos_standard",

    "quality_flag_count",
]


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print()
    print("=" * 75)
    print("STEP 1 - LOADING PROCESSED DATA")
    print("=" * 75)

    print(f"File: {PROCESSED_FILE}")

    if not PROCESSED_FILE.exists():

        raise FileNotFoundError(
            f"\nProcessed file not found:\n{PROCESSED_FILE}"
        )

    df = pd.read_csv(PROCESSED_FILE)

    print(f"Rows    : {len(df):,}")
    print(f"Columns : {len(df.columns)}")

    return df


# ============================================================
# VALIDATE COLUMNS
# ============================================================

def validate_columns(df):

    print()
    print("=" * 75)
    print("STEP 2 - COLUMN VALIDATION")
    print("=" * 75)

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in df.columns
    ]

    unexpected_columns = [
        column
        for column in df.columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns:

        print("Missing columns:")

        for column in missing_columns:
            print(f"  - {column}")

        raise ValueError(
            "Required columns are missing."
        )

    print("✓ All required columns are present.")

    if unexpected_columns:

        print()
        print("⚠ Unexpected columns found:")

        for column in unexpected_columns:
            print(f"  - {column}")

    else:

        print("✓ No unexpected columns.")


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_data(df):

    print()
    print("=" * 75)
    print("STEP 3 - PREPARING DATA FOR POSTGRESQL")
    print("=" * 75)

    df = df.copy()

    # --------------------------------------------------------
    # Keep only expected columns
    # --------------------------------------------------------

    df = df[EXPECTED_COLUMNS]

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    for column in NUMERIC_COLUMNS:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    print("✓ Numeric columns converted.")

    # --------------------------------------------------------
    # Date conversion
    # --------------------------------------------------------

    df["year_month"] = pd.to_datetime(
        df["year_month"],
        errors="coerce"
    ).dt.date

    print("✓ year_month converted to DATE.")

    # --------------------------------------------------------
    # Boolean conversion
    # --------------------------------------------------------

    for column in BOOLEAN_COLUMNS:

        df[column] = (
            df[column]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "yes": True,
                "no": False,
            })
        )

    print("✓ Boolean flags converted.")

    # --------------------------------------------------------
    # Quality status
    # --------------------------------------------------------

    df["quality_status"] = (
        df["quality_status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    print("✓ Quality status standardized.")

    # --------------------------------------------------------
    # SKU / Country / Platform
    # --------------------------------------------------------

    df["sku"] = (
        df["sku"]
        .astype(str)
        .str.strip()
    )

    df["country"] = (
        df["country"]
        .astype(str)
        .str.strip()
    )

    df["platform"] = (
        df["platform"]
        .astype(str)
        .str.strip()
    )

    print("✓ Text dimensions cleaned.")

    return df


# ============================================================
# CREATE DATABASE TABLE
# ============================================================

def create_table():

    print()
    print("=" * 75)
    print("STEP 4 - CREATING SUPABASE TABLE")
    print("=" * 75)

    create_table_sql = f"""

    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (

        id BIGSERIAL PRIMARY KEY,

        sku TEXT NOT NULL,

        unit_ordered NUMERIC,
        gross_sales NUMERIC(18,4),
        ad_spend NUMERIC(18,4),
        ad_revenue NUMERIC(18,4),

        tacos NUMERIC(18,6),
        acos NUMERIC(18,6),
        roas NUMERIC(18,6),

        ad_orders NUMERIC,
        ad_units NUMERIC,

        cvr NUMERIC(18,6),

        impression NUMERIC,
        click NUMERIC,

        ctr NUMERIC(18,6),
        cpc NUMERIC(18,6),

        organic_percentage NUMERIC(18,6),
        organic_sale NUMERIC(18,4),

        fba_inv NUMERIC,
        awd NUMERIC,
        fba_other NUMERIC,
        esq NUMERIC,
        moc_sellable NUMERIC,
        moc_wh NUMERIC,

        country TEXT,
        platform TEXT,

        year_month DATE,

        roas_standard NUMERIC(18,6),
        roas_percentage NUMERIC(18,6),

        acos_standard NUMERIC(18,6),
        ctr_standard NUMERIC(18,6),
        cvr_standard NUMERIC(18,6),
        tacos_standard NUMERIC(18,6),

        flag_cvr_anomaly BOOLEAN,
        flag_high_acos BOOLEAN,
        flag_high_tacos BOOLEAN,

        flag_negative_organic_sales BOOLEAN,
        flag_negative_organic_percentage BOOLEAN,

        flag_ad_spend_zero_sales BOOLEAN,
        flag_ad_spend_zero_ad_revenue BOOLEAN,

        flag_inventory_risk BOOLEAN,

        flag_click_gt_impression BOOLEAN,
        flag_ad_orders_gt_units BOOLEAN,

        flag_no_activity BOOLEAN,

        quality_flag_count INTEGER,

        quality_status TEXT

    );

    """

    with engine.begin() as connection:

        connection.execute(
            text(create_table_sql)
        )

    print(
        f"✓ Table ready: {TABLE_NAME}"
    )


# ============================================================
# CLEAR OLD DATA
# ============================================================

def clear_table():

    print()
    print("=" * 75)
    print("STEP 5 - PREPARING TABLE FOR LOAD")
    print("=" * 75)

    with engine.begin() as connection:

        connection.execute(
            text(
                f"TRUNCATE TABLE {TABLE_NAME} "
                "RESTART IDENTITY;"
            )
        )

    print("✓ Previous ETL data cleared.")


# ============================================================
# DATABASE DATA TYPES
# ============================================================

def get_sqlalchemy_types():

    return {

        # Text
        "sku": Text(),
        "country": Text(),
        "platform": Text(),
        "quality_status": Text(),

        # Date
        "year_month": Date(),

        # Boolean
        "flag_cvr_anomaly": Boolean(),
        "flag_high_acos": Boolean(),
        "flag_high_tacos": Boolean(),

        "flag_negative_organic_sales": Boolean(),
        "flag_negative_organic_percentage": Boolean(),

        "flag_ad_spend_zero_sales": Boolean(),
        "flag_ad_spend_zero_ad_revenue": Boolean(),

        "flag_inventory_risk": Boolean(),

        "flag_click_gt_impression": Boolean(),
        "flag_ad_orders_gt_units": Boolean(),

        "flag_no_activity": Boolean(),

        # Integer
        "quality_flag_count": BigInteger(),

        # Numeric
        "unit_ordered": Numeric(),
        "gross_sales": Numeric(18, 4),
        "ad_spend": Numeric(18, 4),
        "ad_revenue": Numeric(18, 4),

        "tacos": Numeric(18, 6),
        "acos": Numeric(18, 6),
        "roas": Numeric(18, 6),

        "ad_orders": Numeric(),
        "ad_units": Numeric(),

        "cvr": Numeric(18, 6),

        "impression": Numeric(),
        "click": Numeric(),

        "ctr": Numeric(18, 6),
        "cpc": Numeric(18, 6),

        "organic_percentage": Numeric(18, 6),
        "organic_sale": Numeric(18, 4),

        "fba_inv": Numeric(),
        "awd": Numeric(),
        "fba_other": Numeric(),
        "esq": Numeric(),
        "moc_sellable": Numeric(),
        "moc_wh": Numeric(),

        "roas_standard": Numeric(18, 6),
        "roas_percentage": Numeric(18, 6),

        "acos_standard": Numeric(18, 6),
        "ctr_standard": Numeric(18, 6),
        "cvr_standard": Numeric(18, 6),
        "tacos_standard": Numeric(18, 6),
    }


# ============================================================
# INSERT DATA
# ============================================================

def insert_data(df):

    print()
    print("=" * 75)
    print("STEP 6 - INSERTING DATA INTO SUPABASE")
    print("=" * 75)

    print(
        f"Uploading {len(df):,} rows..."
    )

    # --------------------------------------------------------
    # Convert NaN to None
    # --------------------------------------------------------

    df = df.astype(object).where(
        pd.notna(df),
        None
    )

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    df.to_sql(
        name=TABLE_NAME,
        con=engine,
        if_exists="append",
        index=False,
        chunksize=500,
        method="multi",
        dtype=get_sqlalchemy_types(),
    )

    print(
        f"✓ Successfully inserted "
        f"{len(df):,} rows."
    )


# ============================================================
# VERIFY ROW COUNT
# ============================================================

def verify_row_count(expected_rows):

    print()
    print("=" * 75)
    print("STEP 7 - ROW COUNT VALIDATION")
    print("=" * 75)

    with engine.connect() as connection:

        actual_rows = connection.execute(
            text(
                f"SELECT COUNT(*) "
                f"FROM {TABLE_NAME};"
            )
        ).scalar()

    print(
        f"Expected rows : {expected_rows:,}"
    )

    print(
        f"Database rows : {actual_rows:,}"
    )

    if actual_rows == expected_rows:

        print(
            "✓ Row count validation PASSED."
        )

    else:

        raise ValueError(
            f"Row count mismatch! "
            f"Expected {expected_rows:,}, "
            f"found {actual_rows:,}."
        )


# ============================================================
# BUSINESS DATA VALIDATION
# ============================================================

def validate_database():

    print()
    print("=" * 75)
    print("STEP 8 - DATABASE BUSINESS VALIDATION")
    print("=" * 75)

    with engine.connect() as connection:

        result = connection.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS rows,
                    COUNT(DISTINCT sku) AS skus,
                    COUNT(DISTINCT country) AS countries,
                    COUNT(DISTINCT platform) AS platforms,
                    COUNT(DISTINCT year_month) AS months,

                    COALESCE(SUM(gross_sales), 0)
                        AS total_sales,

                    COALESCE(SUM(ad_spend), 0)
                        AS total_ad_spend,

                    COALESCE(SUM(ad_revenue), 0)
                        AS total_ad_revenue

                FROM {TABLE_NAME};
                """
            )
        )

        data = result.fetchone()

    print(
        f"Rows              : {data.rows:,}"
    )

    print(
        f"Unique SKUs       : {data.skus:,}"
    )

    print(
        f"Unique Countries  : {data.countries:,}"
    )

    print(
        f"Unique Platforms  : {data.platforms:,}"
    )

    print(
        f"Unique Months     : {data.months:,}"
    )

    print(
        f"Total Gross Sales : {data.total_sales:,.2f}"
    )

    print(
        f"Total Ad Spend    : {data.total_ad_spend:,.2f}"
    )

    print(
        f"Total Ad Revenue  : {data.total_ad_revenue:,.2f}"
    )

    print()
    print("✓ Business validation completed.")


# ============================================================
# QUALITY STATUS VALIDATION
# ============================================================

def validate_quality_status():

    print()
    print("=" * 75)
    print("STEP 9 - QUALITY STATUS DISTRIBUTION")
    print("=" * 75)

    with engine.connect() as connection:

        result = connection.execute(
            text(
                f"""
                SELECT
                    quality_status,
                    COUNT(*) AS row_count

                FROM {TABLE_NAME}

                GROUP BY quality_status

                ORDER BY quality_status;
                """
            )
        )

        rows = result.fetchall()

    for row in rows:

        print(
            f"{row.quality_status:<15}"
            f"{row.row_count:>10,}"
        )

    print()
    print("✓ Quality status validation completed.")


# ============================================================
# SAMPLE DATA CHECK
# ============================================================

def show_sample():

    print()
    print("=" * 75)
    print("STEP 10 - SAMPLE DATABASE RECORDS")
    print("=" * 75)

    query = text(
        f"""
        SELECT
            sku,
            gross_sales,
            ad_spend,
            ad_revenue,
            roas_standard,
            acos_standard,
            fba_inv,
            country,
            platform,
            year_month,
            quality_status

        FROM {TABLE_NAME}

        ORDER BY id

        LIMIT 5;
        """
    )

    with engine.connect() as connection:

        result = connection.execute(query)

        rows = result.fetchall()

    for row in rows:

        print(
            f"SKU={row.sku} | "
            f"Sales={row.gross_sales} | "
            f"AdSpend={row.ad_spend} | "
            f"AdRevenue={row.ad_revenue} | "
            f"ROAS={row.roas_standard} | "
            f"ACOS={row.acos_standard} | "
            f"Inventory={row.fba_inv} | "
            f"Country={row.country} | "
            f"Platform={row.platform} | "
            f"Month={row.year_month} | "
            f"Status={row.quality_status}"
        )

    print()
    print("✓ Sample records retrieved.")


# ============================================================
# MAIN ETL PIPELINE
# ============================================================

def main():

    print()
    print("=" * 75)
    print("       AI BUSINESS ANALYST - SUPABASE ETL PIPELINE")
    print("=" * 75)

    try:

        # ----------------------------------------------------
        # 1. Load
        # ----------------------------------------------------

        df = load_data()

        # ----------------------------------------------------
        # 2. Validate
        # ----------------------------------------------------

        validate_columns(df)

        # ----------------------------------------------------
        # 3. Prepare
        # ----------------------------------------------------

        df = prepare_data(df)

        # ----------------------------------------------------
        # 4. Create table
        # ----------------------------------------------------

        create_table()

        # ----------------------------------------------------
        # 5. Clear old records
        # ----------------------------------------------------

        clear_table()

        # ----------------------------------------------------
        # 6. Insert
        # ----------------------------------------------------

        insert_data(df)

        # ----------------------------------------------------
        # 7. Verify rows
        # ----------------------------------------------------

        verify_row_count(len(df))

        # ----------------------------------------------------
        # 8. Business validation
        # ----------------------------------------------------

        validate_database()

        # ----------------------------------------------------
        # 9. Quality validation
        # ----------------------------------------------------

        validate_quality_status()

        # ----------------------------------------------------
        # 10. Sample
        # ----------------------------------------------------

        show_sample()

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        print()
        print("=" * 75)
        print("              ETL PIPELINE COMPLETED")
        print("=" * 75)

        print()
        print("✓ Data successfully loaded into Supabase.")
        print(f"✓ Table: {TABLE_NAME}")
        print(f"✓ Rows loaded: {len(df):,}")
        print()

    except Exception as error:

        print()
        print("=" * 75)
        print("                 ETL PIPELINE FAILED")
        print("=" * 75)

        print()
        print(f"Error: {error}")
        print()

        raise


# ============================================================
# RUN ETL
# ============================================================

if __name__ == "__main__":

    main()