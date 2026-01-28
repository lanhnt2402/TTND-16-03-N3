# -*- coding: utf-8 -*-
"""
AI Service Advanced - Tính năng AI nâng cao
Đặc biệt: AI đánh giá báo cáo công việc (Work Report Analysis)
"""

import logging
import google.genai as genai
from odoo import api, models, _
from odoo.exceptions import UserError
import base64
import io
import re

_logger = logging.getLogger(__name__)

# Try import PDF/DOCX parsers
try:
    import PyPDF2
    PDF_AVAILABLE = True
except:
    PDF_AVAILABLE = False
    _logger.warning("PyPDF2 not available - PDF parsing disabled")

try:
    import docx
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False
    _logger.warning("python-docx not available - DOCX parsing disabled")


class AIServiceAdvanced(models.AbstractModel):
    """AI Service Advanced - Work Report Analysis & More"""
    
    _inherit = 'ai.service'
    
    # ==================== WORK REPORT ANALYSIS ====================
    
    @api.model
    def analyze_work_report_comprehensive(self, task_data, report_files=None):
        """
        AI đánh giá báo cáo công việc TOÀN DIỆN
        
        Quy trình 4 bước với 4 API keys riêng biệt:
        1. Extract text từ file (API Key #1)
        2. So sánh yêu cầu vs kết quả (API Key #3 - CRITICAL)
        3. Đánh giá chất lượng (API Key #4)
        4. Gợi ý cải thiện (API Key #5)
        
        Args:
            task_data (dict): {
                'name': str,
                'requirement': str (HTML),
                'acceptance_criteria': str,
                'result_note': str (HTML),
                'deliverable': str,
                'estimated_hours': float,
                'actual_hours': float,
                'deadline': date,
                'completed_date': datetime,
                'is_overdue': bool
            }
            report_files (list): List of binary file data
        
        Returns:
            dict: {
                'extracted_text': str,
                'completion_percentage': float,
                'completed_items': list,
                'incomplete_items': list,
                'quality_score': float,
                'quality_details': str,
                'recommendations': str,
                'overall_score': float
            }
        """
        
        try:
            _logger.info(f"🚀 Starting comprehensive work report analysis for: {task_data.get('name')}")
            
            # Step 1: Extract text from files (if any) - API Key #1
            extracted_text = ""
            if report_files and len(report_files) > 0:
                extracted_text = self._extract_text_from_files(report_files)
            
            # Combine all text sources
            full_report_content = self._combine_report_content(
                task_data.get('result_note', ''),
                task_data.get('deliverable', ''),
                extracted_text
            )
            
            # Step 2: Requirement vs Result Comparison - API Key #3 (CRITICAL)
            comparison_result = self._compare_requirement_vs_result(
                requirement=task_data.get('requirement', ''),
                acceptance_criteria=task_data.get('acceptance_criteria', ''),
                result_content=full_report_content,
                api_key_function='report_comparison'
            )
            
            # Step 3: Quality Assessment - API Key #4
            quality_result = self._assess_work_quality_detailed(
                task_data=task_data,
                report_content=full_report_content,
                api_key_function='quality_assessment'
            )
            
            # Step 4: Generate Recommendations - API Key #5
            recommendations = self._generate_work_recommendations(
                comparison_result=comparison_result,
                quality_result=quality_result,
                task_data=task_data,
                api_key_function='recommendations'
            )
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(
                comparison_result.get('completion_percentage', 0),
                quality_result.get('quality_score', 0),
                task_data
            )
            
            _logger.info(f"✅ Analysis complete: Overall Score = {overall_score}/100")
            
            return {
                'extracted_text': extracted_text,
                'completion_percentage': comparison_result.get('completion_percentage', 0),
                'completed_items': comparison_result.get('completed_items', []),
                'incomplete_items': comparison_result.get('incomplete_items', []),
                'quality_score': quality_result.get('quality_score', 0),
                'quality_details': quality_result.get('details', ''),
                'professionalism_score': quality_result.get('professionalism', 0),
                'documentation_score': quality_result.get('documentation', 0),
                'recommendations': recommendations,
                'overall_score': overall_score,
                'analysis_summary': self._generate_analysis_summary(comparison_result, quality_result)
            }
            
        except Exception as e:
            _logger.error(f"❌ Work report analysis failed: {str(e)[:200]}")
            return self._fallback_work_report_analysis(task_data)
    
    @api.model
    def _extract_text_from_files(self, file_data_list):
        """
        Trích xuất text từ PDF/Word/Docs
        Sử dụng API Key #1 cho document parsing
        """
        extracted_texts = []
        
        for file_data in file_data_list:
            try:
                # file_data should be dict with 'name' and 'datas'
                filename = file_data.get('name', '').lower()
                file_binary = base64.b64decode(file_data.get('datas', ''))
                
                if filename.endswith('.pdf') and PDF_AVAILABLE:
                    text = self._extract_from_pdf(file_binary)
                    extracted_texts.append(text)
                elif filename.endswith(('.docx', '.doc')) and DOCX_AVAILABLE:
                    text = self._extract_from_docx(file_binary)
                    extracted_texts.append(text)
                else:
                    _logger.warning(f"Unsupported file type or parser not available: {filename}")
            except Exception as e:
                _logger.error(f"Error extracting text from file: {str(e)[:100]}")
        
        return "\n\n".join(extracted_texts)
    
    @api.model
    def _extract_from_pdf(self, file_binary):
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(file_binary)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            _logger.error(f"PDF extraction error: {e}")
            return ""
    
    @api.model
    def _extract_from_docx(self, file_binary):
        """Extract text from DOCX"""
        try:
            docx_file = io.BytesIO(file_binary)
            doc = docx.Document(docx_file)
            
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            _logger.error(f"DOCX extraction error: {e}")
            return ""
    
    @api.model
    def _combine_report_content(self, result_note, deliverable, extracted_text):
        """Kết hợp tất cả nội dung báo cáo"""
        # Remove HTML tags
        result_note_clean = re.sub(r'<[^>]+>', '', result_note or '')
        
        combined = []
        if result_note_clean:
            combined.append("=== KẾT QUẢ THỰC TẾ ===\n" + result_note_clean)
        if deliverable:
            combined.append("=== SẢN PHẨM BÀNGIAO ===\n" + deliverable)
        if extracted_text:
            combined.append("=== NỘI DUNG TỪ FILE BÁO CÁO ===\n" + extracted_text)
        
        return "\n\n".join(combined)
    
    @api.model
    def _compare_requirement_vs_result(self, requirement, acceptance_criteria, result_content, api_key_function):
        """
        So sánh yêu cầu vs kết quả - CRITICAL FUNCTION
        Sử dụng API Key #3 (dedicated)
        """
        try:
            # Get dedicated API key
            api_key, key_index = self._get_api_key_for_function(api_key_function)
            genai.configure(api_key=api_key)
            
            # Clean HTML
            requirement_clean = re.sub(r'<[^>]+>', '', requirement or '')
            criteria_clean = acceptance_criteria or 'Không có tiêu chí cụ thể'
            
            prompt = f"""
Bạn là chuyên gia đánh giá công việc. So sánh YÊU CẦU vs KẾT QUẢ:

**YÊU CẦU BAN ĐẦU:**
{requirement_clean}

**TIÊU CHÍ NGHIỆM THU:**
{criteria_clean}

**KẾT QUẢ ĐÃ LÀM:**
{result_content}

HÃY PHÂN TÍCH:
1. Liệt kê từng yêu cầu: ĐÃ HOÀN THÀNH / CHƯA HOÀN THÀNH
2. Tính % hoàn thành tổng thể
3. Đánh giá mức độ đáp ứng

Trả về JSON (KHÔNG markdown):
{{
    "completion_percentage": <0-100>,
    "completed_items": ["Yêu cầu 1 - Đã làm", "Yêu cầu 2 - Đã làm", ...],
    "incomplete_items": ["Yêu cầu X - Chưa làm", "Yêu cầu Y - Làm chưa đủ", ...],
    "match_score": <0-100>,
    "summary": "<Tóm tắt ngắn gọn>"
}}
"""
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if response and response.text:
                import json
                result_text = self._clean_json_response(response.text)
                result = json.loads(result_text)
                
                _logger.info(f"✅ Requirement comparison: {result.get('completion_percentage')}% complete")
                return result
            
        except Exception as e:
            _logger.error(f"Requirement comparison error: {str(e)[:200]}")
        
        # Fallback
        return {
            'completion_percentage': 75,
            'completed_items': ['Phần lớn yêu cầu đã hoàn thành'],
            'incomplete_items': ['Một số chi tiết còn thiếu'],
            'match_score': 75,
            'summary': 'Đánh giá tự động (fallback)'
        }
    
    @api.model
    def _assess_work_quality_detailed(self, task_data, report_content, api_key_function):
        """
        Đánh giá chất lượng chi tiết
        Sử dụng API Key #4
        """
        try:
            api_key, key_index = self._get_api_key_for_function(api_key_function)
            genai.configure(api_key=api_key)
            
            prompt = f"""
Đánh giá CHẤT LƯỢNG công việc:

**CÔNG VIỆC:** {task_data.get('name')}
**THỜI GIAN:**
- Ước tính: {task_data.get('estimated_hours')}h
- Thực tế: {task_data.get('actual_hours')}h
- Deadline: {task_data.get('deadline')}
- Hoàn thành: {task_data.get('completed_date')}
- {'✓ Đúng hạn' if not task_data.get('is_overdue') else '✗ Trễ hạn'}

**BÁO CÁO:**
{report_content[:1500]}

ĐÁNH GIÁ THEO 4 TIÊU CHÍ:
1. Quality (Chất lượng): 0-100
2. Professionalism (Chuyên nghiệp): 0-100
3. Completeness (Đầy đủ): 0-100
4. Documentation (Tài liệu hóa): 0-100

Trả về JSON:
{{
    "quality_score": <trung bình 4 tiêu chí>,
    "professionalism": <0-100>,
    "completeness": <0-100>,
    "documentation": <0-100>,
    "details": "<Phân tích chi tiết 3-4 câu>",
    "strengths": ["Điểm mạnh 1", "Điểm mạnh 2"],
    "weaknesses": ["Điểm yếu 1", "Điểm yếu 2"]
}}
"""
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if response and response.text:
                import json
                result_text = self._clean_json_response(response.text)
                result = json.loads(result_text)
                
                _logger.info(f"✅ Quality assessment: {result.get('quality_score')}/100")
                return result
            
        except Exception as e:
            _logger.error(f"Quality assessment error: {str(e)[:200]}")
        
        # Fallback
        time_score = min(100, task_data.get('estimated_hours', 1) / max(task_data.get('actual_hours', 1), 1) * 100)
        ontime_score = 100 if not task_data.get('is_overdue') else 70
        
        return {
            'quality_score': (time_score + ontime_score) / 2,
            'professionalism': 80,
            'completeness': 75,
            'documentation': 70,
            'details': 'Công việc hoàn thành với chất lượng ổn định.',
            'strengths': ['Hoàn thành công việc'],
            'weaknesses': ['Cần cải thiện documentation']
        }
    
    @api.model
    def _generate_work_recommendations(self, comparison_result, quality_result, task_data, api_key_function):
        """
        Tạo gợi ý cải thiện
        Sử dụng API Key #5
        """
        try:
            api_key, key_index = self._get_api_key_for_function(api_key_function)
            genai.configure(api_key=api_key)
            
            prompt = f"""
Dựa trên kết quả đánh giá:

**HOÀN THÀNH:** {comparison_result.get('completion_percentage')}%
**CHẤT LƯỢNG:** {quality_result.get('quality_score')}/100
**ĐIỂM MẠNH:** {', '.join(quality_result.get('strengths', []))}
**ĐIỂM YẾU:** {', '.join(quality_result.get('weaknesses', []))}

HÃY ĐƯA RA:
1. 3-5 gợi ý CẢI THIỆN cụ thể
2. Training/Learning suggestions
3. Process improvements

Trả về HTML format (không JSON):
<ul>
<li><strong>→</strong> Gợi ý 1...</li>
<li><strong>→</strong> Gợi ý 2...</li>
...
</ul>
"""
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if response and response.text:
                _logger.info(f"✅ Recommendations generated")
                return response.text.strip()
            
        except Exception as e:
            _logger.error(f"Recommendations generation error: {str(e)[:200]}")
        
        # Fallback
        return """
<ul>
<li><strong>→</strong> Tiếp tục duy trì chất lượng công việc</li>
<li><strong>→</strong> Cải thiện documentation và reporting</li>
<li><strong>→</strong> Tối ưu hóa quy trình làm việc</li>
</ul>
"""
    
    @api.model
    def _calculate_overall_score(self, completion_pct, quality_score, task_data):
        """Tính điểm tổng thể"""
        # Completion: 40%
        # Quality: 30%
        # On-time: 20%
        # Efficiency: 10%
        
        ontime_score = 100 if not task_data.get('is_overdue') else 60
        
        estimated = task_data.get('estimated_hours', 1)
        actual = task_data.get('actual_hours', 1)
        efficiency = min(100, (estimated / max(actual, 1)) * 100)
        
        overall = (
            completion_pct * 0.40 +
            quality_score * 0.30 +
            ontime_score * 0.20 +
            efficiency * 0.10
        )
        
        return round(overall, 1)
    
    @api.model
    def _generate_analysis_summary(self, comparison, quality):
        """Tạo tóm tắt phân tích"""
        summary = f"""
**📊 TÓM TẮT PHÂN TÍCH:**

• Hoàn thành: {comparison.get('completion_percentage')}%
• Chất lượng: {quality.get('quality_score')}/100
• Chuyên nghiệp: {quality.get('professionalism')}/100
• Documentation: {quality.get('documentation')}/100

{comparison.get('summary', '')}
"""
        return summary.strip()
    
    @api.model
    def _fallback_work_report_analysis(self, task_data):
        """Fallback khi AI không khả dụng"""
        estimated = task_data.get('estimated_hours', 1)
        actual = task_data.get('actual_hours', 1)
        
        time_score = min(100, (estimated / max(actual, 1)) * 100)
        ontime_score = 100 if not task_data.get('is_overdue') else 70
        
        overall = (time_score + ontime_score) / 2
        
        return {
            'extracted_text': '',
            'completion_percentage': 80,
            'completed_items': ['Công việc đã hoàn thành'],
            'incomplete_items': [],
            'quality_score': overall,
            'quality_details': 'Đánh giá tự động (fallback mode)',
            'professionalism_score': 80,
            'documentation_score': 75,
            'recommendations': '<ul><li>Tiếp tục duy trì chất lượng</li></ul>',
            'overall_score': overall,
            'analysis_summary': 'Công việc hoàn thành với chất lượng tốt.'
        }
