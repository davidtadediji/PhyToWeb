from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import boto3

load_dotenv()

app_name = os.getenv("APP_NAME")
router = APIRouter(
    prefix="/api",
    tags=[app_name],
    responses={404: {"description": "Not found"}},
)

# Initialize boto3 Textract client
textract = boto3.client('textract')


@router.post("/extract/", response_class=JSONResponse)
async def extract_form_data(file: UploadFile = File(...)):
    """
    Extract form data from the uploaded file using AWS Textract.

    Args:
        file (UploadFile): The uploaded file containing form data.

    Returns:
        JSONResponse: Extracted form data or error message.
    """
    try:
        # Save the uploaded file temporarily
        file_location = f"./temp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Call AWS Textract to analyze the document
        with open(file_location, 'rb') as document:
            response = textract.analyze_document(
                Document={'Bytes': document.read()},
                FeatureTypes=['TABLES', 'FORMS']
            )

        # Debug: Log the Textract response
        print("Textract Response:", response)

        # Return the extracted form data (or part of it)
        return JSONResponse(content={"extracted_data": response}, status_code=200)

    except Exception as e:
        # Handle errors
        print("Error processing the file:", e)
        return JSONResponse(
            content={"error": "Failed to extract form data", "details": str(e)},
            status_code=500,
        )
