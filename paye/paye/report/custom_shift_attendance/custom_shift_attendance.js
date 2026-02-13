frappe.query_reports["Custom Shift Attendance"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_start(frappe.datetime.get_today())
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_end(frappe.datetime.get_today())
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee"
        },
        {
            fieldname: "shift",
            label: __("Shift Type"),
            fieldtype: "Link",
            options: "Shift Type"
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department"
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_default("company")
        },
        {
            fieldname: "late_entry",
            label: __("Late Entry"),
            fieldtype: "Check"
        },
        {
            fieldname: "early_exit",
            label: __("Early Exit"),
            fieldtype: "Check"
        },
        {
            fieldname: "consider_grace_period",
            label: __("Consider Grace Period"),
            fieldtype: "Check",
            default: 1
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (
            (column.fieldname === "in_time" && data && data.late_entry) ||
            (column.fieldname === "out_time" && data && data.early_exit)
        ) {
            value = `<span style="color:red!important">${value}</span>`;
        }
        return value;
    }
};
