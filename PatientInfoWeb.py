import streamlit as st
import mysql.connector
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import tempfile
from datetime import datetime
import time
import os
import random
import base64
import textwrap
import barcode
from barcode.writer import ImageWriter
from barcode.codex import Code128

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'digital_health_db'
}


def create_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error connecting to MySQL: {err}")
        return None


def initialize_database():
    conn = create_db_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS digital_health_db")
        cursor.execute("USE digital_health_db")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(10),
                full_name VARCHAR(100) NOT NULL,
                other_names VARCHAR(100),
                gender VARCHAR(20),
                address_line1 VARCHAR(100),
                address_line2 VARCHAR(100),
                district VARCHAR(50),
                province VARCHAR(50),
                mh_division VARCHAR(50),
                birthday DATE,
                age VARCHAR(20),
                nic VARCHAR(20) UNIQUE,
                phn VARCHAR(50) UNIQUE,
                marital_status VARCHAR(20),
                guardian VARCHAR(100),
                contact_numbers VARCHAR(100),
                occupation VARCHAR(50),
                blood_type VARCHAR(10),
                known_allergies TEXT,
                chronic_conditions TEXT,
                primary_physician VARCHAR(100),
                avatar BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error initializing database: {err}")
        return False
    finally:
        if conn:
            conn.close()


def generate_phn(nic=None):
    hospital_id = "1250"
    timestamp = datetime.now().strftime("%y%m%d%H%M")
    nic_part = nic[-4:] if nic and len(nic) >= 4 else f"{random.randint(1000, 9999):04d}"
    phn = f"PHN-{hospital_id}-{timestamp}-{nic_part}"
    return phn

def create_fallback_barcode(text, width, height):
    """Create a simple barcode when python-barcode is not available"""
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Create binary pattern from text hash
    text_hash = hash(text) & 0xffffffff  # Get consistent 32-bit hash
    binary_str = bin(text_hash)[2:].zfill(32)  # Convert to 32-bit binary

    # Draw barcode lines
    bar_width = max(1, width // 32)
    for i, bit in enumerate(binary_str):
        x = i * bar_width
        if bit == '1':
            draw.rectangle([x, 0, x + bar_width, height - 20], fill="black")

    # Add text below
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()

    text_width = draw.textlength(text, font=font)
    draw.text(((width - text_width) / 2, height - 20), text, font=font, fill="black")
    return img


def generate_label_image(patient_data):
    """Generate label with ultra high DPI (600) for maximum print quality"""
    # Dimensions for 10cm x 4.3cm at 600 DPI
    width, height = 2362, 1016  # 10cm x 4.3cm at 600 DPI

    # Create blank image with white background
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        # Load fonts with larger sizes for better readability
        title_font = ImageFont.truetype("arialbd.ttf", 80)  # Increased for 600 DPI
        header_font = ImageFont.truetype("arialbd.ttf", 64)  # Increased for 600 DPI
        normal_font = ImageFont.truetype("arial.ttf", 58)  # Increased for 600 DPI
        small_font = ImageFont.truetype("arial.ttf", 55)  # Increased for 600 DPI
    except:
        # Fallback to default fonts
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Start position
    y_position = 60

    # Hospital name - Centered at top
    hospital = "GENERAL HOSPITAL ABCDEFG"
    bbox = draw.textbbox((0, 0), hospital, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, y_position), hospital, font=title_font, fill=(0, 0, 0))
    y_position += 100

    # Patient name - Centered
    name = f"{patient_data.get('title', '')} {patient_data.get('full_name', '')}"
    bbox = draw.textbbox((0, 0), name, font=header_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, y_position), name, font=header_font, fill=(0, 0, 0))
    y_position += 80

    # Address line (single line)
    address_line1 = patient_data.get('address_line1', '')
    if address_line1:
        # Allow more characters due to larger sticker size
        if len(address_line1) > 45:
            address_line1 = address_line1[:42] + "..."

        bbox = draw.textbbox((0, 0), address_line1, font=header_font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        draw.text((text_x, y_position), address_line1, font=header_font, fill=(0, 0, 0))
        y_position += 70

    # Contact number
    contact_text = f"Tel: {patient_data.get('contact_numbers', '')}"
    if len(contact_text) > 35:
        contact_text = contact_text[:32] + "..."

    bbox = draw.textbbox((0, 0), contact_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, y_position), contact_text, font=title_font, fill=(0, 0, 0))
    y_position += 80

    # Generate barcode with proper width for the new sticker size
    barcode_img = generate_barcode(patient_data, target_width_cm=8.0)  # 8cm wide barcode

    # Center barcode horizontally
    barcode_x = (width - barcode_img.width) // 2
    img.paste(barcode_img, (barcode_x, y_position))

    # Add timestamp below PHN
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    bbox = draw.textbbox((0, 0), timestamp, font=header_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, y_position + barcode_img.height - 40), timestamp, font=header_font, fill=(0, 0, 0))

    return img

