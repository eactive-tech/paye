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