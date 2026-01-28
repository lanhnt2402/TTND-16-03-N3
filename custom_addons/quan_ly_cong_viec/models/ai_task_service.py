# -*- coding: utf-8 -*-
"""
AI Task Service - Đánh giá báo cáo công việc bằng AI
Tích hợp Google Gemini 2.5 để phân tích báo cáo, so sánh yêu cầu vs kết quả
"""

import logging
import google.genai as genai
from odoo import api, models, _
from odoo.exceptions import UserError
import json
import re
import base64
import PyPDF2
import docx
from io import BytesIO

_logger = logging.getLogger(__name__)


class AITaskService(models.AbstractModel):
    """Service AI chuyên cho đánh giá công việc"""
    
    _name = 'ai.task.service'
    _description = 'AI Task Evaluation Service'
    
    # Fallback API keys (sẽ được override bởi config parameter)
    DEFAULT_API_KEYS = [
        "AIzaSyApIoPs91hDIor3pA3PjlNPoVV0nzPeMl0",
        "AIzaSyAEKaLFrnUbHQ8jbGu23jk5hGop2UJMQbw",
        "AIzaSyAb5Fxtzg0AlFrWv4I6SKE34hr10v8OY-Y",
        "AIzaSyAZ887ml8jI01uAwnuN7DCduczUg9zsyDM",
        "AIzaSyBEALAyUVpOGbsFKkM2SX5LdR2n4QWOhcg"
    ]
    
    # Dùng ir.config_parameter để lưu index hiện tại (tránh lỗi attribute read-only trên model record)
    CURRENT_KEY_INDEX_PARAM = 'quan_ly_cong_viec.current_key_index'
    
    # ==================== HELPER METHODS ====================
    
    @api.model
    def _get_api_keys(self):
        """
        Lấy API keys từ config parameter hoặc fallback về default
        Format trong config: key1,key2,key3,key4,key5
        """
        try:
            config_param = self.env['ir.config_parameter'].sudo().get_param(
                'quan_ly_cong_viec.gemini_api_keys', ''
            )
            if config_param:
                keys = [k.strip() for k in config_param.split(',') if k.strip()]
                if len(keys) >= 5:
                    _logger.info("✅ Using API keys from config parameter")
                    return keys
        except Exception as e:
            _logger.warning(f"⚠️ Could not load API keys from config: {str(e)}")
        
        _logger.info("⚠️ Using default API keys (fallback)")
        return self.DEFAULT_API_KEYS
    
    @api.model
    def _get_current_key_index(self):
        """Lấy current key index từ config parameter (default 0)."""
        val = self.env['ir.config_parameter'].sudo().get_param(self.CURRENT_KEY_INDEX_PARAM, '0')
        try:
            return int(val)
        except Exception:
            return 0

    @api.model
    def _set_current_key_index(self, idx):
        """Set current key index vào config parameter."""
        self.env['ir.config_parameter'].sudo().set_param(self.CURRENT_KEY_INDEX_PARAM, str(int(idx)))

    @api.model
    def _get_next_api_key(self):
        """Lấy API key tiếp theo"""
        api_keys = self._get_api_keys()
        idx = self._get_current_key_index()
        if idx >= len(api_keys):
            idx = 0
            self._set_current_key_index(idx)
        return api_keys[idx]

    @api.model
    def _rotate_api_key(self):
        """Chuyển sang API key tiếp theo"""
        api_keys = self._get_api_keys()
        idx = (self._get_current_key_index() + 1) % max(len(api_keys), 1)
        self._set_current_key_index(idx)
        return idx
    
    @api.model
    def _call_gemini_with_retry(self, prompt, max_retries=5):
        """
        Call Gemini 2.5 API với retry và rotation
        Sử dụng Google GenAI SDK mới
        """
        for attempt in range(max_retries):
            try:
                api_key = self._get_next_api_key()
                
                # Khởi tạo client với API key
                client = genai.Client(api_key=api_key)
                
                # Gọi API với model gemini-2.5-flash
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                
                if response and response.text:
                    _logger.info(f"✅ Gemini 2.5 API success (attempt {attempt + 1})")
                    return response.text
                else:
                    raise Exception("Empty response from Gemini")
                    
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check quota errors
                if any(x in error_msg for x in ['quota', 'resource_exhausted', '429', 'rate limit']):
                    _logger.warning(f"⚠️ API Key quota exceeded - rotating key")
                    self._rotate_api_key()
                    if attempt < max_retries - 1:
                        _logger.info(f"🔄 Retrying with next API key...")
                        continue
                
                # Other errors
                _logger.error(f"❌ Gemini API error (attempt {attempt + 1}): {str(e)[:200]}")
                
                if attempt < max_retries - 1:
                    self._rotate_api_key()
                    continue
                else:
                    raise UserError(f"Tất cả {max_retries} API keys đều thất bại. Lỗi: {str(e)[:200]}")
        
        raise UserError("Không thể kết nối Gemini AI sau nhiều lần thử")
    
    @api.model
    def _clean_json_response(self, text):
        """Loại bỏ markdown và format JSON"""
        text = text.strip()
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        return text.strip()
    
    @api.model
    def _extract_text_from_file(self, file_data, filename):
        """
        Trích xuất text từ file báo cáo (PDF, DOCX, TXT)
        
        Args:
            file_data: Binary data của file (base64 decoded)
            filename: Tên file
        
        Returns:
            str: Nội dung text
        """
        try:
            file_lower = filename.lower()
            
            # PDF
            if file_lower.endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_data))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
            
            # DOCX
            elif file_lower.endswith('.docx'):
                doc = docx.Document(BytesIO(file_data))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text.strip()
            
            # TXT
            elif file_lower.endswith('.txt'):
                return file_data.decode('utf-8', errors='ignore').strip()
            
            else:
                return ""
                
        except Exception as e:
            _logger.error(f"Lỗi trích xuất file {filename}: {str(e)}")
            return ""
    
    # ==================== API 1: ĐÁNH GIÁ BÁO CÁO CÔNG VIỆC ====================
    
    @api.model
    def evaluate_task_report(self, task_data, report_files=None):
        """
        API 1: Đánh giá báo cáo công việc - So sánh yêu cầu vs kết quả
        
        Đây là API QUAN TRỌNG NHẤT - Phân tích chi tiết:
        1. Đọc yêu cầu công việc ban đầu
        2. Đọc báo cáo kết quả (text + file đính kèm)
        3. So sánh từng điểm yêu cầu với kết quả
        4. Đánh giá mức độ hoàn thành (%)
        5. Liệt kê: Đã làm gì / Chưa làm gì / Làm vượt mức
        
        Args:
            task_data (dict): {
                'task_code': str,
                'name': str,
                'requirement': str (HTML),
                'acceptance_criteria': str,
                'deliverable': str,
                'result_note': str (HTML),
                'estimated_hours': float,
                'actual_hours': float,
                'deadline': date,
                'completed_date': datetime,
                'is_overdue': bool
            }
            report_files (list): [{
                'filename': str,
                'file_data': binary (base64 decoded)
            }]
        
        Returns:
            dict: {
                'overall_completion': float (0-100),
                'requirement_match_score': float (0-100),
                'quality_score': float (0-100),
                'time_efficiency_score': float (0-100),
                'deadline_score': float (0-100),
                'completed_items': str (danh sách các việc đã làm),
                'incomplete_items': str (danh sách các việc chưa làm),
                'exceeded_items': str (danh sách các việc làm vượt mức),
                'strengths': str,
                'weaknesses': str,
                'recommendations': str,
                'detailed_analysis': str,
                'grade': str (A+/A/B+/B/C+/C/D/F)
            }
        """
        try:
            # Chuẩn bị dữ liệu
            requirement_text = re.sub(r'<[^>]+>', '', task_data.get('requirement', ''))
            result_text = re.sub(r'<[^>]+>', '', task_data.get('result_note', ''))
            
            # Trích xuất text từ file báo cáo
            report_content = ""
            if report_files:
                for file_info in report_files:
                    extracted = self._extract_text_from_file(
                        file_info.get('file_data'),
                        file_info.get('filename')
                    )
                    if extracted:
                        report_content += f"\n\n--- {file_info.get('filename')} ---\n{extracted}"
            
            # Tính toán metrics cơ bản
            time_variance = 0
            if task_data.get('estimated_hours', 0) > 0:
                time_variance = ((task_data.get('actual_hours', 0) - task_data.get('estimated_hours', 0)) 
                                / task_data.get('estimated_hours', 0) * 100)
            
            # Xây dựng prompt chi tiết và chuyên nghiệp
            prompt = f"""
Bạn là chuyên gia đánh giá chất lượng công việc với nhiều năm kinh nghiệm. Nhiệm vụ của bạn là PHÂN TÍCH KỸ LƯỠNG và SO SÁNH CHI TIẾT giữa YÊU CẦU BAN ĐẦU và KẾT QUẢ THỰC TẾ để đưa ra đánh giá khách quan, chính xác.

═══════════════════════════════════════════════════════════════
📋 THÔNG TIN CÔNG VIỆC
═══════════════════════════════════════════════════════════════
- Mã công việc: {task_data.get('task_code')}
- Tên công việc: {task_data.get('name')}
- Sản phẩm bàn giao: {task_data.get('deliverable', 'N/A')}

═══════════════════════════════════════════════════════════════
📝 YÊU CẦU BAN ĐẦU (Từ khách hàng/nhà quản lý)
═══════════════════════════════════════════════════════════════
{requirement_text[:2500]}

═══════════════════════════════════════════════════════════════
✅ TIÊU CHÍ NGHIỆM THU (Acceptance Criteria)
═══════════════════════════════════════════════════════════════
{task_data.get('acceptance_criteria', 'Không có tiêu chí cụ thể')[:1200]}

═══════════════════════════════════════════════════════════════
📊 KẾT QUẢ THỰC TẾ (Báo cáo từ nhân viên)
═══════════════════════════════════════════════════════════════
{result_text[:2500]}

═══════════════════════════════════════════════════════════════
📎 NỘI DUNG TỪ FILE BÁO CÁO ĐÍNH KÈM
═══════════════════════════════════════════════════════════════
{report_content[:4000] if report_content else 'Không có file đính kèm - Chỉ có báo cáo text'}

═══════════════════════════════════════════════════════════════
⏱️ THỜI GIAN THỰC HIỆN
═══════════════════════════════════════════════════════════════
- Thời gian ước tính ban đầu: {task_data.get('estimated_hours', 0):.1f} giờ
- Thời gian thực tế đã làm: {task_data.get('actual_hours', 0):.1f} giờ
- Chênh lệch: {time_variance:+.1f}% ({'Vượt dự kiến' if time_variance > 10 else 'Tiết kiệm thời gian' if time_variance < -10 else 'Đúng dự kiến'})

═══════════════════════════════════════════════════════════════
📅 DEADLINE & THỜI HẠN
═══════════════════════════════════════════════════════════════
- Hạn hoàn thành: {task_data.get('deadline')}
- Ngày hoàn thành thực tế: {task_data.get('completed_date', 'N/A')}
- Tình trạng: {'⚠️ TRỄ HẠN' if task_data.get('is_overdue') else '✅ ĐÚNG HẠN'}

═══════════════════════════════════════════════════════════════
🎯 NHIỆM VỤ ĐÁNH GIÁ CỦA BẠN
═══════════════════════════════════════════════════════════════

Bước 1: PHÂN TÍCH YÊU CẦU
- Đọc kỹ từng điểm trong YÊU CẦU BAN ĐẦU
- Xác định các yêu cầu bắt buộc và yêu cầu mong muốn
- Hiểu rõ TIÊU CHÍ NGHIỆM THU để biết tiêu chuẩn chấp nhận

Bước 2: PHÂN TÍCH KẾT QUẢ
- Đọc kỹ KẾT QUẢ THỰC TẾ và FILE BÁO CÁO
- Xác định những gì đã được thực hiện
- Đánh giá chất lượng và độ đầy đủ của kết quả

Bước 3: SO SÁNH CHI TIẾT
- So sánh TỪNG ĐIỂM yêu cầu với kết quả tương ứng
- Xác định:
  ✅ Các công việc ĐÃ HOÀN THÀNH ĐẦY ĐỦ (liệt kê cụ thể, chi tiết)
  ❌ Các công việc CHƯA HOÀN THÀNH hoặc THIẾU SÓT (liệt kê cụ thể, nêu rõ phần nào thiếu)
  ⭐ Các công việc LÀM VƯỢT MỨC YÊU CẦU (nếu có, đây là điểm cộng)

Bước 4: ĐÁNH GIÁ CHẤT LƯỢNG
- Chất lượng sản phẩm bàn giao (code, design, documentation, v.v.)
- Tính chuyên nghiệp trong cách trình bày báo cáo
- Độ chi tiết và đầy đủ của thông tin

Bước 5: ĐÁNH GIÁ HIỆU SUẤT
- Hiệu quả sử dụng thời gian
- Tuân thủ deadline
- Khả năng ước lượng thời gian

═══════════════════════════════════════════════════════════════
📊 HỆ THỐNG CHẤM ĐIỂM
═══════════════════════════════════════════════════════════════
- Requirement Match (40%): Mức độ đáp ứng yêu cầu ban đầu
- Quality Score (30%): Chất lượng sản phẩm và báo cáo
- Time Efficiency (20%): Hiệu quả sử dụng thời gian
- Deadline Compliance (10%): Tuân thủ thời hạn

═══════════════════════════════════════════════════════════════
📤 YÊU CẦU ĐẦU RA
═══════════════════════════════════════════════════════════════

Trả về JSON (KHÔNG có markdown, chỉ JSON thuần túy):
{{
    "overall_completion": <0-100, % hoàn thành tổng thể, tính chính xác>,
    "requirement_match_score": <0-100, điểm đáp ứng yêu cầu>,
    "quality_score": <0-100, điểm chất lượng>,
    "time_efficiency_score": <0-100, điểm hiệu suất thời gian>,
    "deadline_score": <0-100, điểm tuân thủ deadline>,
    "completed_items": "✅ Yêu cầu 1: [Mô tả chi tiết đã làm gì]\\n✅ Yêu cầu 2: [Mô tả chi tiết]\\n...",
    "incomplete_items": "❌ Yêu cầu X: [Mô tả phần nào thiếu, chưa đạt]\\n❌ Yêu cầu Y: [Mô tả chi tiết]\\n...",
    "exceeded_items": "⭐ Đã làm thêm: [Mô tả công việc vượt mức yêu cầu]\\n⭐ Cải tiến: [Mô tả]\\n...",
    "strengths": "💪 Điểm mạnh 1: [Mô tả cụ thể]\\n💪 Điểm mạnh 2: [Mô tả cụ thể]\\n...",
    "weaknesses": "⚠️ Điểm yếu 1: [Mô tả cụ thể, cần cải thiện]\\n⚠️ Điểm yếu 2: [Mô tả cụ thể]\\n...",
    "recommendations": "🎯 Khuyến nghị 1: [Hành động cụ thể cần làm]\\n🎯 Khuyến nghị 2: [Hành động cụ thể]\\n...",
    "detailed_analysis": "<Phân tích chi tiết 5-8 câu về tổng thể chất lượng công việc, so sánh yêu cầu vs kết quả, đánh giá điểm mạnh/yếu, và kết luận>",
    "grade": "<A+/A/A-/B+/B/B-/C+/C/C-/D/F - Xếp loại dựa trên overall_completion và chất lượng>"
}}

LƯU Ý QUAN TRỌNG:
- Phải phân tích KỸ LƯỠNG, không được bỏ sót yêu cầu nào
- Liệt kê CỤ THỂ, CHI TIẾT từng điểm đã làm/chưa làm
- Đánh giá KHÁCH QUAN, CÔNG BẰNG dựa trên bằng chứng
- Đưa ra khuyến nghị THỰC TẾ, CÓ THỂ THỰC HIỆN
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            # Validate và set defaults
            result.setdefault('overall_completion', 70)
            result.setdefault('requirement_match_score', 70)
            result.setdefault('quality_score', 70)
            result.setdefault('time_efficiency_score', 70)
            result.setdefault('deadline_score', 100 if not task_data.get('is_overdue') else 50)
            result.setdefault('grade', 'B')
            
            # Clamp scores 0-100
            for key in ['overall_completion', 'requirement_match_score', 'quality_score', 
                       'time_efficiency_score', 'deadline_score']:
                result[key] = max(0, min(100, float(result[key])))
            
            _logger.info(f"✅ Task report evaluated: {task_data.get('task_code')} = {result['overall_completion']:.1f}%")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Task report evaluation failed: {str(e)[:300]}")
            return self._fallback_task_evaluation(task_data)
    
    @api.model
    def _fallback_task_evaluation(self, task_data):
        """Fallback khi AI không khả dụng"""
        has_result = bool(task_data.get('result_note'))
        has_files = bool(task_data.get('has_result_files'))
        is_ontime = not task_data.get('is_overdue')
        
        time_score = 100
        if task_data.get('estimated_hours', 0) > 0:
            ratio = task_data.get('actual_hours', 0) / task_data.get('estimated_hours', 1)
            time_score = max(50, 100 - abs(ratio - 1) * 50)
        
        completion = 80 if has_result else 50
        quality = 75 if has_files else 60
        deadline_score = 100 if is_ontime else 50
        
        overall = (completion * 0.4 + quality * 0.3 + time_score * 0.2 + deadline_score * 0.1)
        
        return {
            'overall_completion': round(overall, 1),
            'requirement_match_score': completion,
            'quality_score': quality,
            'time_efficiency_score': time_score,
            'deadline_score': deadline_score,
            'completed_items': '✅ Hoàn thành cơ bản' if has_result else '❌ Chưa có báo cáo',
            'incomplete_items': '❌ Không xác định được (AI không khả dụng)',
            'exceeded_items': '⭐ Không xác định được',
            'strengths': '💪 Có nộp báo cáo' if has_result else '💪 N/A',
            'weaknesses': '⚠️ Không sử dụng được AI để phân tích chi tiết',
            'recommendations': '🎯 Cập nhật kết quả chi tiết hơn\n🎯 Đính kèm file báo cáo',
            'detailed_analysis': 'Đánh giá cơ bản dựa trên dữ liệu có sẵn (AI không khả dụng)',
            'grade': 'B' if overall >= 70 else 'C'
        }
    
    # ==================== API 2: GỢI Ý PHÂN CÔNG THÔNG MINH ====================
    
    @api.model
    def suggest_task_assignment(self, task_info, available_employees):
        """
        API 2: Gợi ý phân công công việc thông minh dựa trên AI
        
        Phân tích:
        - Kỹ năng nhân viên vs yêu cầu công việc
        - Workload hiện tại của nhân viên
        - Lịch sử hoàn thành công việc tương tự
        - Tính khả dụng (đang có bao nhiêu task)
        
        Args:
            task_info (dict): {
                'name': str,
                'requirement': str,
                'estimated_hours': float,
                'priority': str,
                'deadline': date,
                'required_skills': list
            }
            available_employees (list): [{
                'id': int,
                'name': str,
                'job_position': str,
                'skills': str,
                'current_tasks_count': int,
                'avg_completion_rate': float,
                'avg_quality_score': float,
                'workload_hours': float
            }]
        
        Returns:
            dict: {
                'recommended_employee_id': int,
                'confidence_score': float (0-100),
                'reasoning': str,
                'alternatives': [{'id': int, 'name': str, 'score': float}],
                'workload_warning': str or None
            }
        """
        try:
            # Build employee comparison
            employees_text = ""
            for emp in available_employees[:10]:  # Limit 10 employees
                employees_text += f"""