def print_barcode_web(barcode_img, patient_phn, patient_data=None):
    """Provide ultra high-quality output for both download and print"""
    try:
        # Create the highest quality image for both functions at 600 DPI
        high_quality_buffer = BytesIO()
        barcode_img.save(high_quality_buffer, format="PNG", dpi=(600, 600))
        barcode_bytes = high_quality_buffer.getvalue()

        # Create a base64 version for the print function
        img_str = base64.b64encode(barcode_bytes).decode()

        # Download button
        st.download_button(
            label="📥 Download Ultra High-Quality Barcode (600 DPI)",
            data=barcode_bytes,
            file_name=f"barcode_{patient_phn}.png",
            mime="image/png",
            use_container_width=True,
            help="Download ultra high-resolution barcode for printing"
        )

        # Print button with direct image handling
        html_code = f"""
        <div style="text-align: center; margin: 15px 0;">
            <button onclick="printDirectImage()" 
                    style="padding: 12px 24px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">
                🖨️ Print Ultra High-Quality Barcode
            </button>
        </div>

        <script>
        function printDirectImage() {{
            // Create a new window for printing
            var printWindow = window.open('', '_blank');

            if (!printWindow) {{
                alert('Please allow pop-ups for this site to print the barcode.');
                return;
            }}

            // Write the HTML content with exact dimensions for 10cm x 4.3cm
            printWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Print Barcode - {patient_phn}</title>
                    <style>
                        @page {{
                            size: 100mm 43mm;
                            margin: 0;
                            padding: 0;
                        }}
                        body {{
                            margin: 0;
                            padding: 0;
                            width: 100mm;
                            height: 43mm;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            background: white;
                        }}
                        .barcode-container {{
                            width: 100%;
                            height: 100%;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                        }}
                        img {{
                            width: 100%;
                            height: 100%;
                            object-fit: contain;
                            image-rendering: crisp-edges;
                        }}
                    </style>
                </head>
                <body>
                    <div class="barcode-container">
                        <img src="data:image/png;base64,{img_str}" 
                             alt="Patient Barcode: {patient_phn}"
                             onload="setTimeout(function() {{ 
                                 window.print(); 
                                 setTimeout(function() {{ window.close(); }}, 100);
                             }}, 500)">
                    </div>
                </body>
                </html>
            `);

            printWindow.document.close();
        }}
        </script>
        """
        st.components.v1.html(html_code, height=100)

    except Exception as e:
        st.error(f"Error preparing barcode for printing: {e}")


