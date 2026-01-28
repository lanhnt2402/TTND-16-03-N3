# -*- coding: utf-8 -*-

import logging
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DataCleanupWizard(models.TransientModel):
    _name = 'data.cleanup.wizard'
    _description = 'Dọn dữ liệu cũ'

    purge_employees = fields.Boolean(
        string='Xóa nhân viên',
        default=True
    )
    purge_customers = fields.Boolean(
        string='Xóa khách hàng',
        default=True
    )
    purge_tasks = fields.Boolean(
        string='Xóa công việc',
        default=True
    )
    purge_interactions = fields.Boolean(
        string='Xóa tương tác khách hàng',
        default=True
    )
    reset_sequences = fields.Boolean(
        string='Reset mã KH/CV theo năm (YYYY)',
        default=True
    )
    confirm = fields.Boolean(
        string='Tôi hiểu thao tác này không thể hoàn tác',
        default=False
    )

    def action_purge(self):
        self.ensure_one()
        if not self.env.user.has_group('quan_ly_nhan_su.group_nhan_su_admin'):
            raise UserError('Chỉ Admin mới được phép dọn dữ liệu.')
        if not self.confirm:
            raise UserError('Vui lòng xác nhận trước khi xóa dữ liệu.')

        env = self.env.sudo().with_context(force_unlink=True)

        if self.purge_tasks:
            tasks = env['cong.viec'].search([])
            _logger.info("Purge tasks: %s", len(tasks))
            tasks.unlink()

        if self.purge_interactions:
            interactions = env['khach.hang.interaction'].search([])
            _logger.info("Purge interactions: %s", len(interactions))
            interactions.unlink()

        if self.purge_customers:
            customers = env['khach.hang'].search([])
            _logger.info("Purge customers: %s", len(customers))
            customers.unlink()

        if self.purge_employees:
            employees = env['nhan.su'].search([])
            _logger.info("Purge employees: %s", len(employees))
            employees.unlink()

        if self.reset_sequences:
            self._reset_sequences(env)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Hoàn tất',
                'message': 'Đã dọn dữ liệu và reset mã thành công.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _reset_sequences(self, env):
        sequences = env['ir.sequence'].search([
            ('code', 'in', ['khach.hang', 'cong.viec'])
        ])
        for seq in sequences:
            values = {'number_next': 1}
            if seq.code == 'khach.hang':
                values.update({'prefix': 'KH-%(year)s-', 'padding': 4})
            elif seq.code == 'cong.viec':
                values.update({'prefix': 'CV-%(year)s-', 'padding': 5})
            seq.write(values)