- {emp['name']} ({emp['job_position']}):
  • Kỹ năng: {emp.get('skills', 'N/A')}
  • Công việc hiện tại: {emp.get('current_tasks_count', 0)} tasks
  • Tỷ lệ hoàn thành TB: {emp.get('avg_completion_rate', 0):.1f}%
  • Điểm chất lượng TB: {emp.get('avg_quality_score', 0):.1f}/100
  • Khối lượng công việc: {emp.get('workload_hours', 0):.1f}h
"""
            
            prompt = f"""
Bạn là AI chuyên phân công công việc. Nhiệm vụ: Chọn nhân viên PHÙ HỢP NHẤT.

**CÔNG VIỆC CẦN PHÂN CÔNG:**
- Tên: {task_info['name']}
- Yêu cầu: {task_info.get('requirement', '')[:500]}
- Thời gian ước lượng: {task_info.get('estimated_hours', 0)}h
- Ưu tiên: {task_info.get('priority', 'Bình thường')}
- Deadline: {task_info.get('deadline')}
- Kỹ năng cần: {', '.join(task_info.get('required_skills', [])) or 'Không xác định'}

**DANH SÁCH NHÂN VIÊN KHẢ DỤNG:**
{employees_text}

**TIÊU CHÍ LỰA CHỌN:**
1. Skill Match (40%): Kỹ năng phù hợp với yêu cầu
2. Workload (25%): Khối lượng công việc hiện tại (ưu tiên ít việc hơn)
3. Performance (20%): Lịch sử hoàn thành và chất lượng
4. Availability (15%): Tính khả dụng theo thời gian