def generate_barcode(patient_data, target_width_cm=8.0):
    """Generate a properly sized barcode with ultra high DPI (600)"""
    try:
        # Get PHN from patient data
        patient_phn = patient_data.get('phn', '')
        if not patient_phn:
            patient_phn = "PHN-NOT-FOUND"

        # Remove dashes for barcode encoding
        clean_phn = patient_phn.replace('-', '')

        # Calculate exact pixel dimensions at 600 DPI
        dpi = 600
        target_width_px = int(target_width_cm / 2.54 * dpi)  # Convert cm to pixels

        # Use python-barcode library with optimized settings
        code128 = barcode.get_barcode_class('code128')
        barcode_obj = code128(clean_phn, writer=ImageWriter())

        # Configure barcode options for proper size at 600 DPI
        options = {
            'module_width': 1.5,  # Adjusted for proper barcode width
            'module_height': 40.0,  # Proper barcode height at 600 DPI
            'quiet_zone': 12.0,  # Adequate quiet zone at 600 DPI
            'font_size': 35,  # Readable font size for barcode text at 600 DPI
            'text_distance': 16,  # Proper text spacing at 600 DPI
            'background': 'white',
            'foreground': 'black',
            'write_text': True,
            'dpi': dpi
        }

        # Generate barcode image
        buffer = BytesIO()
        barcode_obj.write(buffer, options=options)
        buffer.seek(0)
        img = Image.open(buffer)

        # Resize to exact width with high-quality interpolation
        current_width, current_height = img.size
        scaling_factor = target_width_px / current_width
        target_height = int(current_height * scaling_factor)

        return img.resize((target_width_px, target_height), Image.LANCZOS)

    except Exception as e:
        st.error(f"Barcode generation error: {e}")
        return create_fallback_barcode(patient_phn, target_width_px, target_height)


def create_precise_fallback_barcode(text, width_cm, height_cm):
    """Create a precise fallback barcode with exact dimensions"""
    dpi = 600
    width_px = int(width_cm / 2.54 * dpi)
    height_px = int(height_cm / 2.54 * dpi)

    img = Image.new('RGB', (width_px, height_px), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Create a simple pattern that resembles a barcode
    pattern_length = 40  # Number of bars
    bar_width = width_px / pattern_length

    for i in range(pattern_length):
        # Alternate between black and white bars
        if i % 2 == 0:
            x_start = i * bar_width
            x_end = (i + 1) * bar_width
            draw.rectangle([x_start, 0, x_end, height_px], fill="black")

    # Add text below
    try:
        font_size = int(height_px * 0.2)
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    text_width = draw.textlength(text, font=font)
    text_x = (width_px - text_width) / 2
    text_y = height_px - font_size - 5
    draw.text((text_x, text_y), text, font=font, fill="black")

    return img


def clear_form():
    """Completely reset the form and session state"""
    # Reset all form fields to default values
    st.session_state.patient_data = {
        'title': 'Mr.',
        'full_name': '',
        'other_names': '',
        'gender': 'Male',
        'address_line1': '',
        'address_line2': '',
        'district': 'Kegalle',
        'province': 'Sabaragamuwa',
        'mh_division': '',
        'birthday': datetime.now().date(),
        'age': '',
        'nic': '',
        'phn': '',
        'marital_status': 'Single',
        'guardian': '',
        'contact_numbers': '',
        'occupation': 'Student',
        'blood_type': 'A+',
        'known_allergies': '',
        'chronic_conditions': '',
        'primary_physician': 'Dr. S. Perera'
    }

    # Clear avatar and any other temporary data
    keys_to_remove = ['avatar_img', 'reprint_patient']
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]

    # Force a rerun to update all widgets
    st.rerun()


