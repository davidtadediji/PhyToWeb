import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile, Form, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from llm_client import process_form_data, LLMProcessingError
from logger import configured_logger
from s3_facade import s3
from text_extractor import extract_text
from text_extractor2 import  text_extractor_enhanced

load_dotenv()

app_name = os.getenv("APP_NAME")
router = APIRouter(
    prefix="/api",
    tags=[app_name],
    responses={404: {"description": "Not found"}},
)


# Define a Pydantic model for the additional fields
class FormMetadata:
    def __init__(
            self,
            data_schema_key: str,
            case_type: str,
            case_sub_type: str,
            user_id: str,
            timestamp: str = None,
    ):
        self.data_schema_key = data_schema_key
        self.case_type = case_type
        self.case_sub_type = case_sub_type
        self.user_id = user_id
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()


class SchemaUploadRequest(BaseModel):
    key: str
    data_schema: dict


@router.post("/upload-schema", response_class=JSONResponse)
async def upload_schema(payload: SchemaUploadRequest = Body(...)):
    """
    Upload a schema by providing a key and a JSON payload.

    Args:
        data_schema_key (str): The unique identifier for the schema.
        schema (dict): The JSON object representing the schema.

    Returns:
        JSONResponse: A response indicating success or failure.
    """
    try:
        # Extract data
        data_schema_key = payload.key
        schema = payload.data_schema

        # Debug: Log the received inputs
        configured_logger.info(f"Received data_schema_key: {data_schema_key}")
        print(f"Received schema: {schema}")

        # Process the schema as needed (e.g., save it to S3, database, or a file)
        # Example: Save schema to a file (replace with actual implementation)
        file_name = "schema.json"
        with open("schema.json", "w") as file:
            json.dump(schema, file, indent=4)

        # Debug: Confirm saving the file
        print(f"Schema saved to {file_name}")

        s3.upload_schema(data_schema_key)

        # Return a success response
        return JSONResponse(
            content={
                "message": "Schema uploaded successfully",
                "data_schema_key": data_schema_key,
            },
            status_code=200,
        )

    except Exception as e:
        # Handle errors
        configured_logger.error(f"Error uploading schema --> {e}")
        return JSONResponse(
            content={"error": "Failed to upload schema", "details": str(e)},
            status_code=500,
        )


@router.post("/extract/", response_class=JSONResponse)
async def extract_form_data(
        file: UploadFile = File(...),
        data_schema_key: str = Form(...),
        case_type: str = Form(...),
        case_sub_type: str = Form(...),
        user_id: str = Form(...),
        timestamp: str = Form(None),
):
    """
    Extract form data from the uploaded file using AWS Textract.

    Args:
        file (UploadFile): The uploaded file containing form data.
        data_schema_key (str): Form Schema Key.
        case_type (str): Type of case.
        case_sub_type (str): Subtype of case.
        user_id (str): User ID.
        timestamp (str): Optional timestamp.

    Returns:
        JSONResponse: Extracted form data or error message.
    """
    try:
        # Create a FormMetadata object with the provided data
        metadata = FormMetadata(
            data_schema_key=data_schema_key,
            case_type=case_type,
            case_sub_type=case_sub_type,
            user_id=user_id,
            timestamp=timestamp,
        )

        # Construct a unique filename
        original_filename = file.filename
        file_extension = os.path.splitext(original_filename)[1]

        # Generate a unique UUID
        file_uuid = uuid.uuid4()
        constructed_filename = (
            f"{metadata.case_type}_{metadata.case_sub_type}_{metadata.user_id}_{file_uuid}"
            f"{file_extension}"
        )
        file_content = await file.read()

        uploaded_filename = s3.upload_pdf_form_with_caching(file_content=file_content, file_name=constructed_filename)

        form_text_data = extract_text([uploaded_filename])

        # Debug: Log the Textract response
        print("Textract Response:", form_text_data)

        result = process_form_data(
            data_schema_key=data_schema_key,
            use_pydantic=True,
            input_content=form_text_data,
        )

        # Compile the response data
        response_data = {
            "data_schema_key": metadata.data_schema_key,
            "case_type": metadata.case_type,
            "case_sub_type": metadata.case_sub_type,
            "user_id": metadata.user_id,
            "timestamp": metadata.timestamp,
            "form_text_data": form_text_data,
            "extracted_form_data": result,
        }

        # Return the response data
        return JSONResponse(content=response_data, status_code=200)

    except LLMProcessingError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": str(e),
                "original_error": str(e.original_error) if e.original_error else None
            }
        )

    except Exception as e:
        # Handle errors
        configured_logger.error(f"Error processing the file --> {e}")
        return JSONResponse(
            content={"error": "Failed to extract form data", "details": str(e)},
            status_code=500,
        )
