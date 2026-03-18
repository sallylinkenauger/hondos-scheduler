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
    "Day", "Day Closer", "Day Trainee",
    "Evening", "Evening Closer 1", "Evening Closer 2", "Evening Bartender", "Evening Trainee"
]
DAYS   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_REQUIRED = {
    "Day": 3, "Day Closer": 1, "Day Trainee": 1,
    "Evening": 3, "Evening Closer 1": 1, "Evening Closer 2": 1,
    "Evening Bartender": 1, "Evening Trainee": 1
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
    }

# ── Read / write helpers ───────────────────────────────────────────────────────
def read_cell(sheet, cell):
    val = sheet.acell(cell).value
    return json.loads(val) if val else None

def write_cell(sheet, cell, data):
    sheet.update_acell(cell, json.dumps(data))

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

    return staff_dict, avail, sched, req

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

# ── Load ───────────────────────────────────────────────────────────────────────
try:
    staff_dict, avail_data, schedule, REQUIRED = load_all()
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
    SHIFT_COLORS = {
        "Day": HexColor("#e8f5ee"), "Day Closer": HexColor("#fff3e0"),
        "Day Trainee": HexColor("#e8f8ff"),
        "Evening": HexColor("#e8eaf6"),
        "Evening Closer 1": HexColor("#fce4ec"), "Evening Closer 2": HexColor("#fce4ec"),
        "Evening Bartender": HexColor("#f3e5f5"),
        "Evening Trainee": HexColor("#e0f7fa"),
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
        row_y = TOP - ROW_H - (si+1)*ROW_H
        for di, day in enumerate(DAYS):
            x        = MARGIN + di*COL_W
            assigned = schedule[day][shift]
            req      = REQUIRED.get(shift, 1)
            is_under = len(assigned) < req
            bg = HexColor("#ffe8e8") if is_under else SHIFT_COLORS.get(shift, HexColor("#f5f5f5"))
            c.setFillColor(bg); c.setStrokeColor(HexColor("#cccccc")); c.setLineWidth(0.5)
            c.rect(x, row_y, COL_W, ROW_H, fill=1, stroke=1)
            if di == 0:
                c.setFillColor(HexColor("#444444")); c.setFont("Helvetica-Bold", 7)
                c.drawString(x+3, row_y+ROW_H-10, shift)
            if assigned:
                c.setFillColor(DARK); c.setFont("Helvetica", 7.5)
                for ni, name in enumerate(assigned):
                    ny = row_y + ROW_H - 20 - ni*11
                    if ny > row_y + 2:
                        parts = name.split()
                        short = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else name
                        c.drawString(x+4, ny, short)
            else:
                c.setFillColor(RED); c.setFont("Helvetica-BoldOblique", 7.5)
                c.drawString(x+4, row_y+ROW_H/2-4, "UNFILLED")
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
understaffed   = sum(1 for d in DAYS for s in SHIFTS if len(schedule[d][s]) < REQUIRED.get(s, 1))
avail_count    = len([n for n in staff_list if any(
    avail_data.get(n, {}).get(d, {}).get(s, False) for d in DAYS for s in SHIFTS)])

c1,c2,c3,c4 = st.columns(4)
for col, label, value in zip([c1,c2,c3,c4],
    ["Total Staff","Shifts Assigned","Understaffed Slots","Staff Available"],
    [total_staff, total_assigned, understaffed, avail_count]):
    with col:
        color = "#ff4444" if label == "Understaffed Slots" and value > 0 else "#f0e6d3"
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value" style="color:{color}">{value}</div></div>', unsafe_allow_html=True)

st.markdown("---")

tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
    "📅 Weekly Schedule","✏️ Assign Shifts",
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
                req      = REQUIRED.get(shift, 1)
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
                st.markdown(f'<div class="{css}"><strong>{short}</strong> ({count}/{req})<br><small>{names}</small></div>', unsafe_allow_html=True)

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
        req     = REQUIRED.get(sel_shift, 1)

        if len(already) < req:
            st.warning(f"⚠️ {sel_day} — {sel_shift}: {len(already)}/{req} — need {req-len(already)} more")
        else:
            st.success(f"✓ {sel_day} — {sel_shift}: Fully staffed ({len(already)}/{req})")

        c_add, c_remove = st.columns(2)
        with c_add:
            st.markdown("**Add available staff:**")
            avail_for_slot = [n for n in staff_list
                if avail_data.get(n,{}).get(sel_day,{}).get(sel_shift, False)
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
                    req_s    = REQUIRED.get(shift, 1)
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
# TAB 3 — Availability
# ════════════════════════════════════════════
with tab3:
    st.markdown("### Staff Availability")
    if not staff_list:
        st.warning("No staff added yet.")
    else:
        sel_staff = st.selectbox("Staff Member", staff_list, key="avail_staff")
        if sel_staff not in avail_data:
            avail_data[sel_staff] = {d: {s: False for s in SHIFTS} for d in DAYS}

        st.markdown(f"**Availability for {sel_staff}:**")
        updated = False
        for day in DAYS:
            st.markdown(f"**{day}**")
            day_cols = st.columns(len(SHIFTS))
            for si, shift in enumerate(SHIFTS):
                current = avail_data[sel_staff].get(day, {}).get(shift, False)
                new_val = day_cols[si].checkbox(
                    shift.replace("Evening Closer 1","Eve▲1").replace("Evening Closer 2","Eve▲2").replace("Evening Bartender","Eve🍸").replace("Evening Trainee","Eve🎓").replace("Day Closer","Day★").replace("Day Trainee","Day🎓").replace("Evening","Eve"),
                    value=current, key=f"avail_{sel_staff}_{day}_{shift}"
                )
                if new_val != current:
                    if day not in avail_data[sel_staff]: avail_data[sel_staff][day] = {}
                    avail_data[sel_staff][day][shift] = new_val
                    updated = True
        if updated:
            save_avail(avail_data)
            st.success(f"✓ Availability updated for {sel_staff}!")

        st.markdown("---")
        st.markdown("**Block out a full day:**")
        block_day = st.selectbox("Day to block", DAYS, key="block_day")
        if st.button("Block This Day", key="block_btn"):
            for s in SHIFTS: avail_data[sel_staff][block_day][s] = False
            save_avail(avail_data)
            st.success(f"✓ {sel_staff} blocked for {block_day}!"); st.rerun()

# ════════════════════════════════════════════
# TAB 4 — Manage Staff
# ════════════════════════════════════════════
with tab4:
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
# TAB 5 — Export
# ════════════════════════════════════════════
with tab5:
    st.markdown("### Export Schedule")

    rows = []
    for day in DAYS:
        for shift in SHIFTS:
            assigned = schedule[day][shift]
            req      = REQUIRED.get(shift, 1)
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

# ════════════════════════════════════════════
# TAB 6 — Settings
# ════════════════════════════════════════════
with tab6:
    st.markdown("### Shift Slot Settings")
    s1, s2 = st.columns(2)
    updated_required = {}
    with s1:
        st.markdown("**Day Shifts:**")
        updated_required["Day"]         = st.number_input("Day — required", min_value=0, max_value=20, value=REQUIRED.get("Day",3), key="req_day")
        updated_required["Day Closer"]  = st.number_input("Day Closer — required", min_value=0, max_value=10, value=REQUIRED.get("Day Closer",1), key="req_day_c")
        updated_required["Day Trainee"] = st.number_input("Day Trainee — required", min_value=0, max_value=10, value=REQUIRED.get("Day Trainee",1), key="req_day_t")
    with s2:
        st.markdown("**Evening Shifts:**")
        updated_required["Evening"]            = st.number_input("Evening — required", min_value=0, max_value=20, value=REQUIRED.get("Evening",3), key="req_eve")
        updated_required["Evening Closer 1"]   = st.number_input("Evening Closer 1 — required", min_value=0, max_value=10, value=REQUIRED.get("Evening Closer 1",1), key="req_eve_c1")
        updated_required["Evening Closer 2"]   = st.number_input("Evening Closer 2 — required", min_value=0, max_value=10, value=REQUIRED.get("Evening Closer 2",1), key="req_eve_c2")
        updated_required["Evening Bartender"]  = st.number_input("Evening Bartender — required", min_value=0, max_value=10, value=REQUIRED.get("Evening Bartender",1), key="req_eve_bar")
        updated_required["Evening Trainee"]    = st.number_input("Evening Trainee — required", min_value=0, max_value=10, value=REQUIRED.get("Evening Trainee",1), key="req_eve_t")
    if st.button("Save Settings", key="save_req"):
        save_required(updated_required)
        st.success("✓ Settings saved!"); st.rerun()

    st.markdown("---")
    st.markdown("### 🔧 Connection Debug")
    st.caption("Use this to test whether the app can read and write to Google Sheets.")
    if st.button("Test Google Sheets Connection", key="debug_btn"):
        ok, err = test_connection()
        if ok:
            st.success("✓ Connection working — app can read and write to Google Sheets!")
        else:
            st.error(f"✗ Connection failed: {err}")