def main():
    st.set_page_config(
        page_title="Patient Information System",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("Patient Information System")
    st.markdown("## General Hospital Abcdefg - Patient Registration")

    # Initialize database
    if 'db_initialized' not in st.session_state:
        if initialize_database():
            st.session_state.db_initialized = True
        else:
            st.error("Database initialization failed!")

    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Personal Info", "Contact Info", "Medical Info", "Avatar", "Reprint"
    ])

    # Initialize session state for form data
    if 'patient_data' not in st.session_state:
        st.session_state.patient_data = {
            'title': 'Mr.',
            'full_name': '',
            'other_names': '',
            'gender': 'Male',
            'address_line1': '',
            'address_line2': '',
            'district': 'Kegalle',
            'province': 'Sabaragamuwa',
            'mh_division': '',
            'birthday': datetime.now().date(),
            'age': '',
            'nic': '',
            'phn': '',
            'marital_status': 'Single',
            'guardian': '',
            'contact_numbers': '',
            'occupation': 'Student',
            'blood_type': 'A+',
            'known_allergies': '',
            'chronic_conditions': '',
            'primary_physician': 'Dr. S. Perera'
        }

    # Personal Info Tab
    with tab1:
        st.header("Personal Details")

        col1, col2 = st.columns(2)

        with col1:
            st.session_state.patient_data['title'] = st.selectbox(
                "Title",
                ["Mr.", "Mrs.", "Miss", "Master", "Baby", "Ven.", "Dr.", "Other"],
                index=0,
                key="title_select"
            )
            st.session_state.patient_data['full_name'] = st.text_input(
                "FULL NAME:*",
                value=st.session_state.patient_data['full_name'],
                key="full_name_input"
            )
            st.session_state.patient_data['other_names'] = st.text_input(
                "Other Names:",
                value=st.session_state.patient_data['other_names'],
                key="other_names_input"
            )
            st.session_state.patient_data['gender'] = st.selectbox(
                "Gender:*",
                ["Male", "Female", "Prefer not to say"],
                index=0,
                key="gender_select"
            )

        with col2:
            try:
                st.session_state.patient_data['birthday'] = st.date_input(
                    "Birthday:",
                    value=st.session_state.patient_data['birthday'],
                    min_value=datetime(1900, 1, 1),
                    max_value=datetime.now().date(),
                    key="birthday_input"
                )
            except Exception as e:
                st.error(f"Error with date input: {e}")
                st.session_state.patient_data['birthday'] = datetime.now().date()

            st.session_state.patient_data['nic'] = st.text_input(
                "NIC Number:",
                value=st.session_state.patient_data['nic'],
                key="nic_input"
            )

            phn_col1, phn_col2 = st.columns([3, 1])
            with phn_col1:
                st.session_state.patient_data['phn'] = st.text_input(
                    "PHN:*",
                    value=st.session_state.patient_data['phn'],
                    key="phn_input"
                )
            with phn_col2:
                if st.button("Generate PHN", use_container_width=True, key="generate_phn_btn"):
                    st.session_state.patient_data['phn'] = generate_phn(
                        st.session_state.patient_data['nic']
                    )
                    st.rerun()

    # Contact Info Tab
    with tab2:
        st.header("Contact Details")

        col1, col2 = st.columns(2)

        with col1:
            st.session_state.patient_data['address_line1'] = st.text_input(
                "Address Line 1:*",
                value=st.session_state.patient_data['address_line1'],
                key="address_line1_input"
            )
            st.session_state.patient_data['address_line2'] = st.text_input(
                "Address Line 2:",
                value=st.session_state.patient_data['address_line2'],
                key="address_line2_input"
            )
            st.session_state.patient_data['district'] = st.selectbox(
                "District:*",
                ["Kegalle", "Gampaha", "Kalutara", "Kandy", "Matale", "Nuwara Eliya",
                 "Galle", "Matara", "Hambantota", "Jaffna", "Kilinochchi", "Mannar",
                 "Vavuniya", "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee",
                 "Kurunegala", "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla",
                 "Monaragala", "Ratnapura", "Colombo"],
                index=0,
                key="district_select"
            )

        with col2:
            st.session_state.patient_data['province'] = st.selectbox(
                "Province:*",
                ["Sabaragamuwa", "Central", "Southern", "Northern", "Eastern",
                 "North Western", "North Central", "Uva", "Western"],
                index=8,
                key="province_select"
            )
            st.session_state.patient_data['mh_division'] = st.text_input(
                "MOH Division:",
                value=st.session_state.patient_data['mh_division'],
                key="mh_division_input"
            )
            st.session_state.patient_data['contact_numbers'] = st.text_input(
                "Contact Numbers:*",
                value=st.session_state.patient_data['contact_numbers'],
                key="contact_numbers_input"
            )

    # Medical Info Tab
    with tab3:
        st.header("Medical Information")

        col1, col2 = st.columns(2)

        with col1:
            st.session_state.patient_data['blood_type'] = st.selectbox(
                "Blood Type:",
                ["Unknown", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                index=1,
                key="blood_type_select"
            )
            st.session_state.patient_data['known_allergies'] = st.text_area(
                "Known Allergies:",
                value=st.session_state.patient_data['known_allergies'],
                key="known_allergies_input"
            )

        with col2:
            st.session_state.patient_data['chronic_conditions'] = st.text_area(
                "Chronic Conditions:",
                value=st.session_state.patient_data['chronic_conditions'],
                key="chronic_conditions_input"
            )
            st.session_state.patient_data['primary_physician'] = st.selectbox(
                "Primary Physician:",
                ["", "Dr. S. Perera", "Dr. R. Fernando", "Dr. M. Silva",
                 "Dr. J. Rajapaksa", "Dr. L. Dias"],
                index=1,
                key="primary_physician_select"
            )

    # Avatar Tab with improved cropping and clearing
    with tab4:
        st.header("Patient Avatar")

        # Option 1: File upload
        uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"], key="avatar_uploader")
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.session_state.avatar_img = image

        # Option 2: Camera input (built into Streamlit)
        picture = st.camera_input("Or take a picture", key="avatar_camera")
        if picture:
            image = Image.open(BytesIO(picture.getvalue()))
            st.session_state.avatar_img = image

        # Display and cropping functionality
        if 'avatar_img' in st.session_state and st.session_state.avatar_img is not None:
            img = st.session_state.avatar_img

            # Display the image
            st.image(img, caption="Original Image", width='stretch')

            # Create a simple but effective cropping interface
            st.subheader("Crop Image")
            st.write("Select the area to crop using the sliders below")

            # Get image dimensions
            img_width, img_height = img.size

            # Create sliders for cropping coordinates
            col1, col2 = st.columns(2)

            with col1:
                left = st.slider("Left", 0, img_width, 0, key="crop_left")
                right = st.slider("Right", 0, img_width, img_width, key="crop_right")

            with col2:
                top = st.slider("Top", 0, img_height, 0, key="crop_top")
                bottom = st.slider("Bottom", 0, img_height, img_height, key="crop_bottom")

            # Ensure valid coordinates
            if left >= right:
                right = left + 1
            if top >= bottom:
                bottom = top + 1

            # Display crop preview
            try:
                cropped_preview = img.crop((left, top, right, bottom))
                st.image(cropped_preview, caption="Cropped Preview", width='stretch')

                # Crop button
                if st.button("Apply Crop", key="apply_crop_btn"):
                    st.session_state.avatar_img = cropped_preview
                    st.success("Image cropped successfully!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error cropping image: {e}")

        # Clear avatar button
        if st.button("Clear Avatar", key="clear_avatar_btn"):
            if 'avatar_img' in st.session_state:
                del st.session_state.avatar_img
            st.success("Avatar cleared!")
            st.rerun()

    # Reprint Tab
    with tab5:
        st.header("Barcode Reprint")

        search_col1, search_col2 = st.columns([1, 3])
        with search_col1:
            search_by = st.selectbox("Search by:", ["PHN", "NIC", "Name"], key="search_by_select")
        with search_col2:
            search_term = st.text_input("Enter search term:", key="search_term_input")

        if st.button("Search", key="search_btn"):
            conn = create_db_connection()
            if conn:
                try:
                    cursor = conn.cursor(dictionary=True)
                    if search_by == "PHN":
                        query = "SELECT * FROM patients WHERE phn = %s"
                    elif search_by == "NIC":
                        query = "SELECT * FROM patients WHERE nic = %s"
                    else:
                        query = "SELECT * FROM patients WHERE full_name LIKE %s"
                        search_term = f"%{search_term}%"

                    cursor.execute(query, (search_term,))
                    patient = cursor.fetchone()

                    if patient:
                        st.session_state.reprint_patient = patient
                        st.success("Patient found!")
                        st.write(f"Name: {patient['full_name']}")
                        st.write(f"PHN: {patient['phn']}")

                        if patient['avatar']:
                            avatar_img = Image.open(BytesIO(patient['avatar']))
                            st.image(avatar_img, caption="Patient Avatar", width=120)
                    else:
                        st.error("No patient found.")
                except mysql.connector.Error as err:
                    st.error(f"Database error: {err}")
                finally:
                    conn.close()

        if 'reprint_patient' in st.session_state:
            if st.button("Reprint Barcode", key="reprint_btn"):
                # Generate the complete label image with patient info and barcode
                label_img = generate_label_image(st.session_state.reprint_patient)
                st.image(label_img, caption="Patient Label", use_container_width=True)  # Fixed deprecated parameter

                # Provide printing options
                print_barcode_web(
                    label_img,
                    st.session_state.reprint_patient['phn'],
                    st.session_state.reprint_patient
                )

    # Sidebar actions
    with st.sidebar:
        st.header("Actions")

        if st.button("Check Duplicates", key="check_duplicates_btn"):
            # Implement duplicate checking
            st.info("Duplicate checking would be implemented here")

        if st.button("Clear Form", key="clear_form_btn"):
            clear_form()

        if st.button("Save Patient", type="primary", key="save_patient_btn"):
            # Validate required fields
            required_fields = [
                ('full_name', 'Full Name'),
                ('gender', 'Gender'),
                ('phn', 'PHN'),
                ('address_line1', 'Address Line 1'),
                ('district', 'District'),
                ('province', 'Province'),
                ('contact_numbers', 'Contact Numbers')
            ]

            missing_fields = []
            for field, name in required_fields:
                if not st.session_state.patient_data[field]:
                    missing_fields.append(name)

            if missing_fields:
                st.error(f"Please fill in the following required fields: {', '.join(missing_fields)}")
            else:
                # Save to database
                conn = create_db_connection()
                if conn:
                    try:
                        cursor = conn.cursor()

                        # Handle avatar image
                        avatar_blob = None
                        if 'avatar_img' in st.session_state:
                            img_byte_arr = BytesIO()
                            st.session_state.avatar_img.save(img_byte_arr, format='JPEG')
                            avatar_blob = img_byte_arr.getvalue()

                        # Insert patient
                        query = """
                        INSERT INTO patients (
                            title, full_name, other_names, gender, address_line1, address_line2, 
                            district, province, mh_division, birthday, age, nic, phn, marital_status, 
                            guardian, contact_numbers, occupation, blood_type, known_allergies, 
                            chronic_conditions, primary_physician, avatar
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """

                        values = (
                            st.session_state.patient_data['title'],
                            st.session_state.patient_data['full_name'],
                            st.session_state.patient_data['other_names'],
                            st.session_state.patient_data['gender'],
                            st.session_state.patient_data['address_line1'],
                            st.session_state.patient_data['address_line2'],
                            st.session_state.patient_data['district'],
                            st.session_state.patient_data['province'],
                            st.session_state.patient_data['mh_division'],
                            st.session_state.patient_data['birthday'],
                            st.session_state.patient_data['age'],
                            st.session_state.patient_data['nic'],
                            st.session_state.patient_data['phn'],
                            st.session_state.patient_data['marital_status'],
                            st.session_state.patient_data['guardian'],
                            st.session_state.patient_data['contact_numbers'],
                            st.session_state.patient_data['occupation'],
                            st.session_state.patient_data['blood_type'],
                            st.session_state.patient_data['known_allergies'],
                            st.session_state.patient_data['chronic_conditions'],
                            st.session_state.patient_data['primary_physician'],
                            avatar_blob
                        )

                        cursor.execute(query, values)
                        conn.commit()

                        # Generate barcode
                        barcode_img = generate_barcode(st.session_state.patient_data)
                        st.image(barcode_img, caption="Patient Barcode", width='stretch')

                        # Provide printing options
                        st.success("Patient information saved successfully!")
                        print_barcode_web(barcode_img, st.session_state.patient_data['phn'])

                        # Clear avatar after saving (as requested)
                        if 'avatar_img' in st.session_state:
                            del st.session_state.avatar_img

                    except mysql.connector.Error as err:
                        st.error(f"Error saving patient: {err}")
                    finally:
                        conn.close()


if __name__ == "__main__":
    main()