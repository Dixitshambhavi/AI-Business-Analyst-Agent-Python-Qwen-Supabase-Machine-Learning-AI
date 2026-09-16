from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "sales_ads_inventory.csv"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

CLEAN_FILE = (
    PROCESSED_DIR
    / "sales_ads_inventory_clean.csv"
)

QUALITY_FILE = (
    PROCESSED_DIR
    / "data_quality_report.csv"
)

SUMMARY_FILE = (
    PROCESSED_DIR
    / "data_quality_summary.csv"
)


# ============================================================
# EXPECTED COLUMNS
# ============================================================

EXPECTED_COLUMNS = [
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
    "fba_inv",
    "awd",
    "fba_other",
    "esq",
    "moc_sellable",
    "moc_wh",
    "country",
    "platform",
    "year_month",
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
]


# ============================================================
# LOAD DATA
# ============================================================

def load_data(file_path: Path) -> pd.DataFrame:

    print("\n" + "=" * 75)
    print("STEP 1 - LOADING RAW DATA")
    print("=" * 75)

    if not file_path.exists():

        raise FileNotFoundError(
            f"\nCSV file not found:\n{file_path}\n\n"
            "Expected location:\n"
            "data/raw/sales_ads_inventory.csv"
        )

    df = pd.read_csv(file_path)

    print(f"File      : {file_path.name}")
    print(f"Rows      : {df.shape[0]:,}")
    print(f"Columns   : {df.shape[1]:,}")

    return df


# ============================================================
# CLEAN COLUMN NAMES
# ============================================================

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )

    return df


# ============================================================
# COLUMN VALIDATION
# ============================================================

