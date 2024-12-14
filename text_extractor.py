import boto3
import os
import uuid
from dotenv import load_dotenv
from logger import configured_logger
from botocore.exceptions import NoCredentialsError, ClientError
from s3_facade import s3

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


def extract_text_enhanced(response, extract_by="WORD"):
    """
    Extract text from Textract response based on block type.

    Args:
        response (dict): Textract response
        extract_by (str): Block type to extract ('WORD', 'LINE', etc.)

    Returns:
        list: Extracted text blocks
    """
    line_text = []
    for block in response["Blocks"]:
        if block["BlockType"] == extract_by:
            line_text.append(block["Text"])
    return line_text


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


def extract_tables(response, word_map):
    """
    Extract table information from Textract response.

    Args:
        response (dict): Textract response
        word_map (dict): Mapping of word IDs to their text

    Returns:
        dict: Extracted tables with unique keys
    """
    tables = {}
    current_table = []
    current_row = []
    current_row_index = 1

    for block in response["Blocks"]:
        if block["BlockType"] == "TABLE":
            # Start of a new table
            table_key = f"table_{uuid.uuid4().hex}"
            current_table = []
            current_row = []
            current_row_index = 1

        if block["BlockType"] == "CELL":
            # Check if we've moved to a new row
            if block["RowIndex"] != current_row_index:
                if current_row:
                    current_table.append(current_row)
                current_row = []
                current_row_index = block["RowIndex"]

            # Extract cell content
            cell_content = " "
            if "Relationships" in block:
                for relation in block["Relationships"]:
                    if relation["Type"] == "CHILD":
                        cell_content = " ".join(
                            [word_map.get(i, "") for i in relation["Ids"]]
                        )

            current_row.append(cell_content.strip())

            # If this is the last cell in the table, add the last row
            if block.get("ColumnIndex") == block.get("Columns"):
                if current_row:
                    current_table.append(current_row)
                    tables[table_key] = current_table
                    current_table = []
                    current_row = []

    return tables


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


def text_extractor_enhanced(s3_file_name: str) -> dict:
    """
    Enhanced text extraction using AWS Textract with comprehensive parsing.

    Args:
        s3_file_name (str): The S3 file name (path) of the document to analyze.

    Returns:
        dict: Comprehensive extraction results
    """
    try:
        # Analyze document with FORMS and TABLES feature types
        response = textract.analyze_document(
            Document={"S3Object": {"Bucket": bucket_name, "Name": s3_file_name}},
            FeatureTypes=["FORMS", "TABLES"],
        )

        # Mapping of word IDs to their text/status
        word_map = map_word_ids(response)

        # Extract different types of information
        extracted_data = {
            # "raw_text": {
            #     # "words": extract_text_enhanced(response, "WORD"),
            # },
            "lines": extract_text_enhanced(response, "LINE"),
            "tables": extract_tables(response, word_map),
            "form_fields": extract_form_fields_advanced(response, word_map),
            # "raw_response": response,
        }

        # Logging and printing extracted information
        configured_logger.info(f"Extracted data from {s3_file_name}")
        print("Extracted Form Fields:")
        for key, value in extracted_data["form_fields"].items():
            print(f"{key}: {value}")

        print("\nExtracted Tables:")
        for table_key, table_data in extracted_data["tables"].items():
            print(f"{table_key}:")
            for row in table_data:
                print(row)

        return extracted_data

    except (NoCredentialsError, ClientError) as e:
        configured_logger.error(f"Textract error: {e}")
        raise Exception("Could not extract text using Textract.") from e


# Example usage
# if __name__ == "__main__":
#     with open("case_registration_form.pdf", "rb") as f:
#         # TODO: Collect case_id, case_type and timestamp and use for
#         file_content = f.read()
#         s3.upload_file(file_content, "case_registration_form.pdf")
#         result = text_extractor_enhanced("case_registration_form.pdf")
