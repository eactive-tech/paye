import frappe
from erpnext.setup.doctype.company.company import Company
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from frappe.utils import flt

class CustomSalarySlip(SalarySlip):
    def calculate_variable_tax(self, tax_component, has_additional_salary_tax_component=False):
        """
        Override to support 13-month tax distribution for Mauritius PAYE
        """
        # Get custom tax periods from Company or Payroll Settings
        company = frappe.get_cached_value("Company", self.company, ["annual_tax_periods", "country"], as_dict=True)
        
        # For Mauritius, use 13 periods, else use default 12
        tax_periods = 13 # if company and company.get("country") == "Mauritius" else 12
        
        # Call parent method first
        super().calculate_variable_tax(tax_component, has_additional_salary_tax_component)
        
        if not has_additional_salary_tax_component and hasattr(self, 'current_structured_tax_amount'):
            # Recalculate with custom periods
            self.current_structured_tax_amount = (
                self.total_structured_tax_amount - self.previous_total_paid_taxes
            ) / tax_periods
            
            # Recalculate total for this period
            self.current_tax_amount = max(
                0,
                flt(self.current_structured_tax_amount + self.full_tax_on_additional_earnings)
            )
            
            # Update the component based variable tax dictionary
            if tax_component in self._component_based_variable_tax:
                self._component_based_variable_tax[tax_component].update({
                    "current_structured_tax_amount": self.current_structured_tax_amount,
                    "current_tax_amount": self.current_tax_amount,
                })
    
    def get_period_factor(self, *args, **kwargs):
        """
        Override to consider 13 periods instead of 12
        """
        from hrms.payroll.doctype.payroll_period.payroll_period import get_period_factor
        
        period_factor, remaining_sub_periods = get_period_factor(*args, **kwargs)
        
        # Adjust for 13-month system if company is in Mauritius
        company_country = frappe.get_cached_value("Company", self.company, "country")
        if company_country == "Mauritius":
            # Convert 12-month factor to 13-month factor
            payroll_frequency = kwargs.get('payroll_frequency') or self.payroll_frequency
            
            if payroll_frequency == "Monthly":
                # For monthly payroll, there are 13 periods
                total_months = 13
                months_elapsed = self.get_months_elapsed_in_period()
                
                period_factor = months_elapsed / total_months
                remaining_sub_periods = total_months - months_elapsed
        
        return period_factor, remaining_sub_periods
    
    def get_months_elapsed_in_period(self):
        """Calculate months elapsed in the payroll period"""
        from frappe.utils import getdate
        
        payroll_period = self.payroll_period
        if not payroll_period:
            return 0
            
        start_date = getdate(payroll_period.start_date)
        current_date = getdate(self.start_date)
        
        # Calculate months difference
        months_diff = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
        
        # Adjust for partial month
        if current_date.day < start_date.day:
            months_diff -= 1
            
        return max(0, months_diff)