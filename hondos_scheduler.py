import streamlit as st
import pandas as pd
from datetime import datetime
import json
import io
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hondo's Scheduler", page_icon="🍽️", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    .stApp { background-color: #1a1a1a; color: #f0e6d3; }
    .block-container { padding-top: 1.5rem; }
    h1, h2, h3 { color: #c9a84c !important; }
    .metric-card { background: linear-gradient(135deg, #2a2a2a, #1a1a1a); border: 1px solid #c9a84c44; border-radius: 8px; padding: 1rem 1.2rem; text-align: center; }
    .metric-label { font-size: 0.7rem; letter-spacing: 0.15em; text-transform: uppercase; color: #c9a84c; margin-bottom: 0.3rem; }
    .metric-value { font-size: 2rem; color: #f0e6d3; font-weight: 600; line-height: 1; }
    .shift-day        { background: #1e3a2a; border: 1px solid #2d6a4f; border-radius: 6px; padding: 6px 10px; margin: 3px 0; font-size: 0.85rem; }
    .shift-eve        { background: #1a1a3a; border: 1px solid #2d2d6a; border-radius: 6px; padding: 6px 10px; margin: 3px 0; font-size: 0.85rem; }
    .shift-closer-day { background: #3a2a1a; border: 1px solid #8b5a1a; border-radius: 6px; padding: 6px 10px; margin: 3px 0; font-size: 0.85rem; }
    .shift-closer-eve { background: #3a1a2a; border: 1px solid #8b1a3a; border-radius: 6px; padding: 6px 10px; margin: 3px 0; font-size: 0.85rem; }
    .understaffed { background: #3a1a1a !important; border: 1px solid #ff4444 !important; }
    .stButton > button { background: linear-gradient(135deg, #8b6914, #c9a84c); color: #1a1a1a; border: none; border-radius: 6px; font-weight: 600; font-size: 0.8rem; padding: 0.4rem 1.2rem; }
    .stButton > button:hover { opacity: 0.88; }
    [data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #c9a84c22; }
    .stTabs [data-baseweb="tab"] { color: #c9a84caa; font-size: 0.78rem; letter-spacing: 0.1em; text-transform: uppercase; }
    .stTabs [aria-selected="true"] { color: #c9a84c !important; border-bottom-color: #c9a84c !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
SHIFTS = [
    "Day", "Day Closer", "Day Trainee", "Day Hostess",
    "Evening", "Evening Closer 1", "Evening Closer 2", "Evening Bartender",
    "Evening Trainee", "Evening Hostess", "Evening Expo", "Evening Busser (optional)"
]
DAY_ROLES     = ["Off", "Day", "Day Closer", "Day Trainee", "Day Hostess"]
EVENING_ROLES = ["Off", "Evening", "Evening Closer 1", "Evening Closer 2",
                 "Evening Bartender", "Evening Trainee", "Evening Hostess",
                 "Evening Expo", "Evening Busser"]

# Short display labels for grid dropdowns
DAY_ROLE_LABELS = {
    "Off": "Off",
    "Day": "Server",
    "Day Closer": "Server Closer",
    "Day Trainee": "Trainee",
    "Day Hostess": "Hostess",
}
EVENING_ROLE_LABELS = {
    "Off": "Off",
    "Evening": "Server",
    "Evening Closer 1": "Closer 1",
    "Evening Closer 2": "Closer 2",
    "Evening Bartender": "Bartender",
    "Evening Trainee": "Trainee",
    "Evening Hostess": "Hostess",
    "Evening Expo": "Expo",
    "Evening Busser": "Busser",
}
# Reverse maps for converting label back to role key
DAY_LABEL_TO_ROLE   = {v: k for k, v in DAY_ROLE_LABELS.items()}
EVE_LABEL_TO_ROLE   = {v: k for k, v in EVENING_ROLE_LABELS.items()}
DAYS   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_REQUIRED = {
    shift: {day: default for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}
    for shift, default in {
        "Day": 3, "Day Closer": 1, "Day Trainee": 1, "Day Hostess": 2,
        "Evening": 3, "Evening Closer 1": 1, "Evening Closer 2": 1,
        "Evening Bartender": 1, "Evening Trainee": 1,
        "Evening Hostess": 2, "Evening Expo": 1, "Evening Busser": 0
    }.items()
}
DEFAULT_ARRIVAL_TIMES = {
    "Day": "10:00 AM", "Day Closer": "11:00 AM", "Day Trainee": "10:00 AM", "Day Hostess": "10:00 AM",
    "Evening": "4:00 PM", "Evening Closer 1": "4:00 PM", "Evening Closer 2": "4:00 PM",
    "Evening Bartender": "4:00 PM", "Evening Trainee": "4:00 PM",
    "Evening Hostess": "4:00 PM", "Evening Expo": "4:00 PM", "Evening Busser": "4:00 PM"
}
SHEET_ID = "1eoHdsEaP_t3RhHhp_LlsqDe1OjhcxbgSrEUB6UHrzig"

# ── Google Sheets connection ───────────────────────────────────────────────────
@st.cache_resource
def get_gspread_client():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource
def get_sheets():
    client = get_gspread_client()
    book   = client.open_by_key(SHEET_ID)
    return {
        "staff":    book.worksheet("staff"),
        "avail":    book.worksheet("availability"),
        "schedule": book.worksheet("schedule"),
        "required": book.worksheet("required"),
        "arrivals": book.worksheet("arrivals"),
        "grid":     book.worksheet("grid"),
    }

# ── Read / write helpers ───────────────────────────────────────────────────────
def read_cell(sheet, cell):
    val = sheet.acell(cell).value
    return json.loads(val) if val else None

def write_cell(sheet, cell, data):
    sheet.update_acell(cell, json.dumps(data))

# ── Arrival time helper ────────────────────────────────────────────────────────
def get_arrival(shift, day):
    """Get arrival time — day override takes priority over default."""
    overrides = arrivals_data.get("overrides", {})
    return overrides.get(day, {}).get(shift) or arrivals_data.get("defaults", {}).get(shift, "")

def get_required(shift, day):
    """Get required staff count for a shift on a specific day."""
    val = REQUIRED.get(shift, {})
    if isinstance(val, dict):
        return val.get(day, 0)
    return val  # backwards compat with old flat structure

# ── Debug connection test ──────────────────────────────────────────────────────
def test_connection():
    try:
        sheets = get_sheets()
        sheets["staff"].update_acell("B1", "connection_test")
        val = sheets["staff"].acell("B1").value
        return val == "connection_test", None
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=10)
def load_all():
    sheets = get_sheets()

    # staff
    raw = read_cell(sheets["staff"], "A1")
    if raw is None:
        staff_dict = {}
    elif isinstance(raw, list):
        staff_dict = {n: {"phone": "", "email": ""} for n in raw}
        write_cell(sheets["staff"], "A1", staff_dict)
    else:
        staff_dict = raw

    # availability
    avail = read_cell(sheets["avail"], "A1")
    if avail is None: avail = {}

    # schedule
    sched = read_cell(sheets["schedule"], "A1")
    if sched is None:
        sched = {d: {s: [] for s in SHIFTS} for d in DAYS}
    for d in DAYS:
        if d not in sched: sched[d] = {s: [] for s in SHIFTS}
        for s in SHIFTS:
            if s not in sched[d]: sched[d][s] = []

    # required
    req = read_cell(sheets["required"], "A1")
    if req is None: req = DEFAULT_REQUIRED

    # arrival times — default + per day overrides
    arrivals_raw = read_cell(sheets["arrivals"], "A1")
    if arrivals_raw is None:
        arrivals_raw = {"defaults": DEFAULT_ARRIVAL_TIMES, "overrides": {}}

    # grid schedule
    grid_raw = read_cell(sheets["grid"], "A1")
    if grid_raw is None: grid_raw = {}

    return staff_dict, avail, sched, req, arrivals_raw, grid_raw

def save_staff(data):
    get_sheets()["staff"].update_acell("A1", json.dumps(data))
    load_all.clear()

def save_avail(data):
    get_sheets()["avail"].update_acell("A1", json.dumps(data))
    load_all.clear()

def save_schedule(data):
    get_sheets()["schedule"].update_acell("A1", json.dumps(data))
    load_all.clear()

def save_required(data):
    get_sheets()["required"].update_acell("A1", json.dumps(data))
    load_all.clear()

def save_arrivals(data):
    get_sheets()["arrivals"].update_acell("A1", json.dumps(data))
    load_all.clear()

def save_grid(data):
    get_sheets()["grid"].update_acell("A1", json.dumps(data))
    load_all.clear()

# ── Load ───────────────────────────────────────────────────────────────────────
try:
    staff_dict, avail_data, schedule, REQUIRED, arrivals_data, grid_data = load_all()
    staff_list = list(staff_dict.keys())
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    st.stop()

# ── PDF builder ────────────────────────────────────────────────────────────────
def build_pdf(week_label):
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.colors import HexColor

    buf  = io.BytesIO()
    W, H = landscape(letter)
    c    = rl_canvas.Canvas(buf, pagesize=landscape(letter))

    GOLD  = HexColor("#c9a84c"); DARK = HexColor("#1a1a1a")
    WHITE = HexColor("#ffffff"); RED  = HexColor("#cc3333")

    # Cell background colors (light pastel)
    SHIFT_COLORS = {
        "Day":               HexColor("#e8f5ee"),
        "Day Closer":        HexColor("#fff3e0"),
        "Day Trainee":       HexColor("#e8f8ff"),
        "Evening":           HexColor("#e8eaf6"),
        "Evening Closer 1":  HexColor("#fce4ec"),
        "Evening Closer 2":  HexColor("#fce4ec"),
        "Evening Bartender": HexColor("#f3e5f5"),
        "Evening Trainee":   HexColor("#e0f7fa"),
    }

    # Title label colors (darker, readable on pastel bg)
    SHIFT_TITLE_COLORS = {
        "Day":               HexColor("#1b5e20"),  # deep green
        "Day Closer":        HexColor("#e65100"),  # deep orange
        "Day Trainee":       HexColor("#0d47a1"),  # deep blue
        "Evening":           HexColor("#4a148c"),  # deep purple
        "Evening Closer 1":  HexColor("#880e4f"),  # deep pink
        "Evening Closer 2":  HexColor("#880e4f"),  # deep pink
        "Evening Bartender": HexColor("#6a1b9a"),  # violet
        "Evening Trainee":   HexColor("#006064"),  # teal
    }

    # Left border accent colors
    SHIFT_ACCENT_COLORS = {
        "Day":               HexColor("#4caf50"),  # green
        "Day Closer":        HexColor("#ff9800"),  # orange
        "Day Trainee":       HexColor("#2196f3"),  # blue
        "Evening":           HexColor("#7c4dff"),  # purple
        "Evening Closer 1":  HexColor("#e91e63"),  # pink
        "Evening Closer 2":  HexColor("#e91e63"),  # pink
        "Evening Bartender": HexColor("#9c27b0"),  # violet
        "Evening Trainee":   HexColor("#00bcd4"),  # teal
    }

    c.setFillColor(DARK); c.rect(0, H-55, W, 55, fill=1, stroke=0)
    c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 20)
    c.drawString(24, H-32, "HONDO'S  —  Weekly Schedule")
    c.setFillColor(WHITE); c.setFont("Helvetica", 12)
    c.drawString(24, H-50, week_label)
    c.setFont("Helvetica", 10)
    c.drawRightString(W-24, H-35, f"Generated: {datetime.now().strftime('%B %d, %Y')}")

    MARGIN = 18; TOP = H-62; BOTTOM = 36
    COL_W  = (W - MARGIN*2) / 7
    ROW_H  = (TOP - BOTTOM) / (len(SHIFTS) + 1)

    for di, day in enumerate(DAYS):
        x = MARGIN + di*COL_W
        c.setFillColor(HexColor("#2a2a2a"))
        c.rect(x, TOP-ROW_H, COL_W, ROW_H, fill=1, stroke=1)
        c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x+COL_W/2, TOP-ROW_H+ROW_H*0.35, day[:3].upper())

    for si, shift in enumerate(SHIFTS):
        row_y      = TOP - ROW_H - (si+1)*ROW_H
        accent     = SHIFT_ACCENT_COLORS.get(shift, HexColor("#999999"))
        title_clr  = SHIFT_TITLE_COLORS.get(shift, HexColor("#333333"))

        for di, day in enumerate(DAYS):
            x        = MARGIN + di*COL_W
            assigned = schedule[day][shift]
            req      = get_required(shift, day)
            is_under = len(assigned) < req
            bg = HexColor("#ffe8e8") if is_under else SHIFT_COLORS.get(shift, HexColor("#f5f5f5"))

            # Cell background
            c.setFillColor(bg); c.setStrokeColor(HexColor("#dddddd")); c.setLineWidth(0.4)
            c.rect(x, row_y, COL_W, ROW_H, fill=1, stroke=1)

            # Colored left accent strip
            c.setFillColor(accent)
            c.rect(x, row_y, 3, ROW_H, fill=1, stroke=0)

            # Shift label and arrival time on first column only
            arrival = get_arrival(shift, day)
            if di == 0:
                c.setFillColor(title_clr); c.setFont("Helvetica-Bold", 7)
                c.drawString(x+6, row_y+ROW_H-10, shift)

            # Arrival time pinned to bottom of every cell
            if arrival:
                c.setFillColor(HexColor("#888888")); c.setFont("Helvetica", 6)
                c.drawString(x+6, row_y+4, f"🕐 {arrival}")

            # Staff names — start below the shift label, stop above the arrival time
            name_top    = row_y + ROW_H - 20
            name_bottom = row_y + 14  # leave room for arrival time at bottom
            if assigned:
                c.setFillColor(DARK); c.setFont("Helvetica", 7.5)
                for ni, name in enumerate(assigned):
                    ny = name_top - ni*11
                    if ny > name_bottom:
                        parts = name.split()
                        short = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else name
                        c.drawString(x+6, ny, short)
            else:
                c.setFillColor(RED); c.setFont("Helvetica-BoldOblique", 7.5)
                c.drawString(x+6, row_y+ROW_H/2-4, "UNFILLED")

            if is_under:
                c.setFillColor(RED); c.setFont("Helvetica-Bold", 6)
                c.drawRightString(x+COL_W-3, row_y+3, f"{len(assigned)}/{req}")

    c.setFillColor(HexColor("#888888")); c.setFont("Helvetica", 8)
    c.drawRightString(W-MARGIN, 20, f"Hondo's Restaurant  |  {week_label}")
    c.save(); buf.seek(0)
    return buf

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("<h1 style='font-size:2.4rem;'>🍽️ Hondo's Weekly Scheduler</h1>", unsafe_allow_html=True)

total_staff    = len(staff_list)
total_assigned = sum(len(schedule[d][s]) for d in DAYS for s in SHIFTS)
understaffed   = sum(1 for d in DAYS for s in SHIFTS if len(schedule[d][s]) < get_required(s, d))
avail_count    = len([n for n in staff_list if not all(
    avail_data.get(n, {}).get(d, {}).get("day_unavail", False) and
    avail_data.get(n, {}).get(d, {}).get("eve_unavail", False)
    for d in DAYS)])

c1,c2,c3,c4 = st.columns(4)
for col, label, value in zip([c1,c2,c3,c4],
    ["Total Staff","Shifts Assigned","Understaffed Slots","Staff Available"],
    [total_staff, total_assigned, understaffed, avail_count]):
    with col:
        color = "#ff4444" if label == "Understaffed Slots" and value > 0 else "#f0e6d3"
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value" style="color:{color}">{value}</div></div>', unsafe_allow_html=True)

st.markdown("---")

tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "📅 Weekly Schedule","✏️ Assign Shifts","📋 Grid Schedule",
    "🙋 Availability","👥 Manage Staff","📤 Export","⚙️ Settings"
])

# ════════════════════════════════════════════
# TAB 1 — Weekly View
# ════════════════════════════════════════════
with tab1:
    st.markdown("### Weekly Schedule Overview")
    cols = st.columns(7)
    for di, day in enumerate(DAYS):
        with cols[di]:
            st.markdown(f"**{day[:3]}**")
            for shift in SHIFTS:
                assigned = schedule[day][shift]
                req      = get_required(shift, day)
                count    = len(assigned)
                names    = ", ".join(assigned) if assigned else "—"
                short    = (shift
                    .replace("Evening Closer 1","Eve▲1")
                    .replace("Evening Closer 2","Eve▲2")
                    .replace("Evening Bartender","Eve🍸")
                    .replace("Evening Trainee","Eve🎓")
                    .replace("Day Closer","Day★")
                    .replace("Day Trainee","Day🎓")
                    .replace("Evening","Eve"))
                css      = "understaffed" if count < req else (
                    "shift-closer-eve" if "Evening Closer" in shift else
                    "shift-closer-day" if "Day Closer" in shift else
                    "shift-eve" if "Evening" in shift else "shift-day")
                arrival  = get_arrival(shift, day)
                arrival_str = f"<br><small style='color:#c9a84c'>🕐 {arrival}</small>" if arrival else ""
                st.markdown(f'<div class="{css}"><strong>{short}</strong> ({count}/{req}){arrival_str}<br><small>{names}</small></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════
# TAB 2 — Assign Shifts
# ════════════════════════════════════════════
with tab2:
    st.markdown("### Assign Shifts")
    if not staff_list:
        st.warning("No staff added yet.")
    else:
        a1, a2 = st.columns(2)
        with a1: sel_day   = st.selectbox("Day",   DAYS,   key="assign_day")
        with a2: sel_shift = st.selectbox("Shift", SHIFTS, key="assign_shift")

        already = schedule[sel_day][sel_shift]
        req     = get_required(sel_shift, sel_day)

        if len(already) < req:
            st.warning(f"⚠️ {sel_day} — {sel_shift}: {len(already)}/{req} — need {req-len(already)} more")
        else:
            st.success(f"✓ {sel_day} — {sel_shift}: Fully staffed ({len(already)}/{req})")

        c_add, c_remove = st.columns(2)
        with c_add:
            st.markdown("**Add available staff:**")
            # Available = not marked unavailable for this day's period (day or evening)
            is_day_shift = not sel_shift.startswith("Evening")
            avail_key    = "day_unavail" if is_day_shift else "eve_unavail"
            avail_for_slot = [n for n in staff_list
                    if not avail_data.get(n,{}).get(sel_day,{}).get(avail_key, False)
                    and n not in already]
            if avail_for_slot:
                to_add = st.selectbox("Available", ["— select —"]+avail_for_slot, key="add_staff")
                if st.button("➕ Add to Shift", key="add_btn"):
                    if to_add != "— select —":
                        schedule[sel_day][sel_shift].append(to_add)
                        save_schedule(schedule)
                        st.success(f"✓ {to_add} added!"); st.rerun()
            else:
                st.info("No available staff for this slot.")
            with st.expander("Add any staff (override)"):
                not_assigned = [n for n in staff_list if n not in already]
                override = st.selectbox("Staff", ["— select —"]+not_assigned, key="override_add")
                if st.button("Add (Override)", key="override_btn"):
                    if override != "— select —":
                        schedule[sel_day][sel_shift].append(override)
                        save_schedule(schedule)
                        st.success(f"✓ {override} added!"); st.rerun()

        with c_remove:
            st.markdown("**Remove from shift:**")
            if already:
                to_remove = st.selectbox("Remove", ["— select —"]+already, key="remove_staff")
                if st.button("➖ Remove", key="remove_btn"):
                    if to_remove != "— select —":
                        schedule[sel_day][sel_shift].remove(to_remove)
                        save_schedule(schedule)
                        st.success(f"✓ {to_remove} removed!"); st.rerun()
            else:
                st.info("No staff assigned yet.")

        st.markdown("---")
        st.markdown("### 📅 Current Week at a Glance")
        grid_cols = st.columns(7)
        for di, day in enumerate(DAYS):
            with grid_cols[di]:
                st.markdown(f"**{'→ ' if day==sel_day else ''}{day[:3]}**")
                for shift in SHIFTS:
                    assigned = schedule[day][shift]
                    req_s    = get_required(shift, day)
                    count    = len(assigned)
                    names    = "<br>".join(n.split()[0] for n in assigned) if assigned else "—"
                    short    = (shift
                        .replace("Evening Closer 1","Eve▲1")
                        .replace("Evening Closer 2","Eve▲2")
                        .replace("Evening Bartender","Eve🍸")
                        .replace("Evening Trainee","Eve🎓")
                        .replace("Day Closer","Day★")
                        .replace("Day Trainee","Day🎓")
                        .replace("Evening","Eve"))
                    is_sel   = (day == sel_day and shift == sel_shift)
                    border   = "3px solid #c9a84c" if is_sel else "1px solid #555"
                    bg       = "#3a1a1a" if count < req_s else ("#2a2a1a" if is_sel else "#1e2a1e" if "Day" in shift else "#1a1a2a")
                    st.markdown(f'<div style="background:{bg};border:{border};border-radius:5px;padding:4px 6px;margin:2px 0;font-size:0.75rem"><strong style="color:#c9a84c">{short}</strong> <span style="color:#aaa">({count}/{req_s})</span><br><span style="color:#ddd;font-size:0.7rem">{names}</span></div>', unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑️ Clear Entire Week", key="clear_week"):
            for d in DAYS:
                for s in SHIFTS:
                    schedule[d][s] = []
            save_schedule(schedule)
            st.success("Schedule cleared!"); st.rerun()

# ════════════════════════════════════════════
# ════════════════════════════════════════════
# TAB 3 — Grid Schedule
# ════════════════════════════════════════════
DAY_ROLES     = ["—", "Day", "Day Closer", "Day Trainee", "Day Hostess", "Off"]
EVENING_ROLES = ["—", "Evening", "Evening Closer 1", "Evening Closer 2",
                 "Evening Bartender", "Evening Trainee", "Evening Hostess",
                 "Evening Expo", "Evening Busser (optional)", "Off"]

with tab3:
    st.markdown("### 📋 Grid Schedule")
    st.caption("Assign each staff member a Day and Evening role for each day. Select Off to leave unassigned.")

    if not staff_list:
        st.warning("No staff added yet.")
    else:
        # Work from a local copy we can mutate
        grid = {n: grid_data.get(n, {d: {"day": "Off", "eve": "Off"} for d in DAYS})
                for n in sorted(staff_list)}
        for name in grid:
            for day in DAYS:
                if day not in grid[name]:
                    grid[name][day] = {"day": "Off", "eve": "Off"}

        # Header
        header_cols = st.columns([2] + [1]*7)
        header_cols[0].markdown("**Staff Member**")
        for di, day in enumerate(DAYS):
            header_cols[di+1].markdown(f"**{day[:3]}**")
        st.markdown("---")

        # One row per staff member
        changed = False
        for name in sorted(staff_list):
            row_cols = st.columns([2] + [1]*7)

            # Name + Day/Evening labels in left column
            with row_cols[0]:
                st.markdown(f"**{name.split()[0]}**")
                st.markdown("<small style='color:#c9a84c'>☀️ Day</small>", unsafe_allow_html=True)
                st.markdown("<small style='color:#7a8fff'>🌙 Eve</small>", unsafe_allow_html=True)

            for di, day in enumerate(DAYS):
                with row_cols[di+1]:
                    cur_day = grid[name][day].get("day", "Off")
                    cur_eve = grid[name][day].get("eve", "Off")

                    # Day dropdown — show short labels
                    day_labels = list(DAY_ROLE_LABELS.values())
                    cur_day_label = DAY_ROLE_LABELS.get(cur_day, "Off")
                    day_idx = day_labels.index(cur_day_label) if cur_day_label in day_labels else 0
                    new_day_label = st.selectbox(
                        "D", day_labels, index=day_idx,
                        key=f"grid_{name}_{day}_day",
                        label_visibility="collapsed"
                    )
                    new_day = DAY_LABEL_TO_ROLE.get(new_day_label, "Off")

                    # Evening dropdown — show short labels
                    eve_labels = list(EVENING_ROLE_LABELS.values())
                    cur_eve_label = EVENING_ROLE_LABELS.get(cur_eve, "Off")
                    eve_idx = eve_labels.index(cur_eve_label) if cur_eve_label in eve_labels else 0
                    new_eve_label = st.selectbox(
                        "E", eve_labels, index=eve_idx,
                        key=f"grid_{name}_{day}_eve",
                        label_visibility="collapsed"
                    )
                    new_eve = EVE_LABEL_TO_ROLE.get(new_eve_label, "Off")

                    if new_day != cur_day or new_eve != cur_eve:
                        grid[name][day]["day"] = new_day
                        grid[name][day]["eve"] = new_eve
                        changed = True

            st.markdown("---")

        st.markdown("---")
        col_save, col_clear = st.columns(2)

        with col_save:
            if st.button("💾 Save Grid Schedule", key="save_grid_btn"):
                # Save grid to Google Sheets
                save_grid(grid)

                # Also sync into the main schedule structure
                for d in DAYS:
                    for s in SHIFTS:
                        schedule[d][s] = []
                for name, days in grid.items():
                    for day, roles in days.items():
                        for role_key in ["day", "eve"]:
                            role = roles.get(role_key, "Off")
                            if role and role != "Off" and role in SHIFTS:
                                if name not in schedule[day][role]:
                                    schedule[day][role].append(name)
                save_schedule(schedule)
                st.success("✓ Grid schedule saved!")
                st.rerun()

        with col_clear:
            if st.button("🗑️ Clear Grid", key="clear_grid_btn"):
                empty = {n: {d: {"day": "Off", "eve": "Off"} for d in DAYS} for n in staff_list}
                save_grid(empty)
                st.success("✓ Grid cleared!"); st.rerun()

        # Quick summary below
        st.markdown("---")
        st.markdown("### This Week at a Glance")
        summary_cols = st.columns(7)
        for di, day in enumerate(DAYS):
            with summary_cols[di]:
                st.markdown(f"**{day[:3]}**")
                day_assigned = [(n, grid[n][day]["day"]) for n in sorted(staff_list)
                    if grid.get(n,{}).get(day,{}).get("day","Off") != "Off"]
                eve_assigned = [(n, grid[n][day]["eve"]) for n in sorted(staff_list)
                    if grid.get(n,{}).get(day,{}).get("eve","Off") != "Off"]
                st.markdown(f"<small style='color:#c9a84c'>☀️ Day ({len(day_assigned)})</small>", unsafe_allow_html=True)
                for n, role in day_assigned:
                    short_role = role.replace("Day","").strip() or "Day"
                    st.markdown(f"<small style='color:#ddd'>{n.split()[0]} <span style='color:#888'>— {short_role}</span></small>", unsafe_allow_html=True)
                st.markdown(f"<small style='color:#7a8fff'>🌙 Eve ({len(eve_assigned)})</small>", unsafe_allow_html=True)
                for n, role in eve_assigned:
                    short_role = role.replace("Evening","").strip() or "Eve"
                    st.markdown(f"<small style='color:#ddd'>{n.split()[0]} <span style='color:#888'>— {short_role}</span></small>", unsafe_allow_html=True)

# ════════════════════════════════════════════
# TAB 4 — Unavailability
# ════════════════════════════════════════════
with tab4:
    st.markdown("### Staff Unavailability")
    st.caption("Tick any shift the staff member **cannot** work. Unticked = available.")
    if not staff_list:
        st.warning("No staff added yet.")
    else:
        sel_staff = st.selectbox("Staff Member", staff_list, key="avail_staff")
        if sel_staff not in avail_data:
            avail_data[sel_staff] = {}

        # Counter for forcing checkbox reset on clear
        counter_key = f"avail_counter_{sel_staff}"
        if counter_key not in st.session_state:
            st.session_state[counter_key] = 0
        cnt = st.session_state[counter_key]

        st.markdown(f"**Mark when {sel_staff} cannot work:**")
        st.markdown("")

        # Header row
        hcols = st.columns([2, 1, 1])
        hcols[0].markdown("**Day**")
        hcols[1].markdown("☀️ **Day shift**")
        hcols[2].markdown("🌙 **Evening shift**")
        st.markdown("---")

        updated = False
        for day in DAYS:
            dcols = st.columns([2, 1, 1])
            dcols[0].markdown(f"**{day}**")

            # Day unavailability
            cur_day = avail_data[sel_staff].get(day, {}).get("day_unavail", False)
            new_day = dcols[1].checkbox(
                "Cannot work", value=cur_day,
                key=f"avail_{sel_staff}_{day}_day_{cnt}",
                label_visibility="collapsed"
            )
            # Evening unavailability
            cur_eve = avail_data[sel_staff].get(day, {}).get("eve_unavail", False)
            new_eve = dcols[2].checkbox(
                "Cannot work", value=cur_eve,
                key=f"avail_{sel_staff}_{day}_eve_{cnt}",
                label_visibility="collapsed"
            )

            if new_day != cur_day or new_eve != cur_eve:
                if day not in avail_data[sel_staff]:
                    avail_data[sel_staff][day] = {}
                avail_data[sel_staff][day]["day_unavail"] = new_day
                avail_data[sel_staff][day]["eve_unavail"] = new_eve
                updated = True

        if updated:
            save_avail(avail_data)
            st.success(f"✓ Unavailability updated for {sel_staff}!")

        st.markdown("---")
        col_block, col_clear = st.columns(2)

        with col_block:
            st.markdown("**Block entire day:**")
            block_day = st.selectbox("Day", DAYS, key="block_day")
            if st.button("Block Day & Evening", key="block_btn"):
                if block_day not in avail_data[sel_staff]:
                    avail_data[sel_staff][block_day] = {}
                avail_data[sel_staff][block_day]["day_unavail"] = True
                avail_data[sel_staff][block_day]["eve_unavail"] = True
                save_avail(avail_data)
                st.session_state[counter_key] += 1
                st.success(f"✓ {sel_staff} blocked for {block_day}!"); st.rerun()

        with col_clear:
            st.markdown("**Reset all:**")
            if st.button(f"Clear All Unavailability", key="clear_avail_btn"):
                avail_data[sel_staff] = {d: {"day_unavail": False, "eve_unavail": False} for d in DAYS}
                save_avail(avail_data)
                st.session_state[counter_key] += 1
                st.success(f"✓ Cleared for {sel_staff}!"); st.rerun()

# ════════════════════════════════════════════
# TAB 5 — Manage Staff
# ════════════════════════════════════════════
with tab5:
    st.markdown("### Manage Staff")
    m1, m2 = st.columns(2)

    with m1:
        st.markdown("**Add New Staff Member:**")
        new_name  = st.text_input("Full name", key="new_staff_name")
        new_phone = st.text_input("Phone (with area code)", key="new_staff_phone")
        new_email = st.text_input("Email", key="new_staff_email")
        if st.button("Add Staff Member", key="add_staff_btn"):
            if new_name.strip() and new_name.strip() not in staff_dict:
                staff_dict[new_name.strip()] = {"phone": new_phone.strip(), "email": new_email.strip()}
                save_staff(staff_dict)
                avail_data[new_name.strip()] = {d: {s: False for s in SHIFTS} for d in DAYS}
                save_avail(avail_data)
                st.success(f"✓ {new_name} added!"); st.rerun()
            elif new_name.strip() in staff_dict:
                st.error("That name already exists.")

    with m2:
        st.markdown("**Remove Staff Member:**")
        if staff_list:
            del_name = st.selectbox("Select to remove", ["— select —"]+staff_list, key="del_staff")
            if st.button("Remove Staff Member", key="del_staff_btn"):
                if del_name != "— select —":
                    del staff_dict[del_name]
                    save_staff(staff_dict)
                    if del_name in avail_data:
                        del avail_data[del_name]
                        save_avail(avail_data)
                    for d in DAYS:
                        for s in SHIFTS:
                            if del_name in schedule[d][s]:
                                schedule[d][s].remove(del_name)
                    save_schedule(schedule)
                    st.success(f"✓ {del_name} removed!"); st.rerun()

        st.markdown("---")
        st.markdown("**Edit Contact Details:**")
        if staff_list:
            edit_name = st.selectbox("Select staff to edit", ["— select —"]+staff_list, key="edit_contact")
            if edit_name != "— select —":
                current    = staff_dict.get(edit_name, {})
                edit_phone = st.text_input("Phone", value=current.get("phone",""), key="edit_phone")
                edit_email = st.text_input("Email", value=current.get("email",""), key="edit_email")
                if st.button("Save Contact", key="save_contact"):
                    staff_dict[edit_name]["phone"] = edit_phone.strip()
                    staff_dict[edit_name]["email"] = edit_email.strip()
                    save_staff(staff_dict)
                    st.success(f"✓ Contact updated for {edit_name}!"); st.rerun()

    st.markdown("---")
    st.markdown("**Staff Directory:**")
    if staff_dict:
        st.dataframe(pd.DataFrame([
            {"Name": n, "Phone": i.get("phone","—"), "Email": i.get("email","—")}
            for n, i in sorted(staff_dict.items())
        ]), use_container_width=True, hide_index=True)
    else:
        st.info("No staff added yet.")

# ════════════════════════════════════════════
# TAB 6 — Export
# ════════════════════════════════════════════
with tab6:
    st.markdown("### Export Schedule")

    rows = []
    for day in DAYS:
        for shift in SHIFTS:
            assigned = schedule[day][shift]
            req      = get_required(shift, day)
            rows.append({
                "Day": day, "Shift": shift, "Required": req,
                "Assigned": len(assigned),
                "Staff": ", ".join(assigned) if assigned else "UNFILLED",
                "Status": "✓ OK" if len(assigned) >= req else "⚠️ UNDERSTAFFED"
            })
    df_export = pd.DataFrame(rows)
    st.dataframe(df_export, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📋 Finalize & Export PDF")

    understaffed_list = [(d,s) for d in DAYS for s in SHIFTS if len(schedule[d][s]) < REQUIRED.get(s,1)]
    if understaffed_list:
        st.warning(f"⚠️ {len(understaffed_list)} shift(s) still understaffed — will show as UNFILLED in PDF.")
    else:
        st.success("✓ All shifts fully staffed — ready to finalize!")

    week_label = st.text_input("Week label (e.g. Week of June 10)", key="week_label")

    if st.button("✅ Finalize & Generate PDF", key="finalize_btn"):
        if not week_label.strip():
            st.error("Please enter a week label.")
        else:
            buf = build_pdf(week_label.strip())
            st.success("✓ Schedule finalized!")
            st.download_button(
                label="📥 Download Schedule PDF",
                data=buf.getvalue(),
                file_name=f"hondos_{week_label.strip().replace(' ','_')}.pdf",
                mime="application/pdf"
            )

    st.markdown("---")
    st.markdown("**Download as Excel:**")
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Weekly Schedule")
        pd.DataFrame([
            {"Name": n, "Phone": i.get("phone",""), "Email": i.get("email","")}
            for n, i in sorted(staff_dict.items())
        ]).to_excel(writer, index=False, sheet_name="Staff Directory")
    st.download_button(
        label="📥 Download as Excel",
        data=excel_buf.getvalue(),
        file_name=f"hondos_schedule_{datetime.now().strftime('%Y_%m_%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("---")
    st.markdown("### 📧 Staff Email List")
    st.caption("Generate a list of staff emails you can copy and paste directly into any email recipient field.")

    email_options = st.radio(
        "Include:",
        ["All staff", "Only staff with emails", "This week's scheduled staff only"],
        horizontal=True, key="email_filter"
    )

    if email_options == "All staff":
        email_staff = [(n, i.get("email","")) for n, i in sorted(staff_dict.items())]
    elif email_options == "Only staff with emails":
        email_staff = [(n, i.get("email","")) for n, i in sorted(staff_dict.items()) if i.get("email","").strip()]
    else:
        # This week's scheduled staff only
        scheduled_names = set(
            name for d in DAYS for s in SHIFTS for name in schedule[d][s]
        )
        email_staff = [(n, staff_dict[n].get("email","")) for n in sorted(scheduled_names) if n in staff_dict]

    if st.button("📧 Generate Email List", key="gen_email_btn"):
        emails_with    = [e for _, e in email_staff if e.strip()]
        emails_without = [n for n, e in email_staff if not e.strip()]

        if emails_with:
            email_string = ", ".join(emails_with)
            st.markdown("**Copy and paste this into your recipient field:**")
            st.code(email_string, language=None)
            st.success(f"✓ {len(emails_with)} email address(es) ready to copy!")
        else:
            st.warning("No email addresses found for the selected staff. Add emails in the Manage Staff tab.")

        if emails_without:
            st.info(f"ℹ️ These staff have no email on file: {', '.join(emails_without)}")

# ════════════════════════════════════════════
# TAB 7 — Settings
# ════════════════════════════════════════════
# ════════════════════════════════════════════
# TAB 7 — Settings
# ════════════════════════════════════════════
with tab7:
    st.markdown("### ⚙️ Shift Slot Settings")
    st.caption("Set how many staff are required for each shift — you can set a different number per day.")

    updated_required = {}
    sel_req_shift = st.selectbox("Select shift to configure", SHIFTS, key="req_shift_sel")

    st.markdown(f"**Required staff for: {sel_req_shift}**")
    day_cols = st.columns(7)
    shift_vals = REQUIRED.get(sel_req_shift, {})
    if isinstance(shift_vals, int):
        shift_vals = {d: shift_vals for d in DAYS}

    new_day_vals = {}
    for di, day in enumerate(DAYS):
        with day_cols[di]:
            st.markdown(f"**{day[:3]}**")
            current = shift_vals.get(day, 0)
            new_day_vals[day] = st.number_input(
                day, min_value=0, max_value=20,
                value=current, step=1,
                key=f"req_{sel_req_shift}_{day}",
                label_visibility="collapsed"
            )

    col_save_req, col_fill = st.columns(2)
    with col_save_req:
        if st.button(f"Save {sel_req_shift} Requirements", key="save_req_btn"):
            updated_required = {**REQUIRED}
            updated_required[sel_req_shift] = new_day_vals
            save_required(updated_required)
            st.success(f"✓ Requirements saved for {sel_req_shift}!"); st.rerun()
    with col_fill:
        fill_val = st.number_input("Fill all days with:", min_value=0, max_value=20, value=0, key="fill_val")
        if st.button("Apply to all days", key="fill_btn"):
            updated_required = {**REQUIRED}
            updated_required[sel_req_shift] = {d: fill_val for d in DAYS}
            save_required(updated_required)
            st.success(f"✓ All days set to {fill_val} for {sel_req_shift}!"); st.rerun()

    # Summary table
    st.markdown("---")
    st.markdown("**Current Requirements Summary:**")
    summary_rows = []
    for shift in SHIFTS:
        vals = REQUIRED.get(shift, {})
        if isinstance(vals, int): vals = {d: vals for d in DAYS}
        row = {"Shift": shift}
        for day in DAYS:
            row[day[:3]] = vals.get(day, 0)
        summary_rows.append(row)
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 🕐 Arrival Times")
    st.caption("Set default arrival times for each shift. You can also override per day below.")

    # ── Default arrival times ──────────────────────────────────────────────
    st.markdown("**Default Arrival Times:**")
    defaults = arrivals_data.get("defaults", DEFAULT_ARRIVAL_TIMES)
    updated_defaults = {}
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("*Day Shifts*")
        for shift in ["Day", "Day Closer", "Day Trainee"]:
            updated_defaults[shift] = st.text_input(
                f"{shift}", value=defaults.get(shift, ""),
                placeholder="e.g. 10:00 AM", key=f"arr_def_{shift}"
            )
    with d2:
        st.markdown("*Evening Shifts*")
        for shift in ["Evening", "Evening Closer 1", "Evening Closer 2", "Evening Bartender", "Evening Trainee"]:
            updated_defaults[shift] = st.text_input(
                f"{shift}", value=defaults.get(shift, ""),
                placeholder="e.g. 4:00 PM", key=f"arr_def_{shift}"
            )

    if st.button("Save Default Arrival Times", key="save_arr_def"):
        arrivals_data["defaults"] = updated_defaults
        save_arrivals(arrivals_data)
        st.success("✓ Default arrival times saved!"); st.rerun()

    st.markdown("---")
    st.markdown("**Per Day Overrides:**")
    st.caption("Leave blank to use the default time. Only fill in if a specific day differs.")

    overrides = arrivals_data.get("overrides", {})
    sel_override_day = st.selectbox("Select day to override", DAYS, key="override_day_sel")

    day_overrides = overrides.get(sel_override_day, {})
    updated_overrides = {}
    o1, o2 = st.columns(2)
    with o1:
        st.markdown("*Day Shifts*")
        for shift in ["Day", "Day Closer", "Day Trainee"]:
            default_hint = defaults.get(shift, "")
            updated_overrides[shift] = st.text_input(
                f"{shift}", value=day_overrides.get(shift, ""),
                placeholder=f"Default: {default_hint}" if default_hint else "e.g. 10:00 AM",
                key=f"arr_ov_{sel_override_day}_{shift}"
            )
    with o2:
        st.markdown("*Evening Shifts*")
        for shift in ["Evening", "Evening Closer 1", "Evening Closer 2", "Evening Bartender", "Evening Trainee"]:
            default_hint = defaults.get(shift, "")
            updated_overrides[shift] = st.text_input(
                f"{shift}", value=day_overrides.get(shift, ""),
                placeholder=f"Default: {default_hint}" if default_hint else "e.g. 4:00 PM",
                key=f"arr_ov_{sel_override_day}_{shift}"
            )

    if st.button(f"Save {sel_override_day} Overrides", key="save_arr_ov"):
        # Only save non-empty overrides
        clean = {s: t for s, t in updated_overrides.items() if t.strip()}
        arrivals_data["overrides"][sel_override_day] = clean
        save_arrivals(arrivals_data)
        st.success(f"✓ Overrides saved for {sel_override_day}!"); st.rerun()

    if st.button(f"Clear {sel_override_day} Overrides (use defaults)", key="clear_arr_ov"):
        arrivals_data["overrides"].pop(sel_override_day, None)
        save_arrivals(arrivals_data)
        st.success(f"✓ {sel_override_day} overrides cleared!"); st.rerun()

    st.markdown("---")
    st.markdown("### 🔧 Connection Debug")
    st.caption("Use this to test whether the app can read and write to Google Sheets.")
    if st.button("Test Google Sheets Connection", key="debug_btn"):
        ok, err = test_connection()
        if ok:
            st.success("✓ Connection working — app can read and write to Google Sheets!")
        else:
            st.error(f"✗ Connection failed: {err}")
