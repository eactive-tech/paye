import frappe
from frappe import _
from frappe.utils import getdate, add_days, get_time, format_duration, flt
from datetime import datetime, timedelta

def execute(filters=None):
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            'label': _('Employee'),
            'fieldname': 'employee',
            'fieldtype': 'Link',
            'options': 'Employee',
            'width': 150
        },
        {
            'label': _('Employee Name'),
            'fieldname': 'employee_name',
            'fieldtype': 'Data',
            'width': 150
        },
        {
            'label': _('Department'),
            'fieldname': 'department',
            'fieldtype': 'Link',
            'options': 'Department',
            'width': 150
        },
        {
            'label': _('Company'),
            'fieldname': 'company',
            'fieldtype': 'Link',
            'options': 'Company',
            'width': 150
        },
        {
            'label': _('Attendance Date'),
            'fieldname': 'attendance_date',
            'fieldtype': 'Date',
            'width': 120
        },
        {
            'label': _('Shift'),
            'fieldname': 'shift',
            'fieldtype': 'Link',
            'options': 'Shift Type',
            'width': 120
        },
        {
            'label': _('Shift Start'),
            'fieldname': 'shift_start',
            'fieldtype': 'Data',
            'width': 100
        },
        {
            'label': _('Shift End'),
            'fieldname': 'shift_end',
            'fieldtype': 'Data',
            'width': 100
        },
        {
            'label': _('First Checkin'),
            'fieldname': 'first_checkin',
            'fieldtype': 'Datetime',
            'width': 150
        },
        {
            'label': _('Last Checkin'),
            'fieldname': 'last_checkin',
            'fieldtype': 'Datetime',
            'width': 150
        },
        {
            'label': _('In Time'),
            'fieldname': 'in_time',
            'fieldtype': 'Time',
            'width': 100
        },
        {
            'label': _('Out Time'),
            'fieldname': 'out_time',
            'fieldtype': 'Time',
            'width': 100
        },
        {
            'label': _('Working Hours'),
            'fieldname': 'working_hours',
            'fieldtype': 'Data',
            'width': 120
        },
        {
            'label': _('Late Entry By'),
            'fieldname': 'late_entry_hrs',
            'fieldtype': 'Data',
            'width': 120
        },
        {
            'label': _('Early Exit By'),
            'fieldname': 'early_exit_hrs',
            'fieldtype': 'Data',
            'width': 120
        },
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
        },
        {
            'label': _('Status'),
            'fieldname': 'status',
            'fieldtype': 'Data',
            'width': 100
        },
        {
            'label': _('Attendance ID'),
            'fieldname': 'attendance_id',
            'fieldtype': 'Link',
            'options': 'Attendance',
            'width': 150
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    # Main SQL query to get attendance data directly from Employee Checkin
    query = """
        SELECT 
            emp.name AS employee,
            emp.employee_name,
            emp.department,
            emp.company,
            DATE(ci.time) AS attendance_date,
            ci.shift AS shift,
            att.name AS attendance_id,
            att.status AS attendance_status,
            MIN(ci.time) AS first_checkin,
            MAX(ci.time) AS last_checkin,
            TIME(MIN(ci.time)) AS in_time,
            TIME(MAX(ci.time)) AS out_time,
            -- Calculate working hours in seconds
            TIMESTAMPDIFF(SECOND, MIN(ci.time), MAX(ci.time)) AS working_seconds,
            -- Shift timings from shift type
            st.start_time AS shift_start_time,
            st.end_time AS shift_end_time,
            st.name AS shift_type
        FROM 
            `tabEmployee Checkin` ci
        INNER JOIN 
            `tabEmployee` emp ON ci.employee = emp.name
        LEFT JOIN 
            `tabAttendance` att ON att.employee = emp.name 
                AND att.attendance_date = DATE(ci.time)
        LEFT JOIN 
            `tabShift Type` st ON st.name = ci.shift
        WHERE 
            ci.time BETWEEN %(from_date)s AND %(to_date)s + INTERVAL 1 DAY
            AND ci.skip_auto_attendance = 0
            {conditions}
        GROUP BY 
            emp.name, DATE(ci.time)
        ORDER BY 
            attendance_date DESC, emp.employee_name
    """.format(conditions=conditions)

    result = frappe.db.sql(query, filters, as_dict=1)
    
    # Process the data
    for row in result:
        process_row_data(row, filters)
    
    return result

def get_conditions(filters):
    conditions = []
    
    if filters.get("employee"):
        conditions.append("emp.name = %(employee)s")
    
    if filters.get("shift"):
        conditions.append("ci.shift = %(shift)s")
    
    if filters.get("department"):
        conditions.append("emp.department = %(department)s")
    
    if filters.get("company"):
        conditions.append("emp.company = %(company)s")
    
    # For late entry filter
    if filters.get("late_entry"):
        conditions.append("""
            TIME(MIN(ci.time)) > ADDTIME(
                st.start_time,
                SEC_TO_TIME(COALESCE(st.late_entry_grace_period, 0) * 60)
            )
        """)
    
    # For early exit filter
    if filters.get("early_exit"):
        conditions.append("""
            TIME(MAX(ci.time)) < SUBTIME(
                st.end_time,
                SEC_TO_TIME(COALESCE(st.early_exit_grace_period, 0) * 60)
            )
        """)
    
    return " AND " + " AND ".join(conditions) if conditions else ""

def process_row_data(row, filters):
    # Initialize grace period variables
    late_entry_grace_period = 0
    early_exit_grace_period = 0
    
    # Get shift type details with both grace periods
    if row.get('shift_type'):
        shift_doc = frappe.db.get_value('Shift Type', row['shift_type'], 
                                       ['start_time', 'end_time', 'late_entry_grace_period', 'early_exit_grace_period'], as_dict=1)
        if shift_doc:
            shift_start = shift_doc.start_time
            shift_end = shift_doc.end_time
            late_entry_grace_period = shift_doc.late_entry_grace_period or 0
            early_exit_grace_period = shift_doc.early_exit_grace_period or 0
    else:
        # Use values from row if shift_doc not available
        shift_start = row.get('shift_start_time')
        shift_end = row.get('shift_end_time')
    
    # Convert to time objects
    shift_start_time = get_time(shift_start) if shift_start else None
    shift_end_time = get_time(shift_end) if shift_end else None
    
    row['shift_start'] = shift_start_time.strftime('%H:%M:%S') if shift_start_time else ''
    row['shift_end'] = shift_end_time.strftime('%H:%M:%S') if shift_end_time else ''
    
    # Set status based on attendance
    row['status'] = row.get('attendance_status', 'Not Marked')
    
    # Calculate working hours
    if row.get('working_seconds'):
        row['working_hours'] = format_duration(row['working_seconds'])
        
        # Calculate late entry and early exit
        if shift_start_time and shift_end_time:
            # Consider grace period if enabled
            consider_grace = filters.get('consider_grace_period', 1)
            
            # Convert to seconds for comparison
            def get_seconds(value):
                if value is None:
                    return 0
                elif hasattr(value, 'seconds'):  # It's a timedelta
                    return value.seconds
                elif hasattr(value, 'hour'):  # It's a time object
                    return value.hour * 3600 + value.minute * 60 + value.second
                else:
                    # Try to parse string
                    try:
                        t = get_time(value)
                        return t.hour * 3600 + t.minute * 60 + t.second
                    except:
                        return 0
            
            in_seconds = get_seconds(row.get('in_time'))
            out_seconds = get_seconds(row.get('out_time'))
            shift_start_seconds = get_seconds(shift_start_time)
            shift_end_seconds = get_seconds(shift_end_time)
            
            # Check for late entry
            if row.get('in_time'):
                if consider_grace:
                    late_threshold = shift_start_seconds + (late_entry_grace_period * 60)
                else:
                    late_threshold = shift_start_seconds
                
                if in_seconds > late_threshold:
                    late_seconds = in_seconds - shift_start_seconds
                    if late_seconds > 0:
                        row['late_entry_hrs'] = format_duration(late_seconds)
                    else:
                        row['late_entry_hrs'] = '00:00:00'
                else:
                    row['late_entry_hrs'] = '00:00:00'
            
            # Check for early exit
            if row.get('out_time'):
                if consider_grace:
                    early_threshold = shift_end_seconds - (early_exit_grace_period * 60)
                else:
                    early_threshold = shift_end_seconds
                
                if out_seconds < early_threshold:
                    early_seconds = shift_end_seconds - out_seconds
                    if early_seconds > 0:
                        row['early_exit_hrs'] = format_duration(early_seconds)
                    else:
                        row['early_exit_hrs'] = '00:00:00'
                else:
                    row['early_exit_hrs'] = '00:00:00'
            
            # Calculate overtime
            # Regular overtime (beyond shift end)
            if row.get('out_time') and shift_end_seconds:
                if out_seconds > shift_end_seconds:
                    overtime_seconds = out_seconds - shift_end_seconds
                    if overtime_seconds > 0:
                        row['over_time'] = format_duration(overtime_seconds)
                    else:
                        row['over_time'] = '00:00:00'
                else:
                    row['over_time'] = '00:00:00'
            
            # Actual overtime (based on shift duration)
            if shift_start_seconds and shift_end_seconds:
                shift_duration_seconds = shift_end_seconds - shift_start_seconds
                working_hours_float = row.get('working_seconds', 0)
                
                if working_hours_float > shift_duration_seconds:
                    actual_ot_seconds = working_hours_float - shift_duration_seconds
                    if actual_ot_seconds > 0:
                        row['actual_over_time'] = format_duration(actual_ot_seconds)
                    else:
                        row['actual_over_time'] = '00:00:00'
                else:
                    row['actual_over_time'] = '00:00:00'
        else:
            row['late_entry_hrs'] = '00:00:00'
            row['early_exit_hrs'] = '00:00:00'
            row['over_time'] = '00:00:00'
            row['actual_over_time'] = '00:00:00'
    else:
        row['working_hours'] = '00:00:00'
        row['late_entry_hrs'] = '00:00:00'
        row['early_exit_hrs'] = '00:00:00'
        row['over_time'] = '00:00:00'
        row['actual_over_time'] = '00:00:00'
    
    # Format times - convert to string if needed
    if row.get('in_time'):
        if hasattr(row['in_time'], 'strftime'):  # It's a time object
            row['in_time'] = row['in_time'].strftime('%H:%M:%S')
        elif hasattr(row['in_time'], 'seconds'):  # It's a timedelta
            seconds = row['in_time'].seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            row['in_time'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    if row.get('out_time'):
        if hasattr(row['out_time'], 'strftime'):  # It's a time object
            row['out_time'] = row['out_time'].strftime('%H:%M:%S')
        elif hasattr(row['out_time'], 'seconds'):  # It's a timedelta
            seconds = row['out_time'].seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            row['out_time'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"