Trả về JSON (KHÔNG markdown):
{{
    "recommended_employee_id": <ID nhân viên được đề xuất>,
    "confidence_score": <0-100, độ tin cậy của gợi ý>,
    "reasoning": "<2-3 câu giải thích tại sao chọn nhân viên này>",
    "alternatives": [
        {{"id": <ID>, "name": "<Tên>", "score": <0-100>}},
        {{"id": <ID>, "name": "<Tên>", "score": <0-100>}}
    ],
    "workload_warning": "<Cảnh báo nếu tất cả nhân viên đều quá tải, null nếu OK>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            result.setdefault('confidence_score', 70)
            result['confidence_score'] = max(0, min(100, float(result['confidence_score'])))
            
            _logger.info(f"✅ Task assignment suggested: Employee ID {result.get('recommended_employee_id')}")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Task assignment suggestion failed: {str(e)[:300]}")
            # Fallback: Chọn nhân viên có ít việc nhất
            if available_employees:
                best = min(available_employees, key=lambda x: x.get('current_tasks_count', 99))
                return {
                    'recommended_employee_id': best['id'],
                    'confidence_score': 50,
                    'reasoning': f"Gợi ý cơ bản: {best['name']} có ít công việc nhất ({best.get('current_tasks_count', 0)} tasks)",
                    'alternatives': [],
                    'workload_warning': None
                }
            return {'recommended_employee_id': None, 'confidence_score': 0}
    
    # ==================== API 3: DỰ ĐOÁN THỜI GIAN HOÀN THÀNH ====================
    
    @api.model
    def predict_task_duration(self, task_description, employee_id=None, historical_tasks=None):
        """
        API 3: Dự đoán thời gian hoàn thành công việc dựa trên AI
        
        Phân tích:
        - Mô tả công việc
        - Lịch sử công việc tương tự
        - Năng lực nhân viên (nếu đã chọn)
        
        Args:
            task_description (str): Mô tả công việc
            employee_id (int): ID nhân viên (optional)
            historical_tasks (list): [{
                'name': str,
                'estimated_hours': float,
                'actual_hours': float,
                'complexity': str
            }]
        
        Returns:
            dict: {
                'predicted_hours': float,
                'confidence_level': str (low/medium/high),
                'reasoning': str,
                'suggested_buffer': float (% dự phòng),
                'risk_factors': str
            }
        """
        try:
            historical_text = ""
            if historical_tasks:
                for task in historical_tasks[:5]:
                    historical_text += f"- {task['name']}: Ước lượng {task['estimated_hours']}h, Thực tế {task['actual_hours']}h\n"
            
            prompt = f"""
Bạn là chuyên gia ước lượng thời gian dự án. Dự đoán thời gian hoàn thành công việc.

**CÔNG VIỆC MỚI:**
{task_description[:1000]}

**LỊCH SỬ CÔNG VIỆC TƯƠNG TỰ:**
{historical_text or 'Không có lịch sử'}

**NHÂN VIÊN:** {'Đã chọn (ID: ' + str(employee_id) + ')' if employee_id else 'Chưa chọn'}

Trả về JSON (KHÔNG markdown):
{{
    "predicted_hours": <số giờ dự đoán (float)>,
    "confidence_level": "<low/medium/high>",
    "reasoning": "<2-3 câu giải thích cách tính>",
    "suggested_buffer": <% thời gian dự phòng (10-50)>,
    "risk_factors": "<Các yếu tố rủi ro có thể làm chậm tiến độ>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            result.setdefault('predicted_hours', 8.0)
            result.setdefault('confidence_level', 'medium')
            result.setdefault('suggested_buffer', 20)
            
            _logger.info(f"✅ Task duration predicted: {result['predicted_hours']:.1f}h")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Task duration prediction failed: {str(e)[:300]}")
            return {
                'predicted_hours': 8.0,
                'confidence_level': 'low',
                'reasoning': 'Ước lượng mặc định 8 giờ (1 ngày làm việc)',
                'suggested_buffer': 25,
                'risk_factors': 'Không có dữ liệu lịch sử để phân tích'
            }
    
    # ==================== API 4: PHÁT HIỆN RỦI RO & CẢNH BÁO ====================
    
    @api.model
    def detect_task_risks(self, task_data):
        """
        API 4: Phát hiện rủi ro công việc bằng AI
        
        Phân tích:
        - Tiến độ hiện tại vs deadline
        - Workload nhân viên
        - Độ phức tạp yêu cầu
        - Lịch sử chậm trễ
        
        Args:
            task_data (dict): {
                'name': str,
                'progress': int (0-100),
                'deadline': date,
                'start_date': date,
                'estimated_hours': float,
                'actual_hours': float,
                'employee_current_tasks': int,
                'employee_overdue_rate': float,
                'is_complex': bool
            }
        
        Returns:
            dict: {
                'risk_level': str (low/medium/high/critical),
                'risk_score': float (0-100),
                'risk_factors': list of str,
                'recommendations': str,
                'early_warning': bool
            }
        """
        try:
            from datetime import datetime, date
            
            # Tính toán thời gian còn lại
            if isinstance(task_data.get('deadline'), (datetime, date)):
                deadline = task_data['deadline']
                if isinstance(deadline, datetime):
                    deadline = deadline.date()
                
                today = date.today()
                days_left = (deadline - today).days
            else:
                days_left = 0
            
            # Tính % thời gian đã trôi qua
            if isinstance(task_data.get('start_date'), (datetime, date)):
                start_date = task_data['start_date']
                if isinstance(start_date, datetime):
                    start_date = start_date.date()
                
                total_days = (deadline - start_date).days
                elapsed_days = (today - start_date).days
                time_progress = (elapsed_days / max(total_days, 1)) * 100 if total_days > 0 else 0
            else:
                time_progress = 50
            
            prompt = f"""
Bạn là chuyên gia quản lý rủi ro dự án. Phân tích rủi ro công việc.

**CÔNG VIỆC:**
- Tên: {task_data['name']}
- Tiến độ: {task_data.get('progress', 0)}%
- Deadline: {task_data.get('deadline')} (còn {days_left} ngày)
- Thời gian đã trôi qua: {time_progress:.0f}%

**THỜI GIAN:**
- Ước lượng: {task_data.get('estimated_hours', 0)}h
- Đã làm: {task_data.get('actual_hours', 0)}h
- Tỷ lệ: {(task_data.get('actual_hours', 0) / max(task_data.get('estimated_hours', 1), 1) * 100):.0f}%

**NHÂN VIÊN:**
- Công việc hiện tại: {task_data.get('employee_current_tasks', 0)}
- Tỷ lệ trễ hạn: {task_data.get('employee_overdue_rate', 0):.1f}%
- Độ phức tạp công việc: {'Cao' if task_data.get('is_complex') else 'Bình thường'}

**CHỈ SỐ RỦI RO:**
- Nếu tiến độ << thời gian đã qua → Rủi ro cao
- Nếu nhân viên quá tải → Rủi ro cao
- Nếu tỷ lệ trễ hạn cao → Rủi ro cao

Trả về JSON (KHÔNG markdown):
{{
    "risk_level": "<low/medium/high/critical>",
    "risk_score": <0-100>,
    "risk_factors": ["<Yếu tố 1>", "<Yếu tố 2>", "<Yếu tố 3>"],
    "recommendations": "🚨 Danh sách khuyến nghị khẩn cấp (mỗi khuyến nghị 1 dòng)",
    "early_warning": <true nếu cần cảnh báo sớm>
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            result.setdefault('risk_level', 'medium')
            result.setdefault('risk_score', 50)
            result.setdefault('risk_factors', [])
            result.setdefault('early_warning', False)
            
            result['risk_score'] = max(0, min(100, float(result['risk_score'])))
            
            _logger.info(f"✅ Task risks detected: {task_data['name']} = {result['risk_level']} ({result['risk_score']:.0f}/100)")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Task risk detection failed: {str(e)[:300]}")
            return {
                'risk_level': 'medium',
                'risk_score': 50,
                'risk_factors': ['Không thể phân tích rủi ro (AI không khả dụng)'],
                'recommendations': '🚨 Theo dõi sát tiến độ công việc',
                'early_warning': False
            }
    
    # ==================== API 5: TỰ ĐỘNG TẠO TIÊU CHÍ NGHIỆM THU ====================
    
    @api.model
    def generate_acceptance_criteria(self, task_requirement):
        """
        API 5: Tự động tạo tiêu chí nghiệm thu từ yêu cầu
        
        Args:
            task_requirement (str): Mô tả yêu cầu công việc
        
        Returns:
            dict: {
                'criteria': str (checklist format),
                'estimated_complexity': str (low/medium/high),
                'suggested_checkpoints': list
            }
        """
        try:
            prompt = f"""
Bạn là business analyst. Từ yêu cầu công việc, tạo TIÊU CHÍ NGHIỆM THU chi tiết.

**YÊU CẦU CÔNG VIỆC:**
{task_requirement[:1500]}

**NHIỆM VỤ:**
Tạo danh sách tiêu chí nghiệm thu (acceptance criteria) dạng checklist:
- Mỗi tiêu chí phải cụ thể, đo lường được
- Bao gồm tiêu chí kỹ thuật và phi kỹ thuật
- Phân loại: Bắt buộc / Mong muốn

Trả về JSON (KHÔNG markdown):
{{
    "criteria": "☐ Tiêu chí 1 (Bắt buộc)\\n☐ Tiêu chí 2 (Bắt buộc)\\n☐ Tiêu chí 3 (Mong muốn)\\n...",
    "estimated_complexity": "<low/medium/high>",
    "suggested_checkpoints": ["Checkpoint 1", "Checkpoint 2", "Checkpoint 3"]
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            result.setdefault('criteria', '☐ Không có tiêu chí cụ thể')
            result.setdefault('estimated_complexity', 'medium')
            result.setdefault('suggested_checkpoints', [])
            
            _logger.info(f"✅ Acceptance criteria generated")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Acceptance criteria generation failed: {str(e)[:300]}")
            return {
                'criteria': '☐ Hoàn thành đúng yêu cầu\n☐ Đảm bảo chất lượng\n☐ Giao đúng hạn',
                'estimated_complexity': 'medium',
                'suggested_checkpoints': []
            }
    
    # ==================== API 6: ĐÁNH GIÁ TIẾN ĐỘ KHI GỬI DUYỆT ====================
    
    @api.model
    def evaluate_task_progress(self, task_data):
        """
        API 6: Đánh giá tiến độ công việc khi nhân viên gửi duyệt
        Được gọi tự động khi nhấn "Gửi duyệt"
        
        Đánh giá dựa trên:
        - Tên công việc
        - Mô tả
        - Ngày bắt đầu
        - Deadline
        - Ngày hiện tại
        - Tiến độ báo cáo (%)
        - Nội dung đã thực hiện
        - Mức độ ưu tiên
        
        Args:
            task_data (dict): {
                'name': str,
                'description': str,
                'start_date': date,
                'deadline': date,
                'current_date': date,
                'progress': int (0-100),
                'result_note': str,
                'priority': str,
                'estimated_hours': float,
                'actual_hours': float
            }
        
        Returns:
            dict: {
                'completion_level': str (Hoàn thành tốt / Hoàn thành / Chưa hoàn thành / Cần bổ sung),
                'completion_percentage': float (0-100),
                'deadline_risk': str (Không có rủi ro / Rủi ro thấp / Rủi ro trung bình / Rủi ro cao / Nguy cơ trễ hạn),
                'deadline_risk_score': float (0-100),
                'supervisor_recommendations': str (Đề xuất hành động cho người giám sát),
                'detailed_assessment': str (Đánh giá chi tiết)
            }
        """
        try:
            from datetime import datetime, date
            
            # Tính toán thời gian
            if isinstance(task_data.get('deadline'), (datetime, date)):
                deadline = task_data['deadline']
                if isinstance(deadline, datetime):
                    deadline = deadline.date()
            else:
                deadline = None
            
            if isinstance(task_data.get('start_date'), (datetime, date)):
                start_date = task_data['start_date']
                if isinstance(start_date, datetime):
                    start_date = start_date.date()
            else:
                start_date = None
            
            current_date = task_data.get('current_date') or date.today()
            if isinstance(current_date, datetime):
                current_date = current_date.date()
            
            # Tính số ngày
            days_elapsed = 0
            days_total = 0
            days_remaining = 0
            if start_date and deadline:
                days_total = (deadline - start_date).days
                days_elapsed = (current_date - start_date).days
                days_remaining = (deadline - current_date).days
            
            # Tính % thời gian đã trôi qua
            time_progress = (days_elapsed / max(days_total, 1)) * 100 if days_total > 0 else 0
            
            # Chuẩn bị dữ liệu
            description_text = re.sub(r'<[^>]+>', '', task_data.get('description', ''))
            result_text = re.sub(r'<[^>]+>', '', task_data.get('result_note', ''))
            
            # Xây dựng prompt theo yêu cầu
            prompt = f"""
Bạn là chuyên gia đánh giá tiến độ công việc. Nhiệm vụ: Đánh giá công việc dựa trên các thông tin sau.

**THÔNG TIN CÔNG VIỆC:**

Tên công việc: {task_data.get('name', 'N/A')}

Mô tả: {description_text[:1000] if description_text else 'Không có mô tả'}

Ngày bắt đầu: {start_date.strftime('%d/%m/%Y') if start_date else 'Chưa xác định'}

Deadline: {deadline.strftime('%d/%m/%Y') if deadline else 'Chưa xác định'}

Ngày hiện tại: {current_date.strftime('%d/%m/%Y')}

Tiến độ báo cáo: {task_data.get('progress', 0)}%

Nội dung đã thực hiện: {result_text[:2000] if result_text else 'Chưa có nội dung'}

Mức độ ưu tiên: {task_data.get('priority', 'Bình thường')}

**THỜI GIAN:**
- Thời gian ước lượng: {task_data.get('estimated_hours', 0):.1f} giờ
- Thời gian thực tế: {task_data.get('actual_hours', 0):.1f} giờ
- Số ngày đã trôi qua: {days_elapsed} ngày
- Số ngày còn lại: {days_remaining} ngày
- % thời gian đã trôi qua: {time_progress:.1f}%

**NHIỆM VỤ CỦA BẠN:**

Hãy đánh giá:

1. **Mức độ hoàn thành:**
   - So sánh tiến độ báo cáo ({task_data.get('progress', 0)}%) với % thời gian đã trôi qua ({time_progress:.1f}%)
   - Đánh giá nội dung đã thực hiện có đầy đủ và chất lượng không
   - Kết luận: "Hoàn thành tốt" / "Hoàn thành" / "Chưa hoàn thành" / "Cần bổ sung"

2. **Nguy cơ trễ hạn:**
   - Phân tích: Tiến độ vs Thời gian còn lại
   - Nếu tiến độ < thời gian đã trôi qua → Nguy cơ trễ hạn
   - Nếu tiến độ = thời gian đã trôi qua → Đúng tiến độ
   - Nếu tiến độ > thời gian đã trôi qua → Sớm hơn dự kiến
   - Kết luận: "Không có rủi ro" / "Rủi ro thấp" / "Rủi ro trung bình" / "Rủi ro cao" / "Nguy cơ trễ hạn"

3. **Đề xuất hành động cho người giám sát:**
   - Dựa trên đánh giá mức độ hoàn thành và nguy cơ trễ hạn
   - Đưa ra 3-5 hành động cụ thể, khả thi
   - Ví dụ: "Duyệt ngay" / "Yêu cầu bổ sung" / "Theo dõi sát" / "Hỗ trợ nhân viên" / "Gia hạn deadline"

Trả về JSON (KHÔNG markdown):
{{
    "completion_level": "<Hoàn thành tốt / Hoàn thành / Chưa hoàn thành / Cần bổ sung>",
    "completion_percentage": <0-100, % hoàn thành thực tế>,
    "deadline_risk": "<Không có rủi ro / Rủi ro thấp / Rủi ro trung bình / Rủi ro cao / Nguy cơ trễ hạn>",
    "deadline_risk_score": <0-100, điểm rủi ro (0 = không rủi ro, 100 = chắc chắn trễ hạn)>,
    "supervisor_recommendations": "🎯 Hành động 1\\n🎯 Hành động 2\\n🎯 Hành động 3\\n...",
    "detailed_assessment": "<Đánh giá chi tiết 4-6 câu về tình trạng công việc>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            # Validate và set defaults
            result.setdefault('completion_level', 'Chưa hoàn thành')
            result.setdefault('completion_percentage', task_data.get('progress', 0))
            result.setdefault('deadline_risk', 'Rủi ro trung bình')
            result.setdefault('deadline_risk_score', 50)
            result.setdefault('supervisor_recommendations', '🎯 Theo dõi tiến độ công việc')
            result.setdefault('detailed_assessment', 'Đánh giá cơ bản dựa trên tiến độ báo cáo')
            
            # Clamp scores
            result['completion_percentage'] = max(0, min(100, float(result['completion_percentage'])))
            result['deadline_risk_score'] = max(0, min(100, float(result['deadline_risk_score'])))
            
            _logger.info(f"✅ Task progress evaluated: {task_data.get('name')} - {result['completion_level']}, Risk: {result['deadline_risk']}")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Task progress evaluation failed: {str(e)[:300]}")
            return self._fallback_progress_evaluation(task_data)
    
    @api.model
    def _fallback_progress_evaluation(self, task_data):
        """Fallback khi AI không khả dụng"""
        progress = task_data.get('progress', 0)
        days_remaining = 0
        
        if task_data.get('deadline') and task_data.get('current_date'):
            from datetime import date
            deadline = task_data['deadline']
            current = task_data['current_date']
            if isinstance(deadline, str):
                deadline = date.fromisoformat(deadline)
            if isinstance(current, str):
                current = date.fromisoformat(current)
            days_remaining = (deadline - current).days
        
        # Đánh giá cơ bản
        if progress >= 100:
            completion = 'Hoàn thành'
            risk = 'Không có rủi ro'
            risk_score = 0
        elif progress >= 80:
            completion = 'Hoàn thành'
            risk = 'Rủi ro thấp' if days_remaining > 0 else 'Nguy cơ trễ hạn'
            risk_score = 20 if days_remaining > 0 else 80
        elif progress >= 50:
            completion = 'Chưa hoàn thành'
            risk = 'Rủi ro trung bình' if days_remaining > 0 else 'Rủi ro cao'
            risk_score = 50 if days_remaining > 0 else 70
        else:
            completion = 'Chưa hoàn thành'
            risk = 'Rủi ro cao' if days_remaining > 0 else 'Nguy cơ trễ hạn'
            risk_score = 70 if days_remaining > 0 else 90
        
        return {
            'completion_level': completion,
            'completion_percentage': progress,
            'deadline_risk': risk,
            'deadline_risk_score': risk_score,
            'supervisor_recommendations': '🎯 Theo dõi tiến độ công việc\n🎯 Kiểm tra chất lượng kết quả\n🎯 Quyết định duyệt hoặc yêu cầu bổ sung',
            'detailed_assessment': f'Tiến độ báo cáo: {progress}%. Đánh giá cơ bản (AI không khả dụng).'
        }