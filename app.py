import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


# -----------------------------
# Config
# -----------------------------
st.set_page_config(
    page_title="Investmend Funds Nav",
    layout="wide",
)


# -----------------------------
# Styles
# -----------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1400px; }
    .title {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: var(--text-color);
    }
    .subtitle {
        color: var(--text-color);
        opacity: 0.78;
        margin-top: 0;
        margin-bottom: 1rem;
    }
    .header-logo-wrap {
        display: flex;
        justify-content: flex-end;
        align-items: flex-start;
    }
    .ak-logo {
        width: min(220px, 100%);
        color: var(--text-color);
        margin-top: -4px;
    }
    .section-spacer { height: 12px; }
    div[data-testid="stHorizontalBlock"] { gap: 1rem; }

    .kpi-card {
        border: 1px solid rgba(128,128,128,0.22);
        background: var(--secondary-background-color);
        border-radius: 18px;
        padding: 16px 18px;
        min-height: 124px;
        box-shadow: 0 8px 26px rgba(0,0,0,0.25);
    }
    .kpi-label {
        font-size: 0.85rem;
        color: var(--text-color);
        opacity: 0.72;
    }
    .kpi-value {
        font-size: 1.65rem;
        font-weight: 800;
        margin-top: 6px;
        color: var(--text-color);
    }
    .kpi-sub {
        font-size: 0.80rem;
        color: var(--text-color);
        opacity: 0.62;
        margin-top: 6px;
    }
    .partner-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text-color);
    }
    .partner-card-copy {
        font-size: 0.82rem;
        color: var(--text-color);
        opacity: 0.68;
        line-height: 1.45;
        margin-top: 10px;
    }
    .empty-state {
        margin-top: 1.2rem;
        border: 1px solid rgba(128,128,128,0.26);
        border-radius: 18px;
        padding: 22px;
        background: var(--secondary-background-color);
    }
    .empty-title {
        font-size: 1.2rem;
        font-weight: 700;
        margin: 0 0 8px;
        color: var(--text-color);
    }
    .empty-sub {
        color: var(--text-color);
        opacity: 0.76;
        margin: 0;
        line-height: 1.45;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Paths / constants
# -----------------------------
DATA_DIR = Path("data")
PUBLISHED_DATA_FILE = DATA_DIR / "published_data.csv"
PUBLISHED_META_FILE = DATA_DIR / "published_meta.json"

EXPECTED_COLS = [
    "Week",
    "Fecha Act",
    "SumaDeBEGINNER NAV",
    "SumaDeCLOSE TRADE",
    "SumaDeNET LIQUID VALUE",
    "SumaDeLIQUIDACION",
    "SumaDeCASH NAV",
    "SumaDeOPEN CASH FLOW",
    "SumaDeFREE CASH",
    "SumaDeTRADING",
    "Fondo",
    "CloseTrade_BRUTO",
]

NUMERIC_COLS = [
    "SumaDeBEGINNER NAV",
    "SumaDeCLOSE TRADE",
    "SumaDeNET LIQUID VALUE",
    "SumaDeLIQUIDACION",
    "SumaDeCASH NAV",
    "SumaDeOPEN CASH FLOW",
    "SumaDeFREE CASH",
    "SumaDeTRADING",
    "CloseTrade_BRUTO",
]

FUND_ALIASES = {
    "INS": "INSTITUTE",
}

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "FundsAdmin_2026!"


# -----------------------------
# Helpers
# -----------------------------
def get_admin_username() -> str:
    username = ""
    try:
        username = str(st.secrets.get("ADMIN_USERNAME", ""))
    except Exception:
        username = ""
    if not username:
        username = os.getenv("FUNDS_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    return username.strip() or DEFAULT_ADMIN_USERNAME


def get_admin_password() -> str:
    password = ""
    try:
        password = str(st.secrets.get("ADMIN_PASSWORD", ""))
    except Exception:
        password = ""
    if not password:
        password = os.getenv("FUNDS_ADMIN_PASSWORD", "")
    if not password:
        password = DEFAULT_ADMIN_PASSWORD
    return password.strip() or DEFAULT_ADMIN_PASSWORD


def format_money(x) -> str:
    if pd.isna(x):
        return "—"
    try:
        return f"${x:,.0f}"
    except Exception:
        return str(x)


def normalize_fund_name(value) -> str:
    raw = str(value).strip().upper()
    return FUND_ALIASES.get(raw, raw)


def normalize_df(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()

    # Normaliza nombres (por si hay espacios raros)
    df.columns = [str(c).strip() for c in df.columns]

    # Si no existe "Fondo", intenta inferirlo
    if "Fondo" not in df.columns:
        upper = source_name.upper()
        if "ESP" in upper:
            df["Fondo"] = "ESP"
        elif "INCUB" in upper:
            df["Fondo"] = "INCUBATOR"
        elif "INSTITUTE" in upper or "INS" in upper:
            df["Fondo"] = "INSTITUTE"
        else:
            df["Fondo"] = "UNKNOWN"

    # Fecha
    if "Fecha Act" in df.columns:
        df["Fecha Act"] = pd.to_datetime(df["Fecha Act"], errors="coerce")
    else:
        df["Fecha Act"] = pd.NaT

    # Ensure numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # CloseTrade_BRUTO: fallback if missing
    if "CloseTrade_BRUTO" not in df.columns:
        df["CloseTrade_BRUTO"] = pd.NA

    # If CloseTrade_BRUTO is empty, use SumaDeCLOSE TRADE as proxy
    if df["CloseTrade_BRUTO"].isna().all() and "SumaDeCLOSE TRADE" in df.columns:
        df["CloseTrade_BRUTO"] = df["SumaDeCLOSE TRADE"]

    # Solo para trazabilidad interna
    df["__source__"] = source_name

    keep = [c for c in EXPECTED_COLS if c in df.columns] + ["__source__"]
    return df[keep]


def clean_all_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "Fecha Act" in out.columns:
        out["Fecha Act"] = pd.to_datetime(out["Fecha Act"], errors="coerce")
    else:
        out["Fecha Act"] = pd.NaT

    for col in NUMERIC_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "__source__" in out.columns:
        # Avoid exposing source file names in the published dataset.
        out = out.drop(columns=["__source__"])

    if "Fondo" not in out.columns:
        out["Fondo"] = "UNKNOWN"

    out = out.dropna(subset=["Fondo"])
    out["Fondo"] = out["Fondo"].apply(normalize_fund_name)
    out = out[out["Fondo"] != ""]

    return out


@st.cache_data(show_spinner=False)
def read_any_file(file) -> pd.DataFrame:
    name = getattr(file, "name", "uploaded_file")
    suffix = Path(name).suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(file, sheet_name=0)
        return normalize_df(df, name)

    if suffix == ".csv":
        try:
            df = pd.read_csv(file)
        except Exception:
            df = pd.read_csv(file, sep=";")
        return normalize_df(df, name)

    raise ValueError(f"Unsupported file format: {suffix}")


def parse_uploaded_files(uploaded_files) -> Tuple[pd.DataFrame, List[Tuple[str, str]]]:
    dfs: List[pd.DataFrame] = []
    errors: List[Tuple[str, str]] = []
    for file in uploaded_files:
        try:
            dfs.append(read_any_file(file))
        except Exception as exc:
            errors.append((getattr(file, "name", "file"), str(exc)))

    if not dfs:
        return pd.DataFrame(), errors

    merged = pd.concat(dfs, ignore_index=True)
    merged = clean_all_df(merged)
    return merged, errors


def save_published_data(df: pd.DataFrame, uploaded_count: int) -> None:
    clean_df = clean_all_df(df)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(PUBLISHED_DATA_FILE, index=False)

    meta = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(clean_df)),
        "funds": int(clean_df["Fondo"].nunique()) if "Fondo" in clean_df.columns else 0,
        "uploaded_files": int(uploaded_count),
    }
    PUBLISHED_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_published_data() -> Tuple[pd.DataFrame, Dict]:
    if not PUBLISHED_DATA_FILE.exists():
        return pd.DataFrame(), {}

    try:
        data = pd.read_csv(PUBLISHED_DATA_FILE)
    except Exception:
        return pd.DataFrame(), {}

    meta: Dict = {}
    if PUBLISHED_META_FILE.exists():
        try:
            meta = json.loads(PUBLISHED_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    data = clean_all_df(data)
    return data, meta


def last_week_per_fund(all_df: pd.DataFrame) -> pd.DataFrame:
    tmp = all_df.dropna(subset=["Fecha Act"]).copy()
    if tmp.empty:
        return tmp
    idx = tmp.sort_values("Fecha Act").groupby("Fondo")["Fecha Act"].idxmax()
    return tmp.loc[idx].sort_values("Fondo")


def render_kpi(label: str, value, sub: str = ""):
    sub_html = (
        f'<div class="kpi-sub">{sub}</div>'
        if isinstance(sub, str) and sub.strip()
        else ""
    )
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_partner_card(title: str, description: str):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="partner-card-title">{title}</div>
            <div class="partner-card-copy">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header_logo():
    st.markdown(
        """
        <div class="header-logo-wrap" aria-hidden="true">
            <svg class="ak-logo" viewBox="0 0 340 340" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <path id="ak-top-arc" d="M 57 170 A 113 113 0 0 1 283 170" />
                    <path id="ak-bottom-arc" d="M 283 170 A 113 113 0 0 1 57 170" />
                </defs>
                <circle cx="170" cy="170" r="146" stroke="currentColor" stroke-width="12" />
                <circle cx="170" cy="170" r="104" stroke="currentColor" stroke-width="10" />
                <text fill="currentColor" font-size="25" font-weight="900" letter-spacing="1.6">
                    <textPath href="#ak-top-arc" startOffset="50%" text-anchor="middle">
                        RESEARCH &amp; DEVELOPMENT
                    </textPath>
                </text>
                <text fill="currentColor" font-size="24" font-weight="900" letter-spacing="1.4">
                    <textPath href="#ak-bottom-arc" startOffset="50%" text-anchor="middle">
                        NEW YORK EST.2010
                    </textPath>
                </text>
                <text
                    x="170"
                    y="208"
                    fill="currentColor"
                    font-size="118"
                    font-weight="900"
                    text-anchor="middle"
                >
                    AK
                </text>
            </svg>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_spacer():
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)


def format_table_column_name(name: str) -> str:
    if name == "Fondo":
        return "Fund"
    if name == "Fecha Act":
        return "Date"
    if name == "CloseTrade_BRUTO":
        return "CLOSE TRADE BRUTO"
    if name.startswith("SumaDe"):
        return name.replace("SumaDe", "", 1)
    return name


def is_truthy_param(value) -> bool:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def render_empty_state(
    can_upload: bool, admin_auth_enabled: bool, admin_panel_enabled: bool
):
    if can_upload:
        title = "No published data yet"
        subtitle = (
            "Upload your CSV/XLSX files from the sidebar and click 'Publish dataset'. "
            "After publishing, viewers will see the dashboard automatically."
        )
    else:
        title = "No published data yet"
        subtitle = (
            "This dashboard is in read-only mode for viewers. "
            "Ask the admin to publish a dataset first."
        )

    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-title">{title}</div>
            <p class="empty-sub">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if admin_panel_enabled and not admin_auth_enabled:
        st.info(
            "Admin login is not configured yet. In Streamlit Cloud go to Manage app -> Settings -> Secrets and add ADMIN_PASSWORD."
        )


# -----------------------------
# Session state
# -----------------------------
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

flash_message = st.session_state.pop("flash_message", "")
if flash_message:
    st.success(flash_message)


# -----------------------------
# UI - Header
# -----------------------------
header_left, header_right = st.columns([3.4, 1])
with header_left:
    st.markdown('<div class="title">Investmend Funds Nav</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Live public view of published fund NAV data.</div>',
        unsafe_allow_html=True,
    )
with header_right:
    render_header_logo()


# -----------------------------
# Sidebar - Auth / Publish / View
# -----------------------------
admin_username = get_admin_username()
admin_password = get_admin_password()
admin_auth_enabled = bool(admin_password)
is_admin = st.session_state.get("is_admin", False)
admin_panel_enabled = is_truthy_param(st.query_params.get("admin", "0"))
can_upload = is_admin and admin_panel_enabled

uploaded_files = []
publish_clicked = False

with st.sidebar:
    if admin_panel_enabled:
        st.header("Access")
        if admin_auth_enabled:
            if is_admin:
                st.success("Admin mode enabled")
                if st.button("Logout admin", use_container_width=True):
                    st.session_state["is_admin"] = False
                    st.rerun()
            else:
                candidate_user = st.text_input("Admin user", value="")
                candidate_pass = st.text_input("Admin password", type="password")
                if st.button("Login as admin", use_container_width=True):
                    if (
                        candidate_user.strip() == admin_username
                        and candidate_pass == admin_password
                    ):
                        st.session_state["is_admin"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect admin credentials.")
        else:
            st.caption("Admin login not configured.")
        st.divider()

    st.subheader("Dashboard View")
    n_weeks = st.slider(
        "Weeks shown in charts", min_value=4, max_value=52, value=16, step=4
    )

    if can_upload:
        st.divider()
        st.subheader("Publish Data")
        uploaded_files = st.file_uploader(
            "Upload one or more files (CSV / XLSX)",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="publish_uploader",
        )
        publish_clicked = st.button(
            "Publish dataset",
            disabled=not uploaded_files,
            use_container_width=True,
        )


# -----------------------------
# Publish flow (admin only)
# -----------------------------
publish_errors: List[Tuple[str, str]] = []
if can_upload and publish_clicked:
    fresh_df, publish_errors = parse_uploaded_files(uploaded_files)
    if fresh_df.empty:
        st.error("Publish failed: no valid rows were found in the uploaded files.")
    else:
        save_published_data(fresh_df, len(uploaded_files))
        st.session_state["flash_message"] = (
            f"Data published successfully ({len(fresh_df)} rows)."
        )
        st.rerun()

if publish_errors:
    with st.expander("Files with publish errors"):
        for name, err in publish_errors:
            st.write(f"**{name}** → {err}")


# -----------------------------
# Load published dataset
# -----------------------------
all_df, _published_meta = load_published_data()
if all_df.empty:
    render_empty_state(
        can_upload=can_upload,
        admin_auth_enabled=admin_auth_enabled,
        admin_panel_enabled=admin_panel_enabled,
    )
    st.stop()

latest_df = last_week_per_fund(all_df)
if latest_df.empty:
    st.error("No rows with valid 'Fecha Act' in the published dataset.")
    st.stop()


# -----------------------------
# Top selector
# -----------------------------
funds = sorted(latest_df["Fondo"].unique().tolist())
selected_fund = st.selectbox("Fund", funds, index=0)

selected_latest = latest_df[latest_df["Fondo"] == selected_fund].iloc[0]
render_spacer()


# -----------------------------
# KPI Grid (Cards)
# -----------------------------
st.markdown("### Fund Snapshot")
k1, k2, k3 = st.columns(3)
with k1:
    render_kpi(
        format_table_column_name("SumaDeBEGINNER NAV"),
        format_money(selected_latest.get("SumaDeBEGINNER NAV")),
    )
with k2:
    render_kpi(
        format_table_column_name("SumaDeNET LIQUID VALUE"),
        format_money(selected_latest.get("SumaDeNET LIQUID VALUE")),
    )
with k3:
    render_kpi(
        format_table_column_name("SumaDeCASH NAV"),
        format_money(selected_latest.get("SumaDeCASH NAV")),
    )

render_spacer()
k4, k5, k6 = st.columns(3)
with k4:
    render_kpi(
        format_table_column_name("SumaDeCLOSE TRADE"),
        format_money(selected_latest.get("SumaDeCLOSE TRADE")),
    )
with k5:
    render_kpi(
        format_table_column_name("SumaDeFREE CASH"),
        format_money(selected_latest.get("SumaDeFREE CASH")),
    )
with k6:
    render_kpi(
        format_table_column_name("CloseTrade_BRUTO"),
        format_money(selected_latest.get("CloseTrade_BRUTO")),
    )

render_spacer()
st.markdown("### Partners")
p1, p2, p3 = st.columns(3)
with p1:
    render_partner_card(
        "Contributions",
        "Reserved for partner contribution data.",
    )
with p2:
    render_partner_card(
        "Withdraws",
        "Reserved for partner withdrawal data.",
    )
with p3:
    render_partner_card(
        "Infographic",
        "Reserved for the future partner infographic view.",
    )

st.divider()

# -----------------------------
# Latest week table
# -----------------------------
st.markdown("### Latest Weekly Detail")
table_cols = [
    "Fondo",
    "Week",
    "Fecha Act",
    "SumaDeBEGINNER NAV",
    "SumaDeCLOSE TRADE",
    "CloseTrade_BRUTO",
    "SumaDeNET LIQUID VALUE",
    "SumaDeCASH NAV",
    "SumaDeFREE CASH",
    "SumaDeOPEN CASH FLOW",
    "SumaDeTRADING",
    "SumaDeLIQUIDACION",
]
existing = [col for col in table_cols if col in latest_df.columns]
pretty = latest_df.copy()

if "Fecha Act" in pretty.columns:
    pretty["Fecha Act"] = pd.to_datetime(pretty["Fecha Act"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )

for col in [x for x in existing if x in NUMERIC_COLS]:
    pretty[col] = pretty[col].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "")

st.dataframe(
    pretty[existing].sort_values("Fondo").rename(columns=format_table_column_name),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# -----------------------------
# Last N weeks trends (charts)
# -----------------------------
st.markdown("### Recent Trends")
df_f = (
    all_df[all_df["Fondo"] == selected_fund]
    .dropna(subset=["Fecha Act"])
    .sort_values("Fecha Act")
)
df_f = df_f.tail(n_weeks)

c1, c2 = st.columns(2)

with c1:
    st.markdown("**SumaDeNET LIQUID VALUE**")
    if "SumaDeNET LIQUID VALUE" in df_f.columns:
        st.line_chart(df_f.set_index("Fecha Act")["SumaDeNET LIQUID VALUE"])
    else:
        st.info("Column 'SumaDeNET LIQUID VALUE' is not available for this fund.")

with c2:
    st.markdown("**SumaDeCASH NAV vs SumaDeFREE CASH**")
    cols = []
    if "SumaDeCASH NAV" in df_f.columns:
        cols.append("SumaDeCASH NAV")
    if "SumaDeFREE CASH" in df_f.columns:
        cols.append("SumaDeFREE CASH")
    if cols:
        st.line_chart(df_f.set_index("Fecha Act")[cols])
    else:
        st.info("Cash columns are not available for this fund.")
