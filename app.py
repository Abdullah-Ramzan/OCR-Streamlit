import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials
import json
import re
from google.oauth2 import service_account

# ✅ Groq API setup
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

# ✅ Google Sheets setup
#GOOGLE_CREDENTIALS_FILE = 'ocr-streamlit-461706-8236ac858ab9.json'
# Get credentials from Streamlit secrets
# Define the scope your app needs
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials from secrets
credentials = Credentials.from_service_account_info(
    st.secrets["google"],
    scopes=SCOPES
)

# Authorize gspread client with credentials
client = gspread.authorize(credentials)
GOOGLE_SHEET_ID = '1UjJj0e4CgPT2RwUFy93rlRI-SRFFfVMC8Z4GbL1fHaI'
SHEET_NAME = 'Sheet1'


scope = ["https://www.googleapis.com/auth/spreadsheets"]
#credentials = Credentials.from_service_account_file(credentials, scopes=scope)
#client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_NAME)

# ✅ UI


# ✅ OCR Functions
def extract_text_from_pdf(file_bytes):
    images = convert_from_bytes(file_bytes)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img)
    return text

def extract_text_from_image(file_bytes):
    image = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(image)

# ✅ LLaMA3 via Groq
def analyze_with_llama(text):
    prompt = f"""
You are a resume parsing assistant. Extract the following details from the resume in JSON format:
{{
    "name": "",
    "phone": "",
    "email": "",
    "address": "",
    "education": "",
    "experience": "",
    "recommended_role": ""
}}

Here is the list of available industries and roles to choose from for the 'recommended_role' field:

  Industry and Manufacturing  
- Automotive  
- Aerospace and aviation  
- Food and beverage  
- Chemical and pharmaceutical  
- Textile, footwear, and fashion  
- Metallurgy and steel industry  
- Machinery and industrial equipment  
- Wood and furniture  
- Plastics and derivatives  
- Paper and printing  
- Energy and environment (renewables, oil, gas)  
- Electrical and electronic equipment  

  Tourism, Hospitality, and Leisure  
- Hotels and accommodations  
- Restaurants and catering  
- Travel agencies and tour operators  
- Entertainment and shows  
- Theme parks and cultural attractions  

  Technology and Communications  
- Software and app development  
- IT services and tech consulting  
- Cybersecurity  
- Telecommunications  
- Artificial intelligence and big data  
- E-commerce and digital platforms  

  Professional and Business Services  
- Strategic and business consulting  
- Human Resources and recruitment  
- Legal services and law firms  
- Accounting and auditing  
- Marketing and advertising  
- Design and branding  

  Health and Wellness  
- Hospitals and medical centers  
- Pharmaceuticals and biotechnology  
- Dental and eye clinics  
- Aesthetics and wellness centers  
- Elderly care and retirement homes  

 Education and Training  
- Schools and universities  
- Vocational training  
- Online education and e-learning  
- Language schools  

  Construction and Infrastructure  
- Residential and commercial construction  
- Public works and infrastructure  
- Real estate development  
- Civil engineering and architecture  

 Logistics, Transport, and International Trade  
- Land, sea, and air transport  
- Warehousing and distribution  
- International trade and customs  
- Parcel delivery and courier services  

 Retail and Consumer Goods  
- Supermarkets and large retailers  
- E-commerce  
- Specialized retail stores  
- Wholesale trade  

 Agribusiness and Fishing  
- Agriculture and livestock  
- Agro-food industry  
- Fishing and aquaculture  
- Wine production and viticulture  

 Finance and Insurance  
- Banks and financial institutions  
- Fintech  
- Insurance companies and brokers  
- Investment funds and asset management  

  Environment and Renewable Energy  
- Solar, wind, and hydroelectric energy  
- Waste treatment and recycling  
- Water management  
- Environmental consulting  

Based on the resume text, extract the JSON and choose the most appropriate 'recommended_role' from the above list.

Here is the resume text:
\"\"\"
{text}
\"\"\"
Only respond with valid JSON.
"""

    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": "You extract structured resume data and return only valid JSON."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# ✅ Parse LLaMA output safely
def clean_and_parse_json(raw_output):
    try:
        match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        json_str = match.group(0)
        return json.loads(json_str)
    except Exception as e:
        st.error("❌ Failed to parse JSON from model output.")
        st.code(raw_output)
        return None

# ✅ Flatten experience (handle list of dicts or plain string)
def flatten_experience(exp):
    if isinstance(exp, list):
        return "; ".join(
            f"{e.get('role', '')} at {e.get('company', '')} ({e.get('duration', '')})"
            for e in exp
        )
    return exp if isinstance(exp, str) else str(exp)

# ✅ Append to Google Sheet
def append_to_sheet(data_dict):
    row = [
        data_dict.get("name", ""),
        data_dict.get("phone", ""),
        data_dict.get("email", ""),
        data_dict.get("address", ""),
        data_dict.get("education", ""),
        flatten_experience(data_dict.get("experience", "")),
        data_dict.get("recommended_role", "")
    ]
    sheet.append_row(row)

# ✅ Main Workflow
uploaded_files = st.file_uploader(
    "Upload CVs (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True
)

if "texts" not in st.session_state:
    st.session_state.texts = {}
if "results" not in st.session_state:
    st.session_state.results = {}

if uploaded_files:
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name

        if file_name not in st.session_state.texts:
            file_bytes = uploaded_file.read()
            if file_name.lower().endswith(".pdf"):
                extracted_text = extract_text_from_pdf(file_bytes)
            else:
                extracted_text = extract_text_from_image(file_bytes)
            st.session_state.texts[file_name] = extracted_text

        # Editable OCR text
        st.subheader(f"📝 Extracted & Editable Text: {file_name}")
        st.session_state.texts[file_name] = st.text_area(
            f"Edit text from {file_name}",
            value=st.session_state.texts[file_name],
            height=300,
            key=f"edited_text_{file_name}"
        )

        # Analyze after editing
        if st.button(f"🔍 Analyze with LLaMA: {file_name}"):
            with st.spinner("Analyzing with LLaMA3..."):
                llama_response = analyze_with_llama(st.session_state.texts[file_name])
                structured_data = clean_and_parse_json(llama_response)

                if structured_data:
                    st.session_state.results[file_name] = structured_data
                    st.success(f"✅ Data extracted for {file_name}")

# Display parsed results for editing and Google Sheet append

    if st.button("✅ Append All to Google Sheet"):
        for final_data in st.session_state.results.values():
            append_to_sheet(final_data)
        st.success("✅ All valid entries appended successfully.")
        st.session_state.results.clear()
        st.session_state.texts.clear()