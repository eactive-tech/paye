import frappe
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

class CustomSalarySlip(SalarySlip):
    def compute_current_and_future_taxable_earnings(self):
        super().compute_current_and_future_taxable_earnings()
        
        # Check if feature is enabled for the company
        if frappe.db.get_value("Company", self.company, "enable_13th_month_tax"):
            self.add_13th_month_projection()

    def add_13th_month_projection(self):
        # calculate one month taxable earnings
        one_month_taxable = self.current_taxable_earnings.taxable_earnings
        one_month_taxable_before_exemption = (
            self.current_taxable_earnings.taxable_earnings + 
            self.current_taxable_earnings.amount_exempted_from_income_tax
        )

        # Add to future projections
        self.future_structured_taxable_earnings += one_month_taxable
        self.future_structured_taxable_earnings_before_exemption += one_month_taxable_before_exemption
    
    def validate(self):
        super().validate()
        
        # Import the execute function
        from paye.paye.report.custom_shift_attendance.custom_shift_attendance import execute

        filters = {
            "employee": self.employee,
            "from_date": self.start_date,
            "to_date": self.end_date
        }

        # Get the result without unpacking first
        result = execute(filters)
        
        if isinstance(result, tuple):
            if len(result) == 2:
                columns, data = result
                frappe.log_error("data", data)
            elif len(result) == 3:
                columns, data, message = result
            elif len(result) == 4:
                columns, data, message, chart = result
            else:
                frappe.log_error("unexpected_tuple_length", str(len(result)))
                # Just take the first two if that's what you need
                columns = result[0] if len(result) > 0 else []
                data = result[1] if len(result) > 1 else []
                frappe.log_error("data_from_long_tuple", data)
        elif isinstance(result, dict):
            # If it returns a dictionary
            columns = result.get('columns', [])
            data = result.get('data', [])
        else:
            data = result
            frappe.log_error("data_only", data)
        

        # Check  overtime
        total_ot_pay = 0
        total_late_deduction = 0
        default_shift = frappe.db.get_value("Employee", self.employee, "default_shift")
        ot_sal_comp = frappe.db.get_value("Shift Type", default_shift, "custom_overtime_salary_component") or "Overtime"
        late_sal_comp = frappe.db.get_value("Shift Type", default_shift, "custom_lateness_salary_component") or "Lateness"
        if not ot_sal_comp or not late_sal_comp:
            frappe.throw("Please set the Overtime salary component and Lateness salary component in the shift type")
        for row in data:
            if row.get("over_time") not in ("", None, "00:00:00"):
                ot = self.parse_time_to_seconds(row.get("over_time"))
                if ot > 0:
                    ot_pay = frappe.db.get_value("Shift Type", default_shift, "custom_overtime_pay")
                    total_ot_pay = ot_pay * (ot/3600)
            
            if row.get("late_entry_hrs") not in ("", None, "00:00:00"):
                lt = self.parse_time_to_seconds(row.get("late_entry_hrs"))
                if lt > 0:
                    lt_ded = frappe.db.get_value("Shift Type", default_shift, "custom_lateness_fine")
                    total_late_deduction = lt_ded * (lt/3600)
        
        # Check if Overtime already exists for this period
        existing_overtime = frappe.db.exists("Additional Salary", {
            "employee": self.employee,
            "salary_component": ot_sal_comp,
            "payroll_date": ["between", [self.start_date, self.end_date]],
            "type": "Earning",
            "docstatus": 1
        })
        
        if not existing_overtime:
            add_sal_earning = frappe.get_doc({
                "doctype": "Additional Salary",
                "employee": self.employee,
                "salary_component": ot_sal_comp,
                "amount": total_ot_pay,
                "payroll_date": self.end_date,
                "company": self.company
            })
            add_sal_earning.insert()
            add_sal_earning.save()
            add_sal_earning.submit()
            
            # Manually add to earnings table
            self.append("earnings", {
                "salary_component": ot_sal_comp,
                "amount": total_ot_pay,
                "additional_salary": add_sal_earning.name
            })

        # Check if Lateness already exists for this period    
        existing_lateness = frappe.db.exists("Additional Salary", {
                "employee": self.employee,
                "salary_component": late_sal_comp,
                "payroll_date": ["between", [self.start_date, self.end_date]],
                "type": "Deduction",
                "docstatus": 1
            })
        
        if not existing_lateness:
            add_sal_deduction = frappe.get_doc({
                "doctype": "Additional Salary",
                "employee": self.employee,
                "salary_component": late_sal_comp,
                "amount": total_late_deduction,
                "payroll_date": self.end_date,
                "company": self.company,
                "type": "Deduction"
            })
            add_sal_deduction.insert()
            add_sal_deduction.save()
            add_sal_deduction.submit()
            
            # Manually add to deductions table
            self.append("deductions", {
                "salary_component": late_sal_comp,
                "amount": total_late_deduction,
                "additional_salary": add_sal_deduction.name
            })
            

    def parse_time_to_seconds(self, time_str):
        """
        Parse various time formats to seconds
        Supports: '1h 30m 55s', '01:30:55', '1:30:55', '90m', etc.
        """
        if not time_str or time_str in ['00:00:00', '0', '']:
            return 0
        
        time_str = str(time_str).strip()
        
        # Handle 'HH:MM:SS' format
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
        
        # Handle format like '1h 30m 55s'
        total_seconds = 0
        
        # Extract hours
        import re
        hours_match = re.search(r'(\d+)h', time_str)
        if hours_match:
            total_seconds += int(hours_match.group(1)) * 3600
        
        # Extract minutes
        minutes_match = re.search(r'(\d+)m', time_str)
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60
        
        # Extract seconds
        seconds_match = re.search(r'(\d+)s', time_str)
        if seconds_match:
            total_seconds += int(seconds_match.group(1))
        return total_seconds