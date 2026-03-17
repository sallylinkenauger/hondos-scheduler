import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os
import io

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
    .stButton > button { background: linear-gradient(135deg, #8b6914, #c9a84c); color: #1a1a1a; border: none; border-radius: 6px; font-weight: 600; font-size: 0.8rem; letter-spacing: 0.05em; padding: 0.4rem 1.2rem; }
    .stButton > button:hover { opacity: 0.88; }
    .stSelectbox select, .stTextInput input { background-color: #2a2a2a !important; color: #f0e6d3 !important; border: 1px solid #c9a84c66 !important; }
    [data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #c9a84c22; }
    .stTabs [data-baseweb="tab"] { color: #c9a84caa; font-size: 0.78rem; letter-spacing: 0.1em; text-transform: uppercase; }
    .stTabs [aria-selected="true"] { color: #c9a84c !important; border-bottom-color: #c9a84c !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
STAFF_FILE    = "hondos_staff.json"
AVAIL_FILE    = "hondos_availability.json"
SCHEDULE_FILE = "hondos_schedule.json"
REQUIRED_FILE = "hondos_required.json"

SHIFTS = ["Day", "Day Closer", "Evening", "Evening Closer 1", "Evening Closer 2"]
DAYS   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_REQUIRED = {"Day": 3, "Day Closer": 1, "Evening": 3, "Evening Closer 1": 1, "Evening Closer 2": 1}

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ── Load data ─────────────────────────────────────────────────────────────────
raw_staff  = load_json(STAFF_FILE, {})
# Handle old format (list) gracefully — convert to dict
if isinstance(raw_staff, list):
    staff_dict = {name: {"phone": "", "email": ""} for name in raw_staff}
    save_json(STAFF_FILE, staff_dict)  # upgrade the file
else:
    staff_dict = raw_staff
staff_list = list(staff_dict.keys())
avail_data = load_json(AVAIL_FILE, {})
schedule   = load_json(SCHEDULE_FILE, {d: {s: [] for s in SHIFTS} for d in DAYS})
REQUIRED   = load_json(REQUIRED_FILE, DEFAULT_REQUIRED)

for d in DAYS:
    if d not in schedule:
        schedule[d] = {s: [] for s in SHIFTS}
    for s in SHIFTS:
        if s not in schedule[d]:
            schedule[d][s] = []

# ── PDF builder ───────────────────────────────────────────────────────────────
def build_pdf(week_label):
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    W, H = landscape(letter)
    c = rl_canvas.Canvas(buf, pagesize=landscape(letter))

    GOLD  = HexColor("#c9a84c")
    DARK  = HexColor("#1a1a1a")
    WHITE = HexColor("#ffffff")
    RED   = HexColor("#cc3333")

    SHIFT_COLORS = {
        "Day":              HexColor("#e8f5ee"),
        "Day Closer":       HexColor("#fff3e0"),
        "Evening":          HexColor("#e8eaf6"),
        "Evening Closer 1": HexColor("#fce4ec"),
        "Evening Closer 2": HexColor("#fce4ec"),
    }

    # Header bar
    c.setFillColor(DARK)
    c.rect(0, H-55, W, 55, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(24, H-32, "HONDO'S  —  Weekly Schedule")
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 12)
    c.drawString(24, H-50, week_label)
    c.setFont("Helvetica", 10)
    c.drawRightString(W-24, H-35, f"Generated: {datetime.now().strftime('%B %d, %Y')}")

    # Grid
    MARGIN = 18
    TOP    = H - 62
    BOTTOM = 36
    COL_W  = (W - MARGIN*2) / 7
    ROW_H  = (TOP - BOTTOM) / (len(SHIFTS) + 1)

    # Day headers
    for di, day in enumerate(DAYS):
        x = MARGIN + di * COL_W
        c.setFillColor(HexColor("#2a2a2a"))
        c.rect(x, TOP - ROW_H, COL_W, ROW_H, fill=1, stroke=1)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + COL_W/2, TOP - ROW_H + ROW_H*0.32, day.upper())

    # Shift label column header
    c.setFillColor(HexColor("#f5f5f5"))
    c.setFont("Helvetica-Bold", 8)

    # Shift rows
    for si, shift in enumerate(SHIFTS):
        row_y = TOP - ROW_H - (si + 1) * ROW_H

        for di, day in enumerate(DAYS):
            x        = MARGIN + di * COL_W
            assigned = schedule[day][shift]
            req      = REQUIRED.get(shift, 1)
            is_under = len(assigned) < req
            bg       = HexColor("#ffe8e8") if is_under else SHIFT_COLORS.get(shift, HexColor("#f5f5f5"))

            c.setFillColor(bg)
            c.setStrokeColor(HexColor("#cccccc"))
            c.setLineWidth(0.5)
            c.rect(x, row_y, COL_W, ROW_H, fill=1, stroke=1)

            # Shift name label on first column
            if di == 0:
                c.setFillColor(HexColor("#555555"))
                c.setFont("Helvetica-Bold", 7)
                c.drawString(x + 3, row_y + ROW_H - 9, shift)

            # Staff names
            if assigned:
                c.setFillColor(DARK)
                c.setFont("Helvetica", 7.5)
                for ni, name in enumerate(assigned):
                    ny = row_y + ROW_H - 18 - ni * 11
                    if ny > row_y + 2:
                        parts = name.split()
                        short = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else name
                        c.drawString(x + 4, ny, short)
            else:
                c.setFillColor(RED)
                c.setFont("Helvetica-BoldOblique", 7.5)
                c.drawString(x + 4, row_y + ROW_H/2 - 4, "UNFILLED")

            # Count indicator
            if is_under:
                c.setFillColor(RED)
                c.setFont("Helvetica-Bold", 6)
                c.drawRightString(x + COL_W - 3, row_y + 3, f"{len(assigned)}/{req}")
            else:
                c.setFillColor(HexColor("#2d6a4f"))
                c.setFont("Helvetica-Bold", 6)
                c.drawRightString(x + COL_W - 3, row_y + 3, f"{len(assigned)}/{req}")

    # Footer
    c.setFillColor(HexColor("#888888"))
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN, 20, "Day  |  Day Closer  |  Evening  |  Evening Closer 1 & 2     🔴 = Understaffed")
    c.drawRightString(W - MARGIN, 20, f"Hondo's Restaurant  •  {week_label}")

    c.save()
    buf.seek(0)
    return buf.getvalue()

# ── Excel builder ─────────────────────────────────────────────────────────────
def build_excel(week_label):
    rows = []
    for day in DAYS:
        for shift in SHIFTS:
            assigned = schedule[day][shift]
            req      = REQUIRED.get(shift, 1)
            rows.append({
                "Day":      day,
                "Shift":    shift,
                "Required": req,
                "Assigned": len(assigned),
                "Staff":    ", ".join(assigned) if assigned else "UNFILLED",
                "Status":   "OK" if len(assigned) >= req else "UNDERSTAFFED"
            })

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Weekly Schedule")

        dir_rows = [
            {"Name": n, "Phone": info.get("phone", ""), "Email": info.get("email", "")}
            for n, info in sorted(staff_dict.items())
        ]
        pd.DataFrame(dir_rows).to_excel(writer, index=False, sheet_name="Staff Directory")

        avail_rows = []
        for name in staff_list:
            for day in DAYS:
                for shift in SHIFTS:
                    avail_rows.append({
                        "Staff":     name,
                        "Day":       day,
                        "Shift":     shift,
                        "Available": "Yes" if avail_data.get(name, {}).get(day, {}).get(shift, False) else "No"
                    })
        pd.DataFrame(avail_rows).to_excel(writer, index=False, sheet_name="Availability")

    buf.seek(0)
    return buf.getvalue()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("<h1 style='font-size:2.4rem; letter-spacing:0.06em;'>🍽️ Hondo's Weekly Scheduler</h1>", unsafe_allow_html=True)

total_staff    = len(staff_list)
total_assigned = sum(len(schedule[d][s]) for d in DAYS for s in SHIFTS)
understaffed_n = sum(1 for d in DAYS for s in SHIFTS if len(schedule[d][s]) < REQUIRED.get(s, 1))
avail_count    = len([n for n in staff_list if any(
    avail_data.get(n, {}).get(d, {}).get(s, False) for d in DAYS for s in SHIFTS
)])

c1, c2, c3, c4 = st.columns(4)
for col, label, value in zip([c1,c2,c3,c4],
    ["Total Staff","Shifts Assigned","Understaffed Slots","Staff Available"],
    [total_staff, total_assigned, understaffed_n, avail_count]):
    with col:
        color = "#ff4444" if label == "Understaffed Slots" and value > 0 else "#f0e6d3"
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value" style="color:{color}">{value}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅  Weekly Schedule", "✏️  Assign Shifts",
    "🙋  Staff Availability", "👥  Manage Staff",
    "📤  Finalize & Export", "⚙️  Settings"
])

# ════════════════════════════════════════════
# TAB 1 — Weekly View
# ════════════════════════════════════════════
with tab1:
    st.markdown("### Weekly Schedule Overview")
    st.caption("🔴 Red = understaffed")
    cols = st.columns(7)
    for di, day in enumerate(DAYS):
        with cols[di]:
            st.markdown(f"**{day[:3]}**")
            for shift in SHIFTS:
                assigned = schedule[day][shift]
                req      = REQUIRED.get(shift, 1)
                count    = len(assigned)
                names    = ", ".join(assigned) if assigned else "—"
                short    = shift.replace("Evening Closer 1","Eve▲1").replace("Evening Closer 2","Eve▲2").replace("Day Closer","Day★").replace("Evening","Eve").replace("Day","Day")
                css      = "understaffed" if count < req else ("shift-closer-eve" if "Evening Closer" in shift else "shift-closer-day" if "Day Closer" in shift else "shift-eve" if "Evening" in shift else "shift-day")
                st.markdown(f'<div class="{css}"><strong>{short}</strong> ({count}/{req})<br><small>{names}</small></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════
# TAB 2 — Assign Shifts
# ════════════════════════════════════════════
with tab2:
    st.markdown("### Assign Shifts")
    if not staff_list:
        st.warning("No staff added yet.")
    else:
        # ── Top: assignment controls ──────────────────────────────────────
        a1, a2 = st.columns(2)
        with a1: sel_day   = st.selectbox("Day",   DAYS,   key="assign_day")
        with a2: sel_shift = st.selectbox("Shift", SHIFTS, key="assign_shift")

        already = schedule[sel_day][sel_shift]
        req     = REQUIRED.get(sel_shift, 1)

        if len(already) < req:
            st.warning(f"⚠️ {sel_day} — {sel_shift}: {len(already)}/{req} filled — need {req - len(already)} more")
        else:
            st.success(f"✓ {sel_day} — {sel_shift}: Fully staffed ({len(already)}/{req})")

        c_add, c_remove = st.columns(2)

        with c_add:
            st.markdown("**Add available staff:**")
            avail_for_slot = [n for n in staff_list
                if avail_data.get(n, {}).get(sel_day, {}).get(sel_shift, False)
                and n not in already]
            if avail_for_slot:
                to_add = st.selectbox("Available", ["— select —"] + avail_for_slot, key="add_staff")
                if st.button("➕ Add to Shift", key="add_btn"):
                    if to_add != "— select —":
                        schedule[sel_day][sel_shift].append(to_add)
                        save_json(SCHEDULE_FILE, schedule)
                        st.success(f"✓ {to_add} added!"); st.rerun()
            else:
                st.info("No available staff for this slot.")
            with st.expander("Add any staff (override availability)"):
                not_assigned = [n for n in staff_list if n not in already]
                override = st.selectbox("Staff", ["— select —"] + not_assigned, key="override_add")
                if st.button("Add (Override)", key="override_btn"):
                    if override != "— select —":
                        schedule[sel_day][sel_shift].append(override)
                        save_json(SCHEDULE_FILE, schedule)
                        st.success(f"✓ {override} added!"); st.rerun()

        with c_remove:
            st.markdown("**Remove from shift:**")
            if already:
                to_remove = st.selectbox("Remove", ["— select —"] + already, key="remove_staff")
                if st.button("➖ Remove", key="remove_btn"):
                    if to_remove != "— select —":
                        schedule[sel_day][sel_shift].remove(to_remove)
                        save_json(SCHEDULE_FILE, schedule)
                        st.success(f"✓ {to_remove} removed!"); st.rerun()
            else:
                st.info("No staff assigned yet.")

        st.markdown("---")

        # ── Live schedule view ────────────────────────────────────────────
        st.markdown("### 📅 Current Week at a Glance")
        st.caption("Updates live as you assign shifts. Red = understaffed.")

        grid_cols = st.columns(7)
        for di, day in enumerate(DAYS):
            with grid_cols[di]:
                # Highlight selected day
                day_label = f"**{'→ ' if day == sel_day else ''}{day[:3]}**"
                st.markdown(day_label)
                for shift in SHIFTS:
                    assigned = schedule[day][shift]
                    req_s    = REQUIRED.get(shift, 1)
                    count    = len(assigned)
                    names    = "<br>".join(n.split()[0] for n in assigned) if assigned else "—"
                    short    = shift.replace("Evening Closer 1","Eve▲1").replace("Evening Closer 2","Eve▲2").replace("Day Closer","Day★").replace("Evening","Eve")
                    # Highlight selected slot
                    is_selected = (day == sel_day and shift == sel_shift)
                    border_style = "3px solid #c9a84c" if is_selected else "1px solid #555"
                    bg = "#3a1a1a" if count < req_s else ("#2a2a1a" if is_selected else "#1e2a1e" if "Day" in shift else "#1a1a2a")
                    st.markdown(
                        f'<div style="background:{bg};border:{border_style};border-radius:5px;padding:4px 6px;margin:2px 0;font-size:0.75rem">'
                        f'<strong style="color:#c9a84c">{short}</strong> '
                        f'<span style="color:#aaa">({count}/{req_s})</span><br>'
                        f'<span style="color:#ddd;font-size:0.7rem">{names}</span></div>',
                        unsafe_allow_html=True
                    )

        st.markdown("---")
        if st.button("🗑️ Clear Entire Week", key="clear_week"):
            for d in DAYS:
                for s in SHIFTS:
                    schedule[d][s] = []
            save_json(SCHEDULE_FILE, schedule)
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
                    shift.replace(" Closer 1","▲1").replace(" Closer 2","▲2").replace(" Closer","★"),
                    value=current, key=f"avail_{sel_staff}_{day}_{shift}")
                if new_val != current:
                    if day not in avail_data[sel_staff]:
                        avail_data[sel_staff][day] = {}
                    avail_data[sel_staff][day][shift] = new_val
                    updated = True
        if updated:
            save_json(AVAIL_FILE, avail_data)
            st.success(f"✓ Availability saved for {sel_staff}!")

        st.markdown("---")
        block_day = st.selectbox("Block out full day", DAYS, key="block_day")
        if st.button("Block This Day", key="block_btn"):
            for s in SHIFTS:
                avail_data[sel_staff][block_day][s] = False
            save_json(AVAIL_FILE, avail_data)
            st.success(f"✓ {sel_staff} blocked for {block_day}!"); st.rerun()

# ════════════════════════════════════════════
# TAB 4 — Manage Staff
# ════════════════════════════════════════════
with tab4:
    st.markdown("### Manage Staff")
    m1, m2 = st.columns(2)

    with m1:
        st.markdown("**Add New Staff Member:**")
        new_name  = st.text_input("Full name",             key="new_staff_name")
        new_phone = st.text_input("Phone (with area code)", placeholder="e.g. 5401234567", key="new_staff_phone")
        new_email = st.text_input("Email",                  placeholder="e.g. name@email.com", key="new_staff_email")
        if st.button("Add Staff Member", key="add_staff_btn"):
            if new_name.strip() and new_name.strip() not in staff_dict:
                staff_dict[new_name.strip()] = {"phone": new_phone.strip(), "email": new_email.strip()}
                save_json(STAFF_FILE, staff_dict)
                avail_data[new_name.strip()] = {d: {s: False for s in SHIFTS} for d in DAYS}
                save_json(AVAIL_FILE, avail_data)
                st.success(f"✓ {new_name} added!"); st.rerun()
            elif new_name.strip() in staff_dict:
                st.error("That name already exists.")

    with m2:
        st.markdown("**Remove Staff Member:**")
        if staff_list:
            del_name = st.selectbox("Select to remove", ["— select —"] + staff_list, key="del_staff")
            if st.button("Remove", key="del_staff_btn"):
                if del_name != "— select —":
                    del staff_dict[del_name]
                    save_json(STAFF_FILE, staff_dict)
                    if del_name in avail_data:
                        del avail_data[del_name]
                        save_json(AVAIL_FILE, avail_data)
                    for d in DAYS:
                        for s in SHIFTS:
                            if del_name in schedule[d][s]:
                                schedule[d][s].remove(del_name)
                    save_json(SCHEDULE_FILE, schedule)
                    st.success(f"✓ {del_name} removed!"); st.rerun()

        st.markdown("---")
        st.markdown("**Edit Contact Details:**")
        if staff_list:
            edit_name = st.selectbox("Select to edit", ["— select —"] + staff_list, key="edit_contact")
            if edit_name != "— select —":
                current    = staff_dict.get(edit_name, {})
                edit_phone = st.text_input("Phone", value=current.get("phone", ""), key="edit_phone")
                edit_email = st.text_input("Email", value=current.get("email", ""), key="edit_email")
                if st.button("Save Contact", key="save_contact"):
                    staff_dict[edit_name]["phone"] = edit_phone.strip()
                    staff_dict[edit_name]["email"] = edit_email.strip()
                    save_json(STAFF_FILE, staff_dict)
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
# TAB 5 — Finalize & Export
# ════════════════════════════════════════════
with tab5:
    st.markdown("### Finalize & Export Schedule")

    # Preview
    rows = []
    for day in DAYS:
        for shift in SHIFTS:
            assigned = schedule[day][shift]
            req      = REQUIRED.get(shift, 1)
            rows.append({
                "Day": day, "Shift": shift, "Required": req,
                "Assigned": len(assigned),
                "Staff":  ", ".join(assigned) if assigned else "UNFILLED",
                "Status": "✓ OK" if len(assigned) >= req else "⚠️ UNDERSTAFFED"
            })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Understaffed warning
    understaffed_list = [(d, s) for d in DAYS for s in SHIFTS if len(schedule[d][s]) < REQUIRED.get(s, 1)]
    if understaffed_list:
        st.warning(f"⚠️ {len(understaffed_list)} shift(s) understaffed — will show as UNFILLED in exports.")
    else:
        st.success("✓ All shifts fully staffed!")

    st.markdown("---")
    st.markdown("### 📋 Finalize")
    week_label = st.text_input("Week label (e.g. Week of June 10, 2025)", placeholder="Week of ___", key="week_label")

    if st.button("✅ Finalize & Generate Exports", key="finalize_btn"):
        if not week_label.strip():
            st.error("Please enter a week label first.")
        else:
            with st.spinner("Generating PDF and Excel..."):
                pdf_bytes   = build_pdf(week_label.strip())
                excel_bytes = build_excel(week_label.strip())

            safe_label = week_label.strip().replace(" ", "_").replace("/", "-")
            st.success("✓ Ready to download!")

            col_pdf, col_xl = st.columns(2)
            with col_pdf:
                st.download_button(
                    label="📄 Download PDF Schedule",
                    data=pdf_bytes,
                    file_name=f"hondos_schedule_{safe_label}.pdf",
                    mime="application/pdf",
                    key="dl_pdf"
                )
            with col_xl:
                st.download_button(
                    label="📊 Download Excel Schedule",
                    data=excel_bytes,
                    file_name=f"hondos_schedule_{safe_label}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_excel"
                )

# ════════════════════════════════════════════
# TAB 6 — Settings
# ════════════════════════════════════════════
with tab6:
    st.markdown("### Shift Slot Settings")
    st.caption("Set how many staff are required per shift. Saves automatically.")

    updated_required = {}
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Day Shifts:**")
        updated_required["Day"]        = st.number_input("Day — required",        min_value=0, max_value=20, value=REQUIRED.get("Day", 3),        step=1, key="req_day")
        updated_required["Day Closer"] = st.number_input("Day Closer — required", min_value=0, max_value=10, value=REQUIRED.get("Day Closer", 1), step=1, key="req_day_closer")
    with s2:
        st.markdown("**Evening Shifts:**")
        updated_required["Evening"]          = st.number_input("Evening — required",          min_value=0, max_value=20, value=REQUIRED.get("Evening", 3),          step=1, key="req_eve")
        updated_required["Evening Closer 1"] = st.number_input("Evening Closer 1 — required", min_value=0, max_value=10, value=REQUIRED.get("Evening Closer 1", 1), step=1, key="req_eve_c1")
        updated_required["Evening Closer 2"] = st.number_input("Evening Closer 2 — required", min_value=0, max_value=10, value=REQUIRED.get("Evening Closer 2", 1), step=1, key="req_eve_c2")

    if st.button("Save Settings", key="save_req"):
        save_json(REQUIRED_FILE, updated_required)
        st.success("✓ Saved!"); st.rerun()