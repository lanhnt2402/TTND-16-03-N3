# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class TaskStartWizard(models.TransientModel):
    """Wizard: Bắt đầu công việc - Nhập thông tin bắt đầu"""
    _name = 'task.start.wizard'
    _description = 'Wizard bắt đầu công việc'

    task_id = fields.Many2one(
        'cong.viec',
        string='Công việc',
        required=True,
        readonly=True
    )

    start_note = fields.Html(
        string='Ghi chú bắt đầu',
        help='Mô tả kế hoạch thực hiện, phương pháp tiếp cận'
    )

    estimated_completion_date = fields.Datetime(
        string='Dự kiến hoàn thành',
        help='Ngày dự kiến hoàn thành công việc'
    )

    def action_confirm(self):
        """Xác nhận bắt đầu công việc"""
        self.ensure_one()
        
        if self.task_id.state != 'todo':
            raise UserError(f'Chỉ có thể bắt đầu từ trạng thái "Cần làm". Trạng thái hiện tại: {dict(self.task_id._fields["state"].selection).get(self.task_id.state)}')
        
        if not self.task_id.assigned_employee_id:
            raise UserError('Công việc chưa được giao cho nhân viên nào!')

        # Chuyển trạng thái
        now = fields.Datetime.now()
        update_vals = {
            'state': 'in_progress',
            'start_date': fields.Date.today(),
        }
        
        if self.estimated_completion_date:
            update_vals['deadline'] = self.estimated_completion_date
        
        try:
            if hasattr(self.task_id, 'started_by_id'):
                update_vals['started_by_id'] = self.env.user.id
            if hasattr(self.task_id, 'started_date'):
                update_vals['started_date'] = now
        except Exception:
            pass
        
        self.task_id.with_context(allow_state_change=True, skip_state_change_message=True).write(update_vals)
        
        body = f"""
        <h3>🚀 Bắt đầu công việc</h3>
        <p>Nhân viên đã bắt đầu thực hiện công việc.</p>
        <ul>
            <li><strong>Người bắt đầu:</strong> {self.env.user.name}</li>
            <li><strong>Thời gian:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
            <li><strong>Ngày bắt đầu:</strong> {fields.Date.today().strftime("%d/%m/%Y")}</li>
        </ul>
        """
        if self.start_note:
            body += f"<p><strong>Ghi chú:</strong> {self.start_note}</p>"
        if self.estimated_completion_date:
            body += f"<p><strong>Dự kiến hoàn thành:</strong> {self.estimated_completion_date.strftime('%d/%m/%Y %H:%M')}</p>"
        
        self.task_id.message_post(
            body=body,
            subject="Bắt đầu công việc"
        )

        # Return action để reload form view và cập nhật statusbar
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class TaskSubmitReviewWizard(models.TransientModel):
    """Wizard: Gửi duyệt - Nhập kết quả và upload file"""
    _name = 'task.submit.review.wizard'
    _description = 'Wizard gửi duyệt công việc'

    task_id = fields.Many2one(
        'cong.viec',
        string='Công việc',
        required=True,
        readonly=True
    )

    result_note = fields.Html(
        string='Kết quả thực tế',
        required=True,
        help='Mô tả chi tiết kết quả đã làm, những gì đã hoàn thành'
    )

    result_file_ids = fields.Many2many(
        'ir.attachment',
        string='File kết quả',
        required=True,
        help='BẮT BUỘC: Upload file kết quả (Báo cáo, Code, Thiết kế, v.v.)'
    )

    actual_hours = fields.Float(
        string='Giờ thực tế',
        help='Số giờ thực tế đã làm'
    )

    def action_confirm(self):
        """Xác nhận gửi duyệt"""
        self.ensure_one()
        
        if self.task_id.state != 'in_progress':
            raise UserError(f'Chỉ có thể gửi duyệt từ trạng thái "Đang thực hiện". Trạng thái hiện tại: {dict(self.task_id._fields["state"].selection).get(self.task_id.state)}')
        
        # Check permission
        if self.task_id.assigned_employee_id.user_id and self.env.uid != self.task_id.assigned_employee_id.user_id.id and not self.env.user.has_group('base.group_system'):
            raise UserError('Chỉ nhân viên thực hiện mới được phép gửi duyệt!')

        if not self.result_note or len(self.result_note.strip()) < 20:
            raise UserError('❌ Vui lòng nhập kết quả chi tiết (ít nhất 20 ký tự)!')

        if not self.result_file_ids:
            raise UserError(
                '❌ BẮT BUỘC phải có file kết quả!\n\n'
                'Vui lòng upload file kết quả công việc.'
            )

        # Cập nhật kết quả
        update_vals = {
            'state': 'review',
            'result_note': self.result_note,
            'result_file_ids': [(6, 0, self.result_file_ids.ids)],
        }
        
        if self.actual_hours:
            update_vals['actual_hours'] = self.actual_hours
        
        now = fields.Datetime.now()
        try:
            if hasattr(self.task_id, 'submitted_by_id'):
                update_vals['submitted_by_id'] = self.env.user.id
            if hasattr(self.task_id, 'submitted_date'):
                update_vals['submitted_date'] = now
        except Exception:
            pass
        
        self.task_id.with_context(allow_state_change=True, skip_state_change_message=True).write(update_vals)
        
        # Gọi AI đánh giá tiến độ (nếu có)
        try:
            ai_task_service = self.env['ai.task.service']
            task_data = {
                'name': self.task_id.name,
                'description': self.task_id.description or '',
                'start_date': self.task_id.start_date,
                'deadline': self.task_id.deadline,
                'current_date': fields.Date.today(),
                'progress': self.task_id.progress,
                'result_note': self.result_note or '',
                'priority': dict(self.task_id._fields['priority'].selection).get(self.task_id.priority, 'Bình thường'),
                'estimated_hours': self.task_id.estimated_hours,
                'actual_hours': self.actual_hours or self.task_id.actual_hours,
            }
            ai_evaluation_result = ai_task_service.evaluate_task_progress(task_data)
            # Lưu kết quả AI (nếu field tồn tại)
            try:
                self.task_id.write({
                    'ai_progress_completion_level': ai_evaluation_result.get('completion_level', ''),
                    'ai_progress_completion_percentage': ai_evaluation_result.get('completion_percentage', 0),
                })
            except Exception:
                pass
        except Exception as e:
            _logger.error(f"Lỗi AI đánh giá tiến độ: {str(e)[:300]}")

        # Post message
        self.task_id.message_post(
            body=f"""
            <h3>📤 Đã gửi duyệt</h3>
            <p>Công việc đã được gửi lên duyệt.</p>
            <ul>
                <li><strong>Người gửi:</strong> {self.env.user.name}</li>
                <li><strong>Thời gian:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
                <li><strong>Số file:</strong> {len(self.result_file_ids)}</li>
            </ul>
            <h4>Kết quả:</h4>
            <div>{self.result_note}</div>
            """,
            subject="Gửi duyệt công việc"
        )

        # Thông báo cho supervisor
        if self.task_id.supervisor_id and self.task_id.supervisor_id.user_id:
            self.task_id.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.task_id.supervisor_id.user_id.id,
                summary=f'Công việc {self.task_id.name} cần duyệt',
                note=f'Công việc đã được gửi lên duyệt bởi {self.env.user.name}'
            )

        # Return action để reload form view và cập nhật statusbar
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class TaskApproveWizard(models.TransientModel):
    """Wizard: Duyệt công việc - Nhập ghi chú duyệt"""
    _name = 'task.approve.wizard'
    _description = 'Wizard duyệt công việc'

    task_id = fields.Many2one(
        'cong.viec',
        string='Công việc',
        required=True,
        readonly=True
    )

    approval_note = fields.Html(
        string='Ghi chú duyệt',
        help='Đánh giá chất lượng công việc, ghi chú khi duyệt'
    )

    def action_confirm(self):
        """Xác nhận duyệt công việc"""
        self.ensure_one()
        
        if self.task_id.state != 'review':
            raise UserError(f'Chỉ có thể duyệt từ trạng thái "Chờ duyệt". Trạng thái hiện tại: {dict(self.task_id._fields["state"].selection).get(self.task_id.state)}')
        
        # Check permission
        if not self.task_id.supervisor_id or not self.task_id.supervisor_id.user_id:
            raise UserError('Công việc chưa có người giám sát, không thể phê duyệt!')
        
        if self.env.uid != self.task_id.supervisor_id.user_id.id and not self.env.user.has_group('base.group_system'):
            raise UserError('Chỉ người giám sát mới được phép phê duyệt!')
        
        if not self.task_id.result_file_ids:
            raise UserError('❌ Công việc chưa có file kết quả. Vui lòng yêu cầu nhân viên upload file kết quả trước khi duyệt.')

        # Chuyển trạng thái
        now = fields.Datetime.now()
        update_vals = {
            'state': 'done',
            'completed_date': now,
            'progress': 100,
        }
        
        try:
            if hasattr(self.task_id, 'approved_by_id'):
                update_vals['approved_by_id'] = self.env.user.id
            if hasattr(self.task_id, 'approved_date'):
                update_vals['approved_date'] = now
        except Exception:
            pass
        
        # Ghi trạng thái với context cho phép đổi state
        # Dùng sudo() để đảm bảo write được thực thi ngay cả khi có vấn đề về access rights
        task_record = self.task_id.sudo().with_context(
            allow_state_change=True,
            skip_state_change_message=True,
        )
        task_record.write(update_vals)
        
        # Invalidate cache để đảm bảo dữ liệu được refresh
        task_record.invalidate_cache()
        
        # Đọc lại record từ database để verify
        task_record.refresh()
        _logger.info(f"✅ Đã cập nhật trạng thái: task_id={task_record.id}, state={task_record.state}, progress={task_record.progress}")
        
        # Verify state đã được cập nhật
        if task_record.state != 'done':
            _logger.error(f"❌ LỖI: Trạng thái không được cập nhật! state={task_record.state}, expected=done")
            raise UserError(f'Lỗi: Không thể cập nhật trạng thái sang "Hoàn thành". Trạng thái hiện tại: {dict(task_record._fields["state"].selection).get(task_record.state)}')
        
        # Gọi AI đánh giá chất lượng công việc
        try:
            task_record.compute_ai_evaluation()
        except Exception as e:
            _logger.error(f"Lỗi AI đánh giá chất lượng công việc: {str(e)[:300]}")
        
        # Tự động đánh giá hiệu suất nhân viên bằng AI khi công việc hoàn thành
        if task_record.assigned_employee_id:
            try:
                employee = task_record.assigned_employee_id
                _logger.info(f"🤖 Bắt đầu đánh giá AI hiệu suất cho nhân viên: {employee.name}")
                
                # Gọi method đánh giá AI tự động
                if hasattr(employee, '_compute_ai_performance'):
                    # Trigger compute để cập nhật điểm AI
                    employee._compute_ai_performance()
                    _logger.info(f"✅ Đã cập nhật điểm AI hiệu suất cho {employee.name}: {employee.ai_performance_score}/100")
                
                # Nếu có method đánh giá chi tiết, gọi nó
                if hasattr(employee, 'action_ai_evaluate_detailed'):
                    try:
                        # Gọi đánh giá chi tiết (có thể tạo record trong employee.performance.ai)
                        employee.action_ai_evaluate_detailed()
                        _logger.info(f"✅ Đã tạo đánh giá AI chi tiết cho {employee.name}")
                    except Exception as eval_error:
                        _logger.warning(f"⚠️ Không thể tạo đánh giá AI chi tiết: {str(eval_error)[:200]}")
                
            except Exception as emp_error:
                _logger.error(f"❌ Lỗi đánh giá AI hiệu suất nhân viên: {str(emp_error)[:300]}")

        # Post message
        body = f"""
        <h3 style="color: #28a745;">✅ CÔNG VIỆC ĐÃ HOÀN THÀNH</h3>
        <p><strong>Công việc "{task_record.name}"</strong> đã được <strong>{task_record.supervisor_id.name if task_record.supervisor_id else 'N/A'}</strong> duyệt và hoàn thành.</p>
        <ul>
            <li><strong>Người duyệt:</strong> {task_record.supervisor_id.name if task_record.supervisor_id else 'N/A'}</li>
            <li><strong>Ngày hoàn thành:</strong> {now.strftime("%d/%m/%Y %H:%M")}</li>
            <li><strong>Tiến độ:</strong> 100%</li>
        </ul>
        """
        if self.approval_note:
            body += f"<h4>Ghi chú duyệt:</h4><div>{self.approval_note}</div>"
        
        task_record.message_post(
            body=body,
            subject="CÔNG VIỆC ĐÃ HOÀN THÀNH"
        )

        # Thông báo cho nhân viên
        if task_record.assigned_employee_id and task_record.assigned_employee_id.user_id:
            task_record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=task_record.assigned_employee_id.user_id.id,
                summary=f'✅ Công việc {task_record.name} đã được phê duyệt',
                note=f'Người duyệt: {task_record.supervisor_id.name if task_record.supervisor_id else "N/A"}\nNgày hoàn thành: {now.strftime("%d/%m/%Y %H:%M")}'
            )
            
            # Gửi email thông báo
            if task_record.assigned_employee_id.work_email:
                try:
                    email_template = self.env.ref('quan_ly_cong_viec.email_template_task_approved')
                    email_template.send_mail(task_record.id, force_send=True)
                except Exception as e:
                    _logger.error(f"Lỗi gửi email phê duyệt: {str(e)}")

        # Check customer completion
        if task_record.customer_id:
            task_record.customer_id.check_completion_status()

        # Return action để reload form view và cập nhật statusbar
        # Đảm bảo reload bằng cách đọc lại record từ DB với fresh context
        final_task = self.env['cong.viec'].browse(task_record.id)
        final_task.invalidate_cache()
        final_task.refresh()
        _logger.info(f"🔍 Final verify: task_id={final_task.id}, state={final_task.state}, progress={final_task.progress}")
        
        # Force reload form bằng cách return action với target='current'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cong.viec',
            'res_id': task_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

