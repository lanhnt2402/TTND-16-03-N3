# -*- coding: utf-8 -*-
"""
AI Service - Google Gemini 2.5 Integration với Auto API Rotation
Tích hợp 5 API keys, tự động chuyển key khi hết quota
"""

import logging
import google.genai as genai
from odoo import api, models, _
from odoo.exceptions import UserError
import os
import json

_logger = logging.getLogger(__name__)


class AIService(models.AbstractModel):
    """Service tích hợp Google Gemini AI với 5 API keys rotation"""
    
    _name = 'ai.service'
    _description = 'AI Service for Gemini Integration with Auto Rotation'

    # Fallback API Keys - Phân bổ theo chức năng
    DEFAULT_API_KEYS = [
        "AIzaSyApIoPs91hDIor3pA3PjlNPoVV0nzPeMl0",  # Key #1: Document Analysis & Employee Eval
        "AIzaSyAEKaLFrnUbHQ8jbGu23jk5hGop2UJMQbw",  # Key #2: Customer Scoring & Backup
        "AIzaSyAb5Fxtzg0AlFrWv4I6SKE34hr10v8OY-Y",  # Key #3: Work Report Comparison (CRITICAL)
        "AIzaSyAZ887ml8jI01uAwnuN7DCduczUg9zsyDM",  # Key #4: Quality Assessment
        "AIzaSyBEALAyUVpOGbsFKkM2SX5LdR2n4QWOhcg"   # Key #5: Recommendations & Advanced
    ]
    
    current_key_index = 0
    
    @api.model
    def _get_api_keys(self):
        """
        Lấy API keys từ config parameter hoặc fallback về default
        Format trong config: key1,key2,key3,key4,key5
        """
        try:
            config_param = self.env['ir.config_parameter'].sudo().get_param(
                'quan_ly_nhan_su.gemini_api_keys', ''
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
    
    # API Key assignment by function
    API_ASSIGNMENT = {
        'employee_eval': 0,        # Key #1
        'customer_scoring': 1,     # Key #2
        'report_comparison': 2,    # Key #3 (CRITICAL)
        'quality_assessment': 3,   # Key #4
        'recommendations': 4,      # Key #5
        'document_parsing': 0,     # Key #1 (shared)
        'task_assignment': 1,      # Key #2 (shared)
        'deadline_estimation': 2,  # Key #3 (shared)
        'progress_tracking': 3,    # Key #4 (shared)
        'communication_check': 4   # Key #5 (shared)
    }
    
    @api.model
    def _get_api_key_for_function(self, function_name):
        """
        Lấy API key theo chức năng
        
        Args:
            function_name: Tên chức năng (employee_eval, customer_scoring, ...)
        
        Returns:
            tuple: (API key, key_index)
        """
        api_keys = self._get_api_keys()
        key_index = self.API_ASSIGNMENT.get(function_name, self.current_key_index)
        if key_index >= len(api_keys):
            key_index = 0
        key = api_keys[key_index]
        _logger.info(f"🔑 Using API Key #{key_index + 1} for '{function_name}'")
        return key, key_index
    
    @api.model
    def _get_next_api_key(self):
        """Lấy API key tiếp theo (rotation) - Fallback"""
        api_keys = self._get_api_keys()
        if self.current_key_index >= len(api_keys):
            self.current_key_index = 0
        key = api_keys[self.current_key_index]
        _logger.info(f"Using Gemini API key #{self.current_key_index + 1}/{len(api_keys)}")
        return key
    
    @api.model
    def _rotate_api_key(self):
        """Chuyển sang API key tiếp theo"""
        api_keys = self._get_api_keys()
        old_index = self.current_key_index
        self.current_key_index = (self.current_key_index + 1) % len(api_keys)
        _logger.warning(f"🔄 API Rotation: Key #{old_index + 1} → Key #{self.current_key_index + 1}")
        return self.current_key_index

    @api.model
    def _call_gemini_with_retry(self, prompt, max_retries=5, function_name='default'):
        """
        Call Gemini 2.5 API với auto-retry và rotation khi hết quota
        Sử dụng Google GenAI SDK mới
        
        Args:
            prompt (str): Prompt gửi cho AI
            max_retries (int): Số lần retry (= số API keys)
            function_name (str): Tên chức năng để chọn API key phù hợp
        
        Returns:
            str: Response từ AI
        """
        for attempt in range(max_retries):
            try:
                # Lấy API key theo chức năng
                api_key, key_index = self._get_api_key_for_function(function_name)
                
                # Khởi tạo client với API key
                try:
                    client = genai.Client(api_key=api_key)
                except Exception as e:
                    _logger.error(f"❌ Không thể khởi tạo Gemini client: {str(e)}")
                    # Fallback: thử với key tiếp theo
                    if attempt < max_retries - 1:
                        self._rotate_api_key()
                        continue
                    raise
                
                # Gọi API với model gemini-2.5-flash
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(x in error_msg for x in ['quota', 'resource_exhausted', '429', 'rate limit', 'permission']):
                        _logger.warning(f"⚠️ API Key #{key_index + 1} quota/permission error")
                        if attempt < max_retries - 1:
                            self._rotate_api_key()
                            continue
                    raise
                
                if response and hasattr(response, 'text') and response.text:
                    _logger.info(f"✅ Gemini 2.5 API success (attempt {attempt + 1}, key #{key_index + 1})")
                    return response.text
                elif response and hasattr(response, 'candidates') and response.candidates:
                    # Fallback: lấy text từ candidates
                    text = response.candidates[0].content.parts[0].text if response.candidates[0].content.parts else ""
                    if text:
                        _logger.info(f"✅ Gemini 2.5 API success (from candidates)")
                        return text
                    else:
                        raise Exception("Empty response from Gemini")
                else:
                    raise Exception("Empty response from Gemini")
                    
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check quota errors
                if any(x in error_msg for x in ['quota', 'resource_exhausted', '429', 'rate limit', 'permission']):
                    _logger.warning(f"⚠️ API Key #{key_index + 1} quota/permission exceeded")
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
                    # All keys failed - return fallback instead of raising
                    _logger.error(f"❌ Tất cả {max_retries} API keys đều thất bại")
                    return None  # Return None để caller có thể xử lý fallback
        
        return None  # Return None thay vì raise để có thể fallback

    # ==================== EMPLOYEE PERFORMANCE ANALYSIS ====================
    
    @api.model
    def analyze_employee_performance(self, employee_data):
        """
        Phân tích hiệu suất nhân viên bằng AI
        
        TIÊU CHÍ ĐÁNH GIÁ (0-100 điểm):
        1. Task Completion Rate (30%): Tỷ lệ hoàn thành công việc
        2. On-Time Delivery (25%): Giao việc đúng hạn
        3. Work Quality (20%): Chất lượng công việc
        4. Skill Match (15%): Phù hợp kỹ năng với công việc
        5. Growth Trend (10%): Xu hướng phát triển
        
        Args:
            employee_data (dict): {
                'name': str,
                'job_position': str,
                'department': str,
                'total_tasks': int,
                'completed_tasks': int,
                'overdue_tasks': int,
                'task_completion_rate': float,
                'average_task_score': float
            }
        
        Returns:
            dict: {
                'overall_score': float (0-100),
                'performance_level': str,
                'strengths': str,
                'improvements': str,
                'recommendations': str,
                'analysis': str
            }
        """
        try:
            prompt = f"""
Bạn là chuyên gia đánh giá hiệu suất nhân viên. Phân tích dữ liệu sau:

**THÔNG TIN NHÂN VIÊN:**
- Họ tên: {employee_data.get('name')}
- Vị trí: {employee_data.get('job_position')}
- Phòng ban: {employee_data.get('department', 'Chưa xác định')}

**THỐNG KÊ CÔNG VIỆC:**
- Tổng công việc: {employee_data.get('total_tasks', 0)}
- Hoàn thành: {employee_data.get('completed_tasks', 0)}
- Quá hạn: {employee_data.get('overdue_tasks', 0)}
- Tỷ lệ hoàn thành: {employee_data.get('task_completion_rate', 0):.1f}%
- Điểm chất lượng TB: {employee_data.get('average_task_score', 0):.1f}/100

**TIÊU CHÍ ĐÁNH GIÁ:**
1. Task Completion Rate (30%): {employee_data.get('task_completion_rate', 0):.1f}%
2. On-Time Delivery (25%): {(employee_data.get('completed_tasks', 0) - employee_data.get('overdue_tasks', 0)) / max(employee_data.get('completed_tasks', 1), 1) * 100:.1f}%
3. Work Quality (20%): {employee_data.get('average_task_score', 0):.1f}/100
4. Skill Match (15%): Đánh giá theo vị trí
5. Growth Trend (10%): Xu hướng cải thiện

Trả về JSON (KHÔNG markdown, chỉ JSON thuần):
{{
    "overall_score": <điểm 0-100>,
    "performance_level": "<poor/below_average/average/good/excellent/outstanding>",
    "strengths": "<3-5 điểm mạnh, mỗi điểm 1 dòng, bắt đầu ✓>",
    "improvements": "<3-5 điểm cải thiện, mỗi điểm 1 dòng, bắt đầu ⚠>",
    "recommendations": "<3-5 khuyến nghị, mỗi khuyến nghị 1 dòng, bắt đầu →>",
    "analysis": "<phân tích ngắn gọn 2-3 câu>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt, function_name='employee_eval')
            
            if not response_text:
                # Fallback nếu AI không khả dụng
                return self._fallback_employee_analysis(employee_data)
            
            # Parse JSON
            response_text = self._clean_json_response(response_text)
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                _logger.error(f"❌ JSON parse error: {str(e)}. Response: {response_text[:200]}")
                return self._fallback_employee_analysis(employee_data)
            
            # Validate & set defaults
            result.setdefault('overall_score', 70)
            result['overall_score'] = max(0, min(100, float(result['overall_score'])))
            
            _logger.info(f"✅ Employee AI analysis: {employee_data.get('name')} = {result['overall_score']}/100")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Employee analysis failed: {str(e)[:200]}")
            return self._fallback_employee_analysis(employee_data)
    
    @api.model
    def _fallback_employee_analysis(self, data):
        """Fallback khi AI không khả dụng"""
        completion = data.get('task_completion_rate', 0)
        quality = data.get('average_task_score', 0)
        total_tasks = data.get('total_tasks', 0)
        overdue_tasks = data.get('overdue_tasks', 0)
        completed_tasks = data.get('completed_tasks', 0)
        
        ontime_rate = 100 if overdue_tasks == 0 and completed_tasks > 0 else max(0, 100 - (overdue_tasks / max(completed_tasks, 1)) * 100)
        
        # Tính điểm chi tiết
        completion_score = completion * 0.3
        ontime_score = ontime_rate * 0.25
        quality_score = quality * 0.20
        workload_score = min(10, (total_tasks / 20) * 10) * 0.15
        growth_score = 70 * 0.10  # Default
        
        score = completion_score + ontime_score + quality_score + workload_score + growth_score
        
        return {
            'overall_score': round(score, 1),
            'performance_level': 'excellent' if score >= 85 else ('good' if score >= 75 else ('average' if score >= 60 else 'below_average')),
            'completion_score': round(completion_score, 1),
            'quality_score': round(quality_score, 1),
            'deadline_score': round(ontime_score, 1),
            'efficiency_score': round(workload_score, 1),
            'growth_score': round(growth_score, 1),
            'strengths': f"✓ Tỷ lệ hoàn thành: {completion:.1f}%\n✓ Chất lượng công việc: {quality:.1f}/100\n✓ Tổng công việc: {total_tasks}",
            'improvements': "⚠ Cải thiện tốc độ" if ontime_rate < 80 else "⚠ Duy trì hiệu suất",
            'recommendations': "→ Tiếp tục phát triển kỹ năng\n→ Tăng năng suất làm việc\n→ Giảm công việc quá hạn",
            'analysis': f"Nhân viên hoàn thành {completion:.1f}% công việc với chất lượng {quality:.1f}/100. Tổng {total_tasks} công việc, {overdue_tasks} quá hạn."
        }
    
    @api.model
    def analyze_employee_performance_detailed(self, employee_data):
        """
        Phân tích hiệu suất nhân viên chi tiết bằng AI (nâng cao)
        
        Returns thêm các điểm số chi tiết cho biểu đồ
        """
        try:
            prompt = f"""
Bạn là chuyên gia đánh giá hiệu suất nhân viên. Phân tích CHI TIẾT dữ liệu sau:

**THÔNG TIN NHÂN VIÊN:**
- Họ tên: {employee_data.get('name')}
- Vị trí: {employee_data.get('job_position')}
- Phòng ban: {employee_data.get('department', 'Chưa xác định')}
- Số năm làm việc: {employee_data.get('working_years', 0)}

**THỐNG KÊ CÔNG VIỆC:**
- Tổng công việc: {employee_data.get('total_tasks', 0)}
- Hoàn thành: {employee_data.get('completed_tasks', 0)}
- Quá hạn: {employee_data.get('overdue_tasks', 0)}
- Tỷ lệ hoàn thành: {employee_data.get('task_completion_rate', 0):.1f}%
- Điểm chất lượng TB: {employee_data.get('average_task_score', 0):.1f}/100

**YÊU CẦU:**
Trả về JSON (KHÔNG markdown, chỉ JSON thuần) với các trường:
{{
    "overall_score": <điểm 0-100>,
    "performance_level": "<poor/below_average/average/good/excellent/outstanding>",
    "completion_score": <điểm 0-30>,
    "quality_score": <điểm 0-20>,
    "deadline_score": <điểm 0-25>,
    "efficiency_score": <điểm 0-15>,
    "growth_score": <điểm 0-10>,
    "strengths": "<3-5 điểm mạnh, mỗi điểm 1 dòng, bắt đầu ✓>",
    "improvements": "<3-5 điểm cải thiện, mỗi điểm 1 dòng, bắt đầu ⚠>",
    "recommendations": "<3-5 khuyến nghị, mỗi khuyến nghị 1 dòng, bắt đầu →>",
    "analysis": "<phân tích ngắn gọn 2-3 câu>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt, function_name='employee_eval')
            
            if not response_text:
                return self._fallback_employee_analysis(employee_data)
            
            response_text = self._clean_json_response(response_text)
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                _logger.error(f"❌ JSON parse error: {str(e)}")
                return self._fallback_employee_analysis(employee_data)
            
            # Validate & set defaults
            result.setdefault('overall_score', 70)
            result['overall_score'] = max(0, min(100, float(result['overall_score'])))
            result.setdefault('completion_score', 0)
            result.setdefault('quality_score', 0)
            result.setdefault('deadline_score', 0)
            result.setdefault('efficiency_score', 0)
            result.setdefault('growth_score', 0)
            
            _logger.info(f"✅ Employee detailed AI analysis: {employee_data.get('name')} = {result['overall_score']}/100")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Employee detailed analysis failed: {str(e)[:200]}")
            return self._fallback_employee_analysis(employee_data)
    
    # ==================== CUSTOMER SCORING ====================
    
    @api.model
    def analyze_customer_potential(self, customer_data):
        """
        Phân tích tiềm năng khách hàng bằng AI
        
        TIÊU CHÍ ĐÁNH GIÁ (0-100 điểm):
        1. Revenue Potential (30%): Tiềm năng doanh thu
        2. Engagement Level (25%): Mức độ tương tác
        3. Payment History (20%): Lịch sử thanh toán
        4. Growth Potential (15%): Tiềm năng phát triển
        5. Strategic Fit (10%): Phù hợp chiến lược
        
        Args:
            customer_data (dict): Dữ liệu khách hàng
        
        Returns:
            dict: {
                'ai_score': float (0-100),
                'score_level': str,
                'churn_risk': float (0-100),
                'recommendations': str
            }
        """
        try:
            prompt = f"""
Bạn là chuyên gia phân tích khách hàng CRM. Đánh giá tiềm năng:

**THÔNG TIN:**
- Tên: {customer_data.get('name')}
- Loại: {customer_data.get('customer_type')}
- Ngành: {customer_data.get('industry', 'N/A')}
- Quy mô: {customer_data.get('company_size', 'N/A')}

**TRẠNG THÁI:**
- Status: {customer_data.get('status')}
- Level: {customer_data.get('level')}
- Nguồn: {customer_data.get('source', 'N/A')}

**TƯƠNG TÁC:**
- Tổng công việc: {customer_data.get('total_tasks', 0)}
- Hoàn thành: {customer_data.get('completed_tasks', 0)}
- Ngày liên hệ cuối: {customer_data.get('last_contact_date', 'Chưa có')}

**TÀI CHÍNH:**
- Doanh thu kỳ vọng: {customer_data.get('expected_revenue', 0):,.0f} VNĐ
- Xác suất: {customer_data.get('probability', 0)}%

**TIÊU CHÍ:**
1. Revenue Potential (30%): Tiềm năng doanh thu
2. Engagement (25%): Tương tác, phản hồi
3. Payment History (20%): Uy tín thanh toán
4. Growth (15%): Xu hướng phát triển
5. Strategic Fit (10%): Phù hợp mục tiêu

Trả về JSON (KHÔNG markdown):
{{
    "ai_score": <0-100>,
    "score_level": "<very_low/low/medium/high/very_high>",
    "churn_risk": <0-100 nguy cơ mất khách>,
    "recommendations": "<3-5 khuyến nghị, mỗi dòng bắt đầu 🎯/⚠️/💰>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            result.setdefault('ai_score', 70)
            result.setdefault('churn_risk', 30)
            result['ai_score'] = max(0, min(100, float(result['ai_score'])))
            result['churn_risk'] = max(0, min(100, float(result['churn_risk'])))
            
            _logger.info(f"✅ Customer AI score: {customer_data.get('name')} = {result['ai_score']}/100")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Customer analysis failed: {str(e)[:200]}")
            return self._fallback_customer_analysis(customer_data)
    
    @api.model
    def _fallback_customer_analysis(self, data):
        """Fallback customer scoring"""
        revenue_score = min(100, data.get('expected_revenue', 0) / 100000000 * 100)
        prob_score = data.get('probability', 50)
        
        score = (revenue_score * 0.3 + prob_score * 0.7)
        
        return {
            'ai_score': round(score, 1),
            'score_level': 'high' if score >= 70 else 'medium',
            'churn_risk': 30,
            'recommendations': f"🎯 Tăng cường chăm sóc\n💰 Khai thác tiềm năng {data.get('expected_revenue', 0):,.0f} VNĐ"
        }
    
    # ==================== TASK QUALITY EVALUATION ====================
    
    @api.model
    def analyze_task_quality(self, task_data):
        """
        Đánh giá chất lượng công việc
        
        TIÊU CHÍ (0-100 điểm):
        1. Deliverable Quality (30%): Chất lượng sản phẩm
        2. Time Efficiency (25%): Hiệu quả thời gian
        3. Requirement Match (20%): Đáp ứng yêu cầu
        4. Communication (15%): Giao tiếp, báo cáo
        5. Innovation (10%): Tính sáng tạo
        
        Args:
            task_data (dict): Dữ liệu công việc
        
        Returns:
            dict: Kết quả đánh giá
        """
        try:
            prompt = f"""
Đánh giá chất lượng công việc:

**CÔNG VIỆC:** {task_data.get('name')}

**YÊU CẦU:**
{task_data.get('requirement', 'N/A')[:300]}

**KẾT QUẢ:**
{task_data.get('deliverable', 'N/A')[:300]}

**THỜI GIAN:**
- Ước tính: {task_data.get('estimated_hours', 0)}h
- Thực tế: {task_data.get('actual_hours', 0)}h
- Hiệu suất: {task_data.get('actual_hours', 1) / max(task_data.get('estimated_hours', 1), 1) * 100:.0f}%

**DEADLINE:**
- Kế hoạch: {task_data.get('deadline')}
- Hoàn thành: {task_data.get('completed_date', 'Chưa xong')}
- {'✓ Đúng hạn' if not task_data.get('is_overdue') else '✗ Trễ hạn'}

**TIÊU CHÍ:**
1. Deliverable Quality (30%)
2. Time Efficiency (25%)
3. Requirement Match (20%)
4. Communication (15%)
5. Innovation (10%)

Trả về JSON (KHÔNG markdown):
{{
    "quality_score": <0-100>,
    "time_score": <0-100>,
    "requirement_score": <0-100>,
    "overall": <0-100>,
    "analysis": "<phân tích 2-3 câu>",
    "suggestions": "<2-3 gợi ý cải thiện>"
}}
"""
            
            response_text = self._call_gemini_with_retry(prompt)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text)
            
            result.setdefault('overall', 70)
            result['overall'] = max(0, min(100, float(result['overall'])))
            
            _logger.info(f"✅ Task quality: {task_data.get('name')} = {result['overall']}/100")
            return result
            
        except Exception as e:
            _logger.error(f"❌ Task analysis failed: {str(e)[:200]}")
            return self._fallback_task_analysis(task_data)
    
    @api.model
    def _fallback_task_analysis(self, data):
        """Fallback task quality"""
        time_eff = min(100, data.get('estimated_hours', 1) / max(data.get('actual_hours', 1), 1) * 100)
        ontime_score = 100 if not data.get('is_overdue') else 60
        
        overall = (time_eff * 0.5 + ontime_score * 0.5)
        
        return {
            'quality_score': 80,
            'time_score': round(time_eff, 1),
            'requirement_score': 75,
            'overall': round(overall, 1),
            'analysis': 'Công việc hoàn thành' + (' đúng hạn' if not data.get('is_overdue') else ' trễ hạn'),
            'suggestions': 'Tiếp tục duy trì chất lượng'
        }
    
    # ==================== HELPER METHODS ====================
    
    @api.model
    def _clean_json_response(self, text):
        """Loại bỏ markdown và format JSON response"""
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
        
        if text.endswith('```'):
            text = text[:-3]
        
        return text.strip()
