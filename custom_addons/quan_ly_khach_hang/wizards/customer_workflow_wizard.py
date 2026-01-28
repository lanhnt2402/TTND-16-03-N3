# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class CustomerContactedWizard(models.TransientModel):
    """Wizard: Đã liên hệ - Nhập thông tin liên hệ"""
    _name = 'customer.contacted.wizard'
    _description = 'Wizard đã liên hệ với khách hàng'

    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        required=True,
        readonly=True
    )

    contact_method = fields.Selection([
        ('call', 'Gọi điện'),
        ('email', 'Gửi email'),
        ('meeting', 'Hẹn gặp'),
        ('visit', 'Thăm khách hàng'),
        ('other', 'Khác')
    ], string='Phương thức liên hệ', required=True, default='call')

    contact_date = fields.Datetime(
        string='Thời gian liên hệ',
        required=True,
        default=fields.Datetime.now
    )

    contact_note = fields.Html(
        string='Nội dung liên hệ',
        required=True,
        help='Mô tả chi tiết nội dung cuộc liên hệ, trao đổi với khách hàng'
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='File đính kèm',
        help='Upload file bằng chứng (email, ghi âm, hình ảnh, v.v.)'
    )

    duration = fields.Float(
        string='Thời lượng (phút)',
        help='Thời gian liên hệ (ví dụ: 15 phút cho cuộc gọi)'
    )

    def action_confirm(self):
        """Xác nhận đã liên hệ"""
        self.ensure_one()
        
        if not self.contact_note or len(self.contact_note.strip()) < 20:
            raise UserError(
                '❌ Vui lòng nhập nội dung liên hệ chi tiết (ít nhất 20 ký tự)!\n\n'
                'Nội dung cần mô tả:\n'
                '• Khách hàng đã trả lời như thế nào?\n'
                '• Nội dung trao đổi chính?\n'
                '• Kết quả cuộc liên hệ?'
            )

        # Tìm employee từ user
        employee = False
        if hasattr(self.env.user, 'employee_ids') and self.env.user.employee_ids:
            employee = self.env.user.employee_ids[0]
        else:
            # Tìm employee theo user_id
            employee = self.env['nhan.su'].search([('user_id', '=', self.env.user.id)], limit=1)
        
        # Tạo tương tác với khách hàng
        interaction_vals = {
            'customer_id': self.customer_id.id,
            'name': f'Liên hệ - {dict(self._fields["contact_method"].selection).get(self.contact_method)}',
            'interaction_type': self.contact_method,
            'interaction_date': self.contact_date,
            'description': self.contact_note,
            'duration': self.duration,
            'employee_id': employee.id if employee else False,
        }
        
        interaction = self.env['khach.hang.interaction'].create(interaction_vals)
        
        # Đính kèm file nếu có
        if self.attachment_ids:
            interaction.attachment_ids = [(6, 0, self.attachment_ids.ids)]
            # Cũng đính kèm vào message
            self.customer_id.message_post(
                body=self.contact_note,
                attachment_ids=self.attachment_ids.ids,
                subject=f'Liên hệ: {dict(self._fields["contact_method"].selection).get(self.contact_method)}'
            )
        else:
            # Nếu không có file, vẫn post message
            self.customer_id.message_post(
                body=self.contact_note,
                subject=f'Liên hệ: {dict(self._fields["contact_method"].selection).get(self.contact_method)}'
            )

        # Chuyển trạng thái
        now = fields.Datetime.now()
        update_vals = {
            'status': 'contacted',
        }
        
        try:
            if hasattr(self.customer_id, 'contacted_by_id'):
                update_vals['contacted_by_id'] = self.env.user.id
            if hasattr(self.customer_id, 'contacted_date'):
                update_vals['contacted_date'] = now
        except Exception:
            pass
        
        self.customer_id.with_context(allow_status_change=True, skip_status_change_message=True).write(update_vals)
        
        self.customer_id.message_post(
            body=f"""
            <h3>📞 Đã liên hệ với khách hàng</h3>
            <p>Khách hàng đã được liên hệ và chuyển sang trạng thái "Đã liên hệ".</p>
            <ul>
                <li><strong>Phương thức:</strong> {dict(self._fields["contact_method"].selection).get(self.contact_method)}</li>
                <li><strong>Thời gian:</strong> {self.contact_date.strftime("%d/%m/%Y %H:%M")}</li>
                <li><strong>Người liên hệ:</strong> {self.env.user.name}</li>
                <li><strong>Nội dung:</strong> {self.contact_note}</li>
                <li><strong>Bằng chứng:</strong> {'Có file đính kèm' if self.attachment_ids else 'Ghi chú chi tiết'}</li>
            </ul>
            """,
            subject="Cập nhật trạng thái: Đã liên hệ"
        )

        # Return action để reload form view và cập nhật statusbar
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'khach.hang',
            'res_id': self.customer_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CustomerQualifiedWizard(models.TransientModel):
    """Wizard: Đủ điều kiện - Nhập đánh giá"""
    _name = 'customer.qualified.wizard'
    _description = 'Wizard đánh giá khách hàng đủ điều kiện'

    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        required=True,
        readonly=True
    )

    qualification_note = fields.Html(
        string='Đánh giá đủ điều kiện',
        required=True,
        help='Mô tả chi tiết lý do khách hàng đủ điều kiện:\n'
             '• Có nhu cầu rõ ràng\n'
             '• Có khả năng chi trả\n'
             '• Có người quyết định\n'
             '• Các yếu tố khác'
    )

    expected_revenue = fields.Monetary(
        string='Giá trị dự kiến',
        currency_field='currency_id',
        help='Giá trị hợp đồng dự kiến'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id
    )

    def action_confirm(self):
        """Xác nhận đủ điều kiện"""
        self.ensure_one()
        
        if not self.qualification_note or len(self.qualification_note.strip()) < 30:
            raise UserError(
                '❌ Vui lòng nhập đánh giá chi tiết (ít nhất 30 ký tự)!\n\n'
                'Đánh giá cần bao gồm:\n'
                '• Nhu cầu của khách hàng\n'
                '• Khả năng chi trả\n'
                '• Người quyết định\n'
                '• Tiềm năng hợp tác'
            )

        # Cập nhật thông tin
        update_vals = {
            'status': 'qualified',
            'status_reason': self.qualification_note,
        }
        
        if self.expected_revenue:
            update_vals['expected_revenue'] = self.expected_revenue
        
        now = fields.Datetime.now()
        try:
            if hasattr(self.customer_id, 'qualified_by_id'):
                update_vals['qualified_by_id'] = self.env.user.id
            if hasattr(self.customer_id, 'qualified_date'):
                update_vals['qualified_date'] = now
        except Exception:
            pass
        
        self.customer_id.with_context(allow_status_change=True, skip_status_change_message=True).write(update_vals)
        
        self.customer_id.message_post(
            body=f"""
            <h3>✅ Khách hàng đủ điều kiện</h3>
            <p>Khách hàng đã được đánh giá và xác nhận đủ điều kiện hợp tác.</p>
            <ul>
                <li><strong>Người đánh giá:</strong> {self.env.user.name}</li>
                <li><strong>Thời gian:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
                <li><strong>Đánh giá:</strong> {self.qualification_note}</li>
                {f'<li><strong>Giá trị dự kiến:</strong> {self.expected_revenue:,.0f} {self.currency_id.symbol}</li>' if self.expected_revenue else ''}
            </ul>
            """,
            subject="Cập nhật trạng thái: Đủ điều kiện"
        )

        # Return action để reload form view và cập nhật statusbar
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'khach.hang',
            'res_id': self.customer_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CustomerProposalWizard(models.TransientModel):
    """Wizard: Gửi đề xuất - Upload file đề xuất"""
    _name = 'customer.proposal.wizard'
    _description = 'Wizard gửi đề xuất cho khách hàng'

    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        required=True,
        readonly=True
    )

    proposal_note = fields.Html(
        string='Ghi chú đề xuất',
        help='Mô tả về đề xuất đã gửi'
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='File đề xuất',
        required=True,
        help='BẮT BUỘC: Upload file đề xuất (Báo giá, Phương án, Hợp đồng nháp) - PDF/Word/Excel'
    )

    proposal_date = fields.Datetime(
        string='Ngày gửi',
        required=True,
        default=fields.Datetime.now
    )

    def action_confirm(self):
        """Xác nhận đã gửi đề xuất"""
        self.ensure_one()
        
        if not self.attachment_ids:
            raise UserError(
                '❌ BẮT BUỘC phải có file đề xuất!\n\n'
                'Vui lòng upload file:\n'
                '• Báo giá (PDF/Word/Excel)\n'
                '• Phương án kỹ thuật (PDF/Word)\n'
                '• Hợp đồng nháp (PDF/Word)'
            )

        # Kiểm tra file hợp lệ
        valid_files = self.attachment_ids.filtered(
            lambda att: att.mimetype and (
                'pdf' in att.mimetype or 
                'word' in att.mimetype or 
                'excel' in att.mimetype or
                'spreadsheet' in att.mimetype or
                att.name and (att.name.endswith('.pdf') or att.name.endswith('.doc') or 
                             att.name.endswith('.docx') or att.name.endswith('.xls') or 
                             att.name.endswith('.xlsx'))
            )
        )
        
        if not valid_files:
            raise UserError(
                '❌ File đề xuất không hợp lệ!\n\n'
                'Chỉ chấp nhận file:\n'
                '• PDF (.pdf)\n'
                '• Word (.doc, .docx)\n'
                '• Excel (.xls, .xlsx)'
            )

        # Post message với file đính kèm
        body = f"""
        <h3>📧 Đã gửi đề xuất cho khách hàng</h3>
        <p>Đề xuất đã được gửi cho khách hàng.</p>
        """
        if self.proposal_note:
            body += f"<p><strong>Ghi chú:</strong> {self.proposal_note}</p>"
        
        self.customer_id.message_post(
            body=body,
            attachment_ids=self.attachment_ids.ids,
            subject='Đã gửi đề xuất'
        )

        # Chuyển trạng thái
        now = fields.Datetime.now()
        update_vals = {
            'status': 'proposal',
        }
        
        try:
            if hasattr(self.customer_id, 'proposal_sent_by_id'):
                update_vals['proposal_sent_by_id'] = self.env.user.id
            if hasattr(self.customer_id, 'proposal_sent_date'):
                update_vals['proposal_sent_date'] = now
        except Exception:
            pass
        
        self.customer_id.with_context(allow_status_change=True, skip_status_change_message=True).write(update_vals)
        
        self.customer_id.message_post(
            body=f"""
            <h3>📧 Đã gửi đề xuất</h3>
            <p>Đề xuất (Báo giá/Phương án/Hợp đồng nháp) đã được gửi cho khách hàng.</p>
            <ul>
                <li><strong>Người gửi:</strong> {self.env.user.name}</li>
                <li><strong>Thời gian:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
                <li><strong>Số file:</strong> {len(self.attachment_ids)}</li>
                <li><strong>Bằng chứng:</strong> File đề xuất đã được đính kèm</li>
            </ul>
            """,
            subject="Cập nhật trạng thái: Đã gửi đề xuất"
        )

        # Return action để reload form view và cập nhật statusbar
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'khach.hang',
            'res_id': self.customer_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CustomerNegotiationWizard(models.TransientModel):
    """Wizard: Đàm phán - Nhập thông tin đàm phán"""
    _name = 'customer.negotiation.wizard'
    _description = 'Wizard bắt đầu đàm phán'

    customer_id = fields.Many2one(
        'khach.hang',
        string='Khách hàng',
        required=True,
        readonly=True
    )

    negotiation_note = fields.Html(
        string='Thông tin đàm phán',
        help='Mô tả về quá trình đàm phán, các điểm đã thảo luận'
    )

    def action_confirm(self):
        """Xác nhận bắt đầu đàm phán"""
        self.ensure_one()

        # Chuyển trạng thái
        now = fields.Datetime.now()
        update_vals = {
            'status': 'negotiation',
        }
        
        try:
            if hasattr(self.customer_id, 'negotiation_started_by_id'):
                update_vals['negotiation_started_by_id'] = self.env.user.id
            if hasattr(self.customer_id, 'negotiation_started_date'):
                update_vals['negotiation_started_date'] = now
        except Exception:
            pass
        
        self.customer_id.with_context(allow_status_change=True, skip_status_change_message=True).write(update_vals)
        
        body = f"""
        <h3>🤝 Bắt đầu đàm phán</h3>
        <p>Bắt đầu đàm phán với khách hàng.</p>
        <ul>
            <li><strong>Người bắt đầu:</strong> {self.env.user.name}</li>
            <li><strong>Thời gian:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
        </ul>
        """
        if self.negotiation_note:
            body += f"<p><strong>Thông tin đàm phán:</strong> {self.negotiation_note}</p>"
        
        self.customer_id.message_post(
            body=body,
            subject="Cập nhật trạng thái: Đàm phán"
        )

        # Return action để reload form view và cập nhật statusbar
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'khach.hang',
            'res_id': self.customer_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

