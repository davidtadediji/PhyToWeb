import os

import boto3
from dotenv import load_dotenv

from logger import configured_logger

# Load environment variables from .env
load_dotenv()

# Fetch credentials and region from environment
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")
bucket_name = os.getenv("S3_FORM_BUCKET")

# Initialize Textract client
textract = boto3.client(
    "textract",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region,
)

import time
from botocore.exceptions import NoCredentialsError, ClientError


def start_async_textract_detection(s3_file_name: str) -> str:
    """
    Start an asynchronous Textract text detection job.

    Args:
        s3_file_name (str): The S3 file name (path) of the document to detect text from.

    Returns:
        str: Job ID to track the status of the detection.
    """
    try:
        response = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket_name, "Name": s3_file_name}}
        )
        return response["JobId"]
    except (NoCredentialsError, ClientError) as e:
        raise Exception(f"Could not start Textract text detection -> {e}")


def get_async_textract_results(job_id: str) -> dict:
    """
    Retrieve the results of the asynchronous Textract text detection.

    Args:
        job_id (str): The Job ID of the Textract detection.

    Returns:
        dict: Textract text detection result.
    """
    try:
        while True:
            result = textract.get_document_text_detection(JobId=job_id)
            status = result["JobStatus"]

            if status == "SUCCEEDED":
                configured_logger.info(f"Textract job {job_id} succeeded.")
                return result
            elif status == "FAILED":
                configured_logger.info(f"Textract job {job_id} failed.")
                raise Exception("Textract text detection failed.")

            configured_logger.info("Waiting for job to complete...")
            time.sleep(5)  # Sleep for 5 seconds before checking again

    except (NoCredentialsError, ClientError) as e:
        raise Exception(f"Error fetching Textract results -> {e}")


def extract_text_by_type(response, block_type="LINE"):
    """
    Extract text from Textract response based on block type.

    Args:
        response (dict): Textract response
        block_type (str): Block type to extract ('WORD' or 'LINE')

    Returns:
        list: Extracted text blocks
    """
    try:
        text_blocks = []
        for block in response["Blocks"]:
            if block["BlockType"] == block_type:
                text_blocks.append(block["Text"])
        return text_blocks
    except Exception as e:
        raise Exception(f"Error occurred while extracting text by type {block_type} -> {str(e)}") from e


def async_text_detection(s3_file_name: str) -> str:
    """
    Simple text extraction using AWS Textract text detection.

    Args:
        s3_file_name (str): The S3 file name (path) of the document to analyze.

    Returns:
        dict: Extracted text results by type
    """
    try:
        # Start the asynchronous Textract text detection
        job_id = start_async_textract_detection(s3_file_name)

        # Get the results once the job is complete
        response = get_async_textract_results(job_id)
        text_output = []

        # Log the extracted data
        configured_logger.info(f"Extracted data from {s3_file_name}")

        return process_response(response)
        word_map = map_word_ids(response)
        lines = extract_text_by_type(response, "LINE"),
        form_fields = extract_form_fields_advanced(response, word_map),

        # Format form fields
        text_output.append("Extracted Form Fields:")
        for key, value in form_fields.items():
            text_output.append(f"- {key}: {value}")

        text_output.append("\nExtracted Text Lines:")
        text_output.extend(lines)

        # Combine all text
        formatted_text = "\n".join(text_output)

        # Log the extracted data
        configured_logger.info(f"Extracted data from {s3_file_name}")
        print(formatted_text)

        return formatted_text


    except Exception as e:
        raise Exception(f"Could not extract text using Textract -> {e}")


def process_response(response):
    try:
        text_output = []

        word_map = map_word_ids(response)
        lines = extract_text_by_type(response, "LINE")
        form_fields = extract_form_fields_advanced(response, word_map)

        # Format form fields
        text_output.append("Extracted Form Fields:")
        for key, value in form_fields.items():
            text_output.append(f"- {key}: {value}")

        text_output.append("\nExtracted Text Lines:")
        text_output.extend(lines)

        # Combine all text
        formatted_text = "\n".join(text_output)

        print(formatted_text)

        return formatted_text
    except Exception as e:
        raise Exception(f"Error occurred while processing ocr response into form data --> {str(e)}")


def sync_text_detection(s3_file_name: str):
    try:
        # Call DetectDocumentText to extract text from the document
        response = textract.detect_document_text(
            Document={"S3Object": {"Bucket": bucket_name, "Name": s3_file_name}}
        )

        return process_response(response)
        extract_text_by_type(response, "LINE")


    except ClientError as e:
        # Handle AWS client errors such as permission or service issues
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            return "Access Denied: You do not have permission to access the S3 object."
        elif error_code == "InvalidS3ObjectException":
            return "Invalid S3 Object: Unable to access the specified S3 object."
        elif error_code == "UnsupportedDocumentException":
            return "Unsupported Document Format: The document format is not supported by Textract."
        elif error_code == "DocumentTooLargeException":
            return "Document Too Large: The document exceeds the size limit for processing."
        elif error_code == "BadDocumentException":
            return "Bad Document: Textract cannot read the document."
        elif error_code == "InvalidParameterException":
            return "Invalid Parameter: One or more input parameters are invalid."
        elif error_code == "InternalServerError":
            return (
                "Internal Server Error: There was a problem with the Textract service."
            )
        elif error_code == "ThrottlingException":
            return "Throttling Exception: Too many requests to the Textract service."
        else:
            return f"An error occurred: {error_code} - {e.response['Error']['Message']}"

    except Exception as e:
        # Catch any other exceptions that may occur
        return f"An unexpected error occurred -> {str(e)}"


