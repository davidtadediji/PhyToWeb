import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile, Form
from fastapi.responses import JSONResponse

from file_upload import upload_file
from main import process_form_data
from text_extractor import text_extractor_enhanced

load_dotenv()

app_name = os.getenv("APP_NAME")
router = APIRouter(
    prefix="/api",
    tags=[app_name],
    responses={404: {"description": "Not found"}},
)


# Define a Pydantic model for the additional fields
class FormMetadata:
    def __init__(self, form_id: str, case_type: str, case_sub_type: str, user_id: str, timestamp: str = None):
        self.form_id = form_id
        self.case_type = case_type
        self.case_sub_type = case_sub_type
        self.user_id = user_id
        self.timestamp = timestamp or datetime.utcnow().isoformat()


@router.post("/extract/", response_class=JSONResponse)
async def extract_form_data(
        file: UploadFile = File(...),
        form_id: str = Form(...),
        case_type: str = Form(...),
        case_sub_type: str = Form(...),
        user_id: str = Form(...),
        timestamp: str = Form(None),
):
    """
    Extract form data from the uploaded file using AWS Textract.

    Args:
        file (UploadFile): The uploaded file containing form data.
        form_id (str): Form ID.
        case_type (str): Type of case.
        case_sub_type (str): Subtype of case.
        user_id (str): User ID.
        timestamp (str): Optional timestamp.

    Returns:
        JSONResponse: Extracted form data or error message.
    """
    try:
        # Create a FormMetadata object with the provided data
        metadata = FormMetadata(form_id=form_id, case_type=case_type, case_sub_type=case_sub_type, user_id=user_id,
                                timestamp=timestamp)

        # Construct a unique filename
        original_filename = file.filename
        file_extension = os.path.splitext(original_filename)[1]
        constructed_filename = (
            f"{os.path.splitext(original_filename)[0]}_{metadata.timestamp}_{metadata.user_id}_"
            f"{metadata.case_type}_{metadata.case_sub_type}{file_extension}"
        )
        file_content = await file.read()

        upload_file(file_content, constructed_filename)

        form_text_data = text_extractor_enhanced("case_registration_form.pdf")

        # Debug: Log the Textract response
        print("Textract Response:", form_text_data)

        result  = process_form_data(input_content=str(form_text_data))

        # Compile the response data
        response_data = {
            "form_id": metadata.form_id,
            "case_type": metadata.case_type,
            "case_sub_type": metadata.case_sub_type,
            "user_id": metadata.user_id,
            "timestamp": metadata.timestamp,
            "form_text_data": form_text_data,
            "extracted_form_data": result,
        }

        # Return the response data
        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        # Handle errors
        print("Error processing the file:", e)
        return JSONResponse(
            content={"error": "Failed to extract form data", "details": str(e)},
            status_code=500,
        )
