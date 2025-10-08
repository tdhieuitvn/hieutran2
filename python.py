import streamlit as st
import pandas as pd
import google.generativeai as genai
import docx
import json
import numpy_financial as npf
from io import BytesIO

# --- CẤU HÌNH TRANG STREAMLIT ---
st.set_page_config(
    page_title="App Thẩm Định Dự Án Đầu Tư",
    page_icon="💡",
    layout="wide"
)

st.title("💡 App Thẩm Định Hiệu Quả Dự Án Kinh Doanh")
st.caption("Tải lên phương án kinh doanh (file .docx), AI sẽ tự động phân tích và tính toán.")

# --- CÁC HÀM XỬ LÝ ---

def read_docx_text(file):
    """Đọc nội dung text từ file .docx."""
    try:
        doc = docx.Document(file)
        full_text = [para.text for para in doc.paragraphs]
        return "\n".join(full_text)
    except Exception as e:
        st.error(f"Lỗi khi đọc file Word: {e}")
        return None

def extract_project_data_with_ai(text, api_key):
    """Sử dụng Gemini AI để trích xuất thông tin tài chính từ văn bản."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính. Hãy đọc kỹ văn bản phương án kinh doanh sau và trích xuất các thông tin sau đây dưới dạng JSON.
        Chỉ trả về đối tượng JSON, không giải thích gì thêm.
        Các khóa cần trích xuất:
        - "von_dau_tu": Tổng vốn đầu tư (chỉ lấy số).
        - "vong_doi": Vòng đời dự án tính bằng năm (chỉ lấy số).
        - "doanh_thu_nam": Doanh thu hàng năm (chỉ lấy số).
        - "chi_phi_nam": Chi phí hoạt động hàng năm (chỉ lấy số).
        - "wacc": Chi phí sử dụng vốn bình quân (WACC) dưới dạng số thập phân (ví dụ: 13% là 0.13).
        - "thue_suat": Thuế suất thuế TNDN dưới dạng số thập phân (ví dụ: 20% là 0.20).

        Văn bản cần phân tích:
        ---
        {text}
        ---
        """
        response = model.generate_content(prompt)
        # Loại bỏ các ký tự không phải JSON khỏi response
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)

    except Exception as e:
        st.error(f"Lỗi khi gọi API của Gemini hoặc xử lý JSON: {e}")
        return None

def calculate_cash_flow(data):
    """Xây dựng bảng dòng tiền từ dữ liệu đã trích xuất."""
    try:
        years = int(data['vong_doi'])
        investment = float(data['von_dau_tu'])
        revenue = float(data['doanh_thu_nam'])
        cost = float(data['chi_phi_nam'])
        tax_rate = float(data['thue_suat'])

        ebt = revenue - cost
        tax = ebt * tax_rate
        pat = ebt - tax
        
        # Giả định đơn giản: Dòng tiền thuần = Lợi nhuận sau thuế + Chi phí khấu hao.
        # Vì không có thông tin khấu hao, ta tạm tính NCF = PAT.
        ncf_op = pat

        # Tạo DataFrame
        cash_flow_data = {
            "Năm": range(years + 1),
            "Doanh thu": [0] + [revenue] * years,
            "Chi phí": [0] + [cost] * years,
            "Lợi nhuận trước thuế (EBT)": [0] + [ebt] * years,
            "Thuế TNDN": [0] + [tax] * years,
            "Lợi nhuận sau thuế (PAT)": [0] + [pat] * years,
            "Dòng tiền thuần (NCF)": [-investment] + [ncf_op] * years
        }
        df = pd.DataFrame(cash_flow_data)
        return df
    except Exception as e:
        st.error(f"Lỗi khi tính toán dòng tiền: {e}")
        return None

def calculate_financial_metrics(df, wacc):
    """Tính toán các chỉ số hiệu quả dự án."""
    try:
        ncf = df['Dòng tiền thuần (NCF)'].values
        
        # NPV
        npv = npf.npv(wacc, ncf)
        
        # IRR
        irr = npf.irr(ncf) * 100  # Chuyển sang %
        
        # PP (Payback Period)
        cumulative_cash_flow = ncf.cumsum()
        pp_years = next((i for i, x in enumerate(cumulative_cash_flow) if x > 0), None)
        pp = pp_years - (cumulative_cash_flow[pp_years-1] / ncf[pp_years]) if pp_years is not None else "Không hoàn vốn"

        # DPP (Discounted Payback Period)
        discounted_ncf = [val / ((1 + wacc) ** i) for i, val in enumerate(ncf)]
        cumulative_discounted_ncf = pd.Series(discounted_ncf).cumsum()
        dpp_years = next((i for i, x in enumerate(cumulative_discounted_ncf) if x > 0), None)
        dpp = dpp_years - (cumulative_discounted_ncf[dpp_years-1] / discounted_ncf[dpp_years]) if dpp_years is not None else "Không hoàn vốn"
        
        return {"NPV": npv, "IRR": irr, "PP": pp, "DPP": dpp}
    except Exception as e:
        st.error(f"Lỗi khi tính toán chỉ số tài chính: {e}")
        return None

