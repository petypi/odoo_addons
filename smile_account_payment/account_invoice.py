# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2010 Smile (<http://www.smile.fr>). All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import orm, osv, fields
from tools.translate import _

class AccountInvoice(osv.osv):
    _inherit = 'account.invoice'

    _columns = {
        'payment_mode_id': fields.many2one('payment.mode', 'Payment mode'),
    }

    def _get_partner_move_line_id(self, cr, uid, invoice, context=None):
        assert isinstance(invoice, orm.browse_record), "invoice argument must be a browse record"
        for move_line in invoice.move_lines:
            if move_line.account_id == invoice.account_id:
                return move_line.id
        return True

    def _get_invoices_by_payment_mode_and_partner(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        invoices_by_payment_mode_and_partner = {}
        for invoice in self.browse(cr, uid, ids, context):
            if invoice.state != 'open':
                raise osv.except_osv(_('Error'), _('You cannot create a payment order for a invoice not validated or already paid!'))
            if invoice.type not in ('in_invoice', 'out_refund'):
                raise osv.except_osv(_('Error'), _('You can create a payment order only for a supplier invoice or a customer credit note!'))
            if not invoice.payment_mode_id:
                raise osv.except_osv(_('Error'), _('Please indicate a payment mode in the invoice %s!') % invoice.name)
            invoices_by_payment_mode_and_partner.setdefault(invoice.payment_mode_id.id, {}).setdefault(invoice.partner_id.id, []).append(invoice)
        return invoices_by_payment_mode_and_partner

    def _get_voucher_lines_from_invoices(self, cr, uid, invoices, context=None):
        assert isinstance(invoices, orm.browse_record_list), 'invoices argument must be a browse record list'
        res = []
        for invoice in invoices:
            res.append({
                'name': invoice.number,
                'type': 'cr',
                'move_line_id': self._get_partner_move_line_id(cr, uid, invoice, context),
                'account_id': invoice.account_id.id,
                'amount': invoice.residual,
                'currency_id': invoice.currency_id.id,
            })
        return res

    def create_payment(self, cr, uid, ids, context=None):
        payment_mode_obj = self.pool.get('payment.mode')
        voucher_obj = self.pool.get('account.voucher')
        invoices_by_payment_mode_and_partner = self._get_invoices_by_payment_mode_and_partner(cr, uid, ids, context)
        for payment_mode_id in invoices_by_payment_mode_and_partner:
            payment_id = payment_mode_obj.get_payment_id(cr, uid, payment_mode_id, context)
            invoices_by_partner = invoices_by_payment_mode_and_partner[payment_mode_id]
            for partner_id in invoices_by_partner:
                voucher_id = voucher_obj.get_voucher_id(cr, uid, payment_id, partner_id, context)
                voucher_obj.write(cr, uid, voucher_id, {
                    'line_ids': [(0, 0, vals) for vals in self._get_voucher_lines_from_invoices(cr, uid, invoices_by_partner[partner_id], context)],
                    'amount': sum([invoice.amount_total for invoice in invoices_by_partner[partner_id]], 0.0),
                }, context)
        return True

    def onchange_company_id(self, cr, uid, ids, company_id, part_id, type_, invoice_line, currency_id, context=None):
        res = super(AccountInvoice, self).onchange_company_id(cr, uid, ids, company_id, part_id, type_, invoice_line, currency_id)
        res.setdefault('value', {})['payment_mode_id'] = False
        if company_id:
            res['value']['payment_mode_id'] = self.pool.get('res.company').read(cr, uid, company_id, ['default_payment_mode_id'], context, '_classic_write')['default_payment_mode_id']
        return res
AccountInvoice()
