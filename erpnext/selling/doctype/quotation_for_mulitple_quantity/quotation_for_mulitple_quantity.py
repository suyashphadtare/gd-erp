# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cstr,cint
from frappe.model.mapper import get_mapped_doc
from frappe import _,msgprint
from erpnext.controllers.selling_controller import SellingController
import json

class QuotationforMulitpleQuantity(Document):
	def validate(self):
		self.check_item_table()
		self.validate_for_items()
		self.check_rates()
		
	def check_item_table(self):
		if not self.get('multiple_quantity_item'):
			frappe.throw(_("Please enter item details"))

	def validate_for_items(self):
		chk_dupl_itm = []
		for d in self.get('multiple_quantity_item'):
			if [cstr(d.item_code),cstr(d.description)] in chk_dupl_itm:
				frappe.throw(_("Item {0} with same description entered twice").format(d.item_code))
			else:
				chk_dupl_itm.append([cstr(d.item_code),cstr(d.description)])

	def check_rates(self):
                for d in self.get('multiple_quantity_item'):
                        if 0 in [d.r_qty1,d.r_qty2,d.r_qty3]:
                                frappe.throw(_("Please enter rates for Item {0} at row {1}").format(d.item_code,d.idx))

	def set_label(self):
		label=['r_qty1','r_qty2','r_qty3']
		label_dict={}
		i=0	
		qty_data=frappe.db.sql("select from_quantity, to_quantity from `tabQuantity Range` where parent='Range Master'",as_dict=1)
		if qty_data:
			for qty in qty_data:
				if qty['to_quantity']:
					label_dict.setdefault(label[i],cstr(qty['from_quantity'])+'-'+cstr(qty['to_quantity']))
				else:
					label_dict.setdefault(label[i],'>'+cstr(qty['from_quantity']))
				i=i+1
			self.quantity_lable=json.dumps(label_dict)
			self.rq1='Quantity '+label_dict.get('r_qty1')
			self.rq2='Quantity '+label_dict.get('r_qty2')
			self.rq3='Quantity '+label_dict.get('r_qty3')
		return "Done"

	def get_item_details(self,item_code):
		self.validate_customer()
		multiple_qty=eval(self.quantity_lable)
		for d in self.get('multiple_quantity_item'):
			if d.item_code==item_code:
				d.item_name=frappe.db.get_value('Item',item_code,'item_name')
				d.description=frappe.db.get_value('Item',item_code,'description')
				parent=frappe.db.get_value('Item Price',{'item_code':item_code,'price_list':self.selling_price_list},'name')
				d.r_qty1=frappe.db.get_value('Price List Quantity',{'parent':parent,'range_qty':multiple_qty.get('r_qty1'),'customer_code':self.customer},'rate')
				d.r_qty2=frappe.db.get_value('Price List Quantity',{'parent':parent,'range_qty':multiple_qty.get('r_qty2'),'customer_code':self.customer},'rate')
				d.r_qty3=frappe.db.get_value('Price List Quantity',{'parent':parent,'range_qty':multiple_qty.get('r_qty3'),'customer_code':self.customer},'rate')
		return "Done"

	def validate_customer(self):
		if not self.customer:
			msgprint(_("Please specify: Customer Code. It is needed to fetch Item Details. Please refresh page"),raise_exception=1)

	def on_submit(self):
		self.validate_customer()
		self.create_item_price_list()

	def create_item_price_list(self):
		for data in self.get('multiple_quantity_item'):
			self.sort_quantity(data.item_code,{'r_qty1':data.r_qty1,'r_qty2':data.r_qty2,'r_qty3':data.r_qty3})

	def sort_quantity(self,item_code,rate):
		#rate=sorted(rate)
		if rate:
			for qty in rate:
				self.add_price(qty,rate[qty],item_code)

	def add_price(self,qty,rate,item_code):
		multiple_qty=eval(self.quantity_lable)
		if '-' in multiple_qty[qty]:
			value=multiple_qty[qty].split('-')
			for r in range(cint(value[0]),cint(value[1])+1):
				self.create_price_list(r,multiple_qty[qty],item_code,rate)
		else:
			value=multiple_qty[qty].split('>')
			self.create_price_list(value[1],multiple_qty[qty],item_code,rate)

	def create_price_list(self,qty,range_qty,item_code,rate):
		check=frappe.db.sql("""select b.name from `tabItem Price` as a,`tabPrice List Quantity` as b 
			where b.parent=a.name and a.price_list='%s' and a.item_code='%s' 
			and b.customer_code='%s' and quantity='%s' and range_qty='%s'"""%(self.selling_price_list,item_code,self.customer,qty,range_qty),as_list=1)
		if check:
			frappe.db.sql("update `tabPrice List Quantity` set rate='%s',parentfield='item',parenttype='Item Price' where range_qty='%s' and name='%s'"%(rate,range_qty,check[0][0]))
		else:
			parent=frappe.db.get_value('Item Price',{'item_code':item_code,'price_list':self.selling_price_list},'name')
			if not parent:
				parent=self.create_new_price_list(item_code,self.selling_price_list)
			pl=frappe.new_doc('Price List Quantity')
			pl.parent=parent
			pl.customer_code=self.customer
			pl.quantity=qty
			pl.rate=cstr(rate)
			pl.parentfield='item'
			pl.parenttype='Item Price'
			pl.range_qty=range_qty
			pl.save(ignore_permissions=True)

	def create_new_price_list(self,item_code,price_list):
		npl=frappe.new_doc('Item Price')
		npl.price_list=price_list
		npl.selling=1
		npl.item_code=item_code
		npl.item_name=frappe.db.get_value('Item',item_code,'item_name')
		npl.description=frappe.db.get_value('Item',item_code,'description')
		npl.save(ignore_permissions=True)
		return npl.name

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	return _make_sales_order(source_name, target_doc)

def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name

		target.ignore_permissions = ignore_permissions
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	doclist = get_mapped_doc("Quotation for Mulitple Quantity", source_name, {
			"Quotation for Mulitple Quantity": {
				"doctype": "Sales Order",
				"validation": {
					"docstatus": ["=", 1]
				}
			},
                        "Multiple Quantity Item": {
                                "doctype": "Sales Order Item"                    
                        },
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"add_if_empty": True
			},
			"Sales Team": {
				"doctype": "Sales Team",
				"add_if_empty": True
			}
		}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

	# postprocess: fetch shipping address, set missing values

	return doclist

def _make_customer(source_name, ignore_permissions=False):
	quotation = frappe.db.get_value("Quotation", source_name, ["lead", "order_type"])
	if quotation and quotation[0]:
		lead_name = quotation[0]
		customer_name = frappe.db.get_value("Customer", {"lead_name": lead_name},
			["name", "customer_name"], as_dict=True)
		if not customer_name:
			from erpnext.selling.doctype.lead.lead import _make_customer
			customer_doclist = _make_customer(lead_name, ignore_permissions=ignore_permissions)
			customer = frappe.get_doc(customer_doclist)
			customer.ignore_permissions = ignore_permissions
			if quotation[1] == "Shopping Cart":
				customer.customer_group = frappe.db.get_value("Shopping Cart Settings", None,
					"default_customer_group")

			try:
				customer.insert()
				return customer
			except frappe.NameError:
				if frappe.defaults.get_global_default('cust_master_name') == "Customer Name":
					customer.run_method("autoname")
					customer.name += "-" + lead_name
					customer.insert()
					return customer
				else:
					raise
			except frappe.MandatoryError:
				from frappe.utils import get_url_to_form
				frappe.throw(_("Please create Customer from Lead {0}").format(lead_name))
		else:
			return customer_name