def validate_columns(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 2 - COLUMN VALIDATION")
    print("=" * 75)

    actual_columns = list(df.columns)

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns:

        print("\n❌ Missing columns:")

        for column in missing_columns:
            print(f"   - {column}")

    else:

        print("✓ All expected columns are present.")

    if unexpected_columns:

        print("\n⚠ Unexpected columns:")

        for column in unexpected_columns:
            print(f"   - {column}")

    else:

        print("✓ No unexpected columns.")


# ============================================================
# DATA TYPE CONVERSION
# ============================================================

def convert_data_types(df: pd.DataFrame) -> pd.DataFrame:

    print("\n" + "=" * 75)
    print("STEP 3 - DATA TYPE CONVERSION")
    print("=" * 75)

    df = df.copy()

    # -----------------------------
    # Numeric columns
    # -----------------------------

    for column in NUMERIC_COLUMNS:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # -----------------------------
    # String columns
    # -----------------------------

    string_columns = [
        "sku",
        "country",
        "platform",
    ]

    for column in string_columns:

        if column in df.columns:

            df[column] = (
                df[column]
                .astype("string")
                .str.strip()
            )

    # -----------------------------
    # Year-month
    # -----------------------------

    if "year_month" in df.columns:

        df["year_month"] = pd.to_datetime(
            df["year_month"].astype(str),
            format="%Y-%m",
            errors="coerce"
        )

    print("✓ Numeric columns converted.")
    print("✓ String columns cleaned.")
    print("✓ year_month converted to datetime.")

    return df


# ============================================================
# MISSING VALUE ANALYSIS
# ============================================================

def missing_value_analysis(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 4 - MISSING VALUE ANALYSIS")
    print("=" * 75)

    missing = df.isna().sum()

    missing = missing[missing > 0]

    if missing.empty:

        print("✓ No missing values detected.")

    else:

        print("\n⚠ Missing values:")

        for column, count in missing.items():

            percentage = (
                count / len(df)
            ) * 100

            print(
                f"   {column:<25}"
                f"{count:>8,} "
                f"({percentage:.2f}%)"
            )


# ============================================================
# DUPLICATE ANALYSIS
# ============================================================

def duplicate_analysis(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 5 - DUPLICATE ANALYSIS")
    print("=" * 75)

    exact_duplicates = df.duplicated().sum()

    print(
        f"Exact duplicate rows: "
        f"{exact_duplicates:,}"
    )

    business_key = [
        "sku",
        "country",
        "platform",
        "year_month",
    ]

    if all(
        column in df.columns
        for column in business_key
    ):

        business_duplicates = (
            df.duplicated(
                subset=business_key,
                keep=False
            ).sum()
        )

        print(
            "Duplicate "
            "SKU/Country/Platform/Month rows: "
            f"{business_duplicates:,}"
        )


# ============================================================
# KPI CALCULATION
# ============================================================

def calculate_kpis(df: pd.DataFrame) -> pd.DataFrame:

    print("\n" + "=" * 75)
    print("STEP 6 - STANDARDIZED KPI CALCULATIONS")
    print("=" * 75)

    df = df.copy()

    # --------------------------------------------------------
    # Standard ROAS
    #
    # Example:
    # Ad Revenue = 120
    # Ad Spend   = 100
    #
    # ROAS = 1.20
    # --------------------------------------------------------

    df["roas_standard"] = np.where(
        df["ad_spend"] > 0,
        df["ad_revenue"] / df["ad_spend"],
        np.nan
    )

    # ROAS percentage representation

    df["roas_percentage"] = (
        df["roas_standard"] * 100
    )

    # --------------------------------------------------------
    # ACOS
    # --------------------------------------------------------

    df["acos_standard"] = np.where(
        df["ad_revenue"] > 0,
        (
            df["ad_spend"]
            / df["ad_revenue"]
        ) * 100,
        np.nan
    )

    # --------------------------------------------------------
    # CTR
    # --------------------------------------------------------

    df["ctr_standard"] = np.where(
        df["impression"] > 0,
        (
            df["click"]
            / df["impression"]
        ) * 100,
        np.nan
    )

    # --------------------------------------------------------
    # CVR
    # --------------------------------------------------------

    df["cvr_standard"] = np.where(
        df["click"] > 0,
        (
            df["ad_orders"]
            / df["click"]
        ) * 100,
        np.nan
    )

    # --------------------------------------------------------
    # TACOS
    # --------------------------------------------------------

    df["tacos_standard"] = np.where(
        df["gross_sales"] > 0,
        (
            df["ad_spend"]
            / df["gross_sales"]
        ) * 100,
        np.nan
    )

    print("✓ Standard ROAS calculated.")
    print("✓ ROAS percentage calculated.")
    print("✓ Standard ACOS calculated.")
    print("✓ Standard CTR calculated.")
    print("✓ Standard CVR calculated.")
    print("✓ Standard TACOS calculated.")

    return df


# ============================================================
# DATA QUALITY FLAGS
# ============================================================

def create_quality_flags(df: pd.DataFrame) -> pd.DataFrame:

    print("\n" + "=" * 75)
    print("STEP 7 - BUSINESS ANOMALY FLAGS")
    print("=" * 75)

    df = df.copy()

    # ========================================================
    # 1. CVR anomaly
    # ========================================================

    df["flag_cvr_anomaly"] = (
        (df["click"] > 0)
        &
        (df["ad_orders"] > df["click"])
    )

    # ========================================================
    # 2. High ACOS
    # ========================================================

    df["flag_high_acos"] = (
        df["acos_standard"] > 100
    )

    # ========================================================
    # 3. High TACOS
    # ========================================================

    df["flag_high_tacos"] = (
        df["tacos_standard"] > 100
    )

    # ========================================================
    # 4. Negative organic sales
    # ========================================================

    df["flag_negative_organic_sales"] = (
        df["organic_sale"] < 0
    )

    # ========================================================
    # 5. Negative organic percentage
    # ========================================================

    df["flag_negative_organic_percentage"] = (
        df["organic_percentage"] < 0
    )

    # ========================================================
    # 6. Advertising spend with zero gross sales
    # ========================================================

    df["flag_ad_spend_zero_sales"] = (
        (df["ad_spend"] > 0)
        &
        (df["gross_sales"] <= 0)
    )

    # ========================================================
    # 7. Ad spend without ad revenue
    # ========================================================

    df["flag_ad_spend_zero_ad_revenue"] = (
        (df["ad_spend"] > 0)
        &
        (df["ad_revenue"] <= 0)
    )

    # ========================================================
    # 8. Inventory risk
    #
    # High sales + low inventory
    # ========================================================

    df["flag_inventory_risk"] = (
        (df["unit_ordered"] > 0)
        &
        (df["fba_inv"] <= 0)
    )

    # ========================================================
    # 9. Clicks greater than impressions
    # ========================================================

    df["flag_click_gt_impression"] = (
        df["click"] > df["impression"]
    )

    # ========================================================
    # 10. Ad orders greater than ad units
    # ========================================================

    df["flag_ad_orders_gt_units"] = (
        df["ad_orders"] > df["ad_units"]
    )

    # ========================================================
    # 11. No activity
    # ========================================================

    df["flag_no_activity"] = (
        (df["gross_sales"] <= 0)
        &
        (df["ad_spend"] <= 0)
        &
        (df["unit_ordered"] <= 0)
        &
        (df["impression"] <= 0)
    )

    # ========================================================
    # Print summary
    # ========================================================

    flag_columns = [
        column
        for column in df.columns
        if column.startswith("flag_")
    ]

    print("\nFlag summary:")

    for column in flag_columns:

        count = int(
            df[column].sum()
        )

        print(
            f"   {column:<40}"
            f"{count:>8,}"
        )

    return df


# ============================================================
# OVERALL QUALITY STATUS
# ============================================================

def create_quality_status(df: pd.DataFrame) -> pd.DataFrame:

    print("\n" + "=" * 75)
    print("STEP 8 - OVERALL DATA QUALITY STATUS")
    print("=" * 75)

    df = df.copy()

    flag_columns = [
        column
        for column in df.columns
        if column.startswith("flag_")
    ]

    # Number of flags per row

    df["quality_flag_count"] = (
        df[flag_columns]
        .sum(axis=1)
    )

    # Status

    df["quality_status"] = np.select(
        [
            df["quality_flag_count"] == 0,
            df["quality_flag_count"] <= 2,
        ],
        [
            "OK",
            "REVIEW",
        ],
        default="HIGH_RISK"
    )

    status_counts = (
        df["quality_status"]
        .value_counts()
    )

    for status, count in status_counts.items():

        percentage = (
            count / len(df)
        ) * 100

        print(
            f"{status:<12}"
            f"{count:>8,} "
            f"({percentage:.2f}%)"
        )

    return df


# ============================================================
# KPI CONSISTENCY CHECK
# ============================================================

def compare_source_kpis(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 9 - SOURCE KPI CONSISTENCY CHECK")
    print("=" * 75)

    comparisons = [
        ("acos", "acos_standard"),
        ("ctr", "ctr_standard"),
        ("cvr", "cvr_standard"),
        ("tacos", "tacos_standard"),
    ]

    for source_column, calculated_column in comparisons:

        valid = (
            df[source_column].notna()
            &
            df[calculated_column].notna()
        )

        if valid.sum() == 0:

            print(
                f"{source_column:<10}"
                "No comparable records."
            )

            continue

        difference = (
            df.loc[valid, source_column]
            -
            df.loc[valid, calculated_column]
        ).abs()

        mean_difference = (
            difference.mean()
        )

        large_difference = (
            difference > 0.01
        ).sum()

        print(
            f"{source_column:<10}"
            f"mean difference = "
            f"{mean_difference:.4f}, "
            f"differences > 0.01 = "
            f"{large_difference:,}"
        )

    # --------------------------------------------------------
    # ROAS special check
    # --------------------------------------------------------

    valid_roas = (
        df["roas"].notna()
        &
        df["roas_percentage"].notna()
    )

    if valid_roas.sum() > 0:

        roas_difference = (
            df.loc[valid_roas, "roas"]
            -
            df.loc[valid_roas, "roas_percentage"]
        ).abs()

        print(
            f"{'roas':<10}"
            f"mean difference vs percentage = "
            f"{roas_difference.mean():.4f}, "
            f"differences > 0.01 = "
            f"{(roas_difference > 0.01).sum():,}"
        )


# ============================================================
# QUALITY REPORT
# ============================================================

def create_quality_report(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 10 - CREATING COLUMN QUALITY REPORT")
    print("=" * 75)

    report = []

    for column in df.columns:

        report.append({

            "column": column,

            "data_type": str(
                df[column].dtype
            ),

            "row_count": len(df),

            "missing_count": int(
                df[column].isna().sum()
            ),

            "missing_percentage": round(
                df[column].isna().mean() * 100,
                2
            ),

            "unique_values": int(
                df[column].nunique(
                    dropna=True
                )
            ),

        })

    report_df = pd.DataFrame(report)

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    report_df.to_csv(
        QUALITY_FILE,
        index=False
    )

    print(
        f"✓ Saved:\n"
        f"  {QUALITY_FILE}"
    )

    return report_df


# ============================================================
# QUALITY SUMMARY
# ============================================================

def create_quality_summary(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 11 - CREATING QUALITY SUMMARY")
    print("=" * 75)

    flag_columns = [
        column
        for column in df.columns
        if column.startswith("flag_")
    ]

    summary = []

    for column in flag_columns:

        count = int(
            df[column].sum()
        )

        percentage = (
            count / len(df)
        ) * 100

        summary.append({

            "flag": column,

            "affected_rows": count,

            "affected_percentage": round(
                percentage,
                2
            ),

        })

    summary_df = pd.DataFrame(summary)

    summary_df = summary_df.sort_values(
        by="affected_rows",
        ascending=False
    )

    summary_df.to_csv(
        SUMMARY_FILE,
        index=False
    )

    print(
        f"✓ Saved:\n"
        f"  {SUMMARY_FILE}"
    )

    return summary_df


# ============================================================
# SAVE CLEAN DATA
# ============================================================

def save_clean_data(df: pd.DataFrame):

    print("\n" + "=" * 75)
    print("STEP 12 - SAVING PROCESSED DATA")
    print("=" * 75)

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_df = df.copy()

    # Convert datetime back to YYYY-MM

    if "year_month" in output_df.columns:

        output_df["year_month"] = (
            output_df["year_month"]
            .dt.strftime("%Y-%m")
        )

    output_df.to_csv(
        CLEAN_FILE,
        index=False
    )

    print(
        f"✓ Clean dataset saved:\n"
        f"  {CLEAN_FILE}"
    )

    print(
        f"\nFinal shape: "
        f"{output_df.shape[0]:,} rows × "
        f"{output_df.shape[1]} columns"
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("\n")
    print("=" * 75)
    print(
        "       AI BUSINESS ANALYST - "
        "DATA QUALITY PIPELINE"
    )
    print("=" * 75)

    # --------------------------------------------------------
    # 1. Load
    # --------------------------------------------------------

    df = load_data(
        RAW_FILE
    )

    # --------------------------------------------------------
    # 2. Clean column names
    # --------------------------------------------------------

    df = clean_column_names(
        df
    )

    # --------------------------------------------------------
    # 3. Validate columns
    # --------------------------------------------------------

    validate_columns(
        df
    )

    # --------------------------------------------------------
    # 4. Convert data types
    # --------------------------------------------------------

    df = convert_data_types(
        df
    )

    # --------------------------------------------------------
    # 5. Missing values
    # --------------------------------------------------------

    missing_value_analysis(
        df
    )

    # --------------------------------------------------------
    # 6. Duplicates
    # --------------------------------------------------------

    duplicate_analysis(
        df
    )

    # --------------------------------------------------------
    # 7. Calculate standardized KPIs
    # --------------------------------------------------------

    df = calculate_kpis(
        df
    )

    # --------------------------------------------------------
    # 8. Create anomaly flags
    # --------------------------------------------------------

    df = create_quality_flags(
        df
    )

    # --------------------------------------------------------
    # 9. Overall status
    # --------------------------------------------------------

    df = create_quality_status(
        df
    )

    # --------------------------------------------------------
    # 10. Compare source KPIs
    # --------------------------------------------------------

    compare_source_kpis(
        df
    )

    # --------------------------------------------------------
    # 11. Column report
    # --------------------------------------------------------

    create_quality_report(
        df
    )

    # --------------------------------------------------------
    # 12. Quality summary
    # --------------------------------------------------------

    create_quality_summary(
        df
    )

    # --------------------------------------------------------
    # 13. Save
    # --------------------------------------------------------

    save_clean_data(
        df
    )

    print("\n")
    print("=" * 75)
    print(
        "                 PIPELINE COMPLETED"
    )
    print("=" * 75)

    print("\nGenerated files:")

    print(
        "1.",
        CLEAN_FILE
    )

    print(
        "2.",
        QUALITY_FILE
    )

    print(
        "3.",
        SUMMARY_FILE
    )

    print(
        "\nNext step: PostgreSQL database ingestion"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()