def extract_form_fields_advanced(response, word_map):
    """
    Advanced form field extraction from Textract response.

    Args:
        response (dict): Textract response
        word_map (dict): Mapping of word IDs to their text

    Returns:
        dict: Extracted form fields
    """
    key_map = {}
    value_map = {}
    final_map = {}

    print(word_map)

    # First pass: create key and value maps
    for block in response["Blocks"]:
        if block["BlockType"] == "KEY_VALUE_SET":
            if "KEY" in block.get("EntityTypes", []):
                # Process key
                key_text = ""
                if "Relationships" in block:
                    for relation in block["Relationships"]:
                        if relation["Type"] == "CHILD":
                            key_text = " ".join(
                                [word_map.get(i, "") for i in relation["Ids"]]
                            )

                # Find associated value IDs
                value_ids = []
                for relation in block.get("Relationships", []):
                    if relation["Type"] == "VALUE":
                        value_ids = relation["Ids"]

                if key_text:
                    key_map[key_text] = value_ids

            elif "VALUE" in block.get("EntityTypes", []):
                # Process value
                if "Relationships" in block:
                    for relation in block["Relationships"]:
                        if relation["Type"] == "CHILD":
                            value_text = " ".join(
                                [word_map.get(i, "") for i in relation["Ids"]]
                            )
                            value_map[block["Id"]] = value_text

    # Second pass: combine keys and values
    for key, value_ids in key_map.items():
        value_text = " ".join([value_map.get(vid, "N/A") for vid in value_ids])
        final_map[key] = value_text.strip()

    return final_map


def map_word_ids(response):
    """
    Create a mapping of word and selection IDs to their text or status.

    Args:
        response (dict): Textract response

    Returns:
        dict: Mapping of block IDs to their text or selection status
    """
    word_map = {}
    for block in response["Blocks"]:
        if block["BlockType"] == "WORD":
            word_map[block["Id"]] = block["Text"]
        if block["BlockType"] == "SELECTION_ELEMENT":
            word_map[block["Id"]] = block["SelectionStatus"]

    print("Word Map: ", word_map)
    return word_map


def extract_form_fields_advanced(response, word_map):
    """
    Advanced form field extraction from Textract response.

    Args:
        response (dict): Textract response
        word_map (dict): Mapping of word IDs to their text

    Returns:
        dict: Extracted form fields
    """
    key_map = {}
    value_map = {}
    final_map = {}

    # First pass: create key and value maps
    for block in response["Blocks"]:
        if block["BlockType"] == "KEY_VALUE_SET":
            if "KEY" in block.get("EntityTypes", []):
                # Process key
                key_text = ""
                if "Relationships" in block:
                    for relation in block["Relationships"]:
                        if relation["Type"] == "CHILD":
                            key_text = " ".join(
                                [word_map.get(i, "") for i in relation["Ids"]]
                            )

                # Find associated value IDs
                value_ids = []
                for relation in block.get("Relationships", []):
                    if relation["Type"] == "VALUE":
                        value_ids = relation["Ids"]

                if key_text:
                    key_map[key_text] = value_ids

            elif "VALUE" in block.get("EntityTypes", []):
                # Process value
                if "Relationships" in block:
                    for relation in block["Relationships"]:
                        if relation["Type"] == "CHILD":
                            value_text = " ".join(
                                [word_map.get(i, "") for i in relation["Ids"]]
                            )
                            value_map[block["Id"]] = value_text

    # Second pass: combine keys and values
    for key, value_ids in key_map.items():
        value_text = " ".join([value_map.get(vid, "N/A") for vid in value_ids])
        final_map[key] = value_text.strip()

    return final_map


def map_word_ids(response):
    """
    Create a mapping of word and selection IDs to their text or status.

    Args:
        response (dict): Textract response

    Returns:
        dict: Mapping of block IDs to their text or selection status
    """
    word_map = {}
    for block in response["Blocks"]:
        if block["BlockType"] == "WORD":
            word_map[block["Id"]] = block["Text"]
        if block["BlockType"] == "SELECTION_ELEMENT":
            word_map[block["Id"]] = block["SelectionStatus"]
    return word_map


def extract_text(file_names):
    """
    Processes a list of file names from S3. Uses StartDocumentTextDetection for images
    and StartDocumentAnalysis for PDFs.

    Args:
        file_names (list): List of S3 file names.

    Returns:
        None
    """
    response = ""
    for file_name in file_names:
        try:
            if file_name.lower().endswith(".pdf"):
                # Handle PDF files with synchronous Textract API
                configured_logger.info(f"Processing PDF: {file_name}")
                result = async_text_detection(file_name)
                configured_logger.info(
                    f"Text detection completed for {file_name}. Response: {result}"
                )
            else:
                # Handle images with asynchronous Textract API
                configured_logger.info(f"Processing image: {file_name}")
                result = sync_text_detection(file_name)
                configured_logger.info(
                    f"Text detection completed for {file_name}. Response: {result}"
                )

        except Exception as e:
            # Log the error and print the exception message
            configured_logger.error(f"Error processing file {file_name} -> {str(e)}")
    return response
