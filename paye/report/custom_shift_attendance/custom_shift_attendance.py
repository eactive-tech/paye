import frappe
from frappe import _
from frappe.utils import flt, get_time, format_duration

def execute(filters=None):
    if not filters:
        filters = {}

    # Map raw filters to what Shift Attendance report expects if needed
    # Standard reports usually take filters directly as passed
    
    # Run the base report
    attendance_data = frappe.call(
        "frappe.desk.query_report.run",
        filters=filters,
        report_name="Shift Attendance",
        ignore_prepared_report=True
    )

    columns = attendance_data.get("columns") or []
    result = attendance_data.get("result") or []
    chart = attendance_data.get("chart")
    report_summary = attendance_data.get("report_summary")

    # Define new columns
    new_cols = [
        {
            'label': _('Overtime'),
            'fieldname': 'over_time',
            'fieldtype': 'Data',
            'width': 100
        },
        {
            'label': _('Actual Overtime'),
            'fieldname': 'actual_over_time',
            'fieldtype': 'Data',
            'width': 100
        }
    ]

    # Insert new columns after 'early_exit_hrs'
    inserted = False
    for index, col_val in enumerate(columns):
        # Column definition can be a dict or object
        fieldname = col_val.get("fieldname") if isinstance(col_val, dict) else getattr(col_val, "fieldname", "")
        if fieldname == "early_exit_hrs":
            for offset, col in enumerate(new_cols, start=1):
                columns.insert(index + offset, col)
            inserted = True
            break
    
    if not inserted:
        # Fallback if early_exit_hrs not found
        columns.extend(new_cols)

    # Calculate Overtime
    for row in result:
        # Dictionary access depends on result format (list of dicts or list of lists)
        # Shift Attendance usually returns list of dicts or list of lists.
        # Assuming dicts based on user code provided.
        
        out_time = row.get("out_time")
        shift_end_time = row.get("shift_end")
        shift_start_time = row.get("shift_start")
        working_hours = flt(row.get("working_hours"))
        
        row["over_time"] = 0
        row["actual_over_time"] = 0
        
        if not (out_time and shift_end_time and shift_start_time):
            continue

        out_t = get_time(out_time)
        shift_end_t = get_time(shift_end_time)
        shift_start_t = get_time(shift_start_time)
        
        # Convert to seconds manually or use timedelta
        # User code uses manual conversion:
        def time_to_seconds(t):
            return t.hour * 3600 + t.minute * 60 + t.second

        out_sec = time_to_seconds(out_t)
        shift_end_sec = time_to_seconds(shift_end_t)
        shift_start_sec = time_to_seconds(shift_start_t)

        if out_sec > shift_end_sec:
            overtime_sec = out_sec - shift_end_sec
            row["over_time"] = format_duration(overtime_sec)
        
        # Actual Overtime Logic
        actual_shift_duration_hours = (shift_end_sec - shift_start_sec) / 3600.0
        
        if working_hours > actual_shift_duration_hours:
            actual_ot_hours = working_hours - actual_shift_duration_hours
            if actual_ot_hours > 0:
                row["actual_over_time"] = format_duration(actual_ot_hours * 3600)

    return columns, result, None, chart, report_summary