def get_ai_analysis(metrics_data, api_key):
    """Yêu cầu AI phân tích các chỉ số hiệu quả dự án."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Bạn là một chuyên gia thẩm định dự án đầu tư. Dựa trên các chỉ số hiệu quả tài chính sau đây, hãy đưa ra một bài phân tích ngắn gọn, chuyên nghiệp (khoảng 3-4 đoạn).
        
        Các chỉ số cần phân tích:
        - NPV: {metrics_data['NPV']:,.0f} VNĐ
        - IRR: {metrics_data['IRR']:.2f}%
        - Thời gian hoàn vốn (PP): {metrics_data['PP']:.2f} năm
        - Thời gian hoàn vốn có chiết khấu (DPP): {metrics_data['DPP']:.2f} năm

        Nội dung phân tích cần bao gồm:
        1. Giải thích ý nghĩa của từng chỉ số trong bối cảnh dự án này.
        2. Đánh giá mức độ khả thi và hấp dẫn của dự án dựa trên các chỉ số.
        3. Đưa ra kết luận cuối cùng: "Dự án có hiệu quả về mặt tài chính" hay "Dự án không hiệu quả về mặt tài chính".
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Lỗi khi gọi API để phân tích: {e}"

# --- GIAO DIỆN ỨNG DỤNG ---
api_key = st.sidebar.text_input("Nhập Gemini API Key của bạn", type="password")

uploaded_file = st.sidebar.file_uploader(
    "Tải lên Phương án kinh doanh (.docx)",
    type=['docx']
)

# Khởi tạo session state
if 'project_data' not in st.session_state:
    st.session_state.project_data = None
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False

if uploaded_file is not None:
    doc_text = read_docx_text(BytesIO(uploaded_file.getvalue()))
    
    if doc_text and api_key:
        if st.button("1. Trích xuất dữ liệu với AI"):
            with st.spinner("AI đang đọc và phân tích file..."):
                st.session_state.project_data = extract_project_data_with_ai(doc_text, api_key)
                st.session_state.analysis_done = False # Reset khi có dữ liệu mới
            
            if st.session_state.project_data:
                st.success("Đã trích xuất dữ liệu thành công!")
            else:
                st.error("Không thể trích xuất dữ liệu. Vui lòng kiểm tra lại file Word hoặc API Key.")

    if st.session_state.project_data:
        st.subheader("Bảng tóm tắt thông số dự án")
        st.json(st.session_state.project_data)
        
        # Tính toán và hiển thị
        df_cash_flow = calculate_cash_flow(st.session_state.project_data)
        
        if df_cash_flow is not None:
            st.subheader("2. Bảng Dòng Tiền Dự Kiến (Đơn vị: VNĐ)")
            st.dataframe(df_cash_flow.style.format("{:,.0f}"))

            metrics = calculate_financial_metrics(df_cash_flow, st.session_state.project_data['wacc'])
            
            if metrics:
                st.subheader("3. Các Chỉ Số Đánh Giá Hiệu Quả Dự Án")
                st.session_state.analysis_done = True
                
                col1, col2 = st.columns(2)
                col3, col4 = st.columns(2)
                
                col1.metric("NPV (Giá trị hiện tại ròng)", f"{metrics['NPV']:,.0f} VNĐ")
                col2.metric("IRR (Tỷ suất hoàn vốn nội bộ)", f"{metrics['IRR']:.2f}%")
                col3.metric("Thời gian hoàn vốn (PP)", f"{metrics['PP']:.2f} năm" if isinstance(metrics['PP'], (int, float)) else "N/A")
                col4.metric("Thời gian hoàn vốn có chiết khấu (DPP)", f"{metrics['DPP']:.2f} năm" if isinstance(metrics['DPP'], (int, float)) else "N/A")

    if st.session_state.analysis_done:
        st.subheader("4. Phân Tích Hiệu Quả Dự Án từ AI")
        if st.button("Yêu cầu AI Phân Tích"):
            if api_key:
                with st.spinner("AI đang phân tích các chỉ số..."):
                    metrics = calculate_financial_metrics(df_cash_flow, st.session_state.project_data['wacc'])
                    ai_feedback = get_ai_analysis(metrics, api_key)
                    st.info(ai_feedback)
            else:
                st.error("Vui lòng nhập API Key để thực hiện phân tích.")
else:
    st.info("Vui lòng nhập API Key và tải lên file .docx để bắt đầu